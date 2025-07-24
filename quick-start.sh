#!/bin/bash

# Task Orchestrator Quick Start Script
# This script sets up and runs the Task Orchestrator Platform

set -e

echo "🚀 Task Orchestrator Quick Start"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    echo "🔍 Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_status "Docker found"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    print_status "Docker Compose found"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_warning "Python 3 not found. You'll need it for local development."
    else
        print_status "Python 3 found"
    fi
}

# Create project structure
create_structure() {
    echo "📁 Creating project structure..."
    
    mkdir -p src tests examples config/grafana logs
    touch src/__init__.py tests/__init__.py
    
    print_status "Project structure created"
}

# Create configuration files
create_configs() {
    echo "⚙️  Creating configuration files..."
    
    # Create requirements.txt if it doesn't exist
    if [ ! -f "requirements.txt" ]; then
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
        print_status "requirements.txt created"
    fi
    
    # Create config.yaml if it doesn't exist
    if [ ! -f "config/config.yaml" ]; then
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

redis:
  host: "redis"
  port: 6379
  db: 0

workers:
  count: 5
  max_queue_size: 10000
  task_timeout: 300

email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  email: "your-email@gmail.com"
  password: "your-app-password"

security:
  cors_origins:
    - "http://localhost:3000"
    - "http://localhost:8080"
EOF
        print_status "config/config.yaml created"
    fi
    
    # Create simple main.py if it doesn't exist
    if [ ! -f "src/main.py" ]; then
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
        print_status "src/main.py created"
    fi
}

# Check if Docker services are running
check_docker_services() {
    echo "🐳 Checking Docker services..."
    
    if docker-compose ps | grep -q "Up"; then
        print_status "Docker services are running"
        return 0
    else
        print_warning "Docker services are not running"
        return 1
    fi
}

# Start services
start_services() {
    echo "🚀 Starting services..."
    
    if check_docker_services; then
        print_info "Services already running. Use 'docker-compose restart' to restart them."
    else
        print_info "Starting Docker Compose services..."
        docker-compose up -d
        
        # Wait for services to be ready
        echo "⏳ Waiting for services to be ready..."
        sleep 10
        
        if check_docker_services; then
            print_status "All services started successfully!"
        else
            print_error "Some services failed to start. Check logs with 'docker-compose logs'"
            exit 1
        fi
    fi
}

# Display access information
show_access_info() {
    echo ""
    echo "🎉 Task Orchestrator is ready!"
    echo "=============================="
    echo ""
    echo "📱 Access your services:"
    echo "  • API Documentation: http://localhost:8080/docs"
    echo "  • Health Check:      http://localhost:8080/health"
    echo "  • Main API:          http://localhost:8080/"
    echo ""
    echo "🔧 Development services:"
    echo "  • PostgreSQL:        localhost:5432"
    echo "  • Redis:             localhost:6379"
    echo ""
    echo "📊 Monitoring (when full implementation is ready):"
    echo "  • Prometheus:        http://localhost:9090"
    echo "  • Grafana:           http://localhost:3000 (admin/admin123)"
    echo ""
    echo "💻 Useful commands:"
    echo "  • View logs:         docker-compose logs -f"
    echo "  • Stop services:     docker-compose down"
    echo "  • Restart services:  docker-compose restart"
    echo ""
}

# Test the setup
test_setup() {
    echo "🧪 Testing the setup..."
    
    # Test health endpoint
    if curl -s http://localhost:8080/health > /dev/null; then
        print_status "Health endpoint is responding"
    else
        print_warning "Health endpoint is not responding yet. It may still be starting up."
    fi
}

# Main execution
main() {
    echo "Starting Task Orchestrator setup..."
    echo ""
    
    check_prerequisites
    create_structure
    create_configs
    start_services
    test_setup
    show_access_info
    
    print_status "Setup complete! 🎉"
}

# Handle script arguments
case "${1:-}" in
    "start")
        start_services
        show_access_info
        ;;
    "stop")
        echo "🛑 Stopping services..."
        docker-compose down
        print_status "Services stopped"
        ;;
    "restart")
        echo "🔄 Restarting services..."
        docker-compose restart
        print_status "Services restarted"
        ;;
    "logs")
        echo "📋 Showing logs..."
        docker-compose logs -f
        ;;
    "status")
        echo "📊 Service status:"
        docker-compose ps
        ;;
    "clean")
        echo "🧹 Cleaning up (removing all data)..."
        docker-compose down -v
        print_status "All data removed"
        ;;
    *)
        main
        ;;
esac
