"""
Baseline Recommendation Models
===============================

Simple baseline models for A/B testing and performance comparison.

Models:
- TopPopular: Most popular products overall or per segment
- Random: Random recommendations for control group
"""

from .top_popular import TopPopularRecommender
from .random_recommender import RandomRecommender

__all__ = ['TopPopularRecommender', 'RandomRecommender']
