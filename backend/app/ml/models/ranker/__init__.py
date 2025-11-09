"""
XGBoost Ranking Models
=======================

Learning-to-rank models for re-ranking recommendation candidates.
"""

from .xgboost_ranker import XGBoostRanker
from .trainer import RankerTrainer, train_ranker_from_db

__all__ = [
    'XGBoostRanker',
    'RankerTrainer',
    'train_ranker_from_db'
]
