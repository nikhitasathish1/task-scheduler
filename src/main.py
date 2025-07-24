import asyncio
import os
import yaml
from pathlib import Path
from task_orchestrator import TaskOrchestrator, TaskOrchestrationAPI
from models import TaskCreateRequest, TaskResponse, TaskStatusResponse, MetricsResponse, HealthResponse
from metrics import prometheus_metrics
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Load configuration
config_path = Path(__file__).parent.parent / "config" / "config.yaml"
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Override with environment variables
config['database']['host'] = os.getenv('DATABASE_HOST', config['database']['host'])
config['redis']['host'] = os.getenv('REDIS_HOST', config['redis']['host'])

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

# Global orchestrator instance
orchestrator = None
api_wrapper = None

@app.on_event("startup")
async def startup():
    global orchestrator, api_wrapper
    orchestrator = TaskOrchestrator(config)
    await orchestrator.initialize()
    await orchestrator.start()
    api_wrapper = TaskOrchestrationAPI(orchestrator)
    print("🚀 Task Orchestration Platform started successfully!")

@app.on_event("shutdown")
async def shutdown():
    global orchestrator
    if orchestrator:
        await orchestrator.stop()
    print("👋 Task Orchestration Platform stopped")

# API Endpoints
@app.post("/api/v1/tasks", response_model=TaskResponse)
async def create_task(task_data: TaskCreateRequest):
    if not api_wrapper:
        raise HTTPException(status_code=503, detail="Service not ready")
    return await api_wrapper.create_task_endpoint(task_data.dict())

@app.get("/api/v1/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task(task_id: str):
    if not api_wrapper:
        raise HTTPException(status_code=503, detail="Service not ready")
    return await api_wrapper.get_task_endpoint(task_id)

@app.delete("/api/v1/tasks/{task_id}", response_model=TaskResponse)
async def cancel_task(task_id: str):
    if not api_wrapper:
        raise HTTPException(status_code=503, detail="Service not ready")
    return await api_wrapper.cancel_task_endpoint(task_id)

@app.get("/api/v1/metrics", response_model=MetricsResponse)
async def get_metrics():
    if not api_wrapper:
        raise HTTPException(status_code=503, detail="Service not ready")
    return await api_wrapper.get_metrics_endpoint()

@app.get("/health", response_model=HealthResponse)
async def health_check():
    uptime = prometheus_metrics.get_uptime() if prometheus_metrics else None
    return HealthResponse(uptime=uptime)

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return prometheus_metrics.get_metrics_response() if prometheus_metrics else Response("Metrics not available")

if __name__ == "__main__":
    # For development - run with: python src/main.py
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )