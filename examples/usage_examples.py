"""
Example usage of the Task Orchestrator
"""

import asyncio
import time
from datetime import datetime, timedelta
from task_orchestrator import TaskOrchestrator, TaskType, TaskPriority, EmailTask, APITask
from scheduler import AdvancedScheduler, ScheduledTaskTemplates

# Sample configuration
SAMPLE_CONFIG = {
    'database': {
        'host': 'localhost',
        'port': 5433,
        'user': 'postgres',
        'password': 'password123',
        'database': 'task_scheduler'
    },
    'redis': {
        'host': 'localhost',
        'port': 6379,
        'db': 0
    },
    'workers': {
        'count': 3
    },
    'email': {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'email': 'your-email@gmail.com',
        'password': 'your-app-password'
    }
}

async def example_basic_tasks():
    """Example of basic task creation and execution"""
    print("🚀 Starting Task Orchestrator Examples...")
    
    # Initialize orchestrator
    orchestrator = TaskOrchestrator(SAMPLE_CONFIG)
    await orchestrator.initialize()
    await orchestrator.start()
    
    try:
        # Example 1: Email Task
        print("\n📧 Creating email task...")
        email_task = EmailTask(
            to_addresses=['recipient@example.com'],
            subject='Welcome to Task Orchestrator!',
            body='This email was sent by the Task Orchestrator system.',
            from_address='system@company.com'
        )
        
        email_task_id = await orchestrator.create_email_task(
            name="Welcome Email",
            email_task=email_task,
            priority=TaskPriority.HIGH
        )
        print(f"✅ Email task created: {email_task_id}")
        
        # Example 2: API Task
        print("\n🌐 Creating API task...")
        api_task = APITask(
            url='https://httpbin.org/post',
            method='POST',
            json_data={'message': 'Hello from Task Orchestrator', 'timestamp': datetime.now().isoformat()},
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        api_task_id = await orchestrator.create_api_task(
            name="API Test Call",
            api_task=api_task,
            priority=TaskPriority.MEDIUM
        )
        print(f"✅ API task created: {api_task_id}")
        
        # Example 3: Custom Function Task
        print("\n⚙️ Creating custom function task...")
        
        # Register custom function
        def calculate_fibonacci(n):
            """Calculate fibonacci sequence"""
            if n <= 1:
                return n
            a, b = 0, 1
            for _ in range(2, n + 1):
                a, b = b, a + b
            return b
        
        orchestrator.register_task_function('fibonacci', calculate_fibonacci)
        
        custom_task_id = await orchestrator.create_task(
            name="Calculate Fibonacci",
            task_type=TaskType.DATA_PROCESSING,
            function_name="fibonacci",
            args=[10],
            priority=TaskPriority.LOW,
            metadata={'calculation_type': 'fibonacci'}
        )
        print(f"✅ Custom task created: {custom_task_id}")
        
        # Example 4: Scheduled Task
        print("\n⏰ Creating scheduled task...")
        future_time = datetime.now() + timedelta(seconds=30)
        
        scheduled_task_id = await orchestrator.create_task(
            name="Future Data Processing",
            task_type=TaskType.DATA_PROCESSING,
            function_name="fibonacci",
            args=[15],
            scheduled_at=future_time,
            priority=TaskPriority.MEDIUM
        )
        print(f"✅ Scheduled task created: {scheduled_task_id} (will run at {future_time})")
        
        # Example 5: Task with Dependencies
        print("\n🔗 Creating dependent tasks...")
        
        # Parent task
        parent_task_id = await orchestrator.create_task(
            name="Data Extraction",
            task_type=TaskType.DATA_PROCESSING,
            function_name="fibonacci",
            args=[5],
            priority=TaskPriority.HIGH
        )
        
        # Child task that depends on parent
        child_task_id = await orchestrator.create_task(
            name="Data Transformation",
            task_type=TaskType.DATA_PROCESSING,
            function_name="fibonacci",
            args=[8],
            dependencies=[parent_task_id],
            priority=TaskPriority.MEDIUM
        )
        print(f"✅ Parent task: {parent_task_id}")
        print(f"✅ Child task: {child_task_id} (depends on parent)")
        
        # Monitor tasks for a bit
        print("\n📊 Monitoring task execution...")
        await monitor_tasks(orchestrator, [email_task_id, api_task_id, custom_task_id, parent_task_id, child_task_id])
        
    finally:
        await orchestrator.stop()
        print("\n👋 Task Orchestrator stopped")


async def example_advanced_scheduling():
    """Example of advanced scheduling with APScheduler"""
    print("\n🕒 Advanced Scheduling Examples...")
    
    orchestrator = TaskOrchestrator(SAMPLE_CONFIG)
    await orchestrator.initialize()
    await orchestrator.start()
    
    # Initialize advanced scheduler
    scheduler = AdvancedScheduler(orchestrator)
    await scheduler.start()
    
    try:
        # Example 1: Cron-based scheduling
        print("📅 Setting up cron-based tasks...")
        
        # Daily health check at 9 AM
        health_check_job = scheduler.schedule_cron_task(
            task_name="Daily Health Check",
            task_type="api_call",
            cron_expression="0 9 * * *",  # Every day at 9 AM
            task_data=ScheduledTaskTemplates.health_check_api("http://localhost:8080/health")
        )
        print(f"✅ Daily health check scheduled: {health_check_job}")
        
        # Weekly cleanup on Sundays at 2 AM
        cleanup_job = scheduler.schedule_cron_task(
            task_name="Weekly Cleanup",
            task_type="data_processing",
            cron_expression="0 2 * * SUN",  # Every Sunday at 2 AM
            task_data=ScheduledTaskTemplates.weekly_cleanup()
        )
        print(f"✅ Weekly cleanup scheduled: {cleanup_job}")
        
        # Example 2: Interval scheduling
        print("⏱️ Setting up interval-based tasks...")
        
        # Health check every 5 minutes
        interval_job = scheduler.schedule_interval_task(
            task_name="Health Check Monitor",
            task_type="api_call",
            interval_seconds=300,  # 5 minutes
            task_data=ScheduledTaskTemplates.health_check_api("http://localhost:8080/health")
        )
        print(f"✅ Interval health check scheduled: {interval_job}")
        
        # Example 3: One-time scheduling
        print("📆 Setting up one-time tasks...")
        
        future_time = datetime.now() + timedelta(minutes=1)
        onetime_job = scheduler.schedule_one_time_task(
            task_name="System Maintenance",
            task_type="data_processing",
            run_date=future_time,
            task_data={
                'function_name': 'fibonacci',
                'args': [20],
                'metadata': {'task_category': 'maintenance'}
            }
        )
        print(f"✅ One-time task scheduled: {onetime_job} at {future_time}")
        
        # List all scheduled jobs
        print("\n📋 All scheduled jobs:")
        jobs = scheduler.list_jobs()
        for job in jobs:
            print(f"  - {job['name']} (ID: {job['id']}) - Next run: {job['next_run_time']}")
        
        # Let it run for a bit
        print("\n⏳ Letting scheduler run for 2 minutes...")
        await asyncio.sleep(120)
        
    finally:
        await scheduler.stop()
        await orchestrator.stop()
        print("\n👋 Advanced scheduler stopped")


async def monitor_tasks(orchestrator, task_ids, max_wait=60):
    """Monitor task execution"""
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        print(f"\n📊 Task Status Update ({time.time() - start_time:.1f}s):")
        all_done = True
        
        for task_id in task_ids:
            status = await orchestrator.get_task_status(task_id)
            print(f"  Task {task_id[:8]}... : {status.value if status else 'NOT_FOUND'}")
            
            if status and status.value in ['pending', 'running', 'scheduled']:
                all_done = False
        
        if all_done:
            print("✅ All monitored tasks completed!")
            break
        
        await asyncio.sleep(5)
    
    # Show final results
    print("\n📋 Final Results:")
    for task_id in task_ids:
        result = await orchestrator.get_task_result(task_id)
        if result:
            print(f"  Task {task_id[:8]}... : {result.status.value}")
            if result.result:
                print(f"    Result: {result.result}")
            if result.error:
                print(f"    Error: {result.error}")


async def example_metrics_monitoring():
    """Example of monitoring system metrics"""
    print("\n📊 Metrics Monitoring Example...")
    
    orchestrator = TaskOrchestrator(SAMPLE_CONFIG)
    await orchestrator.initialize()
    await orchestrator.start()
    
    try:
        # Create some tasks to generate metrics
        for i in range(5):
            await orchestrator.create_task(
                name=f"Metrics Test Task {i}",
                task_type=TaskType.DATA_PROCESSING,
                function_name="fibonacci",
                args=[i + 5],
                priority=TaskPriority.MEDIUM
            )
        
        # Monitor metrics for a while
        for _ in range(6):
            await asyncio.sleep(10)
            metrics = orchestrator.get_metrics()
            
            print(f"\n📈 System Metrics:")
            print(f"  Total Tasks: {metrics.get('tasks_total', 0)}")
            print(f"  Completed: {metrics.get('tasks_completed', 0)}")
            print(f"  Failed: {metrics.get('tasks_failed', 0)}")
            print(f"  Running: {metrics.get('tasks_running', 0)}")
            print(f"  Workers: {metrics.get('worker_count', 0)}")
            print(f"  Running: {metrics.get('is_running', False)}")
            print(f"  Avg Execution Time: {metrics.get('average_execution_time', 0):.2f}s")
    
    finally:
        await orchestrator.stop()
        print("\n👋 Metrics monitoring stopped")


async def main():
    """Run all examples"""
    print("🎯 Task Orchestrator Examples")
    print("=" * 50)
    
    try:
        # Run basic examples
        await example_basic_tasks()
        
        # Wait a bit between examples
        await asyncio.sleep(2)
        
        # Run advanced scheduling examples
        await example_advanced_scheduling()
        
        # Wait a bit between examples
        await asyncio.sleep(2)
        
        # Run metrics monitoring
        await example_metrics_monitoring()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Examples interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error running examples: {e}")
    
    print("\n🎉 All examples completed!")


if __name__ == "__main__":
    # Note: Make sure PostgreSQL and Redis are running before executing
    print("⚠️  Make sure PostgreSQL (port 5433) and Redis (port 6379) are running!")
    print("💡 You can start them with: docker-compose up postgres redis -d")
    print()
    
    asyncio.run(main())
