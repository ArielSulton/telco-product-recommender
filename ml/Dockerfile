# Multi-stage build for ML pipeline
FROM python:3.10-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Training stage
FROM base AS training

# Copy requirements
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy ML code
COPY . .

# Create directories for data and models
RUN mkdir -p data/raw data/processed data/features models

# Expose MLflow port
EXPOSE 5000

# Default command (can be overridden)
CMD ["python", "scripts/train_segmentation.py"]

# Jupyter notebook stage for experimentation
FROM base AS jupyter

# Copy requirements
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy ML code
COPY . .

# Create directories
RUN mkdir -p data/raw data/processed data/features models

# Expose Jupyter port
EXPOSE 8888

# Run Jupyter notebook
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]
