"""
Task Orchestrator Module

This module provides task orchestration capabilities with PostgreSQL, Redis, 
email handling, API task management, and monitoring integration.
"""

import asyncio
import json
import logging
import time
import uuid
import smtplib
import aiohttp
import aioredis
import asyncpg
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from threading import Thread, Lock
from contextlib import asynccontextmanager
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import structlog
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    SCHEDULED = "scheduled"


class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class TaskType(Enum):
    EMAIL = "email"
    API_CALL = "api_call"
    DATA_PROCESSING = "data_processing"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    NOTIFICATION = "notification"


@dataclass
class EmailConfig:
    """Email configuration for SMTP"""
    smtp_server: str
    smtp_port: int
    username: str
    password: str
    use_tls: bool = True
    use_ssl: bool = False


@dataclass
class EmailTask:
    """Email task specification"""
    to_addresses: List[str]
    subject: str
    body: str
    from_address: str
    cc_addresses: List[str] = None
    bcc_addresses: List[str] = None
    attachments: List[Dict[str, Any]] = None
    html_body: str = None
    reply_to: str = None
    
    def __post_init__(self):
        if self.cc_addresses is None:
            self.cc_addresses = []
        if self.bcc_addresses is None:
            self.bcc_addresses = []
        if self.attachments is None:
            self.attachments = []


@dataclass
class APITask:
    """API task specification"""
    url: str
    method: str = "GET"
    headers: Dict[str, str] = None
    params: Dict[str, Any] = None
    json_data: Dict[str, Any] = None
    form_data: Dict[str, Any] = None
    timeout: int = 30
    retry_on_failure: bool = True
    expected_status_codes: List[int] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.expected_status_codes is None:
            self.expected_status_codes = [200, 201, 202]


@dataclass
class Task:
    """Represents a task in the orchestration system"""
    id: str
    name: str
    task_type: TaskType
    function_name: str
    args: List[Any]
    kwargs: Dict[str, Any]
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 300
    dependencies: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TaskResult:
    """Represents the result of a task execution"""
    task_id: str
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class DatabaseManager:
    """Manages PostgreSQL database operations for task persistence"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
    
    async def initialize(self):
        """Initialize database connection pool and schema"""
        self.pool = await asyncpg.create_pool(self.database_url, min_size=5, max_size=20)
        await self.init_database()
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
    
    async def get_connection(self):
        """Get database connection from pool"""
        return self.pool.acquire()
    
    async def init_database(self):
        """Initialize the database schema"""
        async with self.pool.acquire() as conn:
            # Create tasks table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    task_type VARCHAR(50) NOT NULL,
                    function_name VARCHAR(255) NOT NULL,
                    args JSONB,
                    kwargs JSONB,
                    priority INTEGER,
                    status VARCHAR(20),
                    created_at TIMESTAMP WITH TIME ZONE,
                    scheduled_at TIMESTAMP WITH TIME ZONE,
                    started_at TIMESTAMP WITH TIME ZONE,
                    completed_at TIMESTAMP WITH TIME ZONE,
                    result JSONB,
                    error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    timeout INTEGER DEFAULT 300,
                    dependencies JSONB,
                    metadata JSONB
                )
            """)
            
            # Create task history table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS task_history (
                    id SERIAL PRIMARY KEY,
                    task_id VARCHAR(36),
                    status VARCHAR(20),
                    timestamp TIMESTAMP WITH TIME ZONE,
                    details JSONB,
                    worker_id VARCHAR(50)
                )
            """)
            
            # Create email logs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS email_logs (
                    id SERIAL PRIMARY KEY,
                    task_id VARCHAR(36),
                    to_addresses JSONB,
                    subject VARCHAR(500),
                    status VARCHAR(20),
                    sent_at TIMESTAMP WITH TIME ZONE,
                    error_message TEXT,
                    metadata JSONB
                )
            """)
            
            # Create API call logs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS api_call_logs (
                    id SERIAL PRIMARY KEY,
                    task_id VARCHAR(36),
                    url VARCHAR(1000),
                    method VARCHAR(10),
                    status_code INTEGER,
                    response_time FLOAT,
                    sent_at TIMESTAMP WITH TIME ZONE,
                    error_message TEXT,
                    metadata JSONB
                )
            """)
            
            # Create indices for better performance
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks (created_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_at ON tasks (scheduled_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_task_history_task_id ON task_history (task_id)")
    
    async def save_task(self, task: Task):
        """Save a task to the database"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO tasks VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19
                ) ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    started_at = EXCLUDED.started_at,
                    completed_at = EXCLUDED.completed_at,
                    result = EXCLUDED.result,
                    error = EXCLUDED.error,
                    retry_count = EXCLUDED.retry_count,
                    metadata = EXCLUDED.metadata
            """, 
                task.id, task.name, task.task_type.value, task.function_name,
                json.dumps(task.args), json.dumps(task.kwargs),
                task.priority.value, task.status.value,
                task.created_at, task.scheduled_at, task.started_at, task.completed_at,
                json.dumps(task.result) if task.result else None,
                task.error, task.retry_count, task.max_retries,
                task.timeout, json.dumps(task.dependencies), json.dumps(task.metadata)
            )
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task from the database"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
            if not row:
                return None
            
            return Task(
                id=row['id'], name=row['name'], task_type=TaskType(row['task_type']),
                function_name=row['function_name'], args=json.loads(row['args']) if row['args'] else [],
                kwargs=json.loads(row['kwargs']) if row['kwargs'] else {},
                priority=TaskPriority(row['priority']), status=TaskStatus(row['status']),
                created_at=row['created_at'], scheduled_at=row['scheduled_at'], started_at=row['started_at'],
                completed_at=row['completed_at'], result=json.loads(row['result']) if row['result'] else None,
                error=row['error'], retry_count=row['retry_count'], max_retries=row['max_retries'],
                timeout=row['timeout'], dependencies=json.loads(row['dependencies']) if row['dependencies'] else [],
                metadata=json.loads(row['metadata']) if row['metadata'] else {}
            )
    
    async def get_pending_tasks(self) -> List[Task]:
        """Get all pending and scheduled tasks"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM tasks 
                WHERE status IN ('pending', 'scheduled') 
                AND (scheduled_at IS NULL OR scheduled_at <= $1)
                ORDER BY priority DESC, created_at ASC
            """, datetime.now())
            
            tasks = []
            for row in rows:
                tasks.append(Task(
                    id=row['id'], name=row['name'], task_type=TaskType(row['task_type']),
                    function_name=row['function_name'], args=json.loads(row['args']) if row['args'] else [],
                    kwargs=json.loads(row['kwargs']) if row['kwargs'] else {},
                    priority=TaskPriority(row['priority']), status=TaskStatus(row['status']),
                    created_at=row['created_at'], scheduled_at=row['scheduled_at'], started_at=row['started_at'],
                    completed_at=row['completed_at'], result=json.loads(row['result']) if row['result'] else None,
                    error=row['error'], retry_count=row['retry_count'], max_retries=row['max_retries'],
                    timeout=row['timeout'], dependencies=json.loads(row['dependencies']) if row['dependencies'] else [],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                ))
            return tasks
    
    async def log_email(self, task_id: str, to_addresses: List[str], subject: str, 
                       status: str, error_message: str = None, metadata: Dict = None):
        """Log email sending attempt"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO email_logs (task_id, to_addresses, subject, status, sent_at, error_message, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, 
                task_id, json.dumps(to_addresses), subject, status,
                datetime.now(), error_message, json.dumps(metadata or {})
            )
    
    async def log_api_call(self, task_id: str, url: str, method: str, status_code: int,
                          response_time: float, error_message: str = None, metadata: Dict = None):
        """Log API call attempt"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO api_call_logs (task_id, url, method, status_code, response_time, sent_at, error_message, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, 
                task_id, url, method, status_code, response_time,
                datetime.now(), error_message, json.dumps(metadata or {})
            )


class RedisManager:
    """Manages Redis operations for caching and pub/sub"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = None
    
    async def connect(self):
        """Connect to Redis"""
        self.redis = await aioredis.from_url(self.redis_url, decode_responses=True)
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
    
    async def enqueue_task(self, task: Task):
        """Add task to Redis queue based on priority"""
        queue_name = f"task_queue:priority_{task.priority.value}"
        await self.redis.lpush(queue_name, task.id)
    
    async def dequeue_task(self) -> Optional[str]:
        """Get next task from highest priority queue"""
        # Check queues in priority order (highest first)
        for priority in [4, 3, 2, 1]:  # CRITICAL, HIGH, MEDIUM, LOW
            queue_name = f"task_queue:priority_{priority}"
            task_id = await self.redis.rpop(queue_name)
            if task_id:
                return task_id
        return None
    
    async def cache_result(self, task_id: str, result: Any, expiry: int = 3600):
        """Cache task result"""
        await self.redis.setex(f"task_result:{task_id}", expiry, json.dumps(result))
    
    async def get_cached_result(self, task_id: str) -> Optional[Any]:
        """Get cached task result"""
        result = await self.redis.get(f"task_result:{task_id}")
        return json.loads(result) if result else None
    
    async def publish_task_update(self, task_id: str, status: str, metadata: Dict = None):
        """Publish task status update"""
        message = {
            'task_id': task_id,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        await self.redis.publish('task_updates', json.dumps(message))


class EmailHandler:
    """Handles email sending tasks"""
    
    def __init__(self, email_config: EmailConfig):
        self.config = email_config
    
    async def send_email(self, email_task: EmailTask) -> Dict[str, Any]:
        """Send email using SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = email_task.subject
            msg['From'] = email_task.from_address
            msg['To'] = ', '.join(email_task.to_addresses)
            
            if email_task.cc_addresses:
                msg['Cc'] = ', '.join(email_task.cc_addresses)
            
            if email_task.reply_to:
                msg['Reply-To'] = email_task.reply_to
            
            # Add text body
            if email_task.body:
                text_part = MIMEText(email_task.body, 'plain')
                msg.attach(text_part)
            
            # Add HTML body
            if email_task.html_body:
                html_part = MIMEText(email_task.html_body, 'html')
                msg.attach(html_part)
            
            # Add attachments
            for attachment in email_task.attachments:
                if 'filename' in attachment and 'content' in attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    msg.attach(part)
            
            # Send email
            server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
            
            if self.config.use_tls:
                server.starttls()
            
            server.login(self.config.username, self.config.password)
            
            all_recipients = email_task.to_addresses + email_task.cc_addresses + email_task.bcc_addresses
            server.sendmail(email_task.from_address, all_recipients, msg.as_string())
            server.quit()
            
            return {
                'success': True,
                'message': 'Email sent successfully',
                'recipients': all_recipients,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


class APIHandler:
    """Handles API call tasks"""
    
    async def make_api_call(self, api_task: APITask) -> Dict[str, Any]:
        """Make HTTP API call"""
        start_time = time.time()
        
        try:
            timeout = aiohttp.ClientTimeout(total=api_task.timeout)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Prepare request parameters
                request_kwargs = {
                    'headers': api_task.headers,
                    'params': api_task.params
                }
                
                if api_task.json_data:
                    request_kwargs['json'] = api_task.json_data
                elif api_task.form_data:
                    request_kwargs['data'] = api_task.form_data
                
                # Make the request
                async with session.request(
                    api_task.method.upper(),
                    api_task.url,
                    **request_kwargs
                ) as response:
                    response_time = time.time() - start_time
                    response_text = await response.text()
                    
                    # Try to parse JSON response
                    try:
                        response_data = await response.json()
                    except:
                        response_data = response_text
                    
                    success = response.status in api_task.expected_status_codes
                    
                    return {
                        'success': success,
                        'status_code': response.status,
                        'response_time': response_time,
                        'response_data': response_data,
                        'headers': dict(response.headers),
                        'url': str(response.url),
                        'timestamp': datetime.now().isoformat()
                    }
                    
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"API call failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response_time': response_time,
                'timestamp': datetime.now().isoformat()
            }


class MetricsCollector:
    """Collects and manages metrics for Prometheus monitoring"""
    
    def __init__(self):
        self.metrics = {
            'tasks_total': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'tasks_running': 0,
            'emails_sent': 0,
            'emails_failed': 0,
            'api_calls_made': 0,
            'api_calls_failed': 0,
            'average_execution_time': 0.0,
            'queue_size': 0
        }
        self.execution_times = []
        self.lock = Lock()
    
    def increment_counter(self, metric: str):
        """Increment a counter metric"""
        with self.lock:
            if metric in self.metrics:
                self.metrics[metric] += 1
    
    def decrement_counter(self, metric: str):
        """Decrement a counter metric"""
        with self.lock:
            if metric in self.metrics and self.metrics[metric] > 0:
                self.metrics[metric] -= 1
    
    def record_execution_time(self, execution_time: float):
        """Record task execution time"""
        with self.lock:
            self.execution_times.append(execution_time)
            if len(self.execution_times) > 1000:
                self.execution_times = self.execution_times[-1000:]
            
            if self.execution_times:
                self.metrics['average_execution_time'] = sum(self.execution_times) / len(self.execution_times)
    
    def update_queue_size(self, size: int):
        """Update queue size metric"""
        with self.lock:
            self.metrics['queue_size'] = size
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        with self.lock:
            return self.metrics.copy()
    
    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus format"""
        metrics = self.get_metrics()
        prometheus_output = []
        
        for metric_name, value in metrics.items():
            prometheus_output.append(f"task_orchestrator_{metric_name} {value}")
        
        return '\n'.join(prometheus_output)


class TaskOrchestrator:
    """Main task orchestration engine with PostgreSQL, Redis, and email/API support"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_workers = config.get('workers', {}).get('count', 5)
        self.workers = []
        self.running_tasks = {}
        self.task_functions = {}
        self.is_running = False
        
        # Build database URL from config
        db_config = config['database']
        database_url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        
        # Build Redis URL from config
        redis_config = config['redis']
        redis_url = f"redis://{redis_config['host']}:{redis_config['port']}/{redis_config.get('db', 0)}"
        
        # Initialize components
        self.db_manager = DatabaseManager(database_url)
        self.redis_manager = RedisManager(redis_url)
        self.metrics = MetricsCollector()
        
        # Initialize email handler if configured
        email_config = config.get('email')
        if email_config and email_config.get('smtp_server'):
            self.email_handler = EmailHandler(EmailConfig(
                smtp_server=email_config['smtp_server'],
                smtp_port=email_config['smtp_port'],
                username=email_config['email'],
                password=email_config['password'],
                use_tls=True
            ))
        else:
            self.email_handler = None
        
        self.api_handler = APIHandler()
        
        logger.info(f"TaskOrchestrator initialized with {self.max_workers} workers")
    
    async def initialize(self):
        """Initialize the orchestrator components"""
        await self.db_manager.initialize()
        await self.redis_manager.connect()
        logger.info("TaskOrchestrator initialized successfully")
    
    async def start(self):
        """Start the task orchestrator"""
        self.is_running = True
        
        # Load pending tasks into Redis queues
        await self._load_pending_tasks()
        
        # Start worker threads
        for i in range(self.max_workers):
            worker = Thread(target=self._worker, args=(i,), daemon=True)
            worker.start()
            self.workers.append(worker)
        
        # Start scheduler thread
        scheduler = Thread(target=self._scheduler, daemon=True)
        scheduler.start()
        
        logger.info(f"Started TaskOrchestrator with {self.max_workers} workers")
    
    async def stop(self):
        """Stop the task orchestrator"""
        self.is_running = False
        await self.redis_manager.disconnect()
        await self.db_manager.close()
        logger.info("TaskOrchestrator stopped")
    
    def register_task_function(self, name: str, func: Callable):
        """Register a function that can be executed as a task"""
        self.task_functions[name] = func
        logger.info(f"Registered task function: {name}")
    
    async def create_task(self, name: str, task_type: TaskType, function_name: str = None,
                         args: List[Any] = None, kwargs: Dict[str, Any] = None,
                         priority: TaskPriority = TaskPriority.MEDIUM,
                         scheduled_at: datetime = None, max_retries: int = 3,
                         timeout: int = 300, dependencies: List[str] = None,
                         metadata: Dict[str, Any] = None) -> str:
        """Create a new task"""
        task_id = str(uuid.uuid4())
        
        # Set default function name based on task type
        if not function_name:
            function_name = f"{task_type.value}_handler"
        
        task = Task(
            id=task_id,
            name=name,
            task_type=task_type,
            function_name=function_name,
            args=args or [],
            kwargs=kwargs or {},
            priority=priority,
            status=TaskStatus.SCHEDULED if scheduled_at else TaskStatus.PENDING,
            created_at=datetime.now(),
            scheduled_at=scheduled_at,
            max_retries=max_retries,
            timeout=timeout,
            dependencies=dependencies or [],
            metadata=metadata or {}
        )
        
        # Save to database
        await self.db_manager.save_task(task)
        
        # Add to Redis queue if not scheduled
        if not scheduled_at:
            await self.redis_manager.enqueue_task(task)
        
        # Update metrics
        self.metrics.increment_counter('tasks_total')
        
        # Publish task creation event
        await self.redis_manager.publish_task_update(
            task_id, task.status.value, {'action': 'created'}
        )
        
        logger.info(f"Created task: {task_id} - {name}")
        return task_id
    
    async def create_email_task(self, name: str, email_task: EmailTask,
                               priority: TaskPriority = TaskPriority.MEDIUM,
                               scheduled_at: datetime = None) -> str:
        """Create an email task"""
        return await self.create_task(
            name=name,
            task_type=TaskType.EMAIL,
            kwargs={'email_task': asdict(email_task)},
            priority=priority,
            scheduled_at=scheduled_at,
            metadata={'email_recipients': email_task.to_addresses}
        )
    
    async def create_api_task(self, name: str, api_task: APITask,
                             priority: TaskPriority = TaskPriority.MEDIUM,
                             scheduled_at: datetime = None) -> str:
        """Create an API task"""
        return await self.create_task(
            name=name,
            task_type=TaskType.API_CALL,
            kwargs={'api_task': asdict(api_task)},
            priority=priority,
            scheduled_at=scheduled_at,
            metadata={'api_url': api_task.url, 'api_method': api_task.method}
        )
    
    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the status of a task"""
        task = await self.db_manager.get_task(task_id)
        return task.status if task else None
    
    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the result of a completed task"""
        task = await self.db_manager.get_task(task_id)
        if not task:
            return None
        
        return TaskResult(
            task_id=task.id,
            status=task.status,
            result=task.result,
            error=task.error,
            timestamp=task.completed_at or task.created_at,
            metadata=task.metadata
        )
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task"""
        task = await self.db_manager.get_task(task_id)
        if not task:
            return False
        
        if task.status in [TaskStatus.PENDING, TaskStatus.SCHEDULED]:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            await self.db_manager.save_task(task)
            
            # Publish cancellation event
            await self.redis_manager.publish_task_update(
                task_id, TaskStatus.CANCELLED.value, {'action': 'cancelled'}
            )
            
            logger.info(f"Cancelled task: {task_id}")
            return True
        
        return False
    
    async def _load_pending_tasks(self):
        """Load pending tasks from database into Redis queues"""
        pending_tasks = await self.db_manager.get_pending_tasks()
        
        for task in pending_tasks:
            if task.status == TaskStatus.PENDING:
                await self.redis_manager.enqueue_task(task)
        
        logger.info(f"Loaded {len(pending_tasks)} pending tasks into Redis queues")
    
    def _scheduler(self):
        """Scheduler thread that handles scheduled tasks"""
        while self.is_running:
            try:
                # Get scheduled tasks that are ready to run
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                ready_tasks = loop.run_until_complete(self._get_ready_scheduled_tasks())
                
                # Add ready tasks to Redis queues
                for task_id, priority in ready_tasks:
                    task = Task(id=task_id, priority=TaskPriority(priority), 
                               name="", task_type=TaskType.SCHEDULED, function_name="",
                               args=[], kwargs={}, status=TaskStatus.PENDING, created_at=datetime.now())
                    loop.run_until_complete(self.redis_manager.enqueue_task(task))
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(10)
    
    async def _get_ready_scheduled_tasks(self):
        """Get scheduled tasks that are ready to run"""
        async with self.db_manager.pool.acquire() as conn:
            rows = await conn.fetch("""
                UPDATE tasks SET status = 'pending'
                WHERE status = 'scheduled' AND scheduled_at <= $1
                RETURNING id, priority
            """, datetime.now())
            
            return [(row['id'], row['priority']) for row in rows]
    
    def _worker(self, worker_id: int):
        """Worker thread that processes tasks"""
        logger.info(f"Worker {worker_id} started")
        
        while self.is_running:
            try:
                # Get task from Redis queue
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                task_id = loop.run_until_complete(self.redis_manager.dequeue_task())
                
                if not task_id:
                    time.sleep(1)
                    continue
                
                # Get full task details from database
                task = loop.run_until_complete(self.db_manager.get_task(task_id))
                
                if not task:
                    continue
                
                # Check if task was cancelled
                if task.status == TaskStatus.CANCELLED:
                    continue
                
                # Check dependencies
                if not loop.run_until_complete(self._check_dependencies(task)):
                    # Put task back in queue to check later
                    loop.run_until_complete(self.redis_manager.enqueue_task(task))
                    time.sleep(1)
                    continue
                
                # Execute task
                loop.run_until_complete(self._execute_task(task, worker_id))
                
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                time.sleep(1)
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def _check_dependencies(self, task: Task) -> bool:
        """Check if all task dependencies are completed"""
        for dep_id in task.dependencies:
            dep_task = await self.db_manager.get_task(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True
    
    async def _execute_task(self, task: Task, worker_id: int):
        """Execute a single task"""
        start_time = time.time()
        
        # Update task status
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        await self.db_manager.save_task(task)
        self.running_tasks[task.id] = task
        
        # Update metrics
        self.metrics.increment_counter('tasks_running')
        
        # Publish task start event
        await self.redis_manager.publish_task_update(
            task.id, TaskStatus.RUNNING.value, {'worker_id': worker_id}
        )
        
        logger.info(f"Worker {worker_id} executing task: {task.id} - {task.name}")
        
        try:
            result = None
            
            # Execute based on task type
            if task.task_type == TaskType.EMAIL:
                result = await self._execute_email_task(task)
            elif task.task_type == TaskType.API_CALL:
                result = await self._execute_api_task(task)
            else:
                # Execute custom function
                if task.function_name not in self.task_functions:
                    raise ValueError(f"Unknown function: {task.function_name}")
                
                func = self.task_functions[task.function_name]
                result = func(*task.args, **task.kwargs)
            
            # Task completed successfully
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now()
            
            # Cache result in Redis
            await self.redis_manager.cache_result(task.id, result)
            
            # Update metrics
            self.metrics.decrement_counter('tasks_running')
            self.metrics.increment_counter('tasks_completed')
            
            # Publish completion event
            await self.redis_manager.publish_task_update(
                task.id, TaskStatus.COMPLETED.value, {'result': result}
            )
            
            logger.info(f"Task completed: {task.id}")
            
        except Exception as e:
            logger.error(f"Task failed: {task.id} - {str(e)}")
            
            # Handle retries
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.RETRYING
                
                # Put back in queue for retry with delay
                await asyncio.sleep(min(2 ** task.retry_count, 60))  # Exponential backoff
                await self.redis_manager.enqueue_task(task)
                
                logger.info(f"Retrying task: {task.id} (attempt {task.retry_count})")
            else:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.now()
                
                # Update metrics
                self.metrics.decrement_counter('tasks_running')
                self.metrics.increment_counter('tasks_failed')
                
                # Publish failure event
                await self.redis_manager.publish_task_update(
                    task.id, TaskStatus.FAILED.value, {'error': str(e)}
                )
        
        finally:
            # Record execution time
            execution_time = time.time() - start_time
            self.metrics.record_execution_time(execution_time)
            
            # Save task state
            await self.db_manager.save_task(task)
            
            # Remove from running tasks
            if task.id in self.running_tasks:
                del self.running_tasks[task.id]
    
    async def _execute_email_task(self, task: Task) -> Dict[str, Any]:
        """Execute an email task"""
        if not self.email_handler:
            raise ValueError("Email handler not configured")
        
        email_task_data = task.kwargs.get('email_task')
        if not email_task_data:
            raise ValueError("Email task data not provided")
        
        # Convert dict back to EmailTask object
        email_task = EmailTask(**email_task_data)
        
        # Send email
        result = await self.email_handler.send_email(email_task)
        
        # Log email attempt
        await self.db_manager.log_email(
            task.id, email_task.to_addresses, email_task.subject,
            'sent' if result['success'] else 'failed',
            result.get('error'), result
        )
        
        # Update email metrics
        if result['success']:
            self.metrics.increment_counter('emails_sent')
        else:
            self.metrics.increment_counter('emails_failed')
        
        return result
    
    async def _execute_api_task(self, task: Task) -> Dict[str, Any]:
        """Execute an API task"""
        api_task_data = task.kwargs.get('api_task')
        if not api_task_data:
            raise ValueError("API task data not provided")
        
        # Convert dict back to APITask object
        api_task = APITask(**api_task_data)
        
        # Make API call
        result = await self.api_handler.make_api_call(api_task)
        
        # Log API call attempt
        await self.db_manager.log_api_call(
            task.id, api_task.url, api_task.method,
            result.get('status_code', 0), result.get('response_time', 0),
            result.get('error'), result
        )
        
        # Update API metrics
        if result['success']:
            self.metrics.increment_counter('api_calls_made')
        else:
            self.metrics.increment_counter('api_calls_failed')
        
        return result
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current orchestrator metrics"""
        metrics = self.metrics.get_metrics()
        metrics.update({
            'is_running': self.is_running,
            'worker_count': len(self.workers),
            'running_tasks_count': len(self.running_tasks)
        })
        return metrics


class TaskOrchestrationAPI:
    """HTTP API interface for the task orchestrator"""
    
    def __init__(self, orchestrator: TaskOrchestrator):
        self.orchestrator = orchestrator
    
    async def create_task_endpoint(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """API endpoint to create a task"""
        try:
            # Parse task type
            task_type = TaskType(request_data.get('task_type', 'data_processing'))
            
            # Handle different task types
            if task_type == TaskType.EMAIL:
                email_data = request_data.get('email_task', {})
                email_task = EmailTask(**email_data)
                task_id = await self.orchestrator.create_email_task(
                    name=request_data.get('name'),
                    email_task=email_task,
                    priority=TaskPriority(request_data.get('priority', TaskPriority.MEDIUM.value)),
                    scheduled_at=datetime.fromisoformat(request_data['scheduled_at']) if request_data.get('scheduled_at') else None
                )
            elif task_type == TaskType.API_CALL:
                api_data = request_data.get('api_task', {})
                api_task = APITask(**api_data)
                task_id = await self.orchestrator.create_api_task(
                    name=request_data.get('name'),
                    api_task=api_task,
                    priority=TaskPriority(request_data.get('priority', TaskPriority.MEDIUM.value)),
                    scheduled_at=datetime.fromisoformat(request_data['scheduled_at']) if request_data.get('scheduled_at') else None
                )
            else:
                task_id = await self.orchestrator.create_task(
                    name=request_data.get('name'),
                    task_type=task_type,
                    function_name=request_data.get('function_name'),
                    args=request_data.get('args', []),
                    kwargs=request_data.get('kwargs', {}),
                    priority=TaskPriority(request_data.get('priority', TaskPriority.MEDIUM.value)),
                    scheduled_at=datetime.fromisoformat(request_data['scheduled_at']) if request_data.get('scheduled_at') else None,
                    max_retries=request_data.get('max_retries', 3),
                    timeout=request_data.get('timeout', 300),
                    dependencies=request_data.get('dependencies', []),
                    metadata=request_data.get('metadata', {})
                )
            
            return {
                'success': True,
                'task_id': task_id,
                'message': 'Task created successfully'
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to create task'
            }
    
    async def get_task_status_endpoint(self, task_id: str) -> Dict[str, Any]:
        """API endpoint to get task status"""
        try:
            status = await self.orchestrator.get_task_status(task_id)
            if status:
                return {
                    'success': True,
                    'task_id': task_id,
                    'status': status.value
                }
            else:
                return {
                    'success': False,
                    'message': 'Task not found'
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to get task status'
            }
    
    async def get_task_result_endpoint(self, task_id: str) -> Dict[str, Any]:
        """API endpoint to get task result"""
        try:
            result = await self.orchestrator.get_task_result(task_id)
            if result:
                return {
                    'success': True,
                    'task_id': task_id,
                    'status': result.status.value,
                    'result': result.result,
                    'error': result.error,
                    'timestamp': result.timestamp.isoformat(),
                    'metadata': result.metadata
                }
            else:
                return {
                    'success': False,
                    'message': 'Task not found'
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to get task result'
            }
    
    # Add this as an alias for backward compatibility
    async def get_task_endpoint(self, task_id: str) -> Dict[str, Any]:
        """API endpoint to get task (alias for get_task_result_endpoint)"""
        return await self.get_task_result_endpoint(task_id)
    
    async def cancel_task_endpoint(self, task_id: str) -> Dict[str, Any]:
        """API endpoint to cancel a task"""
        try:
            success = await self.orchestrator.cancel_task(task_id)
            if success:
                return {
                    'success': True,
                    'task_id': task_id,
                    'message': 'Task cancelled successfully'
                }
            else:
                return {
                    'success': False,
                    'message': 'Task not found or cannot be cancelled'
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to cancel task'
            }
    
    async def get_metrics_endpoint(self) -> Dict[str, Any]:
        """API endpoint to get orchestrator metrics"""
        try:
            metrics = self.orchestrator.get_metrics()
            return {
                'success': True,
                'metrics': metrics
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to get metrics'
            }
    
    def get_prometheus_metrics_endpoint(self) -> str:
        """API endpoint to get metrics in Prometheus format"""
        return self.orchestrator.metrics.get_prometheus_metrics()


# Example usage and setup functions
def create_email_config_from_env() -> EmailConfig:
    """Create email configuration from environment variables"""
    return EmailConfig(
        smtp_server=os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
        smtp_port=int(os.getenv('SMTP_PORT', '587')),
        username=os.getenv('SMTP_USERNAME', ''),
        password=os.getenv('SMTP_PASSWORD', ''),
        use_tls=os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
    )


async def setup_orchestrator() -> TaskOrchestrator:
    """Setup orchestrator with environment configuration"""
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:password123@localhost:5433/task_scheduler')
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    worker_count = int(os.getenv('WORKER_COUNT', '5'))
    
    # Setup email configuration
    email_config = None
    if os.getenv('SMTP_SERVER'):
        email_config = create_email_config_from_env()
    
    # Create orchestrator
    orchestrator = TaskOrchestrator(
        database_url=database_url,
        redis_url=redis_url,
        max_workers=worker_count,
        email_config=email_config
    )
    
    # Register built-in task functions
    orchestrator.register_task_function('sample_task', sample_task)
    orchestrator.register_task_function('data_processing_task', data_processing_task)
    orchestrator.register_task_function('webhook_task', webhook_task)
    
    return orchestrator


# Example task functions
def sample_task(message: str, delay: int = 1) -> str:
    """Sample task function for testing"""
    time.sleep(delay)
    return f"Processed: {message}"


def data_processing_task(data: List[int]) -> Dict[str, Any]:
    """Sample data processing task"""
    if not data:
        raise ValueError("No data provided")
    
    return {
        'sum': sum(data),
        'average': sum(data) / len(data),
        'min': min(data),
        'max': max(data),
        'count': len(data),
        'timestamp': datetime.now().isoformat()
    }


async def webhook_task(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Webhook notification task"""
    api_task = APITask(
        url=url,
        method='POST',
        json_data=payload,
        headers={'Content-Type': 'application/json'}
    )
    
    api_handler = APIHandler()
    return await api_handler.make_api_call(api_task)


if __name__ == "__main__":
    # Example usage
    async def main():
        orchestrator = await setup_orchestrator()
        await orchestrator.start()
        
        # Create sample email task
        if orchestrator.email_handler:
            email_task = EmailTask(
                to_addresses=['user@example.com'],
                subject='Test Email',
                body='This is a test email from the task orchestrator',
                from_address='system@example.com'
            )
            
            email_task_id = await orchestrator.create_email_task(
                name="Welcome Email",
                email_task=email_task,
                priority=TaskPriority.HIGH
            )
            print(f"Created email task: {email_task_id}")
        
        # Create sample API task
        api_task = APITask(
            url='https://httpbin.org/post',
            method='POST',
            json_data={'message': 'Hello from task orchestrator'},
            timeout=30
        )
        
        api_task_id = await orchestrator.create_api_task(
            name="API Test",
            api_task=api_task,
            priority=TaskPriority.MEDIUM
        )
        print(f"Created API task: {api_task_id}")
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(10)
                metrics = orchestrator.get_metrics()
                print(f"Metrics: {metrics}")
        except KeyboardInterrupt:
            await orchestrator.stop()
            print("Orchestrator stopped")
    
    asyncio.run(main())