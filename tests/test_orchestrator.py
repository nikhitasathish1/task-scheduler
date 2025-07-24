"""
Tests for Task Orchestrator
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock
from task_orchestrator import TaskOrchestrator, TaskStatus, TaskType, TaskPriority
from models import TaskCreateRequest, EmailTaskModel


@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return {
        'database': {
            'host': 'localhost',
            'port': 5433,
            'user': 'postgres',
            'password': 'password123',
            'database': 'test_task_scheduler'
        },
        'redis': {
            'host': 'localhost',
            'port': 6379,
            'db': 1  # Use different DB for tests
        },
        'workers': {
            'count': 2
        },
        'email': {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'email': 'test@example.com',
            'password': 'test_password'
        }
    }


@pytest.fixture
async def orchestrator(sample_config):
    """Create orchestrator instance for testing"""
    orchestrator = TaskOrchestrator(sample_config)
    await orchestrator.initialize()
    yield orchestrator
    await orchestrator.stop()


class TestTaskOrchestrator:
    """Test TaskOrchestrator functionality"""
    
    @pytest.mark.asyncio
    async def test_create_email_task(self, orchestrator):
        """Test creating an email task"""
        email_task = {
            'to_addresses': ['test@example.com'],
            'subject': 'Test Email',
            'body': 'This is a test email',
            'from_address': 'sender@example.com'
        }
        
        task_id = await orchestrator.create_email_task(
            name="Test Email Task",
            email_task=email_task,
            priority=TaskPriority.HIGH
        )
        
        assert task_id is not None
        assert isinstance(task_id, str)
        
        # Check task status
        status = await orchestrator.get_task_status(task_id)
        assert status == TaskStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_create_api_task(self, orchestrator):
        """Test creating an API task"""
        api_task = {
            'url': 'https://httpbin.org/get',
            'method': 'GET',
            'timeout': 30
        }
        
        task_id = await orchestrator.create_api_task(
            name="Test API Task",
            api_task=api_task,
            priority=TaskPriority.MEDIUM
        )
        
        assert task_id is not None
        assert isinstance(task_id, str)
        
        # Check task status
        status = await orchestrator.get_task_status(task_id)
        assert status == TaskStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, orchestrator):
        """Test canceling a task"""
        task_id = await orchestrator.create_task(
            name="Test Cancel Task",
            task_type=TaskType.DATA_PROCESSING,
            function_name="test_function"
        )
        
        # Cancel the task
        success = await orchestrator.cancel_task(task_id)
        assert success is True
        
        # Check task status
        status = await orchestrator.get_task_status(task_id)
        assert status == TaskStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_task_dependencies(self, orchestrator):
        """Test task dependencies"""
        # Create parent task
        parent_id = await orchestrator.create_task(
            name="Parent Task",
            task_type=TaskType.DATA_PROCESSING,
            function_name="parent_function"
        )
        
        # Create child task with dependency
        child_id = await orchestrator.create_task(
            name="Child Task",
            task_type=TaskType.DATA_PROCESSING,
            function_name="child_function",
            dependencies=[parent_id]
        )
        
        assert child_id is not None
        
        # Check that child task has dependency
        task_result = await orchestrator.get_task_result(child_id)
        assert parent_id in task_result.metadata.get('dependencies', [])


class TestTaskModels:
    """Test Pydantic models"""
    
    def test_email_task_model(self):
        """Test EmailTaskModel validation"""
        email_data = {
            'to_addresses': ['test@example.com'],
            'subject': 'Test Subject',
            'body': 'Test body',
            'from_address': 'sender@example.com'
        }
        
        email_task = EmailTaskModel(**email_data)
        assert email_task.to_addresses == ['test@example.com']
        assert email_task.subject == 'Test Subject'
        assert email_task.cc_addresses == []
        assert email_task.bcc_addresses == []
    
    def test_task_create_request(self):
        """Test TaskCreateRequest validation"""
        task_data = {
            'name': 'Test Task',
            'task_type': 'email',
            'priority': 'high',
            'email_task': {
                'to_addresses': ['test@example.com'],
                'subject': 'Test Subject',
                'body': 'Test body',
                'from_address': 'sender@example.com'
            }
        }
        
        request = TaskCreateRequest(**task_data)
        assert request.name == 'Test Task'
        assert request.task_type == 'email'
        assert request.priority == 'high'
        assert request.email_task is not None
    
    def test_task_create_request_validation_error(self):
        """Test validation error for missing required fields"""
        with pytest.raises(ValueError):
            TaskCreateRequest(
                name='Test Task',
                task_type='email',
                # Missing email_task for email type
            )


class TestMetrics:
    """Test metrics functionality"""
    
    def test_metrics_collection(self, orchestrator):
        """Test metrics collection"""
        metrics = orchestrator.get_metrics()
        
        assert 'tasks_total' in metrics
        assert 'tasks_completed' in metrics
        assert 'tasks_failed' in metrics
        assert 'tasks_running' in metrics
        assert 'is_running' in metrics
        assert 'worker_count' in metrics


class TestDatabaseOperations:
    """Test database operations"""
    
    @pytest.mark.asyncio
    async def test_task_persistence(self, orchestrator):
        """Test task saving and retrieval"""
        task_id = await orchestrator.create_task(
            name="Persistence Test",
            task_type=TaskType.DATA_PROCESSING,
            function_name="test_function",
            metadata={'test': 'data'}
        )
        
        # Retrieve task
        task = await orchestrator.db_manager.get_task(task_id)
        assert task is not None
        assert task.name == "Persistence Test"
        assert task.metadata.get('test') == 'data'


# Integration tests
class TestIntegration:
    """Integration tests"""
    
    @pytest.mark.asyncio
    async def test_full_task_lifecycle(self, orchestrator):
        """Test complete task lifecycle"""
        # Register a test function
        def test_function(data):
            return f"Processed: {data}"
        
        orchestrator.register_task_function('test_function', test_function)
        
        # Create task
        task_id = await orchestrator.create_task(
            name="Lifecycle Test",
            task_type=TaskType.DATA_PROCESSING,
            function_name="test_function",
            args=["test_data"]
        )
        
        # Wait a bit for processing (in real tests, you'd mock the worker)
        await asyncio.sleep(0.1)
        
        # Check final status
        task_result = await orchestrator.get_task_result(task_id)
        assert task_result is not None
        assert task_result.task_id == task_id


if __name__ == "__main__":
    pytest.main([__file__])
