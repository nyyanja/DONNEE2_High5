# OpenWeather - Air Quality Data Pipeline

## Project Overview

An automated, production-grade ETL pipeline that ingests real-time and historical air quality data from the OpenWeather API. The architecture orchestrates workflow execution via Apache Airflow, deployed and provisioned through CI/CD pipelines managed by GitHub Actions. Processed datasets are delivered clean and optimized for downstream analytics and Business Intelligence applications.

## Tech Stack

| Component | Technology | Primary Use Case |
|---|---|---|
| Language | Python 3.11 | Core logic, extraction scripts, transformation processing |
| Orchestration | Apache Airflow 2.10.2 | Pipeline dependency management, workflow monitoring |
| Containerization | Docker | Environment standardization, portability, reproducibility |
| Storage | PostgreSQL (Neon) + psycopg2 | Analytical data warehouse hosting dimensional star schema |
| Data Source | OpenWeather API | Ingestion point for ambient air pollution metrics |
| CI/CD | GitHub Actions | Automated execution, cron scheduling, secret management |
| Configuration | python-dotenv | Environment-based credentials management |

## Key Engineering Challenges Solved

| Domain | Challenge | Solution |
|---|---|---|
| Automation | Multi-city metrics collection | Hands-free daily execution via hybrid orchestration |
| Time Series | Dual-mode tracking | Real-time collection + 6-month historical backfill |
| Data Ingestion | Heterogeneous raw formats | Normalization, flattening, deduplication of JSON to CSV |
| Data Quality | Schema violations, out-of-range values | Column-level validation, value range enforcement |
| Data Modeling | Inefficient analytical queries | Dimensional star schema optimized for BI |
| Resilience | Transient failures | Retry mechanisms, error handling, failure alerts |

## Architecture

### Directory Organization
```
DONNEE2_High5/
├── dags/                           # Airflow DAG definitions
│   └── air_quality_pipeline.py     # 5-task sequential pipeline
├── raw/                            # Raw JSON responses (immutable source of truth)
├── clean/                          # Cleaned CSV output
├── src/                            # ETL pipeline source code
│   ├── collect.py                  # Real-time data collection
│   ├── backfill.py                 # Historical data retrieval (6-month window)
│   ├── clean.py                    # Normalization and deduplication
│   ├── validate_clean.py           # 7-category data quality validation
│   ├── load_warehouse.py           # Warehouse loading orchestrator
│   └── warehouse/
│       ├── db.py                   # PostgreSQL connection manager
│       └── models.py               # Idempotent insertion logic
├── sql/
│   └── create_schema.sql           # Star schema DDL (dim_city, dim_time, fact_air_quality)
├── Dockerfile                      # Airflow 2.10.2 + Python 3.11 image
├── requirements.txt                # Python dependencies
└── .github/workflows/
    └── daily_pipeline.yml          # CI/CD automation workflow
```

### Hybrid Orchestration Architecture

**Two-Tier Strategy: GitHub Actions provisions infrastructure; Apache Airflow orchestrates the pipeline.**

**Tier 1 - GitHub Actions (Infrastructure Layer):**
Provisions an Ubuntu runner, starts a temporary PostgreSQL service container for Airflow metadata, builds the Docker image, launches the Airflow scheduler, triggers DAG execution, monitors completion, and performs cleanup. Eliminates need for a permanently running Airflow server.

**Tier 2 - Apache Airflow (Orchestration Layer):**
Executes the `air_quality_pipeline` DAG defining five sequential tasks with built-in retry logic (1 retry, 5-minute delay), dependency management, and state reporting. Configured with `catchup=False` to prevent backfilling missed intervals.

### Database Architecture: Two Distinct PostgreSQL Instances

**Airflow Metadata Database (Temporary - Local Service Container):**
Transient PostgreSQL instance for Airflow's internal state (DAG runs, task statuses, scheduler info). Created at workflow start, destroyed during cleanup. No connection to business data.

**Neon Data Warehouse (Permanent - Cloud Hosted):**
Production data warehouse hosted on Neon (serverless PostgreSQL). Stores dimensional model (`dim_city`, `dim_time`, `fact_air_quality`). Accumulates historical data across all executions. Connection parameters stored as GitHub Secrets.

```
GitHub Actions Cron (01:00 UTC)
    │
    ├── Start PostgreSQL Container (Temporary - Airflow Metadata)
    │       └── postgresql://airflow:airflow@localhost:5432/airflow
    │
    ├── Build Docker Image
    ├── airflow db init → Temporary DB
    ├── Launch Airflow Scheduler
    └── Trigger DAG: air_quality_pipeline
            │
            ├── Task 1: collect_data → raw/*.json
            ├── Task 2: backfill_data → raw/*.json
            ├── Task 3: clean_data → clean/air_quality_clean.csv
            ├── Task 4: validate_data → Quality checks
            └── Task 5: load_warehouse → Neon PostgreSQL (PERMANENT)
                    ├── dim_city
                    ├── dim_time
                    └── fact_air_quality
```

### Secret Management

| Secret | Purpose | Target |
|--------|---------|--------|
| `OPENWEATHER_API_KEY` | API authentication | OpenWeather API |
| `DB_HOST` | Neon hostname | Neon (Permanent) |
| `DB_PORT` | Neon port | Neon (Permanent) |
| `DB_NAME` | Neon database name | Neon (Permanent) |
| `DB_USER` | Neon user | Neon (Permanent) |
| `DB_PASSWORD` | Neon password | Neon (Permanent) |

Temporary Airflow DB uses hardcoded local credentials (`airflow:airflow@localhost:5432`) - no sensitive data stored.

### Architectural Design Decisions

- **ETL Separation**: Independent, testable modules per pipeline stage enabling isolated debugging
- **Raw Data Preservation**: Immutable JSON files serve as source of truth and audit trail
- **Deterministic Cleaning**: Identical raw inputs always produce identical CSV output
- **Star Schema**: Surrogate keys, city/time dimensions optimized for analytical aggregation
- **Environment-Based Config**: `.env` for local dev, GitHub Secrets for CI/CD - zero hardcoded credentials
- **Hybrid Orchestration**: Airflow's scheduling without permanent server costs

## Technical Implementation

### Data Collection (`src/collect.py`)
Queries OpenWeather API for five cities. Enriches responses with metadata (`_meta` key). Persists as JSON files in `raw/`. Implements exponential backoff retry for network errors and HTTP 5xx responses.

### Historical Backfill (`src/backfill.py`)
Retrieves historical data via `air_pollution/history` endpoint. Batches requests into 5-day windows (API limit). Idempotent: skips existing files. Configurable depth via `--months` parameter (default: 6).

### Data Cleaning (`src/clean.py`)
Reconstructs `clean/air_quality_clean.csv` from all raw files through sequential operations:
1. **Flatten**: Expand nested JSON into flat CSV rows
2. **Normalize**: Standardize missing values to empty cells
3. **Deduplicate**: Composite key (city + hour), retain most recent record
4. **Sort**: City name then timestamp
5. **Preserve metadata**: Collection timestamps retained for lineage

### Data Validation (`src/validate_clean.py`)
Seven-category validation framework:
- **Structural**: File existence, column presence/ordering
- **Uniqueness**: Composite key constraints
- **Temporal**: Chronological ordering within city groups
- **Cardinality**: Minimum 5 distinct cities
- **Range**: Valid coordinates, AQI 1-5, pollutant bounds
- **Format**: ISO 8601 UTC timestamps
- **Observability**: Non-blocking warnings for gaps and missing values

Critical errors halt pipeline; warnings logged but non-blocking.

### Data Warehouse Loading (`src/load_warehouse.py`)

**Schema (Star Schema):**
- `dim_city`: City name, coordinates, surrogate key
- `dim_time`: Timestamp, date components, surrogate key
- `fact_air_quality`: AQI, pollutants (CO, NO, NO2, O3, SO2, PM2.5, PM10, NH3), foreign keys to dimensions

**Loading Strategy:**
- `db.py`: Connection manager using environment variables
- `models.py`: Idempotent inserts via `ON CONFLICT` clauses
- Orchestrator populates dimensions first, then fact records

## Team & Contributions

| Member | Role | Key Contributions |
|---|---|---|
| **Mahery (deep-awak)** | Project Architect & Documentation | System architecture design, technology selection, ETL patterns, technical documentation |
| **Saviola (saviola24)** | Extraction Layer Engineer | API clients with retry logic, raw data preservation strategy, historical backfill module |
| **Nassigael** | CI/CD Automation Engineer | GitHub Actions workflow, hybrid orchestration, service containers, resource optimization |
| **Fiononantsoa01** | Transformation Layer Engineer | Data cleaning/normalization, 7-category validation framework, CSV generation |
| **nyyanja / NyAnja** | Storage Layer Engineer | Star schema design, idempotent insertion logic, database abstraction, warehouse loading |

## Deployment Instructions

### 1. Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install psycopg2-binary
```

### 2. Configuration
```bash
cp .env.example .env
# Set: OPENWEATHER_API_KEY, DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT
```

### 3. Pipeline Execution (Local)
```bash
python src/collect.py                    # Real-time collection
python src/backfill.py --months 6        # Historical backfill
python src/clean.py                      # Generate clean CSV
python src/validate_clean.py             # Validate data quality
psql -f sql/create_schema.sql            # Create warehouse schema
python src/load_warehouse.py             # Load into Neon
```

### 4. Automated Execution
Pipeline runs daily at 01:00 UTC via GitHub Actions. Manual trigger available through `workflow_dispatch`. Monitor in Actions tab.

### Operational Notes
- `raw/` directory is immutable source of truth - preserve all files
- `clean/air_quality_clean.csv` is fully reconstructed each run - do not edit manually
- `backfill.py` is idempotent and safe for re-execution
- All scripts return non-zero exit codes on failure for proper error propagation
- Warehouse loading requires Neon PostgreSQL; other stages run independently

## Resources

### GitHub Actions
- [Understanding GitHub Actions](https://docs.github.com/en/actions) - Workflow syntax, cron triggers, secrets
- [Workflow Syntax Reference](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions) - Service containers, conditions, job dependencies

### Docker
- [docker/setup-buildx-action](https://github.com/docker/setup-buildx-action) - Buildx configuration with caching
- [Dockerfile Reference](https://docs.docker.com/engine/reference/builder/) - Layer optimization, security best practices

### Apache Airflow
- [Airflow CLI Reference](https://airflow.apache.org/docs/apache-airflow/stable/cli-and-env-vars-ref.html) - `db init`, `dags trigger`, `dags list-runs`
- [DAG Authoring Guide](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html) - Task dependencies, retry configuration, catchup behavior
- [Apache Airflow Docker Image](https://hub.docker.com/r/apache/airflow) - Official image, version tags

### Python Libraries
- [Requests](https://docs.python-requests.org/) - HTTP client with retry patterns
- [python-dotenv](https://pypi.org/project/python-dotenv/) - Environment variable management
- [psycopg2](https://www.psycopg.org/docs/) - PostgreSQL adapter

### Data Engineering
- [Dimensional Modeling Techniques](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/) - Kimball star schema methodology
- [ETL Best Practices](https://docs.aws.amazon.com/whitepapers/latest/etl-best-practices/welcome.html) - Idempotency, error handling, modular design patterns
