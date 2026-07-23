"""
backfill.py — Remplissage historique de raw/ via l'API OpenWeather Air Pollution History.

Pour chaque ville et chaque heure disponible, écrit un fichier JSON dans raw/
au même format que collect.py (une mesure par fichier, avec _meta).

Le script est rejouable : les fichiers déjà présents sont ignorés.

Usage:
    export OPENWEATHER_API_KEY=xxxx
    python src/backfill.py                  # 3 mois, toutes les villes
    python src/backfill.py --months 12      # 12 mois
    python src/backfill.py --city Paris     # une seule ville (test)
    python src/backfill.py --days 1 --city Paris
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

# Réutilise la config et le retry de collect.py pour rester cohérent.
from collect import RAW_DIR, VILLES, fetch_with_retry

API_KEY = os.environ.get("OPENWEATHER_API_KEY")
if not API_KEY:
    raise RuntimeError(
        "OPENWEATHER_API_KEY manquant. "
        "Définis-la en variable d'environnement ou dans .env."
    )

HISTORY_URL = "https://api.openweathermap.org/data/2.5/air_pollution/history"
CHUNK_DAYS = 5
REQUEST_DELAY_SECONDS = 1.2  # respecte les limites du plan gratuit


def ville_slug(nom: str) -> str:
    return nom.lower().replace(" ", "_")


def dt_to_filename(dt_unix: int) -> str:
    """Timestamp de mesure API → suffixe de fichier déterministe."""
    return datetime.fromtimestamp(dt_unix, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def raw_path(ville_nom: str, dt_unix: int) -> str:
    return os.path.join(RAW_DIR, f"{ville_slug(ville_nom)}_{dt_to_filename(dt_unix)}.json")


def normalize_coord(coord) -> dict:
    """L'API history renvoie [lon, lat], le current renvoie {lon, lat}."""
    if isinstance(coord, dict):
        return {"lon": coord["lon"], "lat": coord["lat"]}
    return {"lon": coord[0], "lat": coord[1]}


def build_record(coord: dict, hour_data: dict, ville: dict, backfilled_at: str) -> dict:
    """Un fichier = une heure, même structure que collect.py."""
    return {
        "coord": coord,
        "list": [hour_data],
        "_meta": {
            "ville": ville["nom"],
            "pays": ville["pays"],
            "lat": ville["lat"],
            "lon": ville["lon"],
            "collected_at": backfilled_at,
            "source": "backfill",
            "measurement_dt": hour_data["dt"],
        },
    }


def save_record(path: str, data: dict) -> None:
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_history_chunk(ville: dict, start_ts: int, end_ts: int) -> dict:
    params = {
        "lat": ville["lat"],
        "lon": ville["lon"],
        "start": start_ts,
        "end": end_ts,
        "appid": API_KEY,
    }
    return fetch_with_retry(HISTORY_URL, params)


def iter_chunks(start: datetime, end: datetime, chunk_days: int):
    """Découpe [start, end] en fenêtres de chunk_days jours."""
    cursor = start
    delta = timedelta(days=chunk_days)
    while cursor < end:
        chunk_end = min(cursor + delta, end)
        yield cursor, chunk_end
        cursor = chunk_end


def backfill_city(ville: dict, start: datetime, end: datetime) -> tuple[int, int, int]:
    """
    Retourne (saved, skipped, failed) pour une ville.
    """
    saved, skipped, failed = 0, 0, 0
    backfilled_at = datetime.now(timezone.utc).isoformat()

    for chunk_start, chunk_end in iter_chunks(start, end, CHUNK_DAYS):
        start_ts = int(chunk_start.timestamp())
        end_ts = int(chunk_end.timestamp())
        label = (
            f"{ville['nom']} "
            f"{chunk_start.strftime('%Y-%m-%d')} → {chunk_end.strftime('%Y-%m-%d')}"
        )

        try:
            payload = fetch_history_chunk(ville, start_ts, end_ts)
        except Exception as e:
            print(f"FAIL chunk {label} -> {e}")
            failed += 1
            continue

        coord = normalize_coord(payload.get("coord", {"lon": ville["lon"], "lat": ville["lat"]}))
        hours = payload.get("list", [])
        chunk_saved, chunk_skipped = 0, 0

        for hour_data in hours:
            dt_unix = hour_data["dt"]
            path = raw_path(ville["nom"], dt_unix)

            if os.path.exists(path):
                skipped += 1
                chunk_skipped += 1
                continue

            record = build_record(coord, hour_data, ville, backfilled_at)
            save_record(path, record)
            saved += 1
            chunk_saved += 1

        print(f"OK   {label} -> {chunk_saved} nouveaux, {chunk_skipped} déjà présents")
        time.sleep(REQUEST_DELAY_SECONDS)

    return saved, skipped, failed


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill historique AQI dans raw/")
    parser.add_argument(
        "--months",
        type=int,
        default=3,
        help="Nombre de mois à remonter (défaut: 3, minimum projet)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Alternative à --months pour les tests (ex: --days 1)",
    )
    parser.add_argument(
        "--city",
        type=str,
        default=None,
        help="Limiter à une ville (ex: Paris)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    if args.days is not None:
        start = end - timedelta(days=args.days)
    else:
        start = end - timedelta(days=args.months * 30)

    villes = VILLES
    if args.city:
        villes = [v for v in VILLES if v["nom"].lower() == args.city.lower()]
        if not villes:
            print(f"Ville inconnue: {args.city}")
            print("Villes disponibles:", ", ".join(v["nom"] for v in VILLES))
            sys.exit(1)

    print(f"Backfill {start.isoformat()} → {end.isoformat()}")
    print(f"Villes: {', '.join(v['nom'] for v in villes)}")

    total_saved, total_skipped, total_failed = 0, 0, 0

    for ville in villes:
        print(f"\n--- {ville['nom']} ---")
        saved, skipped, failed = backfill_city(ville, start, end)
        total_saved += saved
        total_skipped += skipped
        total_failed += failed

    print(
        f"\nRésumé: {total_saved} fichiers créés, "
        f"{total_skipped} ignorés (déjà présents), {total_failed} chunks en échec"
    )

    if total_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
