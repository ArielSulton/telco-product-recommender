FROM ghcr.io/mlflow/mlflow:v2.9.2

# Install PostgreSQL adapter for backend store
RUN pip install --no-cache-dir psycopg2-binary

# Expose MLflow port
EXPOSE 5000

# Default command (override in docker-compose)
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000"]
