FROM apache/airflow:2.8.0-python3.10

USER root

# Install build dependencies for lightfm
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install Python packages with build dependencies available
RUN pip install --no-cache-dir \
    mlflow==2.9.2 \
    scikit-learn \
    lightfm \
    xgboost \
    joblib \
    shap \
    pandas \
    numpy \
    optuna \
    psycopg2-binary \
    scipy

# Copy DAGs, plugins, and dependencies into image
# Build context is project root, so paths are relative to root
COPY --chown=airflow:root ./infrastructure/airflow/dags /opt/airflow/dags
COPY --chown=airflow:root ./infrastructure/airflow/plugins /opt/airflow/plugins
COPY --chown=airflow:root ./backend /opt/airflow/backend
COPY --chown=airflow:root ./services /opt/airflow/services
COPY --chown=airflow:root ./ml/data /opt/airflow/ml/data
