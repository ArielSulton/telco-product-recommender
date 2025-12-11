"""
Random Forest Recommender Service (v2.0)

Production implementation of improved_rf_topk model.
Replaces legacy 3-stage hybrid recommender.

Performance:
- Accuracy: 97.53%
- Hit Rate@3: 87.24%
- Inference time: <50ms (with cache)
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.database import Product
from app.ml.rf_model import RFRecommender  # Import for unpickling

logger = logging.getLogger(__name__)


class RFRecommenderService:
    """
    Random Forest-based recommendation service.

    Features:
    - Content-based recommendations using user features
    - Top-K recommendations with confidence scores
    - Temperature-scaled probabilities
    - Fast inference (<50ms)
    - No cold start problem
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize RF recommender.

        Args:
            model_path: Path to rf_recommender.pkl. If None, uses default.
        """
        if model_path is None:
            model_path = Path(__file__).parent / "models" / "rf_v2" / "rf_recommender.pkl"
        else:
            model_path = Path(model_path)

        self.model_path = model_path
        self.model = None
        self.metadata = None
        self._load_model()

    def _load_model(self):
        """Load model from disk."""
        try:
            logger.info(f"Loading RF model from: {self.model_path}")
            self.model = joblib.load(self.model_path)

            # Load metadata
            metadata_path = self.model_path.parent / "metadata.json"
            if metadata_path.exists():
                import json
                with open(metadata_path) as f:
                    self.metadata = json.load(f)

            logger.info(f"✅ RF model loaded successfully (v{self.metadata.get('version', 'unknown')})")

        except FileNotFoundError:
            logger.error(f"Model not found at {self.model_path}")
            logger.error("Please run ml/scripts/export_rf_model.py first!")
            raise
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    async def get_recommendations(
        self,
        user_id: int,
        user_features: Dict[str, Any],
        db: AsyncSession,
        k: int = 5,
        min_confidence: float = 0.05,
        include_explanations: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get personalized recommendations for a user.

        Args:
            user_id: User ID
            user_features: Dict with user features (from DB/cache)
            db: Database session for product lookup
            k: Number of recommendations
            min_confidence: Minimum confidence threshold
            include_explanations: Whether to include feature importance

        Returns:
            List of recommendation dicts with FULL product details:
                - product_id: Product ID
                - product_name: Product name
                - price: Product price
                - quota_data_mb: Data quota
                - validity_days: Validity period
                - confidence: Confidence score (0-1)
                - rank: Recommendation rank (1-k)
                - explanation: Feature importance (if enabled)
        """
        start_time = datetime.now()

        try:
            # Validate user features
            required_features = [
                'plan_type', 'device_brand', 'avg_data_usage_gb',
                'pct_video_usage', 'avg_call_duration', 'sms_freq',
                'monthly_spend', 'topup_freq', 'travel_score', 'complaint_count'
            ]

            missing = [f for f in required_features if f not in user_features]
            if missing:
                raise ValueError(f"Missing required features: {missing}")

            # Get recommendations from model
            recommendations = self.model.predict_topk(
                user_features=user_features,
                k=k,
                min_confidence=min_confidence
            )

            # Enrich with product details from database
            enriched_recommendations = await self._enrich_with_products(
                db, recommendations
            )

            # Add explanations if requested
            if include_explanations:
                enriched_recommendations = self._add_explanations(
                    enriched_recommendations, user_features
                )

            # Calculate inference time
            inference_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                f"Generated {len(enriched_recommendations)} recommendations for user {user_id} "
                f"in {inference_time:.1f}ms"
            )

            # Add metadata
            for rec in enriched_recommendations:
                rec['user_id'] = user_id
                rec['model_version'] = self.metadata.get('version', '2.0.0')
                rec['inference_time_ms'] = inference_time
                rec['created_at'] = datetime.now().isoformat()

            return enriched_recommendations

        except Exception as e:
            logger.error(f"Recommendation failed for user {user_id}: {e}")
            raise

    async def _enrich_with_products(
        self,
        db: AsyncSession,
        recommendations: List[Dict]
    ) -> List[Dict]:
        """
        Enrich recommendations with full product details from database.

        Args:
            db: Database session
            recommendations: List of recommendations with product names

        Returns:
            List of recommendations with full product details
        """
        enriched = []

        # Mapping from RF Model Labels (Training Data) -> Database Product Families
        # RF Label -> DB 'product_family'
        FAMILY_MAPPING = {
            'Data Booster': 'data',
            'Streaming Partner Pack': 'data',
            'General Offer': 'combo',
            'Voice Bundle': 'voice',
            'Family Plan Offer': 'combo',
            'Device Upgrade Offer': 'data',  # or 'premium' if tag
            'Retention Offer': 'combo',
            'Roaming Pass': 'data',          # or specific 'roaming' family
            'Top-up Promo': 'data',
            'Starter Pack': 'data'
        }

        for rec in recommendations:
            # The RF model predicts product FAMILY (e.g., "Data Booster"), not specific product names
            model_output_name = rec.get('product')

            if not model_output_name:
                logger.warning(f"Recommendation missing product name: {rec}")
                continue

            # Map model label to DB family
            mapped_family = FAMILY_MAPPING.get(model_output_name, 'data') # Default to 'data'

            # 1. Try to find products by MAPPED FAMILY first (primary strategy)
            # Recommend the entry-level (cheapest) package in that family
            result = await db.execute(
                select(Product)
                .where(Product.product_family == mapped_family)
                .where(Product.is_active == True)
                .order_by(Product.price.asc())
                .limit(1)
            )
            product = result.scalar_one_or_none()

            # 2. Fallback: Try to find by exact PRODUCT NAME (if model predicted a real name)
            if not product:
                result = await db.execute(
                    select(Product)
                    .where(Product.product_name == model_output_name)
                    .where(Product.is_active == True)
                )
                product = result.scalar_one_or_none()

            if not product:
                logger.warning(f"Product family '{model_output_name}' (mapped to '{mapped_family}') not found in database.")
                # Skip this recommendation if product not found
                continue

            # Create enriched recommendation with full product details
            enriched_rec = {
                # Full product details (backward compatible with frontend)
                'product_id': product.product_id,
                'product_name': product.product_name,
                'price': float(product.price),
                'quota_data_mb': product.quota_data_mb,
                'validity_days': product.validity_days,
                'family': product.product_family,
                'description': None,
                # RF model metadata
                'confidence': rec.get('confidence'),
                'rank': rec.get('rank'),
            }

            # Preserve explanation if exists
            if 'explanation' in rec:
                enriched_rec['explanation'] = rec['explanation']

            enriched.append(enriched_rec)

        return enriched

    def _add_explanations(
        self,
        recommendations: List[Dict],
        user_features: Dict[str, Any]
    ) -> List[Dict]:
        """
        Add feature importance explanations to recommendations.

        Uses feature importance from Random Forest to explain
        why each product was recommended.
        """
        try:
            # Get feature importances from model
            feature_importance = self.model.model.feature_importances_
            feature_names = self.model.feature_cols

            # Get top-3 most important features
            top_k_features = 3
            top_indices = np.argsort(feature_importance)[-top_k_features:][::-1]
            top_features = [
                {
                    'feature': feature_names[idx],
                    'importance': float(feature_importance[idx]),
                    'value': user_features.get(feature_names[idx], 'N/A')
                }
                for idx in top_indices
            ]

            # Add to each recommendation
            for rec in recommendations:
                rec['explanation'] = {
                    'top_features': top_features,
                    'explanation_text': self._generate_explanation_text(
                        rec['product'], top_features
                    )
                }

            return recommendations

        except Exception as e:
            logger.warning(f"Failed to generate explanations: {e}")
            # Return recommendations without explanations
            return recommendations

    def _generate_explanation_text(
        self,
        product: str,
        top_features: List[Dict]
    ) -> str:
        """Generate human-readable explanation text."""
        feature_texts = []

        for feat in top_features:
            name = feat['feature']
            value = feat['value']
            importance = feat['importance']

            # Map feature names to human-readable text
            feature_map = {
                'monthly_spend': f"your monthly spending of Rp {value:,.0f}",
                'avg_data_usage_gb': f"your data usage of {value:.1f} GB",
                'plan_type': f"your {value} plan",
                'device_brand': f"your {value} device",
                'topup_freq': f"your top-up frequency of {value} times/month",
                'arpu': f"your average spending pattern",
                'churn_score': "your usage behavior",
                'loyalty_score': "your customer loyalty",
            }

            text = feature_map.get(name, f"your {name}")
            feature_texts.append(text)

        if len(feature_texts) >= 2:
            explanation = (
                f"We recommend {product} based on "
                f"{feature_texts[0]}, {feature_texts[1]}"
            )
        elif len(feature_texts) == 1:
            explanation = f"We recommend {product} based on {feature_texts[0]}"
        else:
            explanation = f"We recommend {product} based on your usage profile"

        return explanation

    async def bulk_recommend(
        self,
        users: List[Dict[str, Any]],
        db: AsyncSession,
        k: int = 5,
        min_confidence: float = 0.05
    ) -> Dict[int, List[Dict]]:
        """
        Generate recommendations for multiple users (batch inference).

        Args:
            users: List of dicts with 'user_id' and user features
            db: Database session for product lookup
            k: Number of recommendations per user
            min_confidence: Minimum confidence threshold

        Returns:
            Dict mapping user_id to list of recommendations
        """
        results = {}

        for user in users:
            user_id = user['user_id']
            try:
                recommendations = await self.get_recommendations(
                    user_id=user_id,
                    user_features=user,
                    db=db,
                    k=k,
                    min_confidence=min_confidence,
                    include_explanations=False  # Skip for bulk
                )
                results[user_id] = recommendations
            except Exception as e:
                logger.error(f"Bulk recommendation failed for user {user_id}: {e}")
                results[user_id] = []

        return results

    def get_model_info(self) -> Dict[str, Any]:
        """Get model metadata and performance info."""
        return {
            'model_type': 'RandomForestRecommender',
            'version': self.metadata.get('version', '2.0.0'),
            'created_at': self.metadata.get('created_at'),
            'n_features': self.metadata.get('n_features'),
            'n_classes': self.metadata.get('n_classes'),
            'temperature': self.metadata.get('temperature'),
            'model_path': str(self.model_path),
            'performance': {
                'accuracy': 0.9753,
                'precision_at_3': 0.2908,
                'hit_rate_at_3': 0.8724,
                'inference_time_ms': '<50ms (cached)'
            }
        }


# Singleton instance
_rf_recommender: Optional[RFRecommenderService] = None


def get_rf_recommender() -> RFRecommenderService:
    """Get singleton RF recommender instance."""
    global _rf_recommender
    if _rf_recommender is None:
        _rf_recommender = RFRecommenderService()
    return _rf_recommender


async def generate_rf_recommendations(
    user_id: int,
    user_features: Dict[str, Any],
    db: AsyncSession,
    k: int = 5,
    min_confidence: float = 0.05,
    include_explanations: bool = True
) -> List[Dict[str, Any]]:
    """
    Convenience function for generating RF recommendations.

    This is the main entry point for getting recommendations
    from the Random Forest model.

    Args:
        user_id: User ID
        user_features: User feature dict
        db: Database session for product lookup
        k: Number of recommendations
        min_confidence: Minimum confidence threshold
        include_explanations: Whether to include explanations

    Returns:
        List of enriched recommendations with full product details
    """
    recommender = get_rf_recommender()
    return await recommender.get_recommendations(
        user_id=user_id,
        user_features=user_features,
        db=db,
        k=k,
        min_confidence=min_confidence,
        include_explanations=include_explanations
    )
