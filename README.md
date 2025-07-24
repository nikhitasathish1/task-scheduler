# Task Orchestration Platform

A comprehensive, enterprise-grade task orchestration system built with FastAPI, PostgreSQL, Redis, and monitoring capabilities.

## Features

🪩 **Core Task Orchestration**
- Async task execution with priority queues
- Task dependencies and retry mechanisms
- Email and API call task types
- Custom task function registration

🪩 **Database & Persistence**
- PostgreSQL with async operations (asyncpg)
- Task history and audit logging
- Email and API call logging

🪩 **Queue Management**
- Redis-based priority queues
- Task caching and pub/sub notifications
- Worker thread management

🪩 **Monitoring & Metrics**
- Prometheus metrics integration
- Grafana dashboard
- Health checks and system metrics

🪩 **API & Validation**
- FastAPI with Pydantic models
- OpenAPI/Swagger documentation
- CORS support

## Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────┐
│   FastAPI App   │────│ Task         │────│  Workers    │
│   (HTTP API)    │    │ Orchestrator │    │  (Threads)  │
└─────────────────┘    └──────────────┘    └─────────────┘
         │                       │                  │
         │                       │                  │
    ┌─────────┐            ┌──────────┐      ┌─────────────┐
    │ Models  │            │   Redis  │      │ PostgreSQL │
    │(Pydantic)│           │ (Queues) │      │ (Persistence)│
    └─────────┘            └──────────┘      └─────────────┘
         │                       │                  │
         │               ┌───────────────┐    ┌──────────────┐
         └───────────────│  Prometheus   │────│   Grafana    │
                        │  (Metrics)    │    │ (Dashboard)  │
                        └───────────────┘    └──────────────┘
```

### 1. Clone and Setup

```bash
git clone <repository-url>
cd task-orchestrator
```

### 2. Environment Configuration

Update `config/config.yaml` with your settings:

```yaml
# Database Configuration
database:
  host: "postgres"
  port: 5433
  user: "postgres"
  password: "password123"
  database: "task_scheduler"

# Email Configuration (Optional)
email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  email: "your-email@gmail.com"
  password: "your-app-password"
```

### 3. Start with Docker Compose

```bash
docker-compose up -d
```

This will start:
- PostgreSQL database (port 5433)
- Redis (port 6379)
- Task Orchestrator API (port 8080)
- Prometheus (port 9090)
- Grafana (port 3000)

### 4. Access the Services

- **API Documentation**: http://localhost:8080/docs
- **Task API**: http://localhost:8080/api/v1/
- **Metrics**: http://localhost:8080/metrics
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin123)

## API Usage

### Create a Task

```bash
curl -X POST "http://localhost:8080/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Send Welcome Email",
    "task_type": "email",
    "priority": "high",
    "email_task": {
      "to_addresses": ["user@example.com"],
      "subject": "Welcome!",
      "body": "Welcome to our platform!",
      "from_address": "system@company.com"
    }
  }'
```

### Create an API Task

```bash
curl -X POST "http://localhost:8080/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "API Health Check",
    "task_type": "api_call",
    "priority": "medium",
    "api_task": {
      "url": "https://httpbin.org/get",
      "method": "GET",
      "timeout": 30
    }
  }'
```

### Schedule a Task

```bash
curl -X POST "http://localhost:8080/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily Report",
    "task_type": "email",
    "priority": "medium",
    "scheduled_at": "2024-12-25T09:00:00",
    "email_task": {
      "to_addresses": ["admin@company.com"],
      "subject": "Daily Report",
      "body": "Your daily report is ready.",
      "from_address": "system@company.com"
    }
  }'
```

### Get Task Status

```bash
curl "http://localhost:8080/api/v1/tasks/{task_id}"
```

### Cancel a Task

```bash
curl -X DELETE "http://localhost:8080/api/v1/tasks/{task_id}"
```

## Development Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start PostgreSQL and Redis

```bash
# Start only database services
docker-compose up postgres redis -d
```

### 3. Run Development Server

```bash
cd src
python main.py
```

## Advanced Features

### Custom Task Functions

```python
from task_orchestrator import TaskOrchestrator

orchestrator = TaskOrchestrator(config)

# Register custom function
def process_data(data_list):
    return {"processed": len(data_list), "sum": sum(data_list)}

orchestrator.register_task_function('process_data', process_data)

# Create task with custom function
await orchestrator.create_task(
    name="Process User Data",
    task_type="data_processing",
    function_name="process_data",
    args=[[1, 2, 3, 4, 5]]
)
```

### Scheduled Tasks with Cron

```python
from scheduler import AdvancedScheduler

scheduler = AdvancedScheduler(orchestrator)
await scheduler.start()

# Daily at 9 AM
scheduler.schedule_cron_task(
    task_name="Daily Backup",
    task_type="data_processing",
    cron_expression="0 9 * * *",
    task_data={
        "function_name": "backup_data",
        "kwargs": {"source": "/data", "dest": "/backup"}
    }
)
```

### Task Dependencies

```python
# Create dependent tasks
parent_task_id = await orchestrator.create_task(
    name="Data Extract",
    task_type="data_processing",
    function_name="extract_data"
)

child_task_id = await orchestrator.create_task(
    name="Data Transform",
    task_type="data_processing",
    function_name="transform_data",
    dependencies=[parent_task_id]  # Will wait for parent to complete
)
```

## Monitoring

### Prometheus Metrics

Available metrics:
- `task_orchestrator_tasks_total` - Total tasks created
- `task_orchestrator_tasks_completed` - Completed tasks
- `task_orchestrator_tasks_failed` - Failed tasks
- `task_orchestrator_tasks_running` - Currently running tasks
- `task_orchestrator_emails_sent` - Emails sent successfully
- `task_orchestrator_api_calls_made` - API calls made
- `task_orchestrator_execution_time_seconds` - Task execution time
- `task_orchestrator_queue_size` - Current queue size

### Grafana Dashboard

The included Grafana dashboard provides:
- Task status overview
- Execution time trends
- Email and API call metrics
- Queue size monitoring
- System health indicators

## Configuration Reference

### Database Settings

```yaml
database:
  host: "postgres"           # Database host
  port: 5433                # Database port
  user: "postgres"          # Database user
  password: "password123"   # Database password
  database: "task_scheduler" # Database name
  pool_size: 20             # Connection pool size
  max_overflow: 10          # Max pool overflow
```

### Worker Settings

```yaml
workers:
  count: 5                  # Number of worker threads
  max_queue_size: 10000     # Maximum queue size
  task_timeout: 300         # Default task timeout (seconds)
```

### Email Settings

```yaml
email:
  smtp_server: "smtp.gmail.com"  # SMTP server
  smtp_port: 587                 # SMTP port
  email: "your-email@gmail.com"  # SMTP username
  password: "app-password"       # SMTP password (use app password for Gmail)
```

## Production Deployment

### Environment Variables

Override config values using environment variables:

```bash
export DATABASE_HOST=your-db-host
export REDIS_HOST=your-redis-host
export WORKER_COUNT=10
export METRICS_PORT=8000
```

### Security Considerations

1. **Database Security**:
   - Use strong passwords
   - Enable SSL connections
   - Restrict database access

2. **Email Security**:
   - Use app passwords instead of account passwords
   - Configure proper SMTP authentication

3. **API Security**:
   - Implement authentication middleware
   - Use HTTPS in production
   - Configure proper CORS origins

4. **Redis Security**:
   - Enable authentication
   - Use TLS for connections
   - Restrict network access

## Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=src tests/
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**:
   - Check PostgreSQL is running
   - Verify connection settings
   - Ensure database exists

2. **Redis Connection Failed**:
   - Check Redis is running
   - Verify Redis URL configuration

3. **Email Tasks Failing**:
   - Check SMTP settings
   - Verify email credentials
   - Check firewall/network restrictions

4. **Tasks Not Processing**:
   - Check worker threads are running
   - Verify task queue status
   - Check for task dependencies

### Logs

Check application logs:
```bash
docker-compose logs task-orchestrator
```

