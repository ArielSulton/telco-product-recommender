"""
Telco Data Streaming Simulator
Simulates real-world data streaming from CSV to PostgreSQL
Sprint 1: Infrastructure & Streaming Foundation
"""

import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import os
import logging
from typing import Optional, Dict
import hashlib
import uuid
from time import sleep

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TelcoDataSimulator:
    """Simulates real-world data streaming from CSV to PostgreSQL"""

    def __init__(self, csv_path: str, db_url: str):
        """
        Initialize the data simulator

        Args:
            csv_path: Path to source CSV file
            db_url: PostgreSQL connection string
        """
        self.csv_path = csv_path
        self.engine = create_engine(db_url, pool_pre_ping=True, pool_size=5)
        self.data = None
        self.current_index = 0
        self.batch_id = None

        logger.info(f"📊 Initializing TelcoDataSimulator")
        logger.info(f"📁 CSV Path: {csv_path}")
        logger.info(f"🗄️ Database: {db_url.split('@')[1] if '@' in db_url else 'local'}")

        # Load CSV data
        self._load_data()

    def _load_data(self):
        """Load and validate CSV data"""
        try:
            self.data = pd.read_csv(self.csv_path)
            logger.info(f"✅ Loaded {len(self.data)} records from CSV")
            logger.info(f"📋 Columns: {list(self.data.columns)}")

            # Validate required columns
            required_columns = ['customer_id', 'plan_type', 'monthly_spend', 'target_offer']
            missing = set(required_columns) - set(self.data.columns)
            if missing:
                raise ValueError(f"Missing required columns: {missing}")

        except Exception as e:
            logger.error(f"❌ Failed to load CSV: {e}")
            raise

    def _create_batch_record(self, status: str = 'running') -> str:
        """Create ingestion batch tracking record"""
        batch_id = str(uuid.uuid4())

        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO ingestion_batches
                    (batch_id, batch_start_time, status, source_file)
                    VALUES (:batch_id, :start_time, :status, :source_file)
                """),
                {
                    'batch_id': batch_id,
                    'start_time': datetime.now(),
                    'status': status,
                    'source_file': os.path.basename(self.csv_path)
                }
            )
            conn.commit()

        return batch_id

    def _update_batch_record(
        self,
        batch_id: str,
        status: str,
        records_processed: int = 0,
        records_failed: int = 0,
        error_message: Optional[str] = None
    ):
        """Update ingestion batch tracking record"""
        with self.engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE ingestion_batches
                    SET batch_end_time = :end_time,
                        status = :status,
                        records_processed = :processed,
                        records_failed = :failed,
                        error_message = :error,
                        updated_at = NOW()
                    WHERE batch_id = :batch_id
                """),
                {
                    'batch_id': batch_id,
                    'end_time': datetime.now(),
                    'status': status,
                    'processed': records_processed,
                    'failed': records_failed,
                    'error': error_message
                }
            )
            conn.commit()

    def _hash_msisdn(self, customer_id: str) -> str:
        """Create SHA-256 hash of customer ID for privacy"""
        return hashlib.sha256(customer_id.encode()).hexdigest()

    def _ensure_user_exists(self, customer_id: str, plan_type: str) -> str:
        """Ensure user exists in database, return user_id"""
        msisdn_hash = self._hash_msisdn(customer_id)

        with self.engine.connect() as conn:
            # Check if user exists
            result = conn.execute(
                text("SELECT user_id FROM users WHERE msisdn_hash = :hash"),
                {'hash': msisdn_hash}
            ).fetchone()

            if result:
                return str(result[0])

            # Create new user
            user_id = str(uuid.uuid4())
            conn.execute(
                text("""
                    INSERT INTO users (user_id, msisdn_hash, registration_date)
                    VALUES (:user_id, :msisdn_hash, :reg_date)
                    ON CONFLICT (msisdn_hash) DO NOTHING
                """),
                {
                    'user_id': user_id,
                    'msisdn_hash': msisdn_hash,
                    'reg_date': datetime.now() - timedelta(days=365)  # Simulate old registration
                }
            )
            conn.commit()

            return user_id

    def _map_offer_to_product(self, target_offer: str) -> str:
        """Map target offer to product ID"""
        offer_mapping = {
            'General Offer': 'PKG003',  # Combo Hemat 5GB
            'Device Upgrade Offer': 'PKG004',  # Combo Super 15GB
            'Data Booster': 'PKG002',  # Internet Freedom 25GB
            'Top-up Promo': 'PKG001'  # Internet Freedom 10GB
        }
        return offer_mapping.get(target_offer, 'PKG003')

    def ingest_batch(self, batch_size: int = 1000, time_offset_hours: int = 0) -> Dict:
        """
        Ingest a batch of records to simulate streaming

        Args:
            batch_size: Number of records to ingest
            time_offset_hours: Hours to offset from current time (for realistic timestamps)

        Returns:
            dict: Ingestion results with status and counts
        """
        if self.current_index >= len(self.data):
            logger.info("📭 No more data to ingest - all records processed")
            return {
                "status": "completed",
                "records_processed": 0,
                "records_failed": 0,
                "progress": f"{self.current_index}/{len(self.data)}"
            }

        # Create batch tracking record
        batch_id = self._create_batch_record()
        logger.info(f"🚀 Starting batch ingestion: {batch_id}")

        # Get batch slice
        end_index = min(self.current_index + batch_size, len(self.data))
        batch = self.data.iloc[self.current_index:end_index].copy()

        records_processed = 0
        records_failed = 0

        try:
            # Process each record
            for idx, row in batch.iterrows():
                try:
                    # Ensure user exists
                    user_id = self._ensure_user_exists(
                        row['customer_id'],
                        row['plan_type']
                    )

                    # Map to product
                    product_id = self._map_offer_to_product(row['target_offer'])

                    # Calculate realistic transaction date
                    days_offset = len(self.data) - self.current_index - (idx - self.current_index)
                    transaction_date = datetime.now() - timedelta(
                        hours=time_offset_hours,
                        days=days_offset % 90  # Spread over 90 days
                    )

                    # Insert transaction
                    with self.engine.connect() as conn:
                        conn.execute(
                            text("""
                                INSERT INTO transactions
                                (user_id, product_id, transaction_date, amount, status)
                                VALUES (:user_id, :product_id, :tx_date, :amount, 'completed')
                            """),
                            {
                                'user_id': user_id,
                                'product_id': product_id,
                                'tx_date': transaction_date,
                                'amount': float(row['monthly_spend'])
                            }
                        )
                        conn.commit()

                    records_processed += 1

                except Exception as e:
                    logger.warning(f"⚠️ Failed to process record {idx}: {e}")
                    records_failed += 1
                    continue

            # Update batch record
            self._update_batch_record(
                batch_id,
                status='completed' if records_failed == 0 else 'partial',
                records_processed=records_processed,
                records_failed=records_failed
            )

            # Update current index
            self.current_index = end_index

            logger.info(f"✅ Batch completed: {records_processed} processed, {records_failed} failed")
            logger.info(f"📊 Progress: {self.current_index}/{len(self.data)} ({self.current_index/len(self.data)*100:.1f}%)")

            return {
                "status": "success",
                "batch_id": batch_id,
                "records_processed": records_processed,
                "records_failed": records_failed,
                "progress": f"{self.current_index}/{len(self.data)}",
                "completion_percentage": round(self.current_index / len(self.data) * 100, 2)
            }

        except Exception as e:
            logger.error(f"❌ Batch ingestion failed: {e}")
            self._update_batch_record(
                batch_id,
                status='failed',
                records_processed=records_processed,
                records_failed=records_failed,
                error_message=str(e)
            )
            raise

    def reset(self):
        """Reset simulator to beginning of data"""
        self.current_index = 0
        logger.info("🔄 Simulator reset to beginning")

    def get_progress(self) -> Dict:
        """Get current ingestion progress"""
        return {
            "current_index": self.current_index,
            "total_records": len(self.data),
            "progress_percentage": round(self.current_index / len(self.data) * 100, 2),
            "remaining_records": len(self.data) - self.current_index
        }

    def get_batch_history(self, limit: int = 10) -> pd.DataFrame:
        """Get recent batch ingestion history"""
        query = text("""
            SELECT batch_id, batch_start_time, batch_end_time,
                   records_processed, records_failed, status
            FROM ingestion_batches
            ORDER BY batch_start_time DESC
            LIMIT :limit
        """)

        with self.engine.connect() as conn:
            return pd.read_sql(query, conn, params={'limit': limit})


def main():
    """Main function for testing"""
    import sys

    # Get configuration from environment
    csv_path = os.getenv(
        'DATA_SOURCE_PATH',
        '/app/ml/data/raw/ac-01_telco_customer_behavior_mock_data.csv'
    )
    db_url = os.getenv(
        'DATABASE_URL',
        'postgresql://postgres:postgres@postgres:5432/telco_recommender'
    )
    batch_size = int(os.getenv('BATCH_SIZE', '1000'))

    # Initialize simulator
    simulator = TelcoDataSimulator(csv_path, db_url)

    # Run single batch
    result = simulator.ingest_batch(batch_size=batch_size)

    logger.info(f"📈 Ingestion Result: {result}")

    # Show progress
    progress = simulator.get_progress()
    logger.info(f"📊 Current Progress: {progress}")


if __name__ == "__main__":
    main()
