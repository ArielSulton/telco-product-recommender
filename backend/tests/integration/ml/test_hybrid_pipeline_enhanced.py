"""
Integration tests for HybridPipeline with EnhancedBaseline.

Tests the complete recommendation pipeline:
K-Means Segmentation → EnhancedBaseline → XGBoost Ranking → MMR Diversification
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, AsyncMock, patch

from app.ml.pipeline.hybrid_pipeline import HybridPipeline, RecommendationResult
from app.ml.models.segmentation.kmeans_segmenter import KMeansSegmenter
from app.ml.models.baseline.enhanced_baseline import EnhancedBaseline
from app.ml.models.ranker.xgboost_ranker import XGBoostRanker


@pytest.fixture
def mock_segmenter():
    """Mock K-Means segmenter."""
    segmenter = Mock(spec=KMeansSegmenter)
    segmenter.is_trained = True
    segmenter.predict = Mock(return_value=np.array([0]))
    segmenter.interpret_segments = Mock(return_value={
        0: "High Value",
        1: "Standard"
    })
    return segmenter


@pytest.fixture
def mock_baseline():
    """Mock EnhancedBaseline."""
    baseline = Mock(spec=EnhancedBaseline)
    baseline.is_fitted = True

    # Define base recommendations
    segment_base = [('P1', 1.0), ('P2', 0.9), ('P3', 0.8)]
    affinity_base = [('P4', 0.85), ('P5', 0.75)]
    similarity_base = [('P6', 0.7), ('P7', 0.65)]

    # Mock segment recommendations with exclusion support
    def segment_recommend(segment, top_k, exclude_products=None):
        results = segment_base
        if exclude_products:
            results = [(pid, score) for pid, score in results if pid not in exclude_products]
        return results[:top_k]

    baseline.recommend_by_segment = Mock(side_effect=segment_recommend)

    # Mock affinity recommendations with exclusion support
    def affinity_recommend(user_features, product_catalog, top_k, exclude_products=None):
        results = affinity_base
        if exclude_products:
            results = [(pid, score) for pid, score in results if pid not in exclude_products]
        return results[:top_k]

    baseline.recommend_by_affinity = Mock(side_effect=affinity_recommend)

    # Mock similarity recommendations with exclusion support
    def similarity_recommend(user_features, product_catalog, top_k, exclude_products=None):
        results = similarity_base
        if exclude_products:
            results = [(pid, score) for pid, score in results if pid not in exclude_products]
        return results[:top_k]

    baseline.recommend_by_similarity = Mock(side_effect=similarity_recommend)

    return baseline


@pytest.fixture
def mock_ranker():
    """Mock XGBoost ranker."""
    ranker = Mock(spec=XGBoostRanker)
    ranker.is_trained = True
    ranker.feature_names = [
        'recency', 'frequency', 'monetary', 'arpu',
        'usage_7d_data_mb', 'churn_score', 'cf_score'
    ]
    # Return decreasing scores for ranking
    ranker.rank = Mock(return_value=np.array([0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65]))
    return ranker


@pytest.fixture
def sample_user_features():
    """Sample user features."""
    return pd.DataFrame([{
        'user_id': 'U1',
        'recency': 15,
        'frequency': 10,
        'monetary': 150000,
        'arpu': 150000,
        'churn_score': 0.3,
        'segment_id': 0,
        'usage_7d_data_mb': 40000
    }])


@pytest.fixture
def sample_product_catalog():
    """Sample product catalog."""
    return pd.DataFrame({
        'product_id': ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7'],
        'product_name': ['Basic', 'Premium', 'Data', 'Retention', 'Value', 'Family', 'Voice'],
        'product_family': ['Basic', 'Premium', 'Data', 'Retention', 'Value', 'Family', 'Voice'],
        'price': [50000, 200000, 100000, 150000, 75000, 120000, 60000],
        'quota_data_mb': [10000, 60000, 50000, 40000, 20000, 30000, 15000],
        'quota_voice_min': [100, 500, 200, 300, 150, 400, 600],
        'validity_days': [30, 30, 30, 30, 30, 30, 30]
    })


@pytest.fixture
def pipeline_with_mocks(mock_segmenter, mock_baseline, mock_ranker):
    """Hybrid pipeline with mocked components."""
    pipeline = HybridPipeline(
        segmenter=mock_segmenter,
        ranker=mock_ranker,
        baseline=mock_baseline,
        diversifier=None,  # Test without diversifier
        cache_client=None
    )

    # Initialize pipeline
    success = pipeline.initialize()
    assert success

    return pipeline


class TestPipelineInitialization:
    """Test pipeline initialization."""

    def test_init_success(self, mock_segmenter, mock_ranker, mock_baseline):
        """Test successful initialization."""
        pipeline = HybridPipeline(
            segmenter=mock_segmenter,
            ranker=mock_ranker,
            baseline=mock_baseline
        )

        assert pipeline.segmenter == mock_segmenter
        assert pipeline.ranker == mock_ranker
        assert pipeline.baseline == mock_baseline
        assert not pipeline.is_ready

    def test_initialize_success(self, mock_segmenter, mock_ranker, mock_baseline):
        """Test successful initialization validation."""
        pipeline = HybridPipeline(
            segmenter=mock_segmenter,
            ranker=mock_ranker,
            baseline=mock_baseline
        )

        success = pipeline.initialize()
        assert success
        assert pipeline.is_ready

    def test_initialize_fail_no_segmenter(self, mock_ranker, mock_baseline):
        """Test initialization fails without segmenter."""
        pipeline = HybridPipeline(
            segmenter=None,
            ranker=mock_ranker,
            baseline=mock_baseline
        )

        success = pipeline.initialize()
        assert not success
        assert not pipeline.is_ready

    def test_initialize_fail_no_ranker(self, mock_segmenter, mock_baseline):
        """Test initialization fails without ranker."""
        pipeline = HybridPipeline(
            segmenter=mock_segmenter,
            ranker=None,
            baseline=mock_baseline
        )

        success = pipeline.initialize()
        assert not success

    def test_initialize_fail_no_baseline(self, mock_segmenter, mock_ranker):
        """Test initialization fails without baseline."""
        pipeline = HybridPipeline(
            segmenter=mock_segmenter,
            ranker=mock_ranker,
            baseline=None
        )

        success = pipeline.initialize()
        assert not success


class TestCandidateGeneration:
    """Test candidate generation with EnhancedBaseline."""

    @pytest.mark.asyncio
    async def test_generate_candidates_success(
        self,
        pipeline_with_mocks,
        sample_user_features,
        sample_product_catalog
    ):
        """Test successful candidate generation."""
        candidates = await pipeline_with_mocks._generate_candidates(
            user_id='U1',
            segment_id=0,
            user_features=sample_user_features,
            product_catalog=sample_product_catalog,
            pool_size=10
        )

        assert len(candidates) > 0
        assert all(isinstance(c, tuple) and len(c) == 2 for c in candidates)
        # All strategies should have been called
        pipeline_with_mocks.baseline.recommend_by_segment.assert_called_once()
        pipeline_with_mocks.baseline.recommend_by_affinity.assert_called_once()
        pipeline_with_mocks.baseline.recommend_by_similarity.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_candidates_with_exclusions(
        self,
        pipeline_with_mocks,
        sample_user_features,
        sample_product_catalog
    ):
        """Test candidate generation with excluded products."""
        candidates = await pipeline_with_mocks._generate_candidates(
            user_id='U1',
            segment_id=0,
            user_features=sample_user_features,
            product_catalog=sample_product_catalog,
            pool_size=10,
            exclude_products=['P1', 'P2']
        )

        assert len(candidates) > 0
        # Exclusions should be passed to all strategies
        assert pipeline_with_mocks.baseline.recommend_by_segment.call_args[1]['exclude_products'] == ['P1', 'P2']
        assert pipeline_with_mocks.baseline.recommend_by_affinity.call_args[1]['exclude_products'] == ['P1', 'P2']

    @pytest.mark.asyncio
    async def test_generate_candidates_deduplication(
        self,
        pipeline_with_mocks,
        sample_user_features,
        sample_product_catalog
    ):
        """Test candidate deduplication across strategies."""
        # Mock strategies to return overlapping products
        pipeline_with_mocks.baseline.recommend_by_segment = Mock(
            side_effect=lambda segment, top_k, exclude_products=None: [('P1', 1.0), ('P2', 0.9)]
        )
        pipeline_with_mocks.baseline.recommend_by_affinity = Mock(
            side_effect=lambda user_features, product_catalog, top_k, exclude_products=None: [
                ('P2', 0.85),  # Duplicate
                ('P3', 0.8)
            ]
        )
        pipeline_with_mocks.baseline.recommend_by_similarity = Mock(
            side_effect=lambda user_features, product_catalog, top_k, exclude_products=None: [
                ('P1', 0.75),  # Duplicate
                ('P4', 0.7)
            ]
        )

        candidates = await pipeline_with_mocks._generate_candidates(
            user_id='U1',
            segment_id=0,
            user_features=sample_user_features,
            product_catalog=sample_product_catalog,
            pool_size=10
        )

        # Should have 4 unique products (P1, P2, P3, P4)
        product_ids = [c[0] for c in candidates]
        assert len(set(product_ids)) == len(product_ids)  # All unique

    @pytest.mark.asyncio
    async def test_generate_candidates_strategy_failure(
        self,
        pipeline_with_mocks,
        sample_user_features,
        sample_product_catalog
    ):
        """Test graceful handling when one strategy fails."""
        # Make affinity strategy fail
        pipeline_with_mocks.baseline.recommend_by_affinity = Mock(
            side_effect=Exception("Affinity failed")
        )

        candidates = await pipeline_with_mocks._generate_candidates(
            user_id='U1',
            segment_id=0,
            user_features=sample_user_features,
            product_catalog=sample_product_catalog,
            pool_size=10
        )

        # Should still get candidates from other strategies
        assert len(candidates) > 0


class TestEndToEndRecommendation:
    """Test complete end-to-end recommendation flow."""

    @pytest.mark.asyncio
    async def test_recommend_success(
        self,
        pipeline_with_mocks,
        sample_user_features,
        sample_product_catalog
    ):
        """Test successful end-to-end recommendation."""
        result = await pipeline_with_mocks.recommend(
            user_id='U1',
            user_features=sample_user_features,
            product_catalog=sample_product_catalog,
            top_k=5
        )

        assert isinstance(result, RecommendationResult)
        assert result.user_id == 'U1'
        assert result.segment_id == 0
        assert result.segment_name == "High Value"
        assert len(result.recommendations) <= 5
        assert result.latency_ms > 0
        assert result.model_version == "v1.0.0"

    @pytest.mark.asyncio
    async def test_recommend_with_exclusions(
        self,
        pipeline_with_mocks,
        sample_user_features,
        sample_product_catalog
    ):
        """Test recommendations with excluded products."""
        result = await pipeline_with_mocks.recommend(
            user_id='U1',
            user_features=sample_user_features,
            product_catalog=sample_product_catalog,
            top_k=5,
            exclude_products=['P1', 'P2']
        )

        recommended_ids = [r['product_id'] for r in result.recommendations]
        assert 'P1' not in recommended_ids
        assert 'P2' not in recommended_ids

    @pytest.mark.asyncio
    async def test_recommend_formats_correctly(
        self,
        pipeline_with_mocks,
        sample_user_features,
        sample_product_catalog
    ):
        """Test recommendation response format."""
        result = await pipeline_with_mocks.recommend(
            user_id='U1',
            user_features=sample_user_features,
            product_catalog=sample_product_catalog,
            top_k=3
        )

        # Check each recommendation has required fields
        for rec in result.recommendations:
            assert 'product_id' in rec
            assert 'product_name' in rec
            assert 'price' in rec
            assert 'score' in rec
            assert 'reason' in rec
            assert 'cta_url' in rec

    @pytest.mark.asyncio
    async def test_recommend_not_initialized(
        self,
        mock_segmenter,
        mock_ranker,
        mock_baseline,
        sample_user_features,
        sample_product_catalog
    ):
        """Test recommendation fails when pipeline not initialized."""
        pipeline = HybridPipeline(
            segmenter=mock_segmenter,
            ranker=mock_ranker,
            baseline=mock_baseline
        )
        # Don't call initialize()

        with pytest.raises(ValueError, match="Pipeline not initialized"):
            await pipeline.recommend(
                user_id='U1',
                user_features=sample_user_features,
                product_catalog=sample_product_catalog,
                top_k=5
            )


class TestPerformanceMetrics:
    """Test performance tracking."""

    @pytest.mark.asyncio
    async def test_latency_tracking(
        self,
        pipeline_with_mocks,
        sample_user_features,
        sample_product_catalog
    ):
        """Test latency is tracked correctly."""
        result = await pipeline_with_mocks.recommend(
            user_id='U1',
            user_features=sample_user_features,
            product_catalog=sample_product_catalog,
            top_k=5
        )

        assert result.latency_ms > 0
        assert len(pipeline_with_mocks.latency_history) == 1
        assert pipeline_with_mocks.latency_history[0] == result.latency_ms

    @pytest.mark.asyncio
    async def test_get_performance_metrics(
        self,
        pipeline_with_mocks,
        sample_user_features,
        sample_product_catalog
    ):
        """Test getting performance metrics."""
        # Generate a few recommendations
        for i in range(3):
            await pipeline_with_mocks.recommend(
                user_id=f'U{i}',
                user_features=sample_user_features,
                product_catalog=sample_product_catalog,
                top_k=5
            )

        metrics = pipeline_with_mocks.get_performance_metrics()

        assert 'latency_p50' in metrics
        assert 'latency_p95' in metrics
        assert 'latency_p99' in metrics
        assert 'latency_mean' in metrics
        assert 'total_requests' in metrics
        assert metrics['total_requests'] == 3


class TestCaching:
    """Test Redis caching behavior."""

    @pytest.mark.asyncio
    async def test_segment_caching(self, mock_segmenter, mock_ranker, mock_baseline):
        """Test user segment caching."""
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.setex = AsyncMock()

        pipeline = HybridPipeline(
            segmenter=mock_segmenter,
            ranker=mock_ranker,
            baseline=mock_baseline,
            cache_client=mock_cache
        )
        pipeline.initialize()

        user_features = pd.DataFrame([{
            'user_id': 'U1',
            'recency': 15,
            'frequency': 10,
            'monetary': 150000
        }])

        segment_id = await pipeline._get_user_segment('U1', user_features)

        # Should call cache
        mock_cache.get.assert_called_once()
        mock_cache.setex.assert_called_once()
        assert segment_id == 0

    @pytest.mark.asyncio
    async def test_candidate_caching(
        self,
        mock_segmenter,
        mock_baseline,
        mock_ranker,
        sample_user_features,
        sample_product_catalog
    ):
        """Test candidate caching."""
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.setex = AsyncMock()

        pipeline = HybridPipeline(
            segmenter=mock_segmenter,
            ranker=mock_ranker,
            baseline=mock_baseline,
            cache_client=mock_cache
        )
        pipeline.initialize()

        candidates = await pipeline._generate_candidates(
            user_id='U1',
            segment_id=0,
            user_features=sample_user_features,
            product_catalog=sample_product_catalog,
            pool_size=10
        )

        # Should cache candidates
        mock_cache.setex.assert_called_once()
        cache_key = mock_cache.setex.call_args[0][0]
        assert 'candidates:U1' in cache_key


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
