"""Temporal ArgoCD Application Health Monitor with automatic retries and fault tolerance."""

import sys
from pathlib import Path
import logging
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@activity.defn
async def get_application_status_activity(filter_by: str = None) -> str:
    """Get application status with optional filtering."""
    from argocd_monitor.argocd_utils import ArgoCDClientWrapper, ArgoCDConnectionError, ApplicationNotFoundError
    
    activity.logger.info(f"Getting application status, filter: {filter_by}")
    
    try:
        argocd_client = ArgoCDClientWrapper()
        
        if filter_by and not filter_by.startswith('project:'):
            # Try to get specific application
            try:
                app = argocd_client.get_application(filter_by)
                return f"Application Details:\n\n{app.format_summary()}"
            except ApplicationNotFoundError:
                # Treat as project filter
                filter_by = f"project:{filter_by}"
        
        project = filter_by.replace('project:', '') if filter_by else None
        applications = argocd_client.get_applications(project=project)
        
        if not applications:
            return f"No applications found" + (f" in project '{project}'" if project else "")
        
        result = [f"Found {len(applications)} application(s):\n"]
        
        healthy_count = sum(1 for app in applications if app.health_status == "Healthy")
        synced_count = sum(1 for app in applications if app.sync_status == "Synced")
        
        result.append(f"Summary: {healthy_count}/{len(applications)} Healthy, {synced_count}/{len(applications)} Synced\n")
        
        for app in applications:
            result.append(app.format_summary())
            result.append("")
        
        activity.logger.info(f"Successfully retrieved {len(applications)} applications")
        return "\n".join(result)
        
    except ArgoCDConnectionError as e:
        activity.logger.error(f"ArgoCD connection error: {e}")
        raise
    except Exception as e:
        activity.logger.exception("Unexpected error in get_application_status_activity")
        raise ApplicationError(f"Unexpected error: {str(e)}", non_retryable=True)


@activity.defn
async def check_application_health_activity(app_name: str = None) -> str:
    """Check health of specific application or all applications."""
    from argocd_monitor.argocd_utils import ArgoCDClientWrapper, ArgoCDConnectionError, ApplicationNotFoundError
    
    activity.logger.info(f"Checking application health: {app_name or 'all'}")
    
    try:
        argocd_client = ArgoCDClientWrapper()
        
        if app_name:
            health = argocd_client.check_application_health(app_name)
            activity.logger.info(f"Health check complete for {app_name}: {'healthy' if health.is_healthy else 'unhealthy'}")
            return health.format_summary()
        
        # Check all applications
        applications = argocd_client.get_applications()
        if not applications:
            return "No applications found"
        
        results = [f"Health check for {len(applications)} application(s):\n"]
        healthy_count = 0
        
        for app in applications:
            try:
                health = argocd_client.check_application_health(app.name)
                results.append(health.format_summary())
                results.append("")
                if health.is_healthy:
                    healthy_count += 1
            except Exception as e:
                results.append(f"✗ {app.name}: Error checking health - {str(e)}")
                results.append("")
        
        results.append(f"Summary: {healthy_count}/{len(applications)} applications healthy")
        activity.logger.info(f"Health check complete: {healthy_count}/{len(applications)} healthy")
        return "\n".join(results)
        
    except ApplicationNotFoundError as e:
        activity.logger.error(f"Application not found: {e}")
        raise ApplicationError(f"Application '{e.app_name}' not found", non_retryable=True)
    except ArgoCDConnectionError as e:
        activity.logger.error(f"ArgoCD connection error: {e}")
        raise
    except Exception as e:
        activity.logger.exception("Unexpected error in check_application_health_activity")
        raise ApplicationError(f"Unexpected error: {str(e)}", non_retryable=True)


@activity.defn
async def get_application_logs_activity(app_name: str, resource_name: str = None, lines: int = 100) -> str:
    """Retrieve application logs."""
    from argocd_monitor.argocd_utils import ArgoCDClientWrapper, ArgoCDConnectionError, ApplicationNotFoundError
    
    activity.logger.info(f"Getting logs for {app_name}, resource: {resource_name}, lines: {lines}")
    
    try:
        argocd_client = ArgoCDClientWrapper()
        logs = argocd_client.get_application_logs(app_name, resource_name=resource_name, tail_lines=lines)
        
        if not logs:
            return f"No logs found for application '{app_name}'"
        
        resource_info = f" (resource: {resource_name})" if resource_name else " (first pod)"
        result = f"Last {lines} lines from application '{app_name}'{resource_info}:\n"
        result += "=" * 60 + "\n"
        result += logs
        
        activity.logger.info(f"Successfully retrieved logs for {app_name}")
        return result
        
    except ApplicationNotFoundError as e:
        activity.logger.error(f"Application not found: {e}")
        raise ApplicationError(f"Application '{e.app_name}' not found", non_retryable=True)
    except ArgoCDConnectionError as e:
        activity.logger.error(f"ArgoCD connection error: {e}")
        raise
    except Exception as e:
        activity.logger.exception("Unexpected error in get_application_logs_activity")
        raise ApplicationError(f"Unexpected error: {str(e)}", non_retryable=True)


@activity.defn
async def sync_application_activity(app_name: str, prune: bool = False) -> str:
    """Sync an application."""
    from argocd_monitor.argocd_utils import ArgoCDClientWrapper, ArgoCDConnectionError, ApplicationNotFoundError
    
    activity.logger.info(f"Syncing application: {app_name}, prune: {prune}")
    
    try:
        argocd_client = ArgoCDClientWrapper()
        result = argocd_client.sync_application(app_name, prune=prune)
        
        activity.logger.info(f"Successfully synced {app_name}")
        return result
        
    except ApplicationNotFoundError as e:
        activity.logger.error(f"Application not found: {e}")
        raise ApplicationError(f"Application '{e.app_name}' not found", non_retryable=True)
    except ArgoCDConnectionError as e:
        activity.logger.error(f"ArgoCD connection error: {e}")
        raise
    except Exception as e:
        activity.logger.exception("Unexpected error in sync_application_activity")
        raise ApplicationError(f"Unexpected error: {str(e)}", non_retryable=True)


@activity.defn
async def get_application_resources_activity(app_name: str) -> str:
    """Get detailed resource information for an application."""
    from argocd_monitor.argocd_utils import ArgoCDClientWrapper, ArgoCDConnectionError, ApplicationNotFoundError
    
    activity.logger.info(f"Getting resources for {app_name}")
    
    try:
        argocd_client = ArgoCDClientWrapper()
        health = argocd_client.check_application_health(app_name)
        
        if not health.resources:
            return f"No resources found for application '{app_name}'"
        
        result = [f"📦 Resources for application '{app_name}':", "=" * 60, ""]
        result.append(f"Total Resources: {health.total_resources}")
        result.append(f"Healthy Resources: {health.total_resources - health.degraded_resources}")
        result.append(f"Degraded Resources: {health.degraded_resources}")
        result.append(f"Out of Sync: {health.out_of_sync_resources}")
        result.append("")
        
        # Group resources by kind
        resources_by_kind = {}
        for resource in health.resources:
            kind = resource.kind
            if kind not in resources_by_kind:
                resources_by_kind[kind] = []
            resources_by_kind[kind].append(resource)
        
        for kind, resources in sorted(resources_by_kind.items()):
            result.append(f"\n{kind} ({len(resources)}):")
            for resource in resources:
                result.append(resource.format_summary())
        
        activity.logger.info(f"Successfully retrieved {health.total_resources} resources for {app_name}")
        return "\n".join(result)
        
    except ApplicationNotFoundError as e:
        activity.logger.error(f"Application not found: {e}")
        raise ApplicationError(f"Application '{e.app_name}' not found", non_retryable=True)
    except ArgoCDConnectionError as e:
        activity.logger.error(f"ArgoCD connection error: {e}")
        raise
    except Exception as e:
        activity.logger.exception("Unexpected error in get_application_resources_activity")
        raise ApplicationError(f"Unexpected error: {str(e)}", non_retryable=True)


@activity.defn
async def ai_orchestrator_activity(task: str) -> str:
    """AI-powered task orchestration that analyzes queries and returns operation plans."""
    from argocd_monitor.config import OLLAMA_BASE_URL, OLLAMA_MODEL_ID
    
    activity.logger.info(f"AI orchestrator processing task: {task}")
    
    try:
        from strands import Agent
        from strands.models import OllamaModel
        
        agent = Agent(
            model=OllamaModel(
                model=OLLAMA_MODEL_ID,
                base_url=OLLAMA_BASE_URL
            ),
            system_prompt="""Analyze the user request and return a comma-separated list of ArgoCD operations.

Available operations:
- status[:filter] - Get application status (optionally filtered by name or project)
- health[:app_name] - Check health (specific app or all if omitted)
- logs:app_name[:resource][:lines] - Get application logs (optionally specify resource and line count)
- sync:app_name[:prune] - Sync an application (prune=true to delete resources)
- resources:app_name - Get detailed resource information for an application

Examples:
"check application status" -> "status"
"show me nginx logs" -> "logs:nginx"
"is apache healthy?" -> "health:apache"
"sync todo-app" -> "sync:todo-app"
"show nginx resources" -> "resources:nginx"
"check nginx health and show logs" -> "health:nginx,logs:nginx"
"show applications in default project" -> "status:project:default"
"analyze apache logs" -> "logs:apache:100"

Return ONLY the comma-separated operation list, no explanations."""
        )
        
        result = agent(task)
        plan = str(result.content if hasattr(result, 'content') else result).strip()
        
        if not plan or len(plan) > 200:
            activity.logger.warning(f"AI returned invalid plan: {plan}")
            plan = "status"
        
        activity.logger.info(f"AI orchestrator generated plan: {plan}")
        return plan
        
    except Exception as e:
        activity.logger.warning(f"AI orchestrator failed: {e}, falling back to 'status'")
        return "status"


@workflow.defn
class ArgoCDMonitorWorkflow:
    """Temporal workflow for ArgoCD application monitoring with automatic retries."""
    
    @workflow.run
    async def run(self, task: str) -> str:
        """Execute ArgoCD monitoring workflow."""
        workflow.logger.info(f"Starting ArgoCD monitor workflow for task: {task}")
        
        # Get execution plan from AI
        plan = await workflow.execute_activity(
            ai_orchestrator_activity,
            task,
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(
                maximum_attempts=2,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=1),
                backoff_coefficient=1.0
            )
        )
        
        workflow.logger.info(f"Execution plan: {plan}")
        
        results = []
        operations = [op.strip() for op in plan.split(',') if op.strip()]
        
        for operation_spec in operations:
            try:
                result = await self._execute_operation(operation_spec)
                results.append(result)
            except Exception as e:
                workflow.logger.error(f"Operation {operation_spec} failed: {e}")
                results.append(f"Operation '{operation_spec}' failed: {str(e)}")
        
        final_result = "\n\n".join(results)
        workflow.logger.info("Workflow completed successfully")
        return final_result
    
    async def _execute_operation(self, operation_spec: str) -> str:
        """Execute a single operation based on the operation specification."""
        parts = operation_spec.split(':')
        operation = parts[0].lower()
        param1 = parts[1] if len(parts) > 1 else None
        param2 = parts[2] if len(parts) > 2 else None
        param3 = parts[3] if len(parts) > 3 else None
        
        if operation == 'status':
            return await workflow.execute_activity(
                get_application_status_activity,
                param1,
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=5),
                    backoff_coefficient=2.0
                )
            )
        
        elif operation == 'health':
            return await workflow.execute_activity(
                check_application_health_activity,
                param1,
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=10),
                    backoff_coefficient=2.0
                )
            )
        
        elif operation == 'logs':
            if not param1:
                return "Error: logs operation requires application name"
            
            resource_name = param2 if param2 and not param2.isdigit() else None
            lines = int(param3) if param3 and param3.isdigit() else (int(param2) if param2 and param2.isdigit() else 100)
            
            return await workflow.execute_activity(
                get_application_logs_activity,
                args=[param1, resource_name, lines],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(
                    maximum_attempts=2,
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=5),
                    backoff_coefficient=2.0
                )
            )
        
        elif operation == 'sync':
            if not param1:
                return "Error: sync operation requires application name"
            
            prune = param2 == 'true' if param2 else False
            
            return await workflow.execute_activity(
                sync_application_activity,
                args=[param1, prune],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(seconds=30),
                    backoff_coefficient=2.0
                )
            )
        
        elif operation == 'resources':
            if not param1:
                return "Error: resources operation requires application name"
            
            return await workflow.execute_activity(
                get_application_resources_activity,
                param1,
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=10),
                    backoff_coefficient=2.0
                )
            )
        
        else:
            return f"Unknown operation: {operation}"
