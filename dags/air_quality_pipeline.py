from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="air_quality_pipeline",
    description="Orchestration du pipeline de qualité de l'air via Airflow",
    schedule_interval="0  * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
) as dag:

    collect_data = BashOperator(
        task_id="collect_data",
        bash_command="cd /opt/airflow && python src/collect.py",
    )

    backfill_data = BashOperator(
        task_id="backfill_data",
        bash_command="cd /opt/airflow && python src/backfill.py --months 6",
    )

    clean_data = BashOperator(
        task_id="clean_data",
        bash_command="cd /opt/airflow && python src/clean.py",
    )

    validate_data = BashOperator(
        task_id="validate_data",
        bash_command="cd /opt/airflow && python src/validate_clean.py",
    )

    load_warehouse = BashOperator(
        task_id="load_warehouse",
        bash_command="cd /opt/airflow && python src/load_warehouse.py",
    )

    collect_data >> backfill_data >> clean_data >> validate_data >> load_warehouse
