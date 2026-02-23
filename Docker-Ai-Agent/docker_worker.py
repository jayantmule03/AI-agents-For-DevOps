import sys
from pathlib import Path
import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import TEMPORAL_HOST, DOCKER_MONITOR_TASK_QUEUE
from docker_monitor.docker_temporal_agent import (
    DockerMonitorWorkflow,
    get_container_status_activity,
    check_container_health_activity,
    get_container_logs_activity,
    restart_container_activity,
    ai_orchestrator_activity
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("=" * 60)
    logger.info("Docker Monitor Temporal Worker")
    logger.info("=" * 60)
    
    try:
        logger.info(f"Connecting to Temporal server at {TEMPORAL_HOST}...")
        client = await Client.connect(TEMPORAL_HOST)
        logger.info("✓ Connected to Temporal server")
        
        logger.info(f"Creating worker for task queue: {DOCKER_MONITOR_TASK_QUEUE}")
        worker = Worker(
            client,
            task_queue=DOCKER_MONITOR_TASK_QUEUE,
            workflows=[DockerMonitorWorkflow],
            activities=[
                get_container_status_activity,
                check_container_health_activity,
                get_container_logs_activity,
                restart_container_activity,
                ai_orchestrator_activity
            ]
        )
        
        logger.info("✓ Worker created successfully")
        logger.info("")
        logger.info("Registered workflows:")
        logger.info("  - DockerMonitorWorkflow")
        logger.info("")
        logger.info("Registered activities:")
        logger.info("  - get_container_status_activity")
        logger.info("  - check_container_health_activity")
        logger.info("  - get_container_logs_activity")
        logger.info("  - restart_container_activity")
        logger.info("  - ai_orchestrator_activity")
        logger.info("")
        logger.info("=" * 60)
        logger.info("Worker is running and waiting for tasks...")
        logger.info("Monitor workflows at: http://localhost:8233")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)
        
        await worker.run()
        
    except KeyboardInterrupt:
        logger.info("\nShutting down worker...")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        logger.exception("Full error details:")
        raise


if __name__ == "__main__":
    asyncio.run(main())
