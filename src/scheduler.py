"""
Advanced scheduler integration using APScheduler for cron-like tasks
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.memory import MemoryJobStore
import structlog

logger = structlog.get_logger(__name__)

class AdvancedScheduler:
    """Advanced scheduler with cron-like capabilities using APScheduler"""
    
    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self.scheduler = AsyncIOScheduler(
            jobstores={'default': MemoryJobStore()},
            timezone='UTC'
        )
        self.running = False
    
    async def start(self):
        """Start the scheduler"""
        if not self.running:
            self.scheduler.start()
            self.running = True
            logger.info("Advanced scheduler started")
    
    async def stop(self):
        """Stop the scheduler"""
        if self.running:
            self.scheduler.shutdown()
            self.running = False
            logger.info("Advanced scheduler stopped")
    
    def schedule_cron_task(self, task_name: str, task_type: str, 
                          cron_expression: str, task_data: Dict[str, Any],
                          job_id: Optional[str] = None) -> str:
        """
        Schedule a task using cron expression
        
        Args:
            task_name: Name of the task
            task_type: Type of task (email, api_call, etc.)
            cron_expression: Cron expression (e.g., "0 9 * * MON-FRI")
            task_data: Task configuration data
            job_id: Optional job ID, if not provided, will be auto-generated
        
        Returns:
            Job ID
        """
        # Parse cron expression
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have 5 parts: minute hour day month day_of_week")
        
        minute, hour, day, month, day_of_week = parts
        
        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week
        )
        
        job_id = job_id or f"cron_{task_name}_{datetime.now().timestamp()}"
        
        self.scheduler.add_job(
            func=self._execute_scheduled_task,
            trigger=trigger,
            args=[task_name, task_type, task_data],
            id=job_id,
            name=task_name,
            replace_existing=True
        )
        
        logger.info(f"Scheduled cron task: {job_id} with expression: {cron_expression}")
        return job_id
    
    def schedule_interval_task(self, task_name: str, task_type: str,
                             interval_seconds: int, task_data: Dict[str, Any],
                             job_id: Optional[str] = None, max_instances: int = 1) -> str:
        """
        Schedule a task to run at regular intervals
        
        Args:
            task_name: Name of the task
            task_type: Type of task
            interval_seconds: Interval in seconds
            task_data: Task configuration data
            job_id: Optional job ID
            max_instances: Maximum number of concurrent instances
        
        Returns:
            Job ID
        """
        trigger = IntervalTrigger(seconds=interval_seconds)
        job_id = job_id or f"interval_{task_name}_{datetime.now().timestamp()}"
        
        self.scheduler.add_job(
            func=self._execute_scheduled_task,
            trigger=trigger,
            args=[task_name, task_type, task_data],
            id=job_id,
            name=task_name,
            max_instances=max_instances,
            replace_existing=True
        )
        
        logger.info(f"Scheduled interval task: {job_id} every {interval_seconds} seconds")
        return job_id
    
    def schedule_one_time_task(self, task_name: str, task_type: str,
                              run_date: datetime, task_data: Dict[str, Any],
                              job_id: Optional[str] = None) -> str:
        """
        Schedule a one-time task for a specific date/time
        
        Args:
            task_name: Name of the task
            task_type: Type of task
            run_date: When to run the task
            task_data: Task configuration data
            job_id: Optional job ID
        
        Returns:
            Job ID
        """
        trigger = DateTrigger(run_date=run_date)
        job_id = job_id or f"onetime_{task_name}_{datetime.now().timestamp()}"
        
        self.scheduler.add_job(
            func=self._execute_scheduled_task,
            trigger=trigger,
            args=[task_name, task_type, task_data],
            id=job_id,
            name=task_name,
            replace_existing=True
        )
        
        logger.info(f"Scheduled one-time task: {job_id} for {run_date}")
        return job_id
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed scheduled job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job"""
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"Paused job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job"""
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"Resumed job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            return False
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all scheduled jobs"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger),
                'func': job.func.__name__,
                'args': job.args,
                'kwargs': job.kwargs
            })
        return jobs
    
    def get_job_info(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific job"""
        job = self.scheduler.get_job(job_id)
        if not job:
            return None
        
        return {
            'id': job.id,
            'name': job.name,
            'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger),
            'func': job.func.__name__,
            'args': job.args,
            'kwargs': job.kwargs,
            'executor': job.executor,
            'misfire_grace_time': job.misfire_grace_time,
            'max_instances': job.max_instances
        }
    
    async def _execute_scheduled_task(self, task_name: str, task_type: str, task_data: Dict[str, Any]):
        """Execute a scheduled task through the orchestrator"""
        if not self.orchestrator:
            logger.error(f"Cannot execute scheduled task {task_name}: No orchestrator configured")
            return
        
        try:
            # Create task through orchestrator
            task_id = await self.orchestrator.create_task(
                name=f"Scheduled: {task_name}",
                task_type=task_type,
                **task_data
            )
            
            logger.info(f"Executed scheduled task {task_name} with ID: {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to execute scheduled task {task_name}: {e}")


class ScheduledTaskTemplates:
    """Pre-defined templates for common scheduled tasks"""
    
    @staticmethod
    def daily_report_email(recipients: List[str], report_type: str = "daily") -> Dict[str, Any]:
        """Template for daily report emails"""
        return {
            'task_type': 'email',
            'kwargs': {
                'email_task': {
                    'to_addresses': recipients,
                    'subject': f'Daily Report - {datetime.now().strftime("%Y-%m-%d")}',
                    'body': f'Your {report_type} report is ready.',
                    'from_address': 'system@company.com'
                }
            }
        }
    
    @staticmethod
    def health_check_api(url: str, alert_emails: List[str] = None) -> Dict[str, Any]:
        """Template for API health check tasks"""
        return {
            'task_type': 'api_call',
            'kwargs': {
                'api_task': {
                    'url': url,
                    'method': 'GET',
                    'timeout': 30,
                    'expected_status_codes': [200]
                }
            },
            'metadata': {
                'alert_emails': alert_emails or [],
                'task_category': 'health_check'
            }
        }
    
    @staticmethod
    def data_backup(source: str, destination: str) -> Dict[str, Any]:
        """Template for data backup tasks"""
        return {
            'task_type': 'data_processing',
            'function_name': 'backup_data',
            'kwargs': {
                'source': source,
                'destination': destination,
                'timestamp': datetime.now().isoformat()
            },
            'metadata': {
                'task_category': 'backup'
            }
        }
    
    @staticmethod
    def weekly_cleanup() -> Dict[str, Any]:
        """Template for weekly cleanup tasks"""
        return {
            'task_type': 'data_processing',
            'function_name': 'cleanup_old_data',
            'kwargs': {
                'days_to_keep': 30,
                'cleanup_logs': True,
                'cleanup_temp_files': True
            },
            'metadata': {
                'task_category': 'maintenance'
            }
        }


# Example usage functions
async def setup_common_scheduled_tasks(scheduler: AdvancedScheduler):
    """Setup common scheduled tasks"""
    
    # Daily reports at 9 AM
    scheduler.schedule_cron_task(
        task_name="Daily Report",
        task_type="email",
        cron_expression="0 9 * * *",  # Every day at 9 AM
        task_data=ScheduledTaskTemplates.daily_report_email(["admin@company.com"])
    )
    
    # Health checks every 5 minutes
    scheduler.schedule_interval_task(
        task_name="API Health Check",
        task_type="api_call",
        interval_seconds=300,  # 5 minutes
        task_data=ScheduledTaskTemplates.health_check_api("http://localhost:8080/health")
    )
    
    # Weekly cleanup on Sundays at 2 AM
    scheduler.schedule_cron_task(
        task_name="Weekly Cleanup",
        task_type="data_processing",
        cron_expression="0 2 * * SUN",  # Every Sunday at 2 AM
        task_data=ScheduledTaskTemplates.weekly_cleanup()
    )
    
    # Monthly backup on the 1st of each month at 1 AM
    scheduler.schedule_cron_task(
        task_name="Monthly Backup",
        task_type="data_processing",
        cron_expression="0 1 1 * *",  # 1st day of month at 1 AM
        task_data=ScheduledTaskTemplates.data_backup("/data", "/backup")
    )
