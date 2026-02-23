import sys
from pathlib import Path
import asyncio
import logging
import uuid
from temporalio.client import Client

sys.path.insert(0, str(Path(__file__).parent.parent))

from argocd_monitor.config import TEMPORAL_HOST, ARGOCD_MONITOR_TASK_QUEUE
from argocd_monitor.argocd_temporal_agent import ArgoCDMonitorWorkflow

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_workflow_id(task: str) -> str:
    """Generate a unique workflow ID for the task."""
    return f"argocd-monitor-{uuid.uuid4()}"


async def main():
    print("=" * 60)
    print("ArgoCD Application Health Monitor - Temporal Client")
    print("=" * 60)
    print()
    print("Monitor workflows at: http://localhost:8233")
    print("Server at: localhost:7233")
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
        print("Check Monitor workflows at: http://localhost:8233")
        return
    
    print("Example queries:")
    print("  - Check application status")
    print("  - Show me all applications")
    print("  - Is nginx healthy?")
    print("  - Show me logs for apache")
    print("  - Analyze logs from todo-app")
    print("  - What resources does nginx have?")
    print("  - Sync the apache application")
    print("  - Show applications in default project")
    print()
    print("Type 'quit' or 'exit' to stop")
    print("=" * 60)
    print()
    
    while True:
        try:
            task = input("Enter task: ").strip()
            
            if task.lower() in ['quit', 'q', 'exit']:
                print("\nShutting down ArgoCD monitor. Goodbye!")
                break
            
            if not task:
                continue
            
            workflow_id = generate_workflow_id(task)
            
            print(f"Processing... (Workflow ID: {workflow_id[:32]}...)")
            logger.info(f"Executing workflow: {workflow_id}")
            
            result = await client.execute_workflow(
                ArgoCDMonitorWorkflow.run,
                task,
                id=workflow_id,
                task_queue=ARGOCD_MONITOR_TASK_QUEUE
            )
            
            print()
            print(result)
            print()
            
        except KeyboardInterrupt:
            print("\n\nShutting down ArgoCD monitor. Goodbye!")
            break
        except Exception as e:
            logger.exception("Error executing workflow")
            print(f"\n✗ Error: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
