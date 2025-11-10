#!/bin/bash
set -e

# Create additional databases for Airflow and MLflow
# This script runs before 01_init.sql (alphabetical order)

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create Airflow database if not exists
    SELECT 'CREATE DATABASE airflow'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec

    -- Grant privileges
    GRANT ALL PRIVILEGES ON DATABASE airflow TO "$POSTGRES_USER";
EOSQL

echo "✅ Airflow database created successfully"
