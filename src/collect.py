"""
collect.py — Collecte horaire de la qualité de l'air (AQI) pour 5 villes
via l'API OpenWeather Air Pollution.

Chaque appel est sauvegardé tel quel (jamais modifié) dans raw/,
un fichier par ville et par appel. C'est la source de vérité du pipeline.

Usage:
    export OPENWEATHER_API_KEY=xxxx
    python src/collect.py
"""

import os
import json
import requests
import time
from datetime import datetime, timezone


API_KEY = os.environ.get("OPENWEATHER_API_KEY")
if not API_KEY:
    raise RuntimeError(
        "OPENWEATHER_API_KEY manquant. "
        "Définis-la en variable d'environnement (voir .env.example)."
    )

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "raw")
API_URL = "http://api.openweathermap.org/data/2.5/air_pollution"

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5  # secondes

VILLES = [
    {"nom": "Antananarivo", "pays": "MG", "lat": -18.8792, "lon": 47.5079},
    {"nom": "Paris",        "pays": "FR", "lat": 48.8566,  "lon": 2.3522},
    {"nom": "Nairobi",      "pays": "KE", "lat": -1.2921,  "lon": 36.8219},
    {"nom": "New York",     "pays": "US", "lat": 40.7128,  "lon": -74.0060},
    {"nom": "Tokyo",        "pays": "JP", "lat": 35.6762,  "lon": 139.6503},
]


def fetch_with_retry(url, params, max_retries=MAX_RETRIES):
    """Appelle l'API avec retry en cas d'erreur réseau ou de code HTTP 5xx."""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code >= 500:
                raise requests.exceptions.HTTPError(
                    f"Erreur serveur {resp.status_code}"
                )
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.RequestException,) as e:
            last_error = e
            if attempt < max_retries:
                print(f"  tentative {attempt}/{max_retries} échouée ({e}), retry dans {RETRY_DELAY_SECONDS}s...")
                time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(f"Échec après {max_retries} tentatives: {last_error}")

def collect_city(ville):
    params = {"lat": ville["lat"], "lon": ville["lon"], "appid": API_KEY}
    data = fetch_with_retry(API_URL, params)

    # On enrichit avec le contexte ville pour ne rien perdre en aval.
    # Le JSON brut d'origine n'est jamais altéré, on ajoute juste des métadonnées.
    data["_meta"] = {
        "ville": ville["nom"],
        "pays": ville["pays"],
        "lat": ville["lat"],
        "lon": ville["lon"],
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    return data

def save_raw(ville_nom, data):
    os.makedirs(RAW_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename_safe = ville_nom.lower().replace(" ", "_")
    path = os.path.join(RAW_DIR, f"{filename_safe}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def main():
    print(f"Collecte lancée pour {len(VILLES)} villes — {datetime.now(timezone.utc).isoformat()}")
    success, failed = 0, 0

    for ville in VILLES:
        try:
            data = collect_city(ville)
            path = save_raw(ville["nom"], data)
            print(f"OK   {ville['nom']:15s} -> {path}")
            success += 1
        except Exception as e:
            print(f"FAIL {ville['nom']:15s} -> {e}")
            failed += 1

    print(f"\nRésumé: {success} succès, {failed} échecs")
    if failed > 0:
        # Code de sortie non-zéro pour que GitHub Actions marque le run en échec
        # si au moins une ville n'a pas pu être collectée.
        exit(1)


if __name__ == "__main__":
    main()

