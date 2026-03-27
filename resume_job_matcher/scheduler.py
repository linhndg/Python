"""
Background scheduler that fetches jobs daily (or at configured interval).
Uses APScheduler for in-process scheduling, or can be run standalone via cron.
"""

import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

_scheduler_thread = None
_scheduler_running = False


def start_scheduler(app=None):
    """Start the background job scheduler."""
    global _scheduler_thread, _scheduler_running

    if _scheduler_running:
        logger.info("Scheduler already running")
        return

    from config import Config
    if not Config.SCHEDULER_ENABLED:
        logger.info("Scheduler disabled via config")
        return

    interval = Config.SCHEDULER_INTERVAL_HOURS * 3600

    def _run_loop():
        global _scheduler_running
        import time
        _scheduler_running = True
        logger.info(f"Scheduler started: fetching every {Config.SCHEDULER_INTERVAL_HOURS} hours")

        # Initial fetch after 60 seconds (give app time to start)
        time.sleep(60)

        while _scheduler_running:
            try:
                logger.info(f"[{datetime.now()}] Running scheduled job fetch...")
                from job_aggregator import run_scheduled_fetch
                count = run_scheduled_fetch()
                logger.info(f"Scheduled fetch complete: {count} jobs found")
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            time.sleep(interval)

    _scheduler_thread = threading.Thread(target=_run_loop, daemon=True)
    _scheduler_thread.start()


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler_running
    _scheduler_running = False
    logger.info("Scheduler stopped")


def run_once():
    """Run a single fetch cycle (for CLI or cron usage)."""
    from job_aggregator import run_scheduled_fetch
    count = run_scheduled_fetch()
    print(f"Fetched {count} jobs at {datetime.now()}")
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_once()
