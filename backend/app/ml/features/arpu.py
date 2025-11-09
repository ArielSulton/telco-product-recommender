"""
ARPU Feature Calculator
=======================

Average Revenue Per User calculation and bucketing.

Features:
- ARPU calculation over configurable time periods
- Customer value segmentation (low, medium, high, premium)
- SQL-based computation for efficiency
"""

from typing import Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ARPUCalculator:
    """
    Calculate Average Revenue Per User (ARPU) features.

    Segments users by spending level for targeted recommendations.
    """

    def __init__(self, months: int = 3):
        """
        Initialize ARPU calculator.

        Args:
            months: Number of months for ARPU calculation (default: 3)
        """
        self.months = months

    def calculate(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate ARPU from transaction data.

        Args:
            transactions: DataFrame with columns [user_id, amount, transaction_date]

        Returns:
            DataFrame with [user_id, arpu, arpu_bucket]
        """
        if transactions.empty:
            return pd.DataFrame(columns=['user_id', 'arpu', 'arpu_bucket'])

        # Calculate total revenue per user
        revenue = transactions.groupby('user_id').agg({
            'amount': 'sum'
        }).reset_index()

        # Calculate ARPU (average monthly revenue)
        revenue['arpu'] = revenue['amount'] / self.months

        # Bucket ARPU into segments
        revenue['arpu_bucket'] = self._bucket_arpu(revenue['arpu'])

        return revenue[['user_id', 'arpu', 'arpu_bucket']]

    def _bucket_arpu(self, arpu_series: pd.Series) -> pd.Series:
        """
        Segment ARPU values into buckets.

        Args:
            arpu_series: Series of ARPU values

        Returns:
            Series of bucket labels
        """
        # Define bucket thresholds (in IDR)
        bins = [0, 50000, 100000, 200000, float('inf')]
        labels = ['low', 'medium', 'high', 'premium']

        return pd.cut(
            arpu_series,
            bins=bins,
            labels=labels,
            include_lowest=True
        ).astype(str)

    async def calculate_from_db(
        self,
        session: AsyncSession,
        months: Optional[int] = None,
        start_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Calculate ARPU directly from database using SQL.

        Args:
            session: Async database session
            months: Number of months for calculation
            start_date: Start date for time window

        Returns:
            DataFrame with ARPU features
        """
        months = months or self.months

        if start_date is None:
            start_date = datetime.now() - timedelta(days=months * 30)

        query = text("""
            WITH user_revenue AS (
                SELECT
                    user_id,
                    SUM(amount) as total_revenue,
                    COUNT(DISTINCT DATE_TRUNC('month', transaction_date)) as active_months
                FROM transactions
                WHERE
                    status = 'completed'
                    AND transaction_date >= :start_date
                GROUP BY user_id
            )
            SELECT
                user_id,
                CASE
                    WHEN active_months > 0 THEN total_revenue / active_months
                    ELSE total_revenue / :months
                END as arpu
            FROM user_revenue
        """)

        result = await session.execute(
            query,
            {"start_date": start_date, "months": months}
        )
        rows = result.fetchall()

        if not rows:
            return pd.DataFrame(columns=['user_id', 'arpu', 'arpu_bucket'])

        df = pd.DataFrame(rows, columns=['user_id', 'arpu'])
        df['arpu_bucket'] = self._bucket_arpu(df['arpu'])

        return df

    def calculate_lifetime_value(
        self,
        transactions: pd.DataFrame,
        discount_rate: float = 0.1,
        churn_rate: float = 0.05
    ) -> pd.DataFrame:
        """
        Calculate Customer Lifetime Value (CLV).

        CLV = ARPU * (1 / churn_rate) * (1 + discount_rate)

        Args:
            transactions: Transaction DataFrame
            discount_rate: Monthly discount rate (default: 0.1)
            churn_rate: Monthly churn rate (default: 0.05)

        Returns:
            DataFrame with [user_id, clv]
        """
        arpu = self.calculate(transactions)

        # Calculate CLV
        arpu['clv'] = arpu['arpu'] * (1 / churn_rate) * (1 + discount_rate)

        return arpu[['user_id', 'clv']]

    def get_bucket_stats(self, arpu_df: pd.DataFrame) -> pd.DataFrame:
        """
        Get statistical summary by ARPU bucket.

        Args:
            arpu_df: DataFrame with arpu_bucket column

        Returns:
            DataFrame with bucket statistics
        """
        if arpu_df.empty or 'arpu_bucket' not in arpu_df.columns:
            return pd.DataFrame()

        stats = arpu_df.groupby('arpu_bucket').agg({
            'arpu': ['count', 'mean', 'median', 'std', 'min', 'max']
        }).round(2)

        stats.columns = ['count', 'mean', 'median', 'std', 'min', 'max']
        return stats.reset_index()

    def get_feature_names(self) -> list:
        """Get list of feature names produced by this calculator."""
        return ['arpu', 'arpu_bucket']
