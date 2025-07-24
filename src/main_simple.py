"""
Task Orchestrator Main Application - Simplified Version for Testing
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
    return {"status": "healthy", "service": "task-orchestrator", "version": "1.0.0"}

@app.get("/")
async def root():
    return {"message": "Task Orchestration Platform", "version": "1.0.0"}

@app.get("/api/v1/status")
async def api_status():
    return {
        "api": "operational",
        "services": {
            "database": "checking...",
            "redis": "checking...",
            "workers": "starting..."
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main_simple:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
