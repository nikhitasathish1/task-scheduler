"""
Pydantic models for task orchestration API
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator

class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    SCHEDULED = "scheduled"

class TaskPriorityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TaskTypeEnum(str, Enum):
    EMAIL = "email"
    API_CALL = "api_call"
    DATA_PROCESSING = "data_processing"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    NOTIFICATION = "notification"

class EmailTaskModel(BaseModel):
    """Pydantic model for email tasks"""
    to_addresses: List[str] = Field(..., min_items=1, description="Recipient email addresses")
    subject: str = Field(..., min_length=1, description="Email subject")
    body: str = Field(..., min_length=1, description="Email body text")
    from_address: str = Field(..., description="Sender email address")
    cc_addresses: Optional[List[str]] = Field(default=[], description="CC email addresses")
    bcc_addresses: Optional[List[str]] = Field(default=[], description="BCC email addresses")
    html_body: Optional[str] = Field(default=None, description="HTML email body")
    reply_to: Optional[str] = Field(default=None, description="Reply-to email address")
    attachments: Optional[List[Dict[str, Any]]] = Field(default=[], description="Email attachments")

class APITaskModel(BaseModel):
    """Pydantic model for API tasks"""
    url: str = Field(..., description="Target URL for the API call")
    method: str = Field(default="GET", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(default={}, description="HTTP headers")
    params: Optional[Dict[str, Any]] = Field(default={}, description="Query parameters")
    json_data: Optional[Dict[str, Any]] = Field(default=None, description="JSON payload")
    form_data: Optional[Dict[str, Any]] = Field(default=None, description="Form data")
    timeout: int = Field(default=30, gt=0, le=300, description="Request timeout in seconds")
    retry_on_failure: bool = Field(default=True, description="Whether to retry on failure")
    expected_status_codes: Optional[List[int]] = Field(default=[200, 201, 202], description="Expected status codes")
    
    @validator('method')
    def validate_method(cls, v):
        allowed_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
        if v.upper() not in allowed_methods:
            raise ValueError(f'Method must be one of {allowed_methods}')
        return v.upper()

class TaskCreateRequest(BaseModel):
    """Request model for creating a task"""
    name: str = Field(..., min_length=1, max_length=255, description="Task name")
    task_type: TaskTypeEnum = Field(..., description="Type of task to create")
    function_name: Optional[str] = Field(default=None, description="Function name to execute")
    args: Optional[List[Any]] = Field(default=[], description="Function arguments")
    kwargs: Optional[Dict[str, Any]] = Field(default={}, description="Function keyword arguments")
    priority: TaskPriorityEnum = Field(default=TaskPriorityEnum.MEDIUM, description="Task priority")
    scheduled_at: Optional[datetime] = Field(default=None, description="When to execute the task")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    timeout: int = Field(default=300, gt=0, le=3600, description="Task timeout in seconds")
    dependencies: Optional[List[str]] = Field(default=[], description="Task dependencies")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")
    
    # Task-specific data
    email_task: Optional[EmailTaskModel] = Field(default=None, description="Email task configuration")
    api_task: Optional[APITaskModel] = Field(default=None, description="API task configuration")
    
    @validator('email_task')
    def validate_email_task(cls, v, values):
        if values.get('task_type') == TaskTypeEnum.EMAIL and v is None:
            raise ValueError('email_task is required when task_type is EMAIL')
        return v
    
    @validator('api_task')
    def validate_api_task(cls, v, values):
        if values.get('task_type') == TaskTypeEnum.API_CALL and v is None:
            raise ValueError('api_task is required when task_type is API_CALL')
        return v

class TaskResponse(BaseModel):
    """Response model for task operations"""
    success: bool
    task_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

class TaskStatusResponse(BaseModel):
    """Response model for task status"""
    success: bool
    task_id: str
    status: TaskStatusEnum
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Optional[Dict[str, Any]] = None

class TaskResultResponse(BaseModel):
    """Response model for task results"""
    success: bool
    task_id: str
    status: TaskStatusEnum
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

class MetricsResponse(BaseModel):
    """Response model for system metrics"""
    success: bool
    metrics: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)

class TaskListResponse(BaseModel):
    """Response model for task list"""
    success: bool
    tasks: List[TaskStatusResponse]
    total_count: int
    page: int = 1
    page_size: int = 50

class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str = "healthy"
    service: str = "task-orchestrator"
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str = "1.0.0"
    uptime: Optional[float] = None
