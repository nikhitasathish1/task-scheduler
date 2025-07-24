"""
Prometheus metrics endpoint for task orchestrator
"""

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from typing import Dict, Any
import time

# Prometheus metrics
task_counter = Counter('task_orchestrator_tasks_total', 'Total number of tasks created')
task_completed = Counter('task_orchestrator_tasks_completed', 'Number of completed tasks')
task_failed = Counter('task_orchestrator_tasks_failed', 'Number of failed tasks')
task_running = Gauge('task_orchestrator_tasks_running', 'Number of currently running tasks')
emails_sent = Counter('task_orchestrator_emails_sent', 'Number of emails sent')
emails_failed = Counter('task_orchestrator_emails_failed', 'Number of failed emails')
api_calls_made = Counter('task_orchestrator_api_calls_made', 'Number of API calls made')
api_calls_failed = Counter('task_orchestrator_api_calls_failed', 'Number of failed API calls')
execution_time = Histogram('task_orchestrator_execution_time_seconds', 'Task execution time in seconds')
queue_size = Gauge('task_orchestrator_queue_size', 'Current queue size')

class PrometheusMetrics:
    """Prometheus metrics integration"""
    
    def __init__(self):
        self.start_time = time.time()
    
    def increment_tasks_total(self):
        task_counter.inc()
    
    def increment_tasks_completed(self):
        task_completed.inc()
    
    def increment_tasks_failed(self):
        task_failed.inc()
    
    def set_tasks_running(self, count: int):
        task_running.set(count)
    
    def increment_emails_sent(self):
        emails_sent.inc()
    
    def increment_emails_failed(self):
        emails_failed.inc()
    
    def increment_api_calls_made(self):
        api_calls_made.inc()
    
    def increment_api_calls_failed(self):
        api_calls_failed.inc()
    
    def observe_execution_time(self, seconds: float):
        execution_time.observe(seconds)
    
    def set_queue_size(self, size: int):
        queue_size.set(size)
    
    def get_metrics_response(self) -> Response:
        """Get Prometheus metrics response"""
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    def get_uptime(self) -> float:
        """Get system uptime in seconds"""
        return time.time() - self.start_time

# Global metrics instance
prometheus_metrics = PrometheusMetrics()
