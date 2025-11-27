"""
Usage Pattern Calculator
========================

Data, voice, and SMS usage pattern analysis.

Features:
- 7-day and 30-day usage metrics
- Usage trend analysis
- Peak usage detection
- SQL-based computation
"""

from typing import Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class UsageCalculator:
    """
    Calculate usage-based features for telco customers.

    Tracks data, voice, and SMS usage patterns.
    """

    def __init__(self):
        """Initialize usage calculator."""
        pass

    def calculate_usage_7d(self, usage_logs: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate 7-day rolling usage metrics.

        Args:
            usage_logs: DataFrame with columns [user_id, usage_date, data_mb, voice_min, sms_count]

        Returns:
            DataFrame with [user_id, usage_7d_data_mb, usage_7d_voice_min, usage_7d_sms]
        """
        if usage_logs.empty:
            return pd.DataFrame(columns=[
                'user_id', 'usage_7d_data_mb', 'usage_7d_voice_min', 'usage_7d_sms'
            ])

        # Ensure usage_date is datetime
        usage_logs['usage_date'] = pd.to_datetime(usage_logs['usage_date'])

        # Filter last 7 days
        cutoff_date = datetime.now() - timedelta(days=7)
        recent_usage = usage_logs[usage_logs['usage_date'] >= cutoff_date]

        # Aggregate usage
        features = recent_usage.groupby('user_id').agg({
            'data_mb': 'sum',
            'voice_min': 'sum',
            'sms_count': 'sum'
        }).rename(columns={
            'data_mb': 'usage_7d_data_mb',
            'voice_min': 'usage_7d_voice_min',
            'sms_count': 'usage_7d_sms'
        })

        return features.reset_index()

    def calculate_usage_30d(self, usage_logs: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate 30-day rolling usage metrics.

        Args:
            usage_logs: DataFrame with columns [user_id, usage_date, data_mb, voice_min, sms_count]

        Returns:
            DataFrame with [user_id, usage_30d_data_mb, usage_30d_voice_min, usage_30d_sms]
        """
        if usage_logs.empty:
            return pd.DataFrame(columns=[
                'user_id', 'usage_30d_data_mb', 'usage_30d_voice_min', 'usage_30d_sms'
            ])

        # Ensure usage_date is datetime
        usage_logs['usage_date'] = pd.to_datetime(usage_logs['usage_date'])

        # Filter last 30 days
        cutoff_date = datetime.now() - timedelta(days=30)
        recent_usage = usage_logs[usage_logs['usage_date'] >= cutoff_date]

        # Aggregate usage
        features = recent_usage.groupby('user_id').agg({
            'data_mb': 'sum',
            'voice_min': 'sum',
            'sms_count': 'sum'
        }).rename(columns={
            'data_mb': 'usage_30d_data_mb',
            'voice_min': 'usage_30d_voice_min',
            'sms_count': 'usage_30d_sms'
        })

        return features.reset_index()

    async def calculate_from_db(
        self,
        session: AsyncSession,
        days: int = 7
    ) -> pd.DataFrame:
        """
        Calculate usage metrics directly from database using SQL.

        Args:
            session: Async database session
            days: Number of days for usage calculation

        Returns:
            DataFrame with usage features
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        query = text(f"""
            SELECT
                user_id,
                SUM(data_mb)::INTEGER as usage_{days}d_data_mb,
                SUM(voice_min)::INTEGER as usage_{days}d_voice_min,
                SUM(sms_count)::INTEGER as usage_{days}d_sms
            FROM usage_logs
            WHERE usage_date >= :cutoff_date
            GROUP BY user_id
        """)

        result = await session.execute(query, {"cutoff_date": cutoff_date})
        rows = result.fetchall()

        if not rows:
            return pd.DataFrame(columns=[
                'user_id', f'usage_{days}d_data_mb',
                f'usage_{days}d_voice_min', f'usage_{days}d_sms'
            ])

        return pd.DataFrame(rows, columns=[
            'user_id', f'usage_{days}d_data_mb',
            f'usage_{days}d_voice_min', f'usage_{days}d_sms'
        ])

    def calculate_usage_trend(
        self,
        usage_logs: pd.DataFrame,
        periods: int = 4
    ) -> pd.DataFrame:
        """
        Calculate usage trend over multiple periods.

        Args:
            usage_logs: Usage data DataFrame
            periods: Number of weekly periods to analyze

        Returns:
            DataFrame with usage trend indicators
        """
        if usage_logs.empty:
            return pd.DataFrame()

        usage_logs['usage_date'] = pd.to_datetime(usage_logs['usage_date'])
        usage_logs['week'] = usage_logs['usage_date'].dt.isocalendar().week

        # Group by user and week
        weekly = usage_logs.groupby(['user_id', 'week']).agg({
            'data_mb': 'sum'
        }).reset_index()

        # Calculate trend (linear regression slope)
        def calc_trend(group):
            if len(group) < 2:
                return 0
            x = np.arange(len(group))
            y = group['data_mb'].values
            return np.polyfit(x, y, 1)[0] if len(x) > 0 else 0

        trends = weekly.groupby('user_id').apply(calc_trend).reset_index()
        trends.columns = ['user_id', 'usage_trend']

        return trends

    def classify_usage_type(self, usage_df: pd.DataFrame) -> pd.DataFrame:
        """
        Classify users by primary usage type.

        Args:
            usage_df: DataFrame with usage columns

        Returns:
            DataFrame with usage_type column
        """
        if usage_df.empty:
            return usage_df

        def determine_type(row):
            """Determine primary usage type."""
            data = row.get('usage_7d_data_mb', 0)
            voice = row.get('usage_7d_voice_min', 0)
            sms = row.get('usage_7d_sms', 0)

            total = data + voice + sms
            if total == 0:
                return 'inactive'

            data_pct = data / total
            voice_pct = voice / total

            if data_pct > 0.6:
                return 'data_heavy'
            elif voice_pct > 0.6:
                return 'voice_heavy'
            elif data_pct > 0.3 and voice_pct > 0.3:
                return 'balanced'
            else:
                return 'light_user'

        usage_df['usage_type'] = usage_df.apply(determine_type, axis=1)
        return usage_df

    def get_feature_names(self) -> list:
        """Get list of feature names produced by this calculator."""
        return [
            'usage_7d_data_mb',
            'usage_7d_voice_min',
            'usage_7d_sms',
            'usage_30d_data_mb',
            'usage_30d_voice_min',
            'usage_30d_sms',
            'usage_trend',
            'usage_type'
        ]
