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

### 2. Start with Docker Compose

```bash
docker-compose up -d
```

This will start:
- PostgreSQL database (port 5433)
- Redis (port 6379)
- Task Orchestrator API (port 8080)
- Prometheus (port 9090)
- Grafana (port 3000)

### 3. Access the Services

- **API Documentation**: http://localhost:8080/docs
- **Task API**: http://localhost:8080/api/v1/
- **Metrics**: http://localhost:8080/metrics
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin123)

## API Usage

### Create an Email Task

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
    "scheduled_at": "2025-08-25T09:00:00",
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


### Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=src tests/
```


### Logs

Check application logs:
```bash
docker-compose logs task-orchestrator
```

