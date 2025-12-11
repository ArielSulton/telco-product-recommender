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
import pandas as pd

from app.core.config import settings
from app.ml.registry.mlflow_registry import MLflowRegistry, ModelLoader
from app.ml.models.baseline.top_popular import TopPopularBaseline
from app.ml.models.baseline.enhanced_baseline import EnhancedBaseline
from app.db.database import get_db_connection

logger = logging.getLogger(__name__)


async def load_production_models(
    tracking_uri: Optional[str] = None,
    fallback_to_baseline: bool = True
) -> Dict[str, Any]:
    """
    Load production ML models from MLflow registry.

    This function loads all models required for the hybrid recommendation pipeline:
    - K-Means segmentation model
    - FixedLightFM collaborative filtering model (matrix factorization)
    - EnhancedBaseline recommendation model (content/affinity/segment strategies)
    - XGBoost ranking model

    If models are not found in MLflow (e.g., first startup), falls back to baseline models.

    Args:
        tracking_uri: MLflow tracking server URI (default: from settings)
        fallback_to_baseline: Use baseline models if MLflow models unavailable

    Returns:
        Dictionary with loaded models:
        {
            'segmenter': KMeansSegmenter or None,
            'cf_model': FixedLightFMRecommender or None,
            'baseline': EnhancedBaseline or None,
            'ranker': XGBoostRanker or None
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
        'baseline': None,
        'ranker': None
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
            logger.info(f"✅ Loaded {loaded_count}/4 ML models from MLflow")

            # Log which models loaded successfully
            if models['segmenter']:
                logger.info("  ✓ K-Means segmentation model loaded")
            if models['cf_model']:
                logger.info("  ✓ FixedLightFM collaborative filtering model loaded")
            if models['baseline']:
                logger.info("  ✓ EnhancedBaseline recommendation model loaded")
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
    Includes fetching data and fitting the model to ensure it's ready for inference.

    Returns:
        Dictionary with baseline models
    """
    logger.info("Loading baseline models...")

    models = {
        'segmenter': None,  # No baseline for segmentation
        'cf_model': None,   # No baseline for collaborative filtering (needs training data)
        'baseline': None,   # EnhancedBaseline with TopPopular fallback
        'ranker': None      # No baseline for ranking
    }

    try:
        # Try to initialize EnhancedBaseline (preferred)
        try:
            # EnhancedBaseline wraps TopPopularBaseline + adds strategies
            baseline = EnhancedBaseline()
            models['baseline'] = baseline
            logger.info("✅ Baseline model (EnhancedBaseline) initialized")
        except Exception as e:
            # Fallback to simple TopPopularBaseline if EnhancedBaseline fails
            logger.warning(f"EnhancedBaseline initialization failed, using TopPopular: {str(e)}")
            baseline = TopPopularBaseline()
            models['baseline'] = baseline
            logger.info("✅ Baseline model (TopPopular) initialized")

        # Fit the baseline model with transaction data
        if models['baseline']:
            try:
                # Fetch recent transactions to calculate popularity
                conn = get_db_connection()
                query = """
                    SELECT user_id, product_id, transaction_date 
                    FROM transactions 
                    WHERE status = 'completed'
                    ORDER BY transaction_date DESC
                    LIMIT 10000
                """
                transactions_df = pd.read_sql(query, conn)
                conn.close()

                if not transactions_df.empty:
                    # Fit the model
                    models['baseline'].fit(transactions_df)
                    logger.info(f"✅ Baseline model fitted with {len(transactions_df)} transactions")
                else:
                    logger.warning("⚠️ No transactions found to fit baseline model - cold start mode")
                    # Force fit with empty dataframe to allow cold start (prevent 'not fitted' error)
                    # Create dummy DF with required columns
                    dummy_df = pd.DataFrame(columns=['user_id', 'product_id', 'transaction_date'])
                    models['baseline'].fit(dummy_df)
                    logger.info("✅ Baseline model force-fitted for cold start")
            
            except Exception as e:
                logger.error(f"❌ Failed to fit baseline model: {str(e)}")
                # Force fit as last resort
                try:
                    dummy_df = pd.DataFrame(columns=['user_id', 'product_id', 'transaction_date'])
                    models['baseline'].fit(dummy_df)
                    logger.info("✅ Baseline model force-fitted after DB error")
                except:
                    logger.error("❌ Could not force-fit baseline model")

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
        'baseline': models.get('baseline') is not None,
        'ranker': models.get('ranker') is not None,
        'all_loaded': all([
            models.get('segmenter'),
            models.get('baseline'),  # CF model optional (can work without it)
            models.get('ranker')
        ]),
        'cf_available': models.get('cf_model') is not None
    }

    return health
