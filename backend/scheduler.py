"""
Scheduler for periodic tasks
Runs daily analytics aggregation and archival
"""
import asyncio
from datetime import datetime, time, timedelta
from typing import Optional
import logging
from sqlalchemy.orm import Session
from database import SessionLocal
from analytics_processor import AnalyticsProcessor
from agents.briefings import refresh_all_shop_briefings

logger = logging.getLogger(__name__)


class DailyScheduler:
    """Schedule and run daily maintenance tasks"""
    
    def __init__(self, run_at_hour: int = 0, run_at_minute: int = 30, briefing_refresh_seconds: int = 300):
        """
        Initialize scheduler
        
        Args:
            run_at_hour: Hour to run daily tasks (0-23, default: 0 = midnight)
            run_at_minute: Minute to run daily tasks (0-59, default: 30)
        """
        self.run_at = time(hour=run_at_hour, minute=run_at_minute)
        self.briefing_refresh_seconds = briefing_refresh_seconds
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
        self.briefing_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._run_schedule())
        self.briefing_task = asyncio.create_task(self._run_briefing_refresh_loop())
        logger.info(f"Scheduler started - will run daily at {self.run_at}")
    
    async def stop(self):
        """Stop the scheduler"""
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.briefing_task:
            self.briefing_task.cancel()
            try:
                await self.briefing_task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _run_briefing_refresh_loop(self):
        """Refresh operational briefing snapshots on a shorter cadence."""
        while self.is_running:
            try:
                refreshed = await asyncio.to_thread(refresh_all_shop_briefings)
                logger.info("Operational briefing refresh completed for %s shop(s)", refreshed)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error refreshing operational briefings: {e}", exc_info=True)

            await asyncio.sleep(self.briefing_refresh_seconds)
    
    async def _run_schedule(self):
        """Internal method to run scheduled tasks"""
        while self.is_running:
            try:
                # Calculate seconds until next run
                now = datetime.now()
                target = datetime.combine(now.date(), self.run_at)
                
                # If target time has passed today, schedule for tomorrow
                if target <= now:
                    target = datetime.combine(
                        now.date() + timedelta(days=1),
                        self.run_at
                    )
                
                seconds_until_run = (target - now).total_seconds()
                logger.info(f"Next maintenance run in {seconds_until_run/3600:.2f} hours at {target}")
                
                # Sleep until target time
                await asyncio.sleep(seconds_until_run)
                
                # Run the maintenance task
                if self.is_running:
                    await self._run_maintenance()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                # Sleep for 5 minutes before retrying
                await asyncio.sleep(300)
    
    async def _run_maintenance(self):
        """Run the actual maintenance tasks"""
        db = None
        try:
            logger.info("Starting daily maintenance tasks")
            
            # Create database session
            db = SessionLocal()
            
            # Run maintenance
            processor = AnalyticsProcessor(db)
            results = processor.run_daily_maintenance()
            
            logger.info(f"Daily maintenance completed: {results}")
            
        except Exception as e:
            logger.error(f"Error during maintenance: {e}", exc_info=True)
        finally:
            if db:
                db.close()
    
    async def run_now(self):
        """Manually trigger maintenance run (useful for testing)"""
        logger.info("Manual maintenance trigger requested")
        await self._run_maintenance()


# Global scheduler instance
_scheduler: Optional[DailyScheduler] = None


async def start_scheduler(run_at_hour: int = 0, run_at_minute: int = 30):
    """
    Start the global scheduler
    Should be called at application startup
    
    Args:
        run_at_hour: Hour to run daily tasks (0-23, default: 0 = midnight)
        run_at_minute: Minute to run daily tasks (0-59, default: 30)
    """
    global _scheduler
    
    if _scheduler is None:
        _scheduler = DailyScheduler(run_at_hour, run_at_minute)
        await _scheduler.start()
    else:
        logger.warning("Scheduler already initialized")


async def stop_scheduler():
    """
    Stop the global scheduler
    Should be called at application shutdown
    """
    global _scheduler
    
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None


async def trigger_maintenance_now():
    """
    Manually trigger maintenance (useful for testing or manual runs)
    """
    global _scheduler
    
    if _scheduler:
        await _scheduler.run_now()
    else:
        logger.warning("Scheduler not initialized - running one-time maintenance")
        db = SessionLocal()
        try:
            processor = AnalyticsProcessor(db)
            results = processor.run_daily_maintenance()
            logger.info(f"One-time maintenance completed: {results}")
        finally:
            db.close()
