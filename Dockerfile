FROM apache/airflow:2.10.2-python3.11

ENV AIRFLOW__CORE__LOAD_EXAMPLES=False
WORKDIR /opt/airflow

USER root
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir python-dotenv psycopg2-binary
COPY src/ /opt/airflow/src/
COPY dags/ /opt/airflow/dags/
RUN chown -R airflow:root /opt/airflow
USER airflow