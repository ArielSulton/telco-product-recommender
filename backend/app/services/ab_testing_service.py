"""
A/B Testing Service
===================

Deterministic variant assignment and experiment management for
recommendation system A/B testing.

Features:
- Consistent user→variant mapping (hash-based)
- Configurable traffic splits
- Multi-variant experiments
- Statistical significance testing
- Experiment configuration management
"""

import hashlib
from typing import Dict, List, Optional
from datetime import datetime
import numpy as np
from scipy import stats
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.database import Event
from app.core.logging import get_logger

logger = get_logger(__name__)


class ExperimentConfig(BaseModel):
    """Experiment configuration."""
    name: str
    variants: List[str]
    traffic_split: List[float]
    start_date: datetime
    end_date: Optional[datetime] = None
    is_active: bool = True
    description: Optional[str] = None


class ABTestResult(BaseModel):
    """A/B test statistical results."""
    variant_a: str
    variant_b: str
    metric: str
    value_a: float
    value_b: float
    difference: float
    relative_lift: float
    p_value: float
    is_significant: bool
    confidence_level: float = 0.95


class ABTestingService:
    """
    A/B Testing Service for recommendation variants.

    Manages experiment configuration, user assignment, and statistical analysis.
    """

    def __init__(self):
        self.experiments: Dict[str, ExperimentConfig] = self._load_default_experiments()

    def _load_default_experiments(self) -> Dict[str, ExperimentConfig]:
        """Load default experiment configurations."""
        return {
            "recommendation_ui": ExperimentConfig(
                name="recommendation_ui",
                variants=["control", "variant_a"],
                traffic_split=[0.5, 0.5],  # 50-50 split
                start_date=datetime.now(),
                description="Test new recommendation card UI design"
            ),
            "ranking_algorithm": ExperimentConfig(
                name="ranking_algorithm",
                variants=["xgboost_v1", "xgboost_v2"],
                traffic_split=[0.7, 0.3],  # 70-30 split
                start_date=datetime.now(),
                description="Test improved XGBoost ranker model"
            ),
            "diversity_lambda": ExperimentConfig(
                name="diversity_lambda",
                variants=["lambda_0.5", "lambda_0.7", "lambda_0.9"],
                traffic_split=[0.33, 0.34, 0.33],  # 3-way split
                start_date=datetime.now(),
                description="Optimize MMR diversity parameter"
            )
        }

    def assign_variant(
        self,
        user_id: str,
        experiment: str = "recommendation_ui"
    ) -> str:
        """
        Assign user to experiment variant using deterministic hashing.

        Args:
            user_id: User identifier
            experiment: Experiment name

        Returns:
            Variant name (e.g., "control", "variant_a")

        Example:
            >>> service = ABTestingService()
            >>> variant = service.assign_variant("user-123")
            >>> print(variant)  # "control" or "variant_a"
        """
        if experiment not in self.experiments:
            logger.warning(f"Experiment '{experiment}' not found, using control")
            return "control"

        config = self.experiments[experiment]

        if not config.is_active:
            logger.info(f"Experiment '{experiment}' is inactive, returning control")
            return config.variants[0]  # Return first variant (control)

        # Hash user_id to get consistent assignment
        hash_value = int(hashlib.md5(f"{user_id}:{experiment}".encode()).hexdigest(), 16)
        bucket = hash_value % 100  # 0-99

        # Assign based on traffic split
        cumulative = 0
        for variant, split in zip(config.variants, config.traffic_split):
            cumulative += split * 100
            if bucket < cumulative:
                logger.debug(f"User {user_id} assigned to {variant} (bucket={bucket})")
                return variant

        # Fallback to first variant
        return config.variants[0]

    def get_experiment_config(self, experiment: str) -> Optional[ExperimentConfig]:
        """Get experiment configuration."""
        return self.experiments.get(experiment)

    def update_experiment(self, experiment: str, config: ExperimentConfig):
        """Update experiment configuration."""
        self.experiments[experiment] = config
        logger.info(f"Updated experiment '{experiment}'")

    async def get_experiment_metrics(
        self,
        db: AsyncSession,
        experiment: str = "recommendation_ui",
        hours: int = 24
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate key metrics for each variant.

        Args:
            db: Database session
            experiment: Experiment name
            hours: Time window in hours

        Returns:
            Dict mapping variant to metrics (impressions, clicks, conversions, CTR, CVR)
        """
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Query events by variant
        result = await db.execute(
            select(
                Event.ab_variant,
                Event.event_type,
                func.count(Event.event_id).label('count')
            )
            .where(Event.timestamp >= cutoff_time)
            .where(Event.ab_variant.isnot(None))
            .group_by(Event.ab_variant, Event.event_type)
        )

        # Aggregate metrics
        variant_metrics = {}

        for row in result:
            variant = row.ab_variant
            event_type = row.event_type
            count = row.count

            if variant not in variant_metrics:
                variant_metrics[variant] = {
                    'impressions': 0,
                    'clicks': 0,
                    'conversions': 0
                }

            if event_type == 'view':
                variant_metrics[variant]['impressions'] += count
            elif event_type == 'click':
                variant_metrics[variant]['clicks'] += count
            elif event_type == 'subscribe':
                variant_metrics[variant]['conversions'] += count

        # Calculate rates
        for variant, metrics in variant_metrics.items():
            impressions = metrics['impressions']
            if impressions > 0:
                metrics['ctr'] = metrics['clicks'] / impressions
                metrics['cvr'] = metrics['conversions'] / impressions
            else:
                metrics['ctr'] = 0.0
                metrics['cvr'] = 0.0

        logger.info(f"Experiment '{experiment}' metrics: {variant_metrics}")

        return variant_metrics

    async def calculate_statistical_significance(
        self,
        db: AsyncSession,
        experiment: str,
        variant_a: str,
        variant_b: str,
        metric: str = "ctr",
        hours: int = 24
    ) -> ABTestResult:
        """
        Calculate statistical significance between two variants.

        Uses Chi-square test for CTR and t-test for continuous metrics.

        Args:
            db: Database session
            experiment: Experiment name
            variant_a: First variant (usually control)
            variant_b: Second variant (test variant)
            metric: Metric to compare (ctr, cvr)
            hours: Time window

        Returns:
            ABTestResult with statistical analysis
        """
        metrics = await self.get_experiment_metrics(db, experiment, hours)

        if variant_a not in metrics or variant_b not in metrics:
            raise ValueError(f"Variants not found in experiment data")

        metrics_a = metrics[variant_a]
        metrics_b = metrics[variant_b]

        # Extract metric values
        if metric == "ctr":
            # Chi-square test for proportions
            impressions_a = metrics_a['impressions']
            clicks_a = metrics_a['clicks']
            impressions_b = metrics_b['impressions']
            clicks_b = metrics_b['clicks']

            # Contingency table
            obs = np.array([
                [clicks_a, impressions_a - clicks_a],
                [clicks_b, impressions_b - clicks_b]
            ])

            chi2, p_value, dof, expected = stats.chi2_contingency(obs)

            value_a = metrics_a['ctr']
            value_b = metrics_b['ctr']

        elif metric == "cvr":
            # Chi-square test for conversions
            impressions_a = metrics_a['impressions']
            conversions_a = metrics_a['conversions']
            impressions_b = metrics_b['impressions']
            conversions_b = metrics_b['conversions']

            obs = np.array([
                [conversions_a, impressions_a - conversions_a],
                [conversions_b, impressions_b - conversions_b]
            ])

            chi2, p_value, dof, expected = stats.chi2_contingency(obs)

            value_a = metrics_a['cvr']
            value_b = metrics_b['cvr']

        else:
            raise ValueError(f"Unsupported metric: {metric}")

        # Calculate difference and lift
        difference = value_b - value_a
        relative_lift = (difference / value_a * 100) if value_a > 0 else 0

        # Determine significance (p < 0.05)
        is_significant = p_value < 0.05

        result = ABTestResult(
            variant_a=variant_a,
            variant_b=variant_b,
            metric=metric,
            value_a=value_a,
            value_b=value_b,
            difference=difference,
            relative_lift=relative_lift,
            p_value=p_value,
            is_significant=is_significant,
            confidence_level=0.95
        )

        logger.info(f"Statistical test: {variant_a} vs {variant_b}")
        logger.info(f"  {metric.upper()}: {value_a:.4f} vs {value_b:.4f}")
        logger.info(f"  Lift: {relative_lift:+.2f}%")
        logger.info(f"  P-value: {p_value:.4f} ({'SIGNIFICANT' if is_significant else 'not significant'})")

        return result

    async def get_experiment_summary(
        self,
        db: AsyncSession,
        experiment: str = "recommendation_ui",
        hours: int = 24
    ) -> Dict:
        """
        Get comprehensive experiment summary with all variants and statistical tests.

        Args:
            db: Database session
            experiment: Experiment name
            hours: Time window

        Returns:
            Summary dict with metrics and significance tests
        """
        config = self.get_experiment_config(experiment)
        if not config:
            raise ValueError(f"Experiment '{experiment}' not found")

        # Get metrics for all variants
        metrics = await self.get_experiment_metrics(db, experiment, hours)

        # Run pairwise significance tests
        significance_tests = []

        if len(config.variants) >= 2:
            # Compare all variants against control (first variant)
            control = config.variants[0]

            for variant in config.variants[1:]:
                try:
                    # Test CTR
                    ctr_test = await self.calculate_statistical_significance(
                        db, experiment, control, variant, metric="ctr", hours=hours
                    )
                    significance_tests.append({
                        "comparison": f"{control} vs {variant}",
                        "metric": "CTR",
                        "result": ctr_test.dict()
                    })

                    # Test CVR
                    cvr_test = await self.calculate_statistical_significance(
                        db, experiment, control, variant, metric="cvr", hours=hours
                    )
                    significance_tests.append({
                        "comparison": f"{control} vs {variant}",
                        "metric": "CVR",
                        "result": cvr_test.dict()
                    })

                except Exception as e:
                    logger.error(f"Error calculating significance: {e}")

        summary = {
            "experiment": experiment,
            "config": config.dict(),
            "time_window_hours": hours,
            "metrics": metrics,
            "significance_tests": significance_tests,
            "generated_at": datetime.now().isoformat()
        }

        return summary
