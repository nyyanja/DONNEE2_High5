"""
validate_clean.py — Vérifie que clean/air_quality_clean.csv respecte le
contrat de données du projet.

Contrôles bloquants (exit code 1 si un seul échoue) :
  1. Le fichier existe et n'est pas vide
  2. Les colonnes sont exactement celles attendues, dans l'ordre
  3. Aucun doublon (même ville + même timestamp_utc)
  4. Tri chronologique respecté (ville, puis timestamp_utc croissant)
  5. Au moins 5 villes distinctes
  6. Types et plages de valeurs cohérents :
       - latitude in [-90, 90], longitude in [-180, 180]
       - heure in [0, 23]
       - is_weekend in {True, False}
       - aqi in [1, 5] ou vide
       - polluants >= 0 ou vide
       - timestamp_utc parseable en ISO 8601 UTC (YYYY-MM-DDTHH:MM:SSZ)

Avertissements (n'empêchent pas la validation, juste affichés) :
  - Valeurs manquantes par colonne
  - Trous horaires par ville (heures attendues vs heures présentes)

Usage:
    python src/validate_clean.py
    python src/validate_clean.py --csv clean/air_quality_clean.csv
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone

EXPECTED_COLUMNS = [
    "ville", "pays", "latitude", "longitude",
    "timestamp_utc", "date", "heure", "jour_semaine", "is_weekend",
    "aqi", "co", "no", "no2", "o3", "so2", "pm2_5", "pm10", "nh3",
]

POLLUTANTS = ["co", "no", "no2", "o3", "so2", "pm2_5", "pm10", "nh3"]

MIN_VILLES = 5

DEFAULT_CSV = os.path.join(os.path.dirname(__file__), "..", "clean", "air_quality_clean.csv")


class ValidationReport:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def ville_slug(nom: str) -> str:
    return nom.strip().lower().replace(" ", "_")


def parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def load_rows(csv_path: str, report: ValidationReport) -> list[dict]:
    if not os.path.exists(csv_path):
        report.error(f"Fichier introuvable : {csv_path}")
        return []

    if os.path.getsize(csv_path) == 0:
        report.error(f"Fichier vide : {csv_path}")
        return []

    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        actual_columns = reader.fieldnames or []

        if actual_columns != EXPECTED_COLUMNS:
            report.error(
                "Colonnes incorrectes.\n"
                f"    Attendu  : {EXPECTED_COLUMNS}\n"
                f"    Obtenu   : {actual_columns}"
            )
            return []

        rows = list(reader)

    if not rows:
        report.error("Le CSV a un en-tête mais aucune ligne de données.")

    return rows


def check_duplicates(rows: list[dict], report: ValidationReport) -> None:
    seen = {}
    dup_count = 0
    for i, row in enumerate(rows):
        key = (ville_slug(row["ville"]), row["timestamp_utc"])
        if key in seen:
            dup_count += 1
        else:
            seen[key] = i

    if dup_count > 0:
        report.error(f"{dup_count} doublons détectés (même ville + même timestamp_utc)")


def check_sort_order(rows: list[dict], report: ValidationReport) -> None:
    keys = [(ville_slug(r["ville"]), r["timestamp_utc"]) for r in rows]
    if keys != sorted(keys):
        report.error(
            "Le fichier n'est pas trié par (ville, timestamp_utc) croissant. "
            "Attendu depuis clean.py : sort_rows() avant l'export CSV."
        )


def check_villes(rows: list[dict], report: ValidationReport) -> set[str]:
    villes = {row["ville"] for row in rows}
    if len(villes) < MIN_VILLES:
        report.error(f"Seulement {len(villes)} ville(s) trouvée(s), minimum requis : {MIN_VILLES}")
    return villes


def check_field(value: str, allow_empty: bool, checker, label: str, row_idx: int, report: ValidationReport) -> None:
    if value == "":
        if not allow_empty:
            report.error(f"Ligne {row_idx}: '{label}' est vide alors qu'il est requis")
        return
    try:
        if not checker(value):
            report.error(f"Ligne {row_idx}: '{label}' hors plage attendue (valeur: {value})")
    except (ValueError, TypeError):
        report.error(f"Ligne {row_idx}: '{label}' n'est pas un nombre valide (valeur: {value})")


def check_types_and_ranges(rows: list[dict], report: ValidationReport) -> dict:
    missing_counts = {col: 0 for col in EXPECTED_COLUMNS}

    for i, row in enumerate(rows, start=2):  # +2 : ligne 1 = header, index humain
        for col in EXPECTED_COLUMNS:
            if row.get(col, "") == "":
                missing_counts[col] += 1

        if parse_timestamp(row["timestamp_utc"]) is None:
            report.error(f"Ligne {i}: timestamp_utc invalide ({row['timestamp_utc']!r}), attendu YYYY-MM-DDTHH:MM:SSZ")

        check_field(row["latitude"], False, lambda v: -90 <= float(v) <= 90, "latitude", i, report)
        check_field(row["longitude"], False, lambda v: -180 <= float(v) <= 180, "longitude", i, report)
        check_field(row["heure"], False, lambda v: 0 <= int(v) <= 23, "heure", i, report)

        if row["is_weekend"] not in ("True", "False"):
            report.error(f"Ligne {i}: is_weekend doit être 'True' ou 'False' (valeur: {row['is_weekend']!r})")

        check_field(row["aqi"], True, lambda v: 1 <= int(v) <= 5, "aqi", i, report)

        for pol in POLLUTANTS:
            check_field(row[pol], True, lambda v: float(v) >= 0, pol, i, report)

    return missing_counts


def check_hourly_coverage(rows: list[dict], report: ValidationReport) -> None:
    """Avertissement (non bloquant) : signale les trous horaires par ville."""
    by_ville: dict[str, list[datetime]] = {}
    for row in rows:
        ts = parse_timestamp(row["timestamp_utc"])
        if ts is None:
            continue
        by_ville.setdefault(row["ville"], []).append(ts)

    for ville, timestamps in sorted(by_ville.items()):
        timestamps.sort()
        span_hours = int((timestamps[-1] - timestamps[0]).total_seconds() // 3600) + 1
        present = len(timestamps)
        missing = span_hours - present
        pct = 100 * present / span_hours if span_hours else 100
        if missing > 0:
            report.warn(
                f"{ville}: {present}/{span_hours} heures présentes ({pct:.1f}%), "
                f"{missing} heures manquantes entre {timestamps[0].isoformat()} et {timestamps[-1].isoformat()}"
            )


def print_report(rows: list[dict], villes: set[str], missing_counts: dict, report: ValidationReport) -> None:
    print("=" * 60)
    print("VALIDATION clean/air_quality_clean.csv")
    print("=" * 60)

    if rows:
        print(f"Lignes            : {len(rows)}")
        print(f"Villes ({len(villes)})       : {', '.join(sorted(villes))}")
        timestamps = [r['timestamp_utc'] for r in rows]
        print(f"Période couverte  : {min(timestamps)} -> {max(timestamps)}")

        cols_with_missing = {k: v for k, v in missing_counts.items() if v > 0}
        if cols_with_missing:
            print("\nValeurs manquantes par colonne :")
            for col, n in cols_with_missing.items():
                print(f"  {col:15s} {n} ({100 * n / len(rows):.1f}%)")

    if report.warnings:
        print(f"\n{len(report.warnings)} avertissement(s) :")
        for w in report.warnings:
            print(f"  [WARN] {w}")

    print()
    if report.ok:
        print(f"VALIDATION OK — {len(report.errors)} erreur(s) bloquante(s)")
    else:
        print(f"VALIDATION ÉCHOUÉE — {len(report.errors)} erreur(s) bloquante(s) :")
        for e in report.errors:
            print(f"  [ERROR] {e}")
    print("=" * 60)


def parse_args():
    parser = argparse.ArgumentParser(description="Valide clean/air_quality_clean.csv")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Chemin du CSV à valider")
    return parser.parse_args()


def main():
    args = parse_args()
    report = ValidationReport()

    rows = load_rows(args.csv, report)
    if rows:
        check_duplicates(rows, report)
        check_sort_order(rows, report)
        villes = check_villes(rows, report)
        missing_counts = check_types_and_ranges(rows, report)
        check_hourly_coverage(rows, report)
    else:
        villes, missing_counts = set(), {}

    print_report(rows, villes, missing_counts, report)

    sys.exit(0 if report.ok else 1)


if __name__ == "__main__":
    main()