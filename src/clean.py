"""
clean.py — Reconstruction de clean/ à partir de raw/ (jamais l'inverse).

Lit TOUS les fichiers JSON de raw/ (un fichier = un appel API = une mesure,
produit par collect.py ou backfill.py), et reconstruit un unique CSV propre :
    - une ligne par (ville, heure)
    - triée chronologiquement (ville, puis timestamp)
    - sans doublons : si une même heure a été collectée plusieurs fois
      (chevauchement collect.py / backfill.py), on garde la mesure dont
      _meta.collected_at est la plus récente
    - valeurs manquantes : un polluant absent ou null dans components est
      exporté comme cellule vide (pas de 0 inventé, pas de suppression de ligne)

clean/ est entièrement reconstruit à chaque exécution : ce script ne lit
jamais clean/ et n'ajoute jamais à un fichier existant, il l'écrase.

Usage:
    python src/clean.py
    python src/clean.py --raw-dir raw --out clean/air_quality_clean.csv
"""

import argparse
import csv
import glob
import json
import os
from datetime import datetime, timezone

# Colonnes du contrat de données clean/ (README du stockage).
# Unités : aqi = indice OpenWeather (1..5) ; polluants en µg/m3 (co en µg/m3
# également, cf. doc OpenWeather Air Pollution API).
POLLUTANTS = ["co", "no", "no2", "o3", "so2", "pm2_5", "pm10", "nh3"]

FIELDNAMES = [
    "ville", "pays", "latitude", "longitude",
    "timestamp_utc", "date", "heure", "jour_semaine", "is_weekend",
    "aqi",
] + POLLUTANTS


def ville_slug(nom: str) -> str:
    return nom.strip().lower().replace(" ", "_")


def parse_record(filepath: str) -> dict | None:
    """
    Extrait une ligne exploitable d'un fichier raw/, ou None si le fichier
    est inexploitable (JSON invalide, pas de mesure, métadonnées absentes).
    Ne modifie jamais le fichier source.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  IGNORE (JSON invalide) {filepath} -> {e}")
        return None

    meta = data.get("_meta")
    if not meta:
        print(f"  IGNORE (pas de _meta) {filepath}")
        return None

    entries = data.get("list") or []
    if not entries:
        # Réponse API vide (ex: erreur ou plage horaire sans donnée) : on
        # garde une trace mais on ne fabrique pas de ligne.
        print(f"  IGNORE (list vide) {filepath}")
        return None

    # collect.py écrit une seule mesure par fichier (list[0]) ; backfill.py
    # aussi (un fichier par heure). On ne traite que la première entrée,
    # mais on boucle quand même pour rester compatible si un fichier
    # contenait plusieurs heures.
    rows = []
    for entry in entries:
        dt_unix = entry.get("dt")
        if dt_unix is None:
            print(f"  IGNORE (pas de dt) {filepath}")
            continue

        ts = datetime.fromtimestamp(dt_unix, tz=timezone.utc)
        components = entry.get("components") or {}
        main = entry.get("main") or {}

        row = {
            "ville": meta["ville"],
            "pays": meta.get("pays", ""),
            "latitude": meta.get("lat", ""),
            "longitude": meta.get("lon", ""),
            "timestamp_utc": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date": ts.strftime("%Y-%m-%d"),
            "heure": ts.hour,
            "jour_semaine": ts.strftime("%A"),
            "is_weekend": ts.weekday() >= 5,  # 5=samedi, 6=dimanche
            "aqi": main.get("aqi", ""),
        }
        for pol in POLLUTANTS:
            val = components.get(pol)
            row[pol] = "" if val is None else val

        # clé de dédup + départage en cas de doublon
        row["_dedup_key"] = (ville_slug(meta["ville"]), dt_unix)
        row["_collected_at"] = meta.get("collected_at", "")

        rows.append(row)

    return rows


def load_all_raw(raw_dir: str) -> list[dict]:
    files = sorted(glob.glob(os.path.join(raw_dir, "*.json")))
    print(f"{len(files)} fichiers trouvés dans {raw_dir}/")

    all_rows = []
    ignored = 0
    for filepath in files:
        rows = parse_record(filepath)
        if not rows:
            ignored += 1
            continue
        all_rows.extend(rows)

    print(f"{len(all_rows)} mesures extraites, {ignored} fichiers ignorés")
    return all_rows


def deduplicate(rows: list[dict]) -> list[dict]:
    """
    Une seule ligne par (ville, heure). En cas de doublon (collect.py et
    backfill.py ont pu couvrir la même heure), on garde la mesure la plus
    récemment collectée (_meta.collected_at le plus grand).
    """
    best_by_key: dict[tuple, dict] = {}
    duplicates = 0

    for row in rows:
        key = row["_dedup_key"]
        existing = best_by_key.get(key)
        if existing is None:
            best_by_key[key] = row
        else:
            duplicates += 1
            if row["_collected_at"] > existing["_collected_at"]:
                best_by_key[key] = row

    print(f"{duplicates} doublons (même ville + même heure) supprimés")
    return list(best_by_key.values())


def sort_rows(rows: list[dict]) -> list[dict]:
    """Tri chronologique : ville puis timestamp croissant."""
    return sorted(rows, key=lambda r: (ville_slug(r["ville"]), r["timestamp_utc"]))


def write_csv(rows: list[dict], out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def print_summary(rows: list[dict]) -> None:
    if not rows:
        print("Aucune ligne exportée.")
        return

    par_ville: dict[str, int] = {}
    manquants = {pol: 0 for pol in POLLUTANTS}
    manquants["aqi"] = 0

    for row in rows:
        par_ville[row["ville"]] = par_ville.get(row["ville"], 0) + 1
        if row["aqi"] == "":
            manquants["aqi"] += 1
        for pol in POLLUTANTS:
            if row[pol] == "":
                manquants[pol] += 1

    print("\nRésumé par ville :")
    for ville, n in sorted(par_ville.items()):
        print(f"  {ville:15s} {n} lignes")

    print("\nValeurs manquantes par colonne :")
    for col, n in manquants.items():
        if n > 0:
            print(f"  {col:8s} {n} manquantes")

    timestamps = [r["timestamp_utc"] for r in rows]
    print(f"\nPériode couverte : {min(timestamps)} -> {max(timestamps)}")
    print(f"Total : {len(rows)} lignes")


DEFAULT_RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "raw")
DEFAULT_OUT = os.path.join(os.path.dirname(__file__), "..", "clean", "air_quality_clean.csv")


def parse_args():
    parser = argparse.ArgumentParser(description="Reconstruit clean/ depuis raw/")
    parser.add_argument("--raw-dir", default=DEFAULT_RAW_DIR, help="Dossier des fichiers bruts")
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help="Chemin du CSV de sortie (écrasé à chaque run)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    raw_rows = load_all_raw(args.raw_dir)
    if not raw_rows:
        print("Aucune donnée à traiter, arrêt.")
        return

    deduped = deduplicate(raw_rows)
    sorted_rows = sort_rows(deduped)

    write_csv(sorted_rows, args.out)
    print(f"\nCSV écrit : {args.out}")

    print_summary(sorted_rows)


if __name__ == "__main__":
    main()