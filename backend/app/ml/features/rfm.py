"""
RFM Feature Calculator
======================

Recency, Frequency, Monetary analysis for customer segmentation.

Features:
- SQL-based feature computation for efficiency
- Batch and real-time calculation
- RFM scoring with quintiles
- Feature versioning
"""

from typing import Optional
from datetime import datetime
import pandas as pd
import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class RFMCalculator:
    """
    Calculate Recency, Frequency, Monetary features.

    Recency: Days since last purchase
    Frequency: Total number of purchases
    Monetary: Total revenue from customer
    """

    def __init__(self, reference_date: Optional[datetime] = None):
        """
        Initialize RFM calculator.

        Args:
            reference_date: Reference date for recency calculation (defaults to now)
        """
        self.reference_date = reference_date or datetime.now()

    def calculate(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate RFM features from transaction data.

        Args:
            transactions: DataFrame with columns [user_id, transaction_date, amount]

        Returns:
            DataFrame with [user_id, recency, frequency, monetary]
        """
        if transactions.empty:
            return pd.DataFrame(columns=['user_id', 'recency', 'frequency', 'monetary'])

        # Ensure transaction_date is datetime
        transactions['transaction_date'] = pd.to_datetime(transactions['transaction_date'])

        # Calculate RFM metrics
        rfm = transactions.groupby('user_id').agg({
            'transaction_date': lambda x: (self.reference_date - x.max()).days,  # Recency
            'transaction_id': 'count',  # Frequency
            'amount': 'sum'  # Monetary
        }).rename(columns={
            'transaction_date': 'recency',
            'transaction_id': 'frequency',
            'amount': 'monetary'
        })

        # Ensure recency is non-negative
        rfm['recency'] = rfm['recency'].clip(lower=0)

        return rfm.reset_index()

    def score_rfm(
        self,
        rfm: pd.DataFrame,
        bins: int = 5,
        labels: bool = True
    ) -> pd.DataFrame:
        """
        Score RFM values into quintiles (1-5).

        Args:
            rfm: DataFrame with recency, frequency, monetary columns
            bins: Number of bins for quintile scoring (default: 5)
            labels: Whether to create RFM score string (default: True)

        Returns:
            DataFrame with r_score, f_score, m_score, rfm_score columns added
        """
        if rfm.empty:
            return rfm

        # Score Recency (lower is better, so reverse)
        try:
            rfm['r_score'] = pd.qcut(
                rfm['recency'],
                bins,
                labels=range(bins, 0, -1),
                duplicates='drop'
            ).astype(int)
        except ValueError:
            # If all values are the same, assign middle score
            rfm['r_score'] = bins // 2 + 1

        # Score Frequency (higher is better)
        try:
            rfm['f_score'] = pd.qcut(
                rfm['frequency'].rank(method='first'),
                bins,
                labels=range(1, bins + 1),
                duplicates='drop'
            ).astype(int)
        except ValueError:
            rfm['f_score'] = bins // 2 + 1

        # Score Monetary (higher is better)
        try:
            rfm['m_score'] = pd.qcut(
                rfm['monetary'].rank(method='first'),
                bins,
                labels=range(1, bins + 1),
                duplicates='drop'
            ).astype(int)
        except ValueError:
            rfm['m_score'] = bins // 2 + 1

        # Create combined RFM score string
        if labels:
            rfm['rfm_score'] = (
                rfm['r_score'].astype(str) +
                rfm['f_score'].astype(str) +
                rfm['m_score'].astype(str)
            )

        return rfm

    async def calculate_from_db(
        self,
        session: AsyncSession,
        reference_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Calculate RFM features directly from database using SQL.

        Args:
            session: Async database session
            reference_date: Reference date for recency (defaults to now)

        Returns:
            DataFrame with RFM features
        """
        ref_date = reference_date or self.reference_date

        query = text("""
            SELECT
                user_id,
                EXTRACT(DAY FROM :ref_date - MAX(transaction_date))::INTEGER as recency,
                COUNT(transaction_id)::INTEGER as frequency,
                SUM(amount)::NUMERIC(10,2) as monetary
            FROM transactions
            WHERE status = 'completed'
            GROUP BY user_id
        """)

        result = await session.execute(query, {"ref_date": ref_date})
        rows = result.fetchall()

        if not rows:
            return pd.DataFrame(columns=['user_id', 'recency', 'frequency', 'monetary'])

        rfm = pd.DataFrame(rows, columns=['user_id', 'recency', 'frequency', 'monetary'])

        # Ensure recency is non-negative
        rfm['recency'] = rfm['recency'].clip(lower=0)

        return rfm

    def segment_customers(self, rfm_scored: pd.DataFrame) -> pd.DataFrame:
        """
        Segment customers based on RFM scores into actionable groups.

        Args:
            rfm_scored: DataFrame with r_score, f_score, m_score columns

        Returns:
            DataFrame with segment column added
        """
        def assign_segment(row):
            """Assign customer segment based on RFM scores."""
            r, f, m = row['r_score'], row['f_score'], row['m_score']

            # Champions: High value, frequent, recent
            if r >= 4 and f >= 4 and m >= 4:
                return 'Champions'

            # Loyal Customers: Frequent buyers
            elif f >= 4:
                return 'Loyal Customers'

            # Potential Loyalists: Recent customers with potential
            elif r >= 4 and f >= 2 and m >= 2:
                return 'Potential Loyalists'

            # Recent Customers: New customers
            elif r >= 4:
                return 'Recent Customers'

            # At Risk: Were valuable but not recent
            elif f >= 4 and r <= 2:
                return 'At Risk'

            # Cannot Lose Them: High value but churning
            elif f >= 4 and m >= 4 and r <= 2:
                return 'Cannot Lose'

            # Hibernating: Low recency, frequency, monetary
            elif r <= 2 and f <= 2:
                return 'Hibernating'

            # Lost: Very low engagement
            elif r == 1:
                return 'Lost'

            # Default
            else:
                return 'Needs Attention'

        if rfm_scored.empty:
            return rfm_scored

        rfm_scored['segment'] = rfm_scored.apply(assign_segment, axis=1)
        return rfm_scored

    def get_feature_names(self) -> list:
        """Get list of feature names produced by this calculator."""
        return ['recency', 'frequency', 'monetary', 'r_score', 'f_score', 'm_score', 'rfm_score']
