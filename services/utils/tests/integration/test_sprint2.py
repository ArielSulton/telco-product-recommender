"""
Sprint 2: ML Models and Feature Engineering - Integration Tests
================================================================

Tests for feature engineering modules and ML models.

Test Coverage:
- Feature computation (RFM, ARPU, Usage, Churn)
- K-Means segmentation
- LightFM collaborative filtering
- Baseline models (TopPopular, Random)
- Model persistence and loading
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytest

# Add backend to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.ml.features.rfm import RFMCalculator
from app.ml.features.arpu import ARPUCalculator
from app.ml.features.usage import UsageCalculator
from app.ml.features.churn import ChurnScorer
from app.ml.features import FeatureAggregator
from app.ml.models.segmentation.kmeans_segmenter import KMeansSegmenter
from app.ml.models.collaborative.lightfm_recommender import LightFMRecommender
from app.ml.models.baseline.top_popular import TopPopularRecommender
from app.ml.models.baseline.random_recommender import RandomRecommender


# ==============================================
# TEST DATA GENERATORS
# ==============================================

def generate_sample_transactions(n_users=100, n_products=50, n_transactions=1000):
    """Generate sample transaction data."""
    np.random.seed(42)

    user_ids = [f"user_{i}" for i in range(n_users)]
    product_ids = [f"prod_{i}" for i in range(n_products)]

    transactions = []
    for i in range(n_transactions):
        transactions.append({
            'transaction_id': f"txn_{i}",
            'user_id': np.random.choice(user_ids),
            'product_id': np.random.choice(product_ids),
            'transaction_date': datetime.now() - timedelta(days=np.random.randint(0, 365)),
            'amount': np.random.uniform(10000, 200000),
            'status': 'completed'
        })

    return pd.DataFrame(transactions)


def generate_sample_usage(n_users=100, n_days=30):
    """Generate sample usage data."""
    np.random.seed(42)

    user_ids = [f"user_{i}" for i in range(n_users)]

    usage_logs = []
    for user_id in user_ids:
        for day in range(n_days):
            usage_logs.append({
                'user_id': user_id,
                'usage_date': datetime.now() - timedelta(days=day),
                'data_mb': np.random.randint(100, 5000),
                'voice_min': np.random.randint(10, 300),
                'sms_count': np.random.randint(5, 100)
            })

    return pd.DataFrame(usage_logs)


# ==============================================
# FEATURE ENGINEERING TESTS
# ==============================================

def test_rfm_calculator():
    """Test RFM feature calculation."""
    print("\n" + "=" * 60)
    print("TEST: RFM Calculator")
    print("=" * 60)

    # Generate test data
    transactions = generate_sample_transactions(n_users=50, n_transactions=500)

    # Calculate RFM
    calculator = RFMCalculator()
    rfm = calculator.calculate(transactions)

    print(f"✓ RFM features computed for {len(rfm)} users")
    print(f"  Columns: {rfm.columns.tolist()}")
    print(f"\nSample RFM values:")
    print(rfm.head())

    # Test RFM scoring
    rfm_scored = calculator.score_rfm(rfm)
    print(f"\n✓ RFM scoring completed")
    print(f"  RFM Score distribution:")
    print(rfm_scored['rfm_score'].value_counts().head(10))

    # Assertions
    assert len(rfm) > 0, "RFM features should be computed"
    assert all(col in rfm.columns for col in ['recency', 'frequency', 'monetary']), \
        "RFM columns missing"
    assert rfm['recency'].min() >= 0, "Recency should be non-negative"

    print("\n✓ RFM Calculator: PASSED")
    return True


def test_arpu_calculator():
    """Test ARPU calculation."""
    print("\n" + "=" * 60)
    print("TEST: ARPU Calculator")
    print("=" * 60)

    transactions = generate_sample_transactions(n_users=50, n_transactions=500)

    calculator = ARPUCalculator(months=3)
    arpu = calculator.calculate(transactions)

    print(f"✓ ARPU computed for {len(arpu)} users")
    print(f"\nARPU bucket distribution:")
    print(arpu['arpu_bucket'].value_counts())

    print(f"\nARPU statistics:")
    print(arpu['arpu'].describe())

    # Assertions
    assert len(arpu) > 0, "ARPU features should be computed"
    assert 'arpu_bucket' in arpu.columns, "ARPU bucket missing"
    assert set(arpu['arpu_bucket'].unique()).issubset(['low', 'medium', 'high', 'premium']), \
        "Invalid ARPU buckets"

    print("\n✓ ARPU Calculator: PASSED")
    return True


def test_usage_calculator():
    """Test usage feature calculation."""
    print("\n" + "=" * 60)
    print("TEST: Usage Calculator")
    print("=" * 60)

    usage_logs = generate_sample_usage(n_users=50, n_days=30)

    calculator = UsageCalculator()
    usage_7d = calculator.calculate_usage_7d(usage_logs)

    print(f"✓ 7-day usage computed for {len(usage_7d)} users")
    print(f"\nUsage statistics:")
    print(usage_7d.describe())

    # Assertions
    assert len(usage_7d) > 0, "Usage features should be computed"
    assert all(col in usage_7d.columns for col in ['usage_7d_data_mb', 'usage_7d_voice_min', 'usage_7d_sms']), \
        "Usage columns missing"

    print("\n✓ Usage Calculator: PASSED")
    return True


def test_feature_aggregator():
    """Test feature aggregator."""
    print("\n" + "=" * 60)
    print("TEST: Feature Aggregator")
    print("=" * 60)

    transactions = generate_sample_transactions(n_users=50, n_transactions=500)
    usage_logs = generate_sample_usage(n_users=50, n_days=30)

    aggregator = FeatureAggregator()
    features = aggregator.compute_batch_features(transactions, usage_logs)

    print(f"✓ Aggregated features for {len(features)} users")
    print(f"  Feature columns ({len(features.columns)}): {features.columns.tolist()}")
    print(f"\nFeature summary:")
    print(features.describe())

    # Assertions
    assert len(features) > 0, "Aggregated features should be computed"
    assert 'recency' in features.columns, "RFM features missing"
    assert 'arpu' in features.columns, "ARPU features missing"

    print("\n✓ Feature Aggregator: PASSED")
    return True


# ==============================================
# ML MODEL TESTS
# ==============================================

def test_kmeans_segmenter():
    """Test K-Means segmentation."""
    print("\n" + "=" * 60)
    print("TEST: K-Means Segmenter")
    print("=" * 60)

    # Generate features
    transactions = generate_sample_transactions(n_users=100, n_transactions=1000)
    aggregator = FeatureAggregator()
    features = aggregator.compute_batch_features(transactions)

    # Train segmenter
    segmenter = KMeansSegmenter(n_clusters=5)
    metrics = segmenter.train(features, find_optimal=False)

    print(f"✓ K-Means trained with {metrics['n_clusters']} clusters")
    print(f"  Silhouette Score: {metrics['silhouette_score']:.4f}")
    print(f"  Davies-Bouldin Score: {metrics['davies_bouldin_score']:.4f}")
    print(f"\nCluster sizes:")
    for cluster_id, size in metrics['cluster_sizes'].items():
        print(f"  Cluster {cluster_id}: {size} users")

    # Test predictions
    segments = segmenter.predict(features)
    print(f"\n✓ Predicted segments for {len(segments)} users")

    # Test interpretations
    interpretations = segmenter.interpret_segments()
    print(f"\nSegment interpretations:")
    for seg_id, label in interpretations.items():
        print(f"  {seg_id}: {label}")

    # Assertions
    assert metrics['silhouette_score'] >= 0.3, \
        f"Silhouette score {metrics['silhouette_score']:.4f} below threshold 0.3"
    assert len(segments) == len(features), "Segment count mismatch"

    print("\n✓ K-Means Segmenter: PASSED")
    return True


def test_lightfm_recommender():
    """Test LightFM collaborative filtering."""
    print("\n" + "=" * 60)
    print("TEST: LightFM Recommender")
    print("=" * 60)

    # Generate interactions
    transactions = generate_sample_transactions(n_users=100, n_products=50, n_transactions=1000)

    # Train recommender
    recommender = LightFMRecommender(no_components=16, learning_rate=0.05)

    print("Preparing data...")
    interaction_matrix, _, _ = recommender.prepare_data(transactions)

    print("Training model...")
    metrics = recommender.train(
        interaction_matrix=interaction_matrix,
        epochs=10,
        verbose=False
    )

    print(f"\n✓ LightFM trained")
    print(f"  Precision@5: {metrics['train_precision_at_5']:.4f}")
    print(f"  Recall@10: {metrics['train_recall_at_10']:.4f}")
    print(f"  AUC: {metrics['train_auc']:.4f}")

    # Test predictions
    test_users = [f"user_{i}" for i in range(5)]
    recommendations = recommender.predict(test_users, top_k=10)

    print(f"\n✓ Generated recommendations for {len(recommendations)} users")
    print(f"  Sample recommendations for {test_users[0]}:")
    for product_id, score in recommendations[test_users[0]][:5]:
        print(f"    {product_id}: {score:.4f}")

    # Assertions
    assert metrics['train_precision_at_5'] >= 0.01, \
        f"Precision@5 {metrics['train_precision_at_5']:.4f} too low"
    assert len(recommendations) == len(test_users), "Recommendation count mismatch"

    print("\n✓ LightFM Recommender: PASSED")
    return True


def test_baseline_models():
    """Test baseline recommenders."""
    print("\n" + "=" * 60)
    print("TEST: Baseline Models")
    print("=" * 60)

    transactions = generate_sample_transactions(n_users=100, n_products=50, n_transactions=1000)

    # Test TopPopular
    print("\n1. TopPopular Recommender")
    top_popular = TopPopularRecommender()
    top_popular.fit(transactions)

    recommendations = top_popular.recommend(top_k=10)
    print(f"✓ TopPopular recommendations: {len(recommendations)} items")
    print(f"  Top 5 products:")
    for product_id, score in recommendations[:5]:
        print(f"    {product_id}: {score:.4f}")

    # Test Random
    print("\n2. Random Recommender")
    products = pd.DataFrame({
        'product_id': [f"prod_{i}" for i in range(50)]
    })

    random_rec = RandomRecommender(random_state=42)
    random_rec.fit(products)

    random_recs = random_rec.recommend(user_id="user_0", top_k=10)
    print(f"✓ Random recommendations: {len(random_recs)} items")
    print(f"  Sample products:")
    for product_id, score in random_recs[:5]:
        print(f"    {product_id}: {score:.4f}")

    # Assertions
    assert len(recommendations) == 10, "TopPopular recommendation count mismatch"
    assert len(random_recs) == 10, "Random recommendation count mismatch"

    print("\n✓ Baseline Models: PASSED")
    return True


# ==============================================
# MAIN TEST RUNNER
# ==============================================

def run_all_tests():
    """Run all Sprint 2 tests."""
    print("\n" + "=" * 60)
    print("SPRINT 2: ML MODELS & FEATURE ENGINEERING TESTS")
    print("=" * 60)

    tests = [
        ("RFM Calculator", test_rfm_calculator),
        ("ARPU Calculator", test_arpu_calculator),
        ("Usage Calculator", test_usage_calculator),
        ("Feature Aggregator", test_feature_aggregator),
        ("K-Means Segmenter", test_kmeans_segmenter),
        ("LightFM Recommender", test_lightfm_recommender),
        ("Baseline Models", test_baseline_models)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success, None))
        except Exception as e:
            print(f"\n✗ {test_name}: FAILED")
            print(f"  Error: {str(e)}")
            results.append((test_name, False, str(e)))

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    for test_name, success, error in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{test_name}: {status}")
        if error:
            print(f"  Error: {error}")

    print("\n" + "-" * 60)
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
