"""
Experiment Management Service
==============================

Higher-level experiment management including configuration,
activation/deactivation, and experiment lifecycle management.

Features:
- Experiment CRUD operations
- Gradual rollout support
- Experiment scheduling
- Safety checks and validation
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ab_testing_service import ABTestingService, ExperimentConfig
from app.core.logging import get_logger

logger = get_logger(__name__)


class GradualRollout(BaseModel):
    """Gradual rollout configuration."""
    start_percentage: float = 0.0
    end_percentage: float = 100.0
    duration_days: int = 7
    increment_percentage: float = 10.0

    @validator('start_percentage', 'end_percentage', 'increment_percentage')
    def validate_percentage(cls, v):
        if not 0 <= v <= 100:
            raise ValueError("Percentage must be between 0 and 100")
        return v


class ExperimentCreate(BaseModel):
    """Create new experiment request."""
    name: str
    variants: List[str]
    traffic_split: List[float]
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    gradual_rollout: Optional[GradualRollout] = None

    @validator('variants')
    def validate_variants(cls, v):
        if len(v) < 2:
            raise ValueError("Experiment must have at least 2 variants")
        if len(set(v)) != len(v):
            raise ValueError("Variant names must be unique")
        return v

    @validator('traffic_split')
    def validate_traffic_split(cls, v, values):
        if 'variants' in values:
            if len(v) != len(values['variants']):
                raise ValueError("Traffic split must match number of variants")

        total = sum(v)
        if not 0.99 <= total <= 1.01:  # Allow small floating point error
            raise ValueError(f"Traffic split must sum to 1.0 (got {total})")

        return v


class ExperimentService:
    """
    Experiment management service.

    Handles experiment lifecycle, validation, and coordination with A/B testing.
    """

    def __init__(self):
        self.ab_service = ABTestingService()

    async def create_experiment(
        self,
        experiment: ExperimentCreate
    ) -> ExperimentConfig:
        """
        Create new experiment with validation.

        Args:
            experiment: Experiment configuration

        Returns:
            Created experiment config

        Raises:
            ValueError: If validation fails
        """
        # Validate no overlapping experiments
        existing = self.ab_service.get_experiment_config(experiment.name)
        if existing and existing.is_active:
            raise ValueError(f"Active experiment '{experiment.name}' already exists")

        # Set start date if not provided
        start_date = experiment.start_date or datetime.now()

        config = ExperimentConfig(
            name=experiment.name,
            variants=experiment.variants,
            traffic_split=experiment.traffic_split,
            start_date=start_date,
            end_date=experiment.end_date,
            is_active=True,
            description=experiment.description
        )

        # Register with A/B service
        self.ab_service.update_experiment(experiment.name, config)

        logger.info(f"Created experiment '{experiment.name}' with {len(experiment.variants)} variants")

        return config

    async def activate_experiment(self, experiment_name: str):
        """Activate experiment."""
        config = self.ab_service.get_experiment_config(experiment_name)
        if not config:
            raise ValueError(f"Experiment '{experiment_name}' not found")

        config.is_active = True
        self.ab_service.update_experiment(experiment_name, config)

        logger.info(f"Activated experiment '{experiment_name}'")

    async def deactivate_experiment(self, experiment_name: str):
        """Deactivate experiment."""
        config = self.ab_service.get_experiment_config(experiment_name)
        if not config:
            raise ValueError(f"Experiment '{experiment_name}' not found")

        config.is_active = False
        self.ab_service.update_experiment(experiment_name, config)

        logger.info(f"Deactivated experiment '{experiment_name}'")

    async def update_traffic_split(
        self,
        experiment_name: str,
        new_split: List[float]
    ):
        """
        Update traffic split for experiment (useful for gradual rollout).

        Args:
            experiment_name: Experiment name
            new_split: New traffic split percentages

        Raises:
            ValueError: If validation fails
        """
        config = self.ab_service.get_experiment_config(experiment_name)
        if not config:
            raise ValueError(f"Experiment '{experiment_name}' not found")

        if len(new_split) != len(config.variants):
            raise ValueError("New split must match number of variants")

        total = sum(new_split)
        if not 0.99 <= total <= 1.01:
            raise ValueError(f"Traffic split must sum to 1.0 (got {total})")

        config.traffic_split = new_split
        self.ab_service.update_experiment(experiment_name, config)

        logger.info(f"Updated traffic split for '{experiment_name}': {new_split}")

    async def gradual_rollout_step(
        self,
        experiment_name: str,
        rollout_config: GradualRollout
    ):
        """
        Perform one step of gradual rollout.

        Gradually increases traffic to variant_b while decreasing control.

        Args:
            experiment_name: Experiment name
            rollout_config: Rollout configuration
        """
        config = self.ab_service.get_experiment_config(experiment_name)
        if not config:
            raise ValueError(f"Experiment '{experiment_name}' not found")

        if len(config.variants) != 2:
            raise ValueError("Gradual rollout only supports 2-variant experiments")

        # Calculate current split
        current_control = config.traffic_split[0]
        current_variant = config.traffic_split[1]

        # Calculate new split
        new_variant = min(
            current_variant + rollout_config.increment_percentage / 100,
            rollout_config.end_percentage / 100
        )
        new_control = 1.0 - new_variant

        # Update
        await self.update_traffic_split(
            experiment_name,
            [new_control, new_variant]
        )

        logger.info(
            f"Gradual rollout step for '{experiment_name}': "
            f"{current_control*100:.1f}/{current_variant*100:.1f} → "
            f"{new_control*100:.1f}/{new_variant*100:.1f}"
        )

        # Check if rollout complete
        if new_variant >= rollout_config.end_percentage / 100:
            logger.info(f"Gradual rollout complete for '{experiment_name}'")
            return True

        return False

    async def check_experiment_health(
        self,
        db: AsyncSession,
        experiment_name: str
    ) -> Dict:
        """
        Check experiment health and raise alerts if needed.

        Args:
            db: Database session
            experiment_name: Experiment name

        Returns:
            Health check results
        """
        config = self.ab_service.get_experiment_config(experiment_name)
        if not config:
            raise ValueError(f"Experiment '{experiment_name}' not found")

        # Get recent metrics
        metrics = await self.ab_service.get_experiment_metrics(
            db, experiment_name, hours=1
        )

        health = {
            "experiment": experiment_name,
            "is_active": config.is_active,
            "issues": [],
            "warnings": []
        }

        # Check minimum sample size
        for variant, variant_metrics in metrics.items():
            impressions = variant_metrics.get('impressions', 0)

            if impressions < 100:
                health["warnings"].append(
                    f"Low sample size for {variant}: {impressions} impressions"
                )

        # Check for anomalies
        all_ctrs = [m.get('ctr', 0) for m in metrics.values()]
        if all_ctrs:
            avg_ctr = sum(all_ctrs) / len(all_ctrs)

            for variant, variant_metrics in metrics.items():
                ctr = variant_metrics.get('ctr', 0)

                # Check if variant CTR is unusually low
                if ctr < avg_ctr * 0.5:
                    health["issues"].append(
                        f"Variant {variant} CTR ({ctr:.2%}) is 50% below average"
                    )

                # Check if variant CTR is 0
                if ctr == 0 and variant_metrics.get('impressions', 0) > 100:
                    health["issues"].append(
                        f"Variant {variant} has 0% CTR with {variant_metrics['impressions']} impressions"
                    )

        health["status"] = "healthy" if not health["issues"] else "unhealthy"

        logger.info(f"Health check for '{experiment_name}': {health['status']}")

        return health

    async def get_winner(
        self,
        db: AsyncSession,
        experiment_name: str,
        min_p_value: float = 0.05,
        min_lift: float = 0.02  # 2% minimum lift
    ) -> Optional[str]:
        """
        Determine winning variant based on statistical significance.

        Args:
            db: Database session
            experiment_name: Experiment name
            min_p_value: Maximum p-value for significance
            min_lift: Minimum relative lift required

        Returns:
            Winning variant name or None if no clear winner
        """
        config = self.ab_service.get_experiment_config(experiment_name)
        if not config or len(config.variants) < 2:
            return None

        control = config.variants[0]

        # Test each variant against control
        best_variant = None
        best_lift = 0.0

        for variant in config.variants[1:]:
            try:
                # Test on CTR (primary metric)
                result = await self.ab_service.calculate_statistical_significance(
                    db, experiment_name, control, variant, metric="ctr", hours=168  # 7 days
                )

                # Check if significant improvement
                if result.is_significant and result.relative_lift > min_lift * 100:
                    if result.relative_lift > best_lift:
                        best_variant = variant
                        best_lift = result.relative_lift

            except Exception as e:
                logger.error(f"Error testing variant {variant}: {e}")

        if best_variant:
            logger.info(
                f"Winner for '{experiment_name}': {best_variant} "
                f"with {best_lift:.2f}% lift over {control}"
            )
        else:
            logger.info(f"No clear winner for '{experiment_name}'")

        return best_variant
