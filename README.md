# DONNEE2_High5 – Pipeline ETL de qualité de l'air

## Présentation

Ce projet implémente un pipeline ETL entièrement automatisé qui collecte, nettoie, valide et charge dans un data warehouse des données de qualité de l'air (AQI) issues de l'API OpenWeather Air Pollution.  
Il répond au cahier des charges du cours : ingestion horaire pour au moins 5 villes, backfill historique (12 mois), stockage brut immuable, reconstruction déterministe d’un fichier propre unique, modélisation dimensionnelle en étoile et exécution continue après le rendu.

**Stack technique**

| Composant          | Technologie                      |
| ------------------ | -------------------------------- |
| Orchestrateur      | GitHub Actions (cron + manuel)   |
| Langage            | Python 3.11                      |
| Extraction         | `requests` avec retry            |
| Stockage brut      | Fichiers JSON dans `raw/`        |
| Stockage propre    | Fichier CSV unique dans `clean/` |
| Data warehouse     | PostgreSQL (Neon, cloud gratuit) |
| Modélisation       | Schéma en étoile                 |
| CI/CD              | GitHub Actions                   |
| Gestion des secrets| GitHub Secrets + `.env`          |

## Architecture

<img width="1886" height="702" alt="Screenshot From 2026-07-22 23-08-00" src="https://github.com/user-attachments/assets/f52a84aa-d0a3-4576-b945-22944ad74f51" />

```
API OpenWeather (Air Pollution)
        │
        ▼
[GitHub Actions – cron horaire]
        │
        ├─ collect.py ────────► raw/ (JSON bruts, un fichier par ville/appel)
        ├─ backfill.py (1x/jour) ► raw/ (données historiques)
        │
        ▼
[clean.py] ────────────────► clean/air_quality_clean.csv
        │
        ▼
[validate_clean.py] ───────► validation (bloquante si échec critique)
        │
        ▼
[load_warehouse.py] ───────► PostgreSQL Neon (schéma en étoile)
```

- **raw/** : fichiers JSON immuables, jamais modifiés. Ils constituent la source de vérité.
- **clean/** : un fichier CSV unique, reconstruit à chaque exécution depuis `raw/`, dédoublonné, trié, normalisé.
- **Data warehouse** : base PostgreSQL hébergée sur Neon, accessible en permanence pour le cours IA1.

L’orchestrateur est GitHub Actions, qui lance le pipeline toutes les heures (et sur déclenchement manuel). Aucun serveur externe n’est nécessaire.

## Villes surveillées

| Ville          | Pays            | Latitude  | Longitude |
| -------------- | --------------- | --------- | --------- |
| Antananarivo   | Madagascar (MG) | -18.8792  | 47.5079   |
| Paris          | France (FR)     | 48.8566   | 2.3522    |
| Nairobi        | Kenya (KE)      | -1.2921   | 36.8219   |
| New York       | États-Unis (US) | 40.7128   | -74.0060  |
| Tokyo          | Japon (JP)      | 35.6762   | 139.6503  |

## Format du fichier `clean/air_quality_clean.csv`

Le fichier propre contient une ligne par ville et par heure, sans doublon, triée par ville puis par date/heure.

| Colonne              | Description                                    | Unité        |
| -------------------- | ---------------------------------------------- | ------------ |
| `ville`              | Nom de la ville                                | —            |
| `pays`               | Code pays sur 2 lettres                        | —            |
| `lat`                | Latitude                                       | degrés       |
| `lon`                | Longitude                                      | degrés       |
| `timestamp`          | Horodatage de la mesure (UTC, ISO 8601)        | —            |
| `aqi`                | Air Quality Index (1 à 5)                      | indice       |
| `co`                 | Concentration de CO                            | μg/m³        |
| `no`                 | Concentration de NO                            | μg/m³        |
| `no2`                | Concentration de NO₂                           | μg/m³        |
| `o3`                 | Concentration d'O₃                             | μg/m³        |
| `so2`                | Concentration de SO₂                           | μg/m³        |
| `pm2_5`              | Concentration de PM2.5                         | μg/m³        |
| `pm10`               | Concentration de PM10                          | μg/m³        |
| `nh3`                | Concentration de NH₃                           | μg/m³        |

Les valeurs manquantes sont représentées par des cellules vides. Les colonnes respectent strictement cet ordre.

## Data Warehouse

Le data warehouse suit un **schéma en étoile** avec une table de faits et deux dimensions.

### dim_city
| Colonne      | Type         | Description                |
| ------------ | ------------ | -------------------------- |
| `city_id`    | SERIAL (PK)  | Identifiant unique         |
| `city_name`  | VARCHAR(100) | Nom de la ville            |
| `country`    | CHAR(2)      | Code pays                  |
| `latitude`   | FLOAT        | Latitude                   |
| `longitude`  | FLOAT        | Longitude                  |

### dim_time
| Colonne      | Type         | Description                        |
| ------------ | ------------ | ---------------------------------- |
| `time_id`    | SERIAL (PK)  | Identifiant unique                 |
| `timestamp`  | TIMESTAMP    | Horodatage UTC                     |
| `year`       | SMALLINT     | Année                              |
| `month`      | SMALLINT     | Mois (1–12)                        |
| `day`        | SMALLINT     | Jour du mois                       |
| `hour`       | SMALLINT     | Heure (0–23)                       |
| `weekday`    | VARCHAR(10)  | Jour de la semaine (ex: Monday)    |
| `is_weekend` | BOOLEAN      | Vrai si samedi ou dimanche         |

### fact_air_quality
| Colonne      | Type         | Description                          |
| ------------ | ------------ | ------------------------------------ |
| `fact_id`    | SERIAL (PK)  | Identifiant unique                   |
| `city_id`    | INT (FK)     | Référence à `dim_city`               |
| `time_id`    | INT (FK)     | Référence à `dim_time`               |
| `aqi`        | SMALLINT     | Air Quality Index (1–5)              |
| `co`         | FLOAT        | Concentration de CO (μg/m³)          |
| `no`         | FLOAT        | Concentration de NO (μg/m³)          |
| `no2`        | FLOAT        | Concentration de NO₂ (μg/m³)         |
| `o3`         | FLOAT        | Concentration d'O₃ (μg/m³)           |
| `so2`        | FLOAT        | Concentration de SO₂ (μg/m³)         |
| `pm2_5`      | FLOAT        | Concentration de PM2.5 (μg/m³)       |
| `pm10`       | FLOAT        | Concentration de PM10 (μg/m³)        |
| `nh3`        | FLOAT        | Concentration de NH₃ (μg/m³)         |

**Cohérence** : le nombre de lignes de `fact_air_quality` doit être approximativement `nombre_de_villes × nombre_d’heures_couvertes`. Les écarts sont expliqués dans la section « Période couverte et trous connus ».

## Déploiement et exécution

### Prérequis (exécution locale)
- Python 3.11
- PostgreSQL accessible (pour la partie warehouse)
- Clé API OpenWeather (plan gratuit)

### 1. Cloner le dépôt et préparer l’environnement
```bash
git clone <url-du-depot>
cd DONNEE2_High5
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configurer les secrets / variables d’environnement
Copier `.env.example` vers `.env` et renseigner :
- `OPENWEATHER_API_KEY`
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

### 3. Exécuter manuellement le pipeline
```bash
python src/collect.py               # Données temps réel
python src/backfill.py --months 12  # Backfill historique (12 mois)
python src/clean.py                 # Générer le CSV propre
python src/validate_clean.py        # Valider le CSV
python src/load_warehouse.py        # Charger dans le data warehouse
```

### 4. Automatisation avec GitHub Actions
Le workflow `.github/workflows/air_quality_etl.yml` exécute le pipeline **toutes les heures**.  
Il :
- Collecte les données courantes
- Exécute le backfill historique une fois par jour seulement (gain de temps)
- Reconstruit le CSV propre, le valide, charge les données dans Neon
- Commit automatiquement les nouveaux fichiers dans le dépôt (sans boucle infinie)
- Envoie une notification par email en cas de succès ou d’échec

**Secrets GitHub requis** :
- `OPENWEATHER_API_KEY`
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `EMAIL_TO` (pour les notifications)

Aucune intervention humaine n’est nécessaire, le pipeline tourne 24h/24.

## Période couverte et trous connus

- **Backfill initial** : 12 mois d’historique sont récupérés (soit environ 8760 heures par ville).  
- **Collecte temps réel** : les données sont ajoutées toutes les heures depuis la mise en service du pipeline.  
- **Écarts éventuels** :  
  - L’API ne fournit pas toujours des données pour toutes les heures (trous ponctuels).  
  - Les périodes de maintenance ou d’indisponibilité de l’API peuvent créer des lacunes.  
  - Le nombre de lignes dans `fact_air_quality` peut donc être légèrement inférieur au produit `villes × heures`.  
- **Déduplication** : en cas de relance du backfill, les fichiers existants sont ignorés ; le CSV propre ne contient jamais de doublons (clé composite ville + heure).

Les trous identifiés seront documentés dans un fichier `known_gaps.md` (ou cette section sera mise à jour après analyse).

## Équipe et contributions

| Membre                  | Rôle principal                              |
| ----------------------- | ------------------------------------------- |
| Mahery (deep-awak)      | Architecture, documentation, coordination   |
| Saviola (saviola24)        | Extraction, collecte et backfill            |
| Nassigael               | CI/CD, automatisation GitHub Actions        |
| Fiononantsoa01          | Transformation, nettoyage, validation       |
| nyyanja / NyAnja        | Modélisation, data warehouse, chargement    |

## Ressources

- [Documentation OpenWeather Air Pollution](https://openweathermap.org/api/air-pollution)
- [Documentation GitHub Actions](https://docs.github.com/actions)
- [PostgreSQL Neon](https://neon.tech)
- [Modélisation dimensionnelle (Kimball)](https://www.kimballgroup.com)
