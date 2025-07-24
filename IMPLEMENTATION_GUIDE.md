# Task Orchestrator - Complete Implementation Guide

This guide will walk you through implementing the Task Orchestration Platform from scratch, step by step.

## Prerequisites

Before starting, ensure you have:
- Python 3.11 or higher
- Docker and Docker Compose
- Git
- A code editor (VS Code recommended)

## Step 1: Project Setup

### 1.1 Create Project Directory
```bash
mkdir task-orchestrator
cd task-orchestrator
```

### 1.2 Initialize Git Repository
```bash
git init
echo "# Task Orchestration Platform" > README.md
git add README.md
git commit -m "Initial commit"
```

### 1.3 Create Project Structure
```bash
# Create directories
mkdir -p src tests examples config/grafana logs

# Create empty files
touch src/__init__.py
touch tests/__init__.py
touch requirements.txt
touch Dockerfile
touch docker-compose.yml
touch config/config.yaml
touch config/init.sql
touch config/prometheus.yml
```

Your project structure should look like:
```
task-orchestrator/
├── src/
│   └── __init__.py
├── tests/
│   └── __init__.py
├── examples/
├── config/
│   ├── grafana/
│   ├── config.yaml
│   ├── init.sql
│   └── prometheus.yml
├── logs/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Step 2: Dependencies and Configuration

### 2.1 Create requirements.txt
```txt
# Core web framework
fastapi==0.104.1
uvicorn[standard]==0.24.0

# Async database and Redis
asyncpg==0.29.0
aioredis==2.0.1
aiohttp==3.9.0

# Task scheduling
APScheduler==3.10.4

# Configuration and data handling
PyYAML==6.0.1
structlog==23.2.0
pydantic==2.5.2

# Email functionality
aiosmtplib==3.0.0

# Monitoring and metrics
prometheus-client==0.19.0

# Additional utilities
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# Development dependencies
pytest==7.4.3
pytest-asyncio==0.21.1
black==23.11.0
flake8==6.1.0
```

### 2.2 Create config/config.yaml
```yaml
# Application Configuration
app:
  name: "Task Orchestration Platform"
  version: "1.0.0"
  debug: false

# Database Configuration
database:
  host: "postgres"
  port: 5432
  user: "postgres"
  password: "password123"
  database: "task_scheduler"
  pool_size: 20
  max_overflow: 10

# Redis Configuration
redis:
  host: "redis"
  port: 6379
  db: 0
  max_connections: 20

# Worker Configuration
workers:
  count: 5
  max_queue_size: 10000
  task_timeout: 300

# Email Configuration (Update with your credentials)
email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  email: "your-email@gmail.com"
  password: "your-app-password"  # Use app password for Gmail

# Monitoring
monitoring:
  metrics_port: 8000
  log_level: "INFO"
  structured_logging: true

# Security
security:
  api_key: "your-secret-api-key"
  cors_origins:
    - "http://localhost:3000"
    - "http://localhost:8080"
```

### 2.3 Create config/init.sql
```sql
-- Database initialization script
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create database user for the application
-- (This is handled by the POSTGRES_USER environment variable)

-- Additional indexes for performance
-- These will be created by the application, but you can add custom ones here

-- Example: Create a custom index for faster task lookups
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_custom_metadata 
-- ON tasks USING GIN (metadata);
```

### 2.4 Create config/prometheus.yml
```yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'task-orchestrator'
    static_configs:
      - targets: ['task-orchestrator:8000']
    scrape_interval: 5s
    metrics_path: /metrics
```

## Step 3: Docker Configuration

### 3.1 Create Dockerfile
```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create logs directory
RUN mkdir -p logs

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Expose ports
EXPOSE 8080 8000

# Health check using Python
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# Run the application
CMD ["python", "src/main.py"]
```

### 3.2 Create docker-compose.yml
```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: task_scheduler
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./config/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis for job storage and caching
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # Task Orchestrator Application
  task-orchestrator:
    build: .
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql://postgres:password123@postgres:5432/task_scheduler
      - REDIS_URL=redis://redis:6379
      - METRICS_PORT=8000
      - WORKER_COUNT=5
    ports:
      - "8000:8000"  # Metrics
      - "8080:8080"  # API
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config
    restart: unless-stopped

  # Prometheus for metrics collection
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  # Grafana for dashboards
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
    volumes:
      - grafana_data:/var/lib/grafana
      - ./config/grafana:/etc/grafana/provisioning

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

## Step 4: Core Implementation

### 4.1 Create src/models.py
```python
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

class MetricsResponse(BaseModel):
    """Response model for system metrics"""
    success: bool
    metrics: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)

class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str = "healthy"
    service: str = "task-orchestrator"
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str = "1.0.0"
    uptime: Optional[float] = None
```

### 4.2 Create src/task_orchestrator.py
This is a large file, so I'll provide it in the next step. For now, let's continue with the setup.

## Step 5: Initial Setup Test

### 5.1 Create a simple test to verify setup
Create `src/main.py` (simplified version first):

```python
"""
Task Orchestrator Main Application - Initial Version
"""

import yaml
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load configuration
config_path = Path(__file__).parent.parent / "config" / "config.yaml"
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

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
    return {"status": "healthy", "service": "task-orchestrator"}

@app.get("/")
async def root():
    return {"message": "Task Orchestration Platform", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
```

### 5.2 Test the basic setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Start databases only**:
```bash
docker-compose up postgres redis -d
```

3. **Test the basic API**:
```bash
cd src
python main.py
```

4. **Verify it works**:
- Open http://localhost:8080/docs in your browser
- You should see the FastAPI documentation
- Check http://localhost:8080/health

## Step 6: Implement Core Components

Now we'll implement the main components step by step.

### 6.1 Next Steps
Once you've verified the basic setup works, we'll implement:

1. **Database Models and Connections** (Step 7)
2. **Task Orchestrator Core** (Step 8)
3. **Workers and Queue Management** (Step 9)
4. **API Endpoints** (Step 10)
5. **Monitoring and Metrics** (Step 11)
6. **Advanced Scheduling** (Step 12)
7. **Testing and Examples** (Step 13)

## What to Do Now

1. **Create the project structure** as shown above
2. **Copy all the configuration files** (requirements.txt, config.yaml, etc.)
3. **Test the basic setup** with the simple main.py
4. **Verify databases start** with docker-compose

## How to Run the Task Orchestrator

### Option 1: Quick Start with Docker (Recommended)

This is the easiest way to get everything running:

```bash
# 1. Clone your repository or create the project structure
git clone <your-repo-url>
cd task-orchestrator

# 2. Make sure you have all the files from the steps above
# (requirements.txt, docker-compose.yml, config files, etc.)

# 3. Start everything with Docker Compose
docker-compose up -d

# 4. Check if services are running
docker-compose ps

# 5. View logs
docker-compose logs -f task-orchestrator
```

**Access the services:**
- API Documentation: http://localhost:8080/docs
- Health Check: http://localhost:8080/health
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin123)

### Option 2: Development Setup (Local Python)

For development and testing:

```bash
# 1. Set up Python environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start only the databases
docker-compose up postgres redis -d

# 4. Run the application locally
cd src
python main.py
```

### Option 3: Step-by-Step Manual Setup

If you want to build everything from scratch:

#### Step A: Create the Basic Structure

```bash
# Create project
mkdir task-orchestrator
cd task-orchestrator

# Create directories
mkdir -p src tests examples config/grafana logs

# Create empty files
touch src/__init__.py
touch tests/__init__.py
```

#### Step B: Create Configuration Files

1. **Create requirements.txt**:
```bash
cat > requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
asyncpg==0.29.0
aioredis==2.0.1
aiohttp==3.9.0
APScheduler==3.10.4
PyYAML==6.0.1
structlog==23.2.0
pydantic==2.5.2
aiosmtplib==3.0.0
prometheus-client==0.19.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
pytest==7.4.3
pytest-asyncio==0.21.1
black==23.11.0
flake8==6.1.0
EOF
```

2. **Create config/config.yaml**:
```bash
cat > config/config.yaml << 'EOF'
app:
  name: "Task Orchestration Platform"
  version: "1.0.0"
  debug: false

database:
  host: "postgres"
  port: 5432
  user: "postgres"
  password: "password123"
  database: "task_scheduler"
  pool_size: 20
  max_overflow: 10

redis:
  host: "redis"
  port: 6379
  db: 0
  max_connections: 20

workers:
  count: 5
  max_queue_size: 10000
  task_timeout: 300

email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  email: "your-email@gmail.com"
  password: "your-app-password"

monitoring:
  metrics_port: 8000
  log_level: "INFO"
  structured_logging: true

security:
  api_key: "your-secret-api-key"
  cors_origins:
    - "http://localhost:3000"
    - "http://localhost:8080"
EOF
```

3. **Create docker-compose.yml** (copy from Step 3.2 above)

4. **Create a simple main.py for testing**:
```bash
cat > src/main.py << 'EOF'
import yaml
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

config_path = Path(__file__).parent.parent / "config" / "config.yaml"
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

app = FastAPI(
    title="Task Orchestration Platform",
    description="Enterprise-grade task scheduling and execution system",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config['security']['cors_origins'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "task-orchestrator"}

@app.get("/")
async def root():
    return {"message": "Task Orchestration Platform", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
EOF
```

#### Step C: Test the Basic Setup

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Start databases
docker-compose up postgres redis -d

# 3. Test the API
cd src
python main.py
```

**Verify it works:**
- Open http://localhost:8080/docs
- Check http://localhost:8080/health

## Troubleshooting

### Common Issues and Solutions

1. **Port already in use**:
```bash
# Check what's using the port
lsof -i :8080
# Kill the process or change ports in docker-compose.yml
```

2. **Docker permission denied**:
```bash
# On Linux, add user to docker group
sudo usermod -aG docker $USER
# Then logout and login again
```

3. **Database connection failed**:
```bash
# Check if PostgreSQL is running
docker-compose ps
# Check logs
docker-compose logs postgres
```

4. **Module not found errors**:
```bash
# Make sure you're in the right directory and venv is active
pwd
which python
pip list
```

### Useful Commands

```bash
# View all running containers
docker-compose ps

# Stop all services
docker-compose down

# Restart a specific service
docker-compose restart task-orchestrator

# View logs for all services
docker-compose logs -f

# View logs for specific service
docker-compose logs -f postgres

# Remove all data (fresh start)
docker-compose down -v

# Build and restart after code changes
docker-compose up --build -d
```

## Quick Test

Once everything is running, test the API:

```bash
# Health check
curl http://localhost:8080/health

# Create a simple task (when full implementation is ready)
curl -X POST "http://localhost:8080/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Task",
    "task_type": "data_processing",
    "function_name": "test_function"
  }'
```

---

Once you have this basic foundation working, I'll guide you through implementing each component step by step.

Would you like me to continue with Step 7 (Database Implementation) or do you need help with any of the setup steps above?
