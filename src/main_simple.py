"""
Task Orchestrator Main Application - Enhanced Version with Task Management
"""

import yaml
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load configuration
config_path = Path(__file__).parent.parent / "config" / "config.yaml"
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Pydantic Models
class TaskType(str, Enum):
    EMAIL = "email"
    API_CALL = "api_call"
    DATA_PROCESSING = "data_processing"

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class EmailTask(BaseModel):
    to_addresses: List[str]
    subject: str
    body: str
    from_address: Optional[str] = None
    cc_addresses: Optional[List[str]] = None
    bcc_addresses: Optional[List[str]] = None

class ApiTask(BaseModel):
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    payload: Optional[Dict[str, Any]] = None
    timeout: int = 30

class TaskCreate(BaseModel):
    name: str = Field(..., description="Task name")
    task_type: TaskType = Field(..., description="Type of task")
    priority: Priority = Field(default=Priority.MEDIUM, description="Task priority")
    scheduled_at: Optional[datetime] = Field(None, description="When to execute the task")
    dependencies: Optional[List[str]] = Field(None, description="Task dependencies (task IDs)")
    email_task: Optional[EmailTask] = None
    api_task: Optional[ApiTask] = None
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    timeout: int = Field(default=300, description="Task timeout in seconds")

class TaskResponse(BaseModel):
    task_id: str
    name: str
    task_type: TaskType
    priority: Priority
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3

# In-memory task storage (for demonstration - would be replaced with database)
tasks_db: Dict[str, TaskResponse] = {}
task_queue: List[str] = []

app = FastAPI(
    title="Task Orchestration Platform",
    description="Enterprise-grade task scheduling and execution system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config['security']['cors_origins'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "task-orchestrator", "version": "1.0.0"}

@app.get("/")
async def root():
    return {"message": "Task Orchestration Platform", "version": "1.0.0"}

@app.get("/api/v1/status")
async def api_status():
    return {
        "api": "operational",
        "services": {
            "database": "healthy",
            "redis": "healthy", 
            "workers": f"running ({len(task_queue)} tasks queued)"
        },
        "tasks": {
            "total": len(tasks_db),
            "pending": len([t for t in tasks_db.values() if t.status == TaskStatus.PENDING]),
            "running": len([t for t in tasks_db.values() if t.status == TaskStatus.RUNNING]),
            "completed": len([t for t in tasks_db.values() if t.status == TaskStatus.COMPLETED]),
            "failed": len([t for t in tasks_db.values() if t.status == TaskStatus.FAILED])
        }
    }

@app.post("/api/v1/tasks", response_model=TaskResponse)
async def create_task(task_data: TaskCreate):
    """Create a new task"""
    
    # Validate task type specific data
    if task_data.task_type == TaskType.EMAIL and not task_data.email_task:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email task data is required for email tasks"
        )
    
    if task_data.task_type == TaskType.API_CALL and not task_data.api_task:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API task data is required for API call tasks"
        )
    
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    
    # Create task response object
    now = datetime.now()
    task = TaskResponse(
        task_id=task_id,
        name=task_data.name,
        task_type=task_data.task_type,
        priority=task_data.priority,
        status=TaskStatus.PENDING,
        created_at=now,
        updated_at=now,
        scheduled_at=task_data.scheduled_at,
        max_retries=task_data.max_retries
    )
    
    # Store task
    tasks_db[task_id] = task
    
    # Add to queue if not scheduled for future
    if not task_data.scheduled_at or task_data.scheduled_at <= now:
        task_queue.append(task_id)
        # Simulate task processing
        asyncio.create_task(process_task(task_id, task_data))
    
    return task

@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get task by ID"""
    if task_id not in tasks_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    
    return tasks_db[task_id]

@app.get("/api/v1/tasks", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[TaskStatus] = None,
    task_type: Optional[TaskType] = None,
    limit: int = 50,
    offset: int = 0
):
    """List tasks with optional filtering"""
    
    filtered_tasks = list(tasks_db.values())
    
    # Apply filters
    if status:
        filtered_tasks = [t for t in filtered_tasks if t.status == status]
    
    if task_type:
        filtered_tasks = [t for t in filtered_tasks if t.task_type == task_type]
    
    # Sort by created_at descending
    filtered_tasks.sort(key=lambda x: x.created_at, reverse=True)
    
    # Apply pagination
    return filtered_tasks[offset:offset + limit]

@app.delete("/api/v1/tasks/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a task"""
    if task_id not in tasks_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    
    task = tasks_db[task_id]
    
    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel task in {task.status} status"
        )
    
    # Update task status
    task.status = TaskStatus.CANCELLED
    task.updated_at = datetime.now()
    
    # Remove from queue if present
    if task_id in task_queue:
        task_queue.remove(task_id)
    
    return {"message": f"Task {task_id} cancelled successfully"}

async def process_task(task_id: str, task_data: TaskCreate):
    """Simulate task processing"""
    task = tasks_db[task_id]
    
    try:
        # Update status to running
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        task.updated_at = datetime.now()
        
        # Simulate processing time
        await asyncio.sleep(2)
        
        # Simulate task execution based on type
        if task_data.task_type == TaskType.EMAIL:
            result = {
                "emails_sent": len(task_data.email_task.to_addresses),
                "subject": task_data.email_task.subject,
                "message": "Email task completed successfully"
            }
        elif task_data.task_type == TaskType.API_CALL:
            result = {
                "url": task_data.api_task.url,
                "method": task_data.api_task.method,
                "status_code": 200,
                "message": "API call completed successfully"
            }
        else:
            result = {"message": "Data processing task completed successfully"}
        
        # Update task as completed
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        task.updated_at = datetime.now()
        task.result = result
        
        # Remove from queue
        if task_id in task_queue:
            task_queue.remove(task_id)
            
    except Exception as e:
        # Handle task failure
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        task.updated_at = datetime.now()
        
        # Remove from queue
        if task_id in task_queue:
            task_queue.remove(task_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main_simple:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
