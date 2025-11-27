"""
Unit tests for EnhancedBaseline recommendation model.

Tests all three recommendation strategies:
1. Segment-based popularity
2. Rule-based affinity matching
3. Content-based similarity
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, MagicMock

from app.ml.models.baseline.enhanced_baseline import EnhancedBaseline
from app.ml.models.baseline.top_popular import TopPopularBaseline


@pytest.fixture
def sample_transactions():
    """Sample transaction data for testing."""
    return pd.DataFrame({
        'user_id': ['U1', 'U2', 'U3', 'U1', 'U2'] * 20,
        'product_id': ['P1', 'P2', 'P3', 'P1', 'P2'] * 20,
        'transaction_date': pd.date_range('2024-01-01', periods=100)
    })


@pytest.fixture
def sample_segments():
    """Sample segment assignments."""
    return pd.Series({
        'U1': 0,
        'U2': 1,
        'U3': 0
    })


@pytest.fixture
def sample_product_catalog():
    """Sample product catalog for testing."""
    return pd.DataFrame({
        'product_id': ['P1', 'P2', 'P3', 'P4', 'P5'],
        'product_name': ['Basic Plan', 'Premium Plan', 'Data Package', 'Retention Offer', 'Value Pack'],
        'product_family': ['Basic', 'Premium', 'Data', 'Retention Offer', 'Value'],
        'price': [50000, 200000, 100000, 150000, 75000],
        'quota_data_mb': [10000, 60000, 50000, 40000, 20000],
        'quota_voice_min': [100, 500, 200, 300, 150],
        'validity_days': [30, 30, 30, 30, 30]
    })


@pytest.fixture
def fitted_baseline(sample_transactions, sample_segments, sample_product_catalog):
    """Fitted EnhancedBaseline instance."""
    baseline = EnhancedBaseline()
    baseline.fit(sample_transactions, sample_segments, sample_product_catalog)
    return baseline


class TestEnhancedBaselineInit:
    """Test EnhancedBaseline initialization."""

    def test_init_default(self):
        """Test default initialization."""
        baseline = EnhancedBaseline()
        assert baseline.popularity_baseline is not None
        assert baseline.product_vectors is None
        assert not baseline.is_fitted

    def test_init_with_popularity_baseline(self):
        """Test initialization with existing popularity baseline."""
        pop_baseline = TopPopularBaseline()
        baseline = EnhancedBaseline(popularity_baseline=pop_baseline)
        assert baseline.popularity_baseline == pop_baseline


class TestEnhancedBaselineFit:
    """Test EnhancedBaseline fitting."""

    def test_fit_success(self, sample_transactions, sample_segments, sample_product_catalog):
        """Test successful fitting."""
        baseline = EnhancedBaseline()
        baseline.fit(sample_transactions, sample_segments, sample_product_catalog)

        assert baseline.is_fitted
        assert baseline.popularity_baseline.is_fitted
        assert baseline.product_vectors is not None
        assert len(baseline.product_vectors) == 5  # 5 products in catalog

    def test_fit_without_segments(self, sample_transactions, sample_product_catalog):
        """Test fitting without segment information."""
        baseline = EnhancedBaseline()
        baseline.fit(sample_transactions, segments=None, product_catalog=sample_product_catalog)

        assert baseline.is_fitted
        assert baseline.product_vectors is not None

    def test_fit_without_product_catalog(self, sample_transactions, sample_segments):
        """Test fitting without product catalog (similarity won't work)."""
        baseline = EnhancedBaseline()
        baseline.fit(sample_transactions, sample_segments, product_catalog=None)

        assert baseline.is_fitted
        assert baseline.product_vectors is None  # No pre-computed vectors


class TestRecommendBySegment:
    """Test segment-based popularity recommendations."""

    def test_recommend_by_segment_success(self, fitted_baseline):
        """Test successful segment recommendation."""
        recommendations = fitted_baseline.recommend_by_segment(
            segment=0,
            top_k=3
        )

        assert isinstance(recommendations, list)
        assert len(recommendations) <= 3
        assert all(isinstance(r, tuple) and len(r) == 2 for r in recommendations)
        assert all(isinstance(r[0], str) and isinstance(r[1], (int, float)) for r in recommendations)

    def test_recommend_by_segment_with_exclusions(self, fitted_baseline):
        """Test segment recommendation with excluded products."""
        recommendations = fitted_baseline.recommend_by_segment(
            segment=0,
            top_k=5,
            exclude_products=['P1']
        )

        product_ids = [r[0] for r in recommendations]
        assert 'P1' not in product_ids

    def test_recommend_by_segment_not_fitted(self):
        """Test recommendation fails when not fitted."""
        baseline = EnhancedBaseline()
        recommendations = baseline.recommend_by_segment(segment=0, top_k=5)
        assert recommendations == []


class TestRecommendByAffinity:
    """Test rule-based affinity matching."""

    def test_affinity_high_arpu_users(self, fitted_baseline, sample_product_catalog):
        """Test high ARPU users get premium products."""
        user_features = {
            'arpu': 250000,  # High ARPU
            'usage_7d_data_mb': 20000,
            'churn_score': 0.3,
            'frequency': 5
        }

        recommendations = fitted_baseline.recommend_by_affinity(
            user_features=user_features,
            product_catalog=sample_product_catalog,
            top_k=3
        )

        assert len(recommendations) > 0
        # Should recommend premium products (price > 150k, quota > 50k)
        recommended_ids = [r[0] for r in recommendations]
        # P2 (Premium Plan) should be included
        assert any(pid in ['P2'] for pid in recommended_ids)

    def test_affinity_high_data_usage(self, fitted_baseline, sample_product_catalog):
        """Test high data usage users get data-heavy packages."""
        user_features = {
            'arpu': 100000,
            'usage_7d_data_mb': 55000,  # High data usage
            'churn_score': 0.4,
            'frequency': 3
        }

        recommendations = fitted_baseline.recommend_by_affinity(
            user_features=user_features,
            product_catalog=sample_product_catalog,
            top_k=3
        )

        assert len(recommendations) > 0
        # Should recommend data-heavy packages
        recommended_ids = [r[0] for r in recommendations]
        assert any(pid in ['P2', 'P3'] for pid in recommended_ids)  # High quota products

    def test_affinity_high_churn_risk(self, fitted_baseline, sample_product_catalog):
        """Test high churn risk users get retention offers."""
        user_features = {
            'arpu': 120000,
            'usage_7d_data_mb': 30000,
            'churn_score': 0.85,  # High churn risk
            'frequency': 2
        }

        recommendations = fitted_baseline.recommend_by_affinity(
            user_features=user_features,
            product_catalog=sample_product_catalog,
            top_k=3
        )

        assert len(recommendations) > 0
        # Should recommend retention offers
        recommended_ids = [r[0] for r in recommendations]
        assert 'P4' in recommended_ids  # Retention Offer

    def test_affinity_high_frequency(self, fitted_baseline, sample_product_catalog):
        """Test high frequency users get loyalty/value packages."""
        user_features = {
            'arpu': 100000,
            'usage_7d_data_mb': 25000,
            'churn_score': 0.2,
            'frequency': 15  # High frequency
        }

        recommendations = fitted_baseline.recommend_by_affinity(
            user_features=user_features,
            product_catalog=sample_product_catalog,
            top_k=3
        )

        assert len(recommendations) > 0
        # Should recommend value packages
        recommended_ids = [r[0] for r in recommendations]
        assert 'P5' in recommended_ids  # Value Pack

    def test_affinity_default_case(self, fitted_baseline, sample_product_catalog):
        """Test default case (no specific rules match)."""
        user_features = {
            'arpu': 80000,  # Below premium threshold
            'usage_7d_data_mb': 20000,  # Below data threshold
            'churn_score': 0.5,  # Medium churn
            'frequency': 5  # Medium frequency
        }

        recommendations = fitted_baseline.recommend_by_affinity(
            user_features=user_features,
            product_catalog=sample_product_catalog,
            top_k=3
        )

        assert len(recommendations) > 0
        # Should get value-sorted recommendations

    def test_affinity_with_exclusions(self, fitted_baseline, sample_product_catalog):
        """Test affinity matching with excluded products."""
        user_features = {
            'arpu': 250000,
            'usage_7d_data_mb': 20000,
            'churn_score': 0.3,
            'frequency': 5
        }

        recommendations = fitted_baseline.recommend_by_affinity(
            user_features=user_features,
            product_catalog=sample_product_catalog,
            top_k=3,
            exclude_products=['P2']
        )

        recommended_ids = [r[0] for r in recommendations]
        assert 'P2' not in recommended_ids


class TestRecommendBySimilarity:
    """Test content-based similarity recommendations."""

    def test_similarity_success(self, fitted_baseline, sample_product_catalog):
        """Test successful similarity recommendation."""
        user_features = {
            'frequency': 10,
            'monetary': 150000,
            'usage_7d_data_mb': 40000,
            'arpu': 150000
        }

        recommendations = fitted_baseline.recommend_by_similarity(
            user_features=user_features,
            product_catalog=sample_product_catalog,
            top_k=3
        )

        assert len(recommendations) > 0
        assert len(recommendations) <= 3
        # Scores should be between 0 and 1 (cosine similarity)
        assert all(0 <= r[1] <= 1 for r in recommendations)

    def test_similarity_with_exclusions(self, fitted_baseline, sample_product_catalog):
        """Test similarity with excluded products."""
        user_features = {
            'frequency': 10,
            'monetary': 150000,
            'usage_7d_data_mb': 40000,
            'arpu': 150000
        }

        recommendations = fitted_baseline.recommend_by_similarity(
            user_features=user_features,
            product_catalog=sample_product_catalog,
            top_k=5,
            exclude_products=['P1', 'P2']
        )

        recommended_ids = [r[0] for r in recommendations]
        assert 'P1' not in recommended_ids
        assert 'P2' not in recommended_ids

    def test_similarity_without_precomputed_vectors(self, sample_product_catalog):
        """Test similarity when product vectors aren't pre-computed."""
        baseline = EnhancedBaseline()
        baseline.is_fitted = True  # Mark as fitted but no vectors

        user_features = {
            'frequency': 10,
            'monetary': 150000,
            'usage_7d_data_mb': 40000,
            'arpu': 150000
        }

        # Should recompute vectors on the fly
        recommendations = baseline.recommend_by_similarity(
            user_features=user_features,
            product_catalog=sample_product_catalog,
            top_k=3
        )

        # Should succeed after recomputation
        assert isinstance(recommendations, list)


class TestRecommendCombined:
    """Test combined recommendation strategy."""

    def test_recommend_all_strategies(self, fitted_baseline, sample_product_catalog):
        """Test combined recommendations from all strategies."""
        user_features = {
            'frequency': 10,
            'monetary': 150000,
            'usage_7d_data_mb': 40000,
            'arpu': 150000,
            'churn_score': 0.4
        }

        recommendations = fitted_baseline.recommend(
            user_features=user_features,
            product_catalog=sample_product_catalog,
            segment=0,
            top_k=10
        )

        assert len(recommendations) > 0
        assert len(recommendations) <= 10
        # Should have scores
        assert all(isinstance(r[1], (int, float)) for r in recommendations)
        # Should be sorted by score descending
        scores = [r[1] for r in recommendations]
        assert scores == sorted(scores, reverse=True)

    def test_recommend_custom_weights(self, fitted_baseline, sample_product_catalog):
        """Test recommendations with custom strategy weights."""
        user_features = {
            'frequency': 10,
            'monetary': 150000,
            'usage_7d_data_mb': 40000,
            'arpu': 150000,
            'churn_score': 0.4
        }

        recommendations = fitted_baseline.recommend(
            user_features=user_features,
            product_catalog=sample_product_catalog,
            segment=0,
            top_k=10,
            strategy_weights={
                'segment': 0.6,
                'affinity': 0.3,
                'similarity': 0.1
            }
        )

        assert len(recommendations) > 0

    def test_recommend_with_exclusions(self, fitted_baseline, sample_product_catalog):
        """Test combined recommendations with excluded products."""
        user_features = {
            'frequency': 10,
            'monetary': 150000,
            'usage_7d_data_mb': 40000,
            'arpu': 150000,
            'churn_score': 0.4
        }

        recommendations = fitted_baseline.recommend(
            user_features=user_features,
            product_catalog=sample_product_catalog,
            segment=0,
            top_k=10,
            exclude_products=['P1', 'P2']
        )

        recommended_ids = [r[0] for r in recommendations]
        assert 'P1' not in recommended_ids
        assert 'P2' not in recommended_ids

    def test_recommend_not_fitted(self, sample_product_catalog):
        """Test recommendation fails when not fitted."""
        baseline = EnhancedBaseline()

        user_features = {
            'frequency': 10,
            'monetary': 150000,
            'usage_7d_data_mb': 40000,
            'arpu': 150000
        }

        recommendations = baseline.recommend(
            user_features=user_features,
            product_catalog=sample_product_catalog,
            segment=0,
            top_k=5
        )

        assert recommendations == []


class TestSaveLoad:
    """Test model persistence."""

    def test_save_and_load(self, fitted_baseline, tmp_path):
        """Test saving and loading model."""
        model_path = tmp_path / "enhanced_baseline.pkl"

        # Save model
        fitted_baseline.save_model(str(model_path))
        assert model_path.exists()

        # Load model
        new_baseline = EnhancedBaseline()
        new_baseline.load_model(str(model_path))

        assert new_baseline.is_fitted
        assert new_baseline.product_vectors is not None
        assert new_baseline.popularity_baseline.is_fitted
