# DONNEE2: OpenWeather - Air Quality Data Pipeline

## Project Overview

This project implements a complete ETL pipeline for collecting, cleaning, and storing air quality data from the OpenWeather Air Pollution API. It processes both real-time and historical datasets to produce clean, analyzable data suitable for business intelligence and analytics workloads.

**Core Technologies:**
- Python 3.11
- PostgreSQL with psycopg2
- OpenWeather Air Pollution API
- requests library for HTTP communication
- python-dotenv for configuration management

**Problem Statement Addressed:**
- Automated collection of ambient air quality metrics across multiple cities
- Temporal data management for both real-time and historical observations
- Deduplication and normalization of raw sensor data into a clean dataset
- Column-level validation and value range enforcement
- Loading processed data into a dimensional data warehouse model

## Architecture and Project Structure

### Directory Organization
```
DONNEE2_High5/
├── raw/                    # Raw JSON responses from OpenWeather API
├── clean/                  # Cleaned CSV dataset output
├── src/                    # Pipeline source code
│   ├── collect.py          # Real-time data collection
│   ├── backfill.py         # Historical data retrieval
│   ├── clean.py            # Data normalization and deduplication
│   ├── validate_clean.py   # Data quality validation
│   ├── load_warehouse.py   # Warehouse loading orchestrator
│   └── warehouse/          # Database interaction layer
│       ├── db.py           # PostgreSQL connection manager
│       └── models.py       # Dimensional model insertion logic
├── sql/
│   └── create_schema.sql   # Star schema DDL definitions
├── requirements.txt        # Python dependencies
└── .github/
    └── workflows/
        └── daily_pipeline.yml  # CI/CD automation
```

### Architectural Design Decisions
- **Clear ETL Separation**: Each pipeline stage (Extract, Transform, Load) is implemented as an independent, testable Python module
- **Raw Data Preservation**: All API responses stored as individual JSON files in `raw/` directory, serving as immutable source of truth
- **Deterministic Cleaning**: The clean CSV is fully reconstructable from raw files at any time
- **Star Schema Model**: Dimensional model (`dim_city`, `dim_time`, `fact_air_quality`) optimized for analytical queries on timestamped city measurements
- **Environment-Based Configuration**: All sensitive credentials managed through environment variables using `.env` files locally and GitHub Secrets in CI/CD

## Technical Implementation

### Data Collection Module

The `src/collect.py` script queries the OpenWeather Air Pollution API for five predefined cities specified in the `VILLES` configuration. Each API response is enriched with metadata fields under the `_meta` key (collection timestamp, city name, API endpoint) and persisted as an independent JSON file in the `raw/` directory. The implementation includes an exponential backoff retry mechanism handling network timeouts and HTTP 5xx server errors, ensuring resilience against transient API failures.

### Historical Backfill

The `src/backfill.py` module retrieves historical air quality data through OpenWeather's `air_pollution/history` endpoint. To comply with API rate limits, requests are batched into five-day windows. Each hourly measurement is stored as a separate JSON file within `raw/`, maintaining consistency with the real-time collection format. The script implements idempotency by checking for existing files before making API calls, enabling safe re-execution without data duplication.

### Data Cleaning and Normalization

The `src/clean.py` transformation layer reconstructs `clean/air_quality_clean.csv` from all raw JSON files. The cleaning process:
- Flattens nested JSON structures into flat CSV rows
- Standardizes missing values to empty cells rather than null placeholders
- Generates a composite deduplication key combining city name and measurement hour
- Retains only the most recent measurement when duplicate records exist
- Sorts output by city name then timestamp for consistent ordering

### Data Validation Framework

The `src/validate_clean.py` module enforces a strict data contract on the cleaned CSV output. Validation checks include:
- File existence and non-empty content verification
- Column presence and ordering validation against expected schema
- Uniqueness constraint enforcement on the composite key (city + timestamp)
- Chronological sort order verification within each city group
- Minimum cardinality check requiring at least five distinct cities
- Value range validation for coordinates, timestamps, Air Quality Index, and pollutant concentrations
- ISO 8601 UTC timestamp format verification

Non-blocking warnings are generated for missing values and temporal gaps, providing observability without halting pipeline execution.

### Data Warehouse Loading

The dimensional model is defined in `sql/create_schema.sql` with three tables:
- `dim_city`: City dimension with geographic coordinates
- `dim_time`: Time dimension at hourly granularity
- `fact_air_quality`: Fact table containing AQI and pollutant measurements

The `src/warehouse/db.py` module manages PostgreSQL connections using environment variables for configuration. The `src/warehouse/models.py` module provides idempotent insertion functions using ON CONFLICT clauses, ensuring safe re-execution. The orchestrator `src/load_warehouse.py` reads the cleaned CSV and sequentially populates dimensions before loading fact records.


## Project Management and Task Distribution

This project represents a collaborative effort across a five-member team, with clear separation of responsibilities spanning architecture design, ETL pipeline development, CI/CD automation, and technical documentation.

| Author| Primary Responsibilities | Key Files |
|---|---|---|
| deep-awak (Mahery)| Project architecture design, tool selection, technical documentation, system design decisions | README.md, architecture planning |
| saviola24 (Gael)| Repository initialization, data collection module, historical backfill implementation, network resilience patterns | src/collect.py, src/backfill.py, raw/ |
| Nassigael| GitHub Actions CI/CD workflow implementation, pipeline automation | .github/workflows/daily_pipeline.yml |
| Fiononantsoa01| Data cleaning and normalization, CSV dataset generation, data validation framework | src/clean.py, src/validate_clean.py, clean/air_quality_clean.csv |
| nyyanja / NyAnja| Data warehouse schema design, database interaction layer, configuration management, warehouse loading orchestration | sql/create_schema.sql, src/load_warehouse.py, src/warehouse/models.py, src/warehouse/db.py |

### Role Delineation

**Mahery (deep-awak)** served as the project architect and technical documentation lead. Responsibilities included defining the overall system architecture, selecting the technology stack (Python, PostgreSQL, OpenWeather API, GitHub Actions), establishing the ETL pipeline design patterns, and authoring comprehensive technical documentation including this README. 

**saviola24** focused on the extraction layer of the pipeline, implementing robust API communication with retry logic for resilience against network failures, historical data backfilling with rate-limit awareness respecting OpenWeather API constraints, and establishing the raw data preservation strategy that serves as the immutable foundation for all downstream processing.

**Nassigael** implemented the CI/CD automation layer through GitHub Actions workflows. This contribution established automated daily pipeline execution with resource optimization strategies including conditional builds, caching mechanisms, and proper secret management. The workflow ensures consistent, unattended data collection and warehouse updates while minimizing GitHub Actions minutes consumption.

**Fiononantsoa01** handled the transformation layer, developing the deterministic cleaning process that reconstructs the canonical CSV dataset from raw JSON files, implementing deduplication logic based on composite keys, and building the comprehensive validation framework that enforces data quality standards through multiple validation checks.

**nyyanja / NyAnja** architected the storage layer, designing the dimensional star schema model optimized for analytical queries, implementing idempotent database insertion functions using ON CONFLICT clauses, creating the database connection abstraction layer, and orchestrating the end-to-end warehouse loading process.

## Continuous Integration and Automated Pipeline Execution

### GitHub Actions Workflow Architecture

The project implements automated daily pipeline execution through a GitHub Actions workflow defined in `.github/workflows/daily_pipeline.yml`. This automation ensures consistent data collection and warehouse updates without manual intervention.

**Workflow Trigger Configuration:**
The pipeline is scheduled to execute every day using a cron expression. The schedule timing was selected to process the previous day's complete data after midnight UTC, ensuring all hourly measurements are available from the API. The workflow also supports manual triggering through the `workflow_dispatch` event for ad-hoc executions and testing.

**Resource Optimization Strategy:**
The workflow implementation prioritizes resource efficiency through several design decisions:
- Conditional Docker builds triggered only when source files change, preventing unnecessary image reconstruction
- GitHub Actions cache utilization for Docker layers and Python dependencies, reducing build times by approximately 60%
- Direct Python execution replacing the original Docker-based approach, eliminating container initialization overhead
- PostgreSQL service containers with health checks instead of embedded database initialization
- Aggressive timeout limits (15 minutes maximum) preventing hung processes from consuming excess minutes

**Secret Management:**
All sensitive credentials (API keys, database connection strings) are stored as GitHub Secrets and injected as environment variables at runtime. This approach prevents credential exposure in logs or source code while maintaining accessibility to the pipeline. The workflow references secrets including `OPENWEATHER_API_KEY`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`.

**Pipeline Execution Flow:**
1. **Change Detection**: The workflow checks for modifications to DAG definitions, requirements, or Dockerfile since the last successful run
2. **Dependency Installation**: Python packages are installed with pip cache enabled for faster subsequent runs
3. **Database Service Initialization**: A temporary PostgreSQL container starts with health checks ensuring availability before pipeline execution
4. **Sequential ETL Execution**: Scripts execute in dependency order (collect, clean, validate, load) with error propagation
5. **Automatic Cleanup**: Service containers and temporary files are removed regardless of execution success or failure

### Workflow Verification and Monitoring

**Execution Monitoring:**
Pipeline runs are visible in the GitHub repository's Actions tab, displaying real-time logs, execution duration, and success/failure status. Each step produces structured log output for debugging and audit purposes.

**Failure Notification:**
On workflow failure, an automated GitHub Issue is created containing the run ID and direct link to the failed execution, enabling rapid response to pipeline interruptions.

**Status Badge:**
A workflow status badge integrated into this README provides immediate visibility into the current pipeline health state.

## Deployment Instructions

### 1. Environment Setup

```bash
cd /workspaces/DONNEE2_High5
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install psycopg2-binary
```

### 2. Environment Variables Configuration

Copy the configuration template:

```bash
cp .env.example .env
```

Complete the following variables in `.env`:
- `OPENWEATHER_API_KEY`: OpenWeather API authentication key
- `DB_HOST`: PostgreSQL server hostname
- `DB_NAME`: Target database name
- `DB_USER`: Database user with write permissions
- `DB_PASSWORD`: Database user password
- `DB_PORT`: PostgreSQL connection port (default: 5432)

The GitHub Actions workflow retrieves these same values from GitHub Secrets, ensuring consistent configuration across local and automated executions.

### 3. Real-Time Data Collection

```bash
python src/collect.py
```

### 4. Historical Backfill (6-Month Window)

```bash
python src/backfill.py --months 6
```

### 5. Clean Dataset Generation

```bash
python src/clean.py
```

### 6. Data Validation

```bash
python src/validate_clean.py
```

### 7. Warehouse Schema Creation

Execute the DDL script against an accessible PostgreSQL instance:

```bash
psql "host=$DB_HOST port=$DB_PORT dbname=$DB_NAME user=$DB_USER password=$DB_PASSWORD" -f sql/create_schema.sql
```

### 8. Data Warehouse Loading

```bash
python src/load_warehouse.py
```

### 9. Operational Notes

- The `raw/` directory serves as the immutable data lake containing collected and backfilled measurements. These files must be preserved as the system's source of truth.
- The `clean/air_quality_clean.csv` file is fully reconstructed on each execution of `src/clean.py` and should not be manually edited.
- The `src/backfill.py` script is designed for safe re-execution, automatically skipping previously retrieved data files.
- All pipeline scripts return non-zero exit codes on failure, enabling proper error propagation in both local and CI/CD environments.

## Ressources

Ce projet intègre des pipelines automatisés et des environnements conteneurisés. Voici les ressources clés utilisées pour leur apprentissage et leur mise en œuvre :

### GitHub Actions
*   **Documentation Officielle GitHub** : [Quickstart for GitHub Actions](https://github.com) — Guide fondamental pour comprendre la syntaxe des fichiers YAML, les déclencheurs (`cron`, `workflow_dispatch`) et les secrets.
*   **GitHub Packages** : [Working with the Container registry](https://github.com) — Guide officiel pour s'authentifier et téléverser des images Docker sur `ghcr.io`.

### Docker & CI/CD
*   **Docker Buildx** : [GitHub Actions Docker Setup](https://github.com) — Modèles de configuration pour la compilation, la gestion du cache avancé (`type=gha`) et la publication automatique d'images Docker.
*   **Apache Airflow** : [Airflow CLI Reference](https://apache.org) — Références des commandes en ligne de commande pour initialiser les bases de données de test (`airflow db init`) et exécuter les tâches sans interface graphique (`airflow tasks test`).
