"""
Production Model Loader
========================

Convenience functions for loading production ML models from MLflow registry.

Usage:
    from app.ml.registry.model_loader import load_production_models
    models = await load_production_models()
"""

import asyncio
from typing import Dict, Any, Optional
import logging

from app.core.config import settings
from app.ml.registry.mlflow_registry import MLflowRegistry, ModelLoader
from app.ml.models.baseline.top_popular import TopPopularBaseline

logger = logging.getLogger(__name__)


async def load_production_models(
    tracking_uri: Optional[str] = None,
    fallback_to_baseline: bool = True
) -> Dict[str, Any]:
    """
    Load production ML models from MLflow registry.

    This function loads all models required for the hybrid recommendation pipeline:
    - K-Means segmentation model
    - LightFM collaborative filtering model
    - XGBoost ranking model

    If models are not found in MLflow (e.g., first startup), falls back to baseline models.

    Args:
        tracking_uri: MLflow tracking server URI (default: from settings)
        fallback_to_baseline: Use baseline models if MLflow models unavailable

    Returns:
        Dictionary with loaded models:
        {
            'segmenter': KMeansSegmenter or None,
            'cf_model': LightFMRecommender or None,
            'ranker': XGBoostRanker or None,
            'baseline': TopPopularBaseline or None
        }

    Raises:
        Exception: If MLflow connection fails and fallback disabled
    """
    logger.info("🔄 Loading production ML models...")

    # Use settings if tracking_uri not provided
    if tracking_uri is None:
        tracking_uri = settings.MLFLOW_TRACKING_URI

    logger.info(f"MLflow tracking URI: {tracking_uri}")

    models = {
        'segmenter': None,
        'cf_model': None,
        'ranker': None,
        'baseline': None
    }

    try:
        # Initialize MLflow registry
        registry = MLflowRegistry(
            tracking_uri=tracking_uri,
            cache_dir="/tmp/mlflow_models",
            cache_ttl_hours=24
        )

        # Create model loader
        loader = ModelLoader(registry=registry, fallback_dir=None)

        # Load models (synchronous call, but fast due to caching)
        # Run in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        loaded_models = await loop.run_in_executor(
            None,
            loader.load_production_models
        )

        # Update models dict
        models.update(loaded_models)

        # Count successfully loaded models
        loaded_count = sum(1 for m in models.values() if m is not None)

        if loaded_count > 0:
            logger.info(f"✅ Loaded {loaded_count}/3 ML models from MLflow")

            # Log which models loaded successfully
            if models['segmenter']:
                logger.info("  ✓ K-Means segmentation model loaded")
            if models['cf_model']:
                logger.info("  ✓ LightFM collaborative filtering model loaded")
            if models['ranker']:
                logger.info("  ✓ XGBoost ranking model loaded")
        else:
            logger.warning("⚠️ No models loaded from MLflow registry")

            if fallback_to_baseline:
                logger.info("🔄 Attempting fallback to baseline models...")
                models = await _load_baseline_models()

    except Exception as e:
        logger.error(f"❌ Failed to load models from MLflow: {str(e)}")

        if fallback_to_baseline:
            logger.info("🔄 Falling back to baseline models...")
            models = await _load_baseline_models()
        else:
            raise

    return models


async def _load_baseline_models() -> Dict[str, Any]:
    """
    Load baseline models as fallback when MLflow models unavailable.

    Returns:
        Dictionary with baseline models
    """
    logger.info("Loading baseline models...")

    models = {
        'segmenter': None,  # No baseline for segmentation
        'cf_model': None,   # No baseline for CF
        'ranker': None,     # No baseline for ranking
        'baseline': None
    }

    try:
        # Initialize baseline recommender
        # This doesn't require training data, just product popularity
        baseline = TopPopularBaseline()
        models['baseline'] = baseline
        logger.info("✅ Baseline model (TopPopular) loaded")

    except Exception as e:
        logger.error(f"❌ Failed to load baseline model: {str(e)}")

    return models


async def reload_models(tracking_uri: Optional[str] = None) -> Dict[str, Any]:
    """
    Reload models from MLflow registry (force refresh cache).

    Useful for model updates without restarting the service.

    Args:
        tracking_uri: MLflow tracking server URI

    Returns:
        Dictionary with reloaded models
    """
    logger.info("🔄 Reloading ML models (force refresh)...")

    if tracking_uri is None:
        tracking_uri = settings.MLFLOW_TRACKING_URI

    registry = MLflowRegistry(tracking_uri=tracking_uri)
    loader = ModelLoader(registry=registry)

    # Clear cache first
    registry.model_cache.clear()
    logger.info("Cache cleared")

    # Reload models
    loop = asyncio.get_event_loop()
    models = await loop.run_in_executor(None, loader.load_production_models)

    logger.info("✅ Models reloaded successfully")

    return models


def check_models_health(models: Dict[str, Any]) -> Dict[str, bool]:
    """
    Check health status of loaded models.

    Args:
        models: Dictionary of loaded models

    Returns:
        Dictionary with health status for each model
    """
    health = {
        'segmenter': models.get('segmenter') is not None,
        'cf_model': models.get('cf_model') is not None,
        'ranker': models.get('ranker') is not None,
        'baseline': models.get('baseline') is not None,
        'all_loaded': all([
            models.get('segmenter'),
            models.get('cf_model'),
            models.get('ranker')
        ])
    }

    return health
