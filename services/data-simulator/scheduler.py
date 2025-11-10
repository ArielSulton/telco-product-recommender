"""
Data Ingestion Scheduler
Uses APScheduler to periodically ingest data batches
Sprint 1: Infrastructure & Streaming Foundation
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from simulator import TelcoDataSimulator
import os
import logging
from datetime import datetime
import signal
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global simulator instance
simulator = None
scheduler = None


def run_ingestion():
    """Scheduled ingestion job"""
    global simulator

    try:
        logger.info(f"⏰ Scheduled ingestion triggered at {datetime.now()}")

        # Run batch ingestion
        result = simulator.ingest_batch(
            batch_size=int(os.getenv('BATCH_SIZE', '1000'))
        )

        logger.info(f"✅ Ingestion completed: {result}")

        # Check if all data is ingested
        if result['status'] == 'completed' and result['records_processed'] == 0:
            logger.info("📭 All data ingested - stopping scheduler")
            if os.getenv('REPLAY_MODE', 'false').lower() == 'true':
                logger.info("🔄 Replay mode enabled - resetting simulator")
                simulator.reset()
            else:
                logger.info("⏹️ Stopping scheduler (replay disabled)")
                scheduler.shutdown(wait=False)

    except Exception as e:
        logger.error(f"❌ Ingestion job failed: {e}", exc_info=True)


def handle_shutdown(signum, frame):
    """Handle graceful shutdown"""
    logger.info("🛑 Shutdown signal received, stopping scheduler...")
    if scheduler:
        scheduler.shutdown(wait=True)
    logger.info("👋 Scheduler stopped gracefully")
    sys.exit(0)


def main():
    """Main scheduler loop"""
    global simulator, scheduler

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Get configuration from environment
    csv_path = os.getenv(
        'DATA_SOURCE_PATH',
        '/app/ml/data/raw/ac-01_telco_customer_behavior_mock_data.csv'
    )
    db_url = os.getenv(
        'DATABASE_URL',
        'postgresql://postgres:postgres@postgres:5432/telco_recommender'
    )
    interval_hours = int(os.getenv('INGESTION_INTERVAL_HOURS', '4'))
    start_immediately = os.getenv('START_IMMEDIATELY', 'true').lower() == 'true'
    use_cron = os.getenv('USE_CRON', 'false').lower() == 'true'
    cron_expression = os.getenv('CRON_EXPRESSION', '0 */4 * * *')  # Every 4 hours

    logger.info("🚀 Starting Data Ingestion Scheduler")
    logger.info(f"📁 CSV Path: {csv_path}")
    logger.info(f"🗄️ Database: {db_url.split('@')[1] if '@' in db_url else 'local'}")
    logger.info(f"⏱️ Interval: {interval_hours} hours")
    logger.info(f"🔄 Replay Mode: {os.getenv('REPLAY_MODE', 'false')}")

    # Initialize simulator
    try:
        simulator = TelcoDataSimulator(csv_path, db_url)
        logger.info("✅ Simulator initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize simulator: {e}")
        sys.exit(1)

    # Initialize scheduler
    scheduler = BlockingScheduler()

    # Configure trigger
    if use_cron:
        # Use cron expression (more flexible)
        trigger = CronTrigger.from_crontab(cron_expression)
        logger.info(f"📅 Using cron trigger: {cron_expression}")
    else:
        # Use interval trigger
        trigger = IntervalTrigger(hours=interval_hours)
        logger.info(f"⏲️ Using interval trigger: every {interval_hours} hours")

    # Add ingestion job
    scheduler.add_job(
        run_ingestion,
        trigger=trigger,
        id='data_ingestion',
        name='Telco Data Ingestion',
        replace_existing=True,
        max_instances=1  # Prevent concurrent executions
    )

    # Run immediately on startup if configured
    if start_immediately:
        logger.info("▶️ Running initial ingestion immediately...")
        run_ingestion()

    # Start scheduler
    try:
        logger.info("🎬 Scheduler started - waiting for triggers...")
        jobs = scheduler.get_jobs()
        if jobs:
            # APScheduler 4.x compatible way to get next run time
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            next_run = jobs[0].trigger.get_next_fire_time(None, now)
            logger.info(f"📊 Next run scheduled at: {next_run}")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("⏹️ Scheduler stopped")


if __name__ == "__main__":
    main()
