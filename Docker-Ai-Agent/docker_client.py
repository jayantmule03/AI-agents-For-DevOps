import sys
from pathlib import Path
import asyncio
import logging
import uuid
from temporalio.client import Client

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import TEMPORAL_HOST, DOCKER_MONITOR_TASK_QUEUE
from docker_monitor.docker_temporal_agent import DockerMonitorWorkflow

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_workflow_id(task: str) -> str:
    return f"docker-monitor-{uuid.uuid4()}"


async def main():
    print("=" * 60)
    print("Docker Container Health Monitor - Temporal Client")
    print("=" * 60)
    print()
    print("Monitor workflows at: http://localhost:8233")
    print()
    print()
    print("Server at: localhost:7233")
    print()
    print()
    print("Metrics at: http://localhost:40539/metrics")
    print()
    try:
        print(f"Connecting to Temporal server at {TEMPORAL_HOST}...")
        client = await Client.connect(TEMPORAL_HOST)
        print("✓ Connected to Temporal server")
        print()
        
    except Exception as e:
        print(f"✗ Failed to connect to Temporal server: {e}")
        print()
        print("Make sure Temporal server is running:")
        print("  temporal server start-dev")
        print()
        print(" Check Monitor workflows at: http://localhost:8233")
        return
    
    print("Example queries:")
    print("  - Check container status")
    print("  - Show me logs for nginx")
    print("  - Analyze logs from demo-logger")
    print("  - Give me a summary of redis logs")
    print("  - Is redis healthy?")
    print("  - Is nginx healthy?")
    print("  - Restart the postgres container")
    print("  - Restart the nginx container")
    print()
    print("Type 'quit' or 'exit' to stop")
    print("=" * 60)
    print()
    
    while True:
        try:
            task = input("Enter task: ").strip()
            
            if task.lower() in ['quit', 'q', 'exit']:
                print("Chal mai Jata hu!")
                break
            
            if not task:
                continue
            
            workflow_id = generate_workflow_id(task)
            
            print(f"Processing... (Workflow ID: {workflow_id[:16]}...)")
            logger.info(f"Executing workflow: {workflow_id}")
            
            result = await client.execute_workflow(
                DockerMonitorWorkflow.run,
                task,
                id=workflow_id,
                task_queue=DOCKER_MONITOR_TASK_QUEUE
            )
            
            print()
            print(result)
            print()
            
        except KeyboardInterrupt:
            print("\nChal mai Jata hu!")
            break
        except Exception as e:
            logger.exception("Error executing workflow")
            print(f"\n✗ Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
