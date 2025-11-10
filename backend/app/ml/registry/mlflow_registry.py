"""
MLflow Model Registry Integration
===================================

Dynamic model loading and lifecycle management using MLflow.

Features:
- Model versioning (production/staging/archived)
- Dynamic model loading from registry
- Model caching in memory
- Fallback strategies when models unavailable
- Model warm-up and health checks
"""

from typing import Optional, Dict, Any, Tuple
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
import joblib

import mlflow
import mlflow.pyfunc
from mlflow.tracking import MlflowClient
from mlflow.exceptions import MlflowException

from app.ml.models.segmentation.kmeans_segmenter import KMeansSegmenter
from app.ml.models.collaborative.lightfm_recommender import LightFMRecommender
from app.ml.models.ranker.xgboost_ranker import XGBoostRanker

logger = logging.getLogger(__name__)


class MLflowRegistry:
    """
    MLflow model registry manager for dynamic model loading.

    Handles model versioning, caching, and lifecycle management.
    """

    def __init__(
        self,
        tracking_uri: str,
        cache_dir: Optional[str] = None,
        cache_ttl_hours: int = 24
    ):
        """
        Initialize MLflow registry.

        Args:
            tracking_uri: MLflow tracking server URI
            cache_dir: Local cache directory for models
            cache_ttl_hours: Cache TTL in hours
        """
        self.tracking_uri = tracking_uri
        self.cache_dir = Path(cache_dir) if cache_dir else Path("/tmp/mlflow_cache")
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

        # Set MLflow tracking URI
        mlflow.set_tracking_uri(tracking_uri)
        self.client = MlflowClient(tracking_uri=tracking_uri)

        # In-memory model cache
        self.model_cache: Dict[str, Tuple[Any, datetime]] = {}

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"MLflow registry initialized: {tracking_uri}")

    def load_model(
        self,
        model_name: str,
        stage: str = "Production",
        version: Optional[int] = None,
        force_reload: bool = False
    ) -> Any:
        """
        Load model from MLflow registry.

        Args:
            model_name: Registered model name
            stage: Model stage (Production, Staging, Archived)
            version: Specific version number (overrides stage)
            force_reload: Force reload even if cached

        Returns:
            Loaded model object
        """
        cache_key = f"{model_name}:{stage if version is None else version}"

        # Check memory cache
        if not force_reload and cache_key in self.model_cache:
            model, cached_at = self.model_cache[cache_key]
            if datetime.now() - cached_at < self.cache_ttl:
                logger.info(f"Using cached model: {cache_key}")
                return model
            else:
                logger.info(f"Cache expired for {cache_key}, reloading...")

        try:
            # Get model version
            if version is not None:
                model_version = self.client.get_model_version(model_name, str(version))
            else:
                model_versions = self.client.get_latest_versions(model_name, stages=[stage])
                if not model_versions:
                    raise ValueError(f"No model found for {model_name} in stage {stage}")
                model_version = model_versions[0]

            logger.info(f"Loading {model_name} version {model_version.version} from {stage}")

            # Load model based on type
            model = self._load_model_by_type(model_name, model_version)

            # Cache in memory
            self.model_cache[cache_key] = (model, datetime.now())

            logger.info(f"Model loaded successfully: {cache_key}")

            return model

        except MlflowException as e:
            logger.error(f"MLflow error loading {model_name}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error loading model {model_name}: {str(e)}", exc_info=True)
            raise

    def _load_model_by_type(self, model_name: str, model_version) -> Any:
        """Load model based on registered name."""
        model_uri = f"models:/{model_name}/{model_version.version}"

        # K-Means Segmentation
        if "kmeans" in model_name.lower() or "segmentation" in model_name.lower():
            return self._load_kmeans(model_uri)

        # LightFM Collaborative Filtering
        elif "lightfm" in model_name.lower() or "collaborative" in model_name.lower():
            return self._load_lightfm(model_uri)

        # XGBoost Ranker
        elif "xgboost" in model_name.lower() or "ranker" in model_name.lower():
            return self._load_xgboost(model_uri)

        # Generic PyFunc model
        else:
            logger.warning(f"Unknown model type for {model_name}, using generic loader")
            return mlflow.pyfunc.load_model(model_uri)

    def _load_kmeans(self, model_uri: str) -> KMeansSegmenter:
        """Load K-Means segmentation model."""
        # Download model artifacts
        local_path = mlflow.artifacts.download_artifacts(model_uri)

        # Load K-Means model
        segmenter = KMeansSegmenter()
        segmenter.load_model(os.path.join(local_path, "kmeans_model"))

        return segmenter

    def _load_lightfm(self, model_uri: str) -> LightFMRecommender:
        """Load LightFM collaborative filtering model."""
        local_path = mlflow.artifacts.download_artifacts(model_uri)

        # Load LightFM model
        recommender = LightFMRecommender()
        recommender.load_model(os.path.join(local_path, "lightfm_model"))

        return recommender

    def _load_xgboost(self, model_uri: str) -> XGBoostRanker:
        """Load XGBoost ranking model."""
        local_path = mlflow.artifacts.download_artifacts(model_uri)

        # Load XGBoost ranker
        ranker = XGBoostRanker()
        ranker.load_model(os.path.join(local_path, "xgboost_ranker"))

        return ranker

    def get_model_info(self, model_name: str, stage: str = "Production") -> Dict:
        """
        Get model metadata from registry.

        Args:
            model_name: Registered model name
            stage: Model stage

        Returns:
            Dictionary with model metadata
        """
        try:
            model_versions = self.client.get_latest_versions(model_name, stages=[stage])
            if not model_versions:
                return {}

            model_version = model_versions[0]

            return {
                'name': model_name,
                'version': model_version.version,
                'stage': model_version.current_stage,
                'run_id': model_version.run_id,
                'creation_timestamp': model_version.creation_timestamp,
                'last_updated_timestamp': model_version.last_updated_timestamp,
                'source': model_version.source,
                'description': model_version.description
            }

        except Exception as e:
            logger.error(f"Error getting model info for {model_name}: {str(e)}")
            return {}

    def list_models(self, name_filter: Optional[str] = None) -> list:
        """
        List all registered models.

        Args:
            name_filter: Optional name filter

        Returns:
            List of registered model names
        """
        try:
            if name_filter:
                models = self.client.search_registered_models(f"name LIKE '%{name_filter}%'")
            else:
                models = self.client.search_registered_models()

            return [model.name for model in models]

        except Exception as e:
            logger.error(f"Error listing models: {str(e)}")
            return []

    def promote_model(
        self,
        model_name: str,
        version: int,
        target_stage: str = "Production"
    ) -> bool:
        """
        Promote model version to target stage.

        Args:
            model_name: Registered model name
            version: Version to promote
            target_stage: Target stage (Production, Staging)

        Returns:
            True if promotion successful
        """
        try:
            # Transition to new stage
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage=target_stage,
                archive_existing_versions=True
            )

            logger.info(f"Promoted {model_name} v{version} to {target_stage}")

            # Clear cache for this model
            self._clear_cache(model_name)

            return True

        except Exception as e:
            logger.error(f"Error promoting model: {str(e)}")
            return False

    def archive_model(self, model_name: str, version: int) -> bool:
        """
        Archive model version.

        Args:
            model_name: Registered model name
            version: Version to archive

        Returns:
            True if archival successful
        """
        try:
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage="Archived"
            )

            logger.info(f"Archived {model_name} v{version}")

            return True

        except Exception as e:
            logger.error(f"Error archiving model: {str(e)}")
            return False

    def _clear_cache(self, model_name: str) -> None:
        """Clear cache for specific model."""
        keys_to_remove = [key for key in self.model_cache.keys() if key.startswith(model_name)]
        for key in keys_to_remove:
            del self.model_cache[key]
        logger.info(f"Cleared cache for {model_name}")

    def warm_up_models(self, model_names: list) -> Dict[str, bool]:
        """
        Pre-load models into memory cache.

        Args:
            model_names: List of model names to warm up

        Returns:
            Dictionary mapping model names to success status
        """
        logger.info(f"Warming up {len(model_names)} models...")

        results = {}
        for model_name in model_names:
            try:
                self.load_model(model_name, stage="Production", force_reload=True)
                results[model_name] = True
                logger.info(f"✓ Warmed up {model_name}")
            except Exception as e:
                logger.error(f"✗ Failed to warm up {model_name}: {str(e)}")
                results[model_name] = False

        return results

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of model registry and cached models.

        Returns:
            Health check results
        """
        health = {
            'mlflow_accessible': False,
            'cached_models': len(self.model_cache),
            'model_details': []
        }

        # Check MLflow accessibility
        try:
            self.client.search_registered_models(max_results=1)
            health['mlflow_accessible'] = True
        except Exception as e:
            logger.error(f"MLflow health check failed: {str(e)}")

        # Check cached models
        for cache_key, (model, cached_at) in self.model_cache.items():
            age = datetime.now() - cached_at
            health['model_details'].append({
                'key': cache_key,
                'cached_at': cached_at.isoformat(),
                'age_seconds': age.total_seconds(),
                'expired': age > self.cache_ttl
            })

        return health


class ModelLoader:
    """
    Simplified model loader with fallback strategies.

    Convenience wrapper around MLflowRegistry for common use cases.
    """

    def __init__(
        self,
        registry: MLflowRegistry,
        fallback_dir: Optional[str] = None
    ):
        """
        Initialize model loader.

        Args:
            registry: MLflow registry instance
            fallback_dir: Directory with fallback models
        """
        self.registry = registry
        self.fallback_dir = Path(fallback_dir) if fallback_dir else None

    def load_production_models(self) -> Dict[str, Any]:
        """
        Load all production models required for hybrid pipeline.

        Returns:
            Dictionary with loaded models
        """
        logger.info("Loading production models...")

        models = {}

        # Load K-Means segmenter
        try:
            models['segmenter'] = self.registry.load_model("kmeans_segmentation", stage="Production")
        except Exception as e:
            logger.error(f"Failed to load segmenter: {str(e)}")
            models['segmenter'] = self._load_fallback("segmenter")

        # Load LightFM CF model
        try:
            models['cf_model'] = self.registry.load_model("lightfm_collaborative", stage="Production")
        except Exception as e:
            logger.error(f"Failed to load CF model: {str(e)}")
            models['cf_model'] = self._load_fallback("cf_model")

        # Load XGBoost ranker
        try:
            models['ranker'] = self.registry.load_model("xgboost_ranker", stage="Production")
        except Exception as e:
            logger.error(f"Failed to load ranker: {str(e)}")
            models['ranker'] = self._load_fallback("ranker")

        logger.info(f"Loaded {len([m for m in models.values() if m is not None])} models")

        return models

    def _load_fallback(self, model_type: str) -> Optional[Any]:
        """Load fallback model from local directory."""
        if not self.fallback_dir or not self.fallback_dir.exists():
            logger.warning(f"No fallback available for {model_type}")
            return None

        fallback_path = self.fallback_dir / f"{model_type}.pkl"
        if not fallback_path.exists():
            logger.warning(f"Fallback not found: {fallback_path}")
            return None

        try:
            model = joblib.load(fallback_path)
            logger.info(f"Loaded fallback model for {model_type}")
            return model
        except Exception as e:
            logger.error(f"Failed to load fallback for {model_type}: {str(e)}")
            return None
