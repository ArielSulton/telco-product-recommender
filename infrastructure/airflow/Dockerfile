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
