import os
import json
import sys
import time
import unicodedata
import requests
from datetime import datetime, timezone


API_KEY = os.environ.get("OPENWEATHER_API_KEY")
if not API_KEY:
    raise RuntimeError(
        "OPENWEATHER_API_KEY manquant. "
        "Définis-la en variable d'environnement (voir .env.example)."
    )

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "raw")
API_URL = "https://api.openweathermap.org/data/2.5/air_pollution"

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

# 24 régions de Madagascar, coordonnées du chef-lieu (à vérifier)
# "ville" = nom de la région : c'est la clé que lit clean.py
VILLES = [
    {"ville": "Diana",             "lat": -12.2787, "lon": 49.2917},
    {"ville": "Sava",              "lat": -14.2667, "lon": 50.1667},
    {"ville": "Itasy",             "lat": -18.9500, "lon": 46.8667},
    {"ville": "Analamanga",        "lat": -18.8792, "lon": 47.5079},
    {"ville": "Vakinankaratra",    "lat": -19.8659, "lon": 47.0333},
    {"ville": "Bongolava",         "lat": -18.7667, "lon": 46.0333},
    {"ville": "Sofia",             "lat": -14.8833, "lon": 47.9833},
    {"ville": "Boeny",             "lat": -15.7167, "lon": 46.3167},
    {"ville": "Betsiboka",         "lat": -16.9500, "lon": 46.8167},
    {"ville": "Melaky",            "lat": -18.0667, "lon": 44.0333},
    {"ville": "Alaotra-Mangoro",   "lat": -17.8333, "lon": 48.4167},
    {"ville": "Atsinanana",        "lat": -18.1496, "lon": 49.4023},
    {"ville": "Ambatosoa",         "lat": -15.4333, "lon": 49.7333},
    {"ville": "Analanjirofo",      "lat": -17.3667, "lon": 49.4000},
    {"ville": "Amoron'i Mania",    "lat": -20.5333, "lon": 47.2500},
    {"ville": "Matsiatra Ambony",  "lat": -21.4500, "lon": 47.0833},
    {"ville": "Vatovavy",          "lat": -21.2833, "lon": 48.3333},
    {"ville": "Atsimo-Atsinanana", "lat": -22.8167, "lon": 47.8333},
    {"ville": "Ihorombe",          "lat": -22.4000, "lon": 46.1167},
    {"ville": "Menabe",            "lat": -20.2833, "lon": 44.2833},
    {"ville": "Atsimo-Andrefana",  "lat": -23.3500, "lon": 43.6833},
    {"ville": "Androy",            "lat": -25.1833, "lon": 46.0833},
    {"ville": "Anosy",             "lat": -25.0319, "lon": 46.9856},
    {"ville": "Fitovinany",        "lat": -22.1333, "lon": 48.0167},
]


def slugify(text):
    """Analamanga -> analamanga, Amoron'i Mania -> amoron_i_mania"""
    sans_accents = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return "".join(c if c.isalnum() else "_" for c in sans_accents.lower()).strip("_")


def fetch_with_retry(url, params, max_retries=MAX_RETRIES):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code >= 500:
                raise requests.exceptions.HTTPError(f"Erreur serveur {resp.status_code}")
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt < max_retries:
                print(f"  tentative {attempt}/{max_retries} échouée ({e}), retry dans {RETRY_DELAY_SECONDS}s...")
                time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(f"Échec après {max_retries} tentatives: {last_error}")


def collect_city(zone):
    params = {"lat": zone["lat"], "lon": zone["lon"], "appid": API_KEY}
    data = fetch_with_retry(API_URL, params)
    data["_meta"] = {
        "ville": zone["ville"],
        "pays": "MG",
        "lat": zone["lat"],
        "lon": zone["lon"],
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    return data


def save_raw(ville_nom, data):
    os.makedirs(RAW_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(RAW_DIR, f"{slugify(ville_nom)}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def main():
    print(f"Collecte lancée pour {len(VILLES)} régions de Madagascar — {datetime.now(timezone.utc).isoformat()}")
    success, failed = 0, 0

    for zone in VILLES:
        try:
            data = collect_city(zone)
            path = save_raw(zone["ville"], data)
            print(f"OK   {zone['ville']:18s} -> {path}")
            success += 1
        except Exception as e:
            print(f"FAIL {zone['ville']:18s} -> {e}")
            failed += 1

    print(f"\nRésumé: {success} succès, {failed} échecs")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
