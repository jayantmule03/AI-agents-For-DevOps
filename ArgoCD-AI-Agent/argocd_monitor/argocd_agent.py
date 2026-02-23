"""Simple ArgoCD Application Health Monitor Agent using Strands framework."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from strands import Agent, tool
from strands.models import OllamaModel
from argocd_monitor.config import OLLAMA_BASE_URL, OLLAMA_MODEL_ID

model = OllamaModel(
    model=OLLAMA_MODEL_ID,
    base_url=OLLAMA_BASE_URL
)

from argocd_monitor.argocd_utils import (
    ArgoCDClientWrapper,
    ArgoCDConnectionError,
    ApplicationNotFoundError
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    argocd_client = ArgoCDClientWrapper()
except ArgoCDConnectionError as e:
    logger.error(f"Failed to initialize ArgoCD client: {e}")
    argocd_client = None


@tool
def get_application_status(filter_by: str = None) -> str:
    """Get status of all applications or filter by name/project."""
    if argocd_client is None:
        return "ArgoCD server is not accessible. Please ensure ArgoCD is running."
    
    try:
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
        
        return "\n".join(result)
        
    except ArgoCDConnectionError as e:
        return f"ArgoCD connection error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in get_application_status")
        return "An unexpected error occurred. Check logs for details."


@tool
def check_application_health(app_name: str = None) -> str:
    """Check detailed health of specific application or all applications."""
    if argocd_client is None:
        return "ArgoCD server is not accessible. Please ensure ArgoCD is running."
    
    try:
        if app_name:
            health = argocd_client.check_application_health(app_name)
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
        return "\n".join(results)
        
    except ApplicationNotFoundError as e:
        return f"Application '{e.app_name}' not found"
    except ArgoCDConnectionError as e:
        return f"ArgoCD connection error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in check_application_health")
        return "An unexpected error occurred. Check logs for details."


@tool
def get_application_logs(app_name: str, resource_name: str = None, lines: int = 100) -> str:
    """Retrieve recent logs from an application's pods."""
    if argocd_client is None:
        return "ArgoCD server is not accessible. Please ensure ArgoCD is running."
    
    try:
        logs = argocd_client.get_application_logs(app_name, resource_name=resource_name, tail_lines=lines)
        
        if not logs:
            return f"No logs found for application '{app_name}'"
        
        resource_info = f" (resource: {resource_name})" if resource_name else " (first pod)"
        result = f"Last {lines} lines from application '{app_name}'{resource_info}:\n"
        result += "=" * 60 + "\n"
        result += logs
        return result
        
    except ApplicationNotFoundError as e:
        return f"Application '{e.app_name}' not found"
    except ArgoCDConnectionError as e:
        return f"ArgoCD connection error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in get_application_logs")
        return "An unexpected error occurred. Check logs for details."


@tool
def sync_application(app_name: str, prune: bool = False) -> str:
    """Trigger sync for an application to match desired state."""
    if argocd_client is None:
        return "ArgoCD server is not accessible. Please ensure ArgoCD is running."
    
    try:
        logger.info(f"Syncing application: {app_name}, prune={prune}")
        result = argocd_client.sync_application(app_name, prune=prune)
        return result
        
    except ApplicationNotFoundError as e:
        return f"Application '{e.app_name}' not found"
    except ArgoCDConnectionError as e:
        return f"ArgoCD connection error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in sync_application")
        return "An unexpected error occurred. Check logs for details."


@tool
def analyze_application_logs(app_name: str, resource_name: str = None, lines: int = 100) -> str:
    """Analyze and summarize application logs to identify patterns, errors, and issues."""
    if argocd_client is None:
        return "ArgoCD server is not accessible. Please ensure ArgoCD is running."
    
    try:
        logs = argocd_client.get_application_logs(app_name, resource_name=resource_name, tail_lines=lines)
        
        if not logs or "No logs" in logs or "not available" in logs:
            return logs
        
        log_lines = logs.strip().split('\n')
        total_lines = len(log_lines)
        
        # Analyze log levels
        info_count = sum(1 for line in log_lines if 'INFO' in line.upper() or 'info' in line.lower())
        warn_count = sum(1 for line in log_lines if 'WARN' in line.upper() or 'warning' in line.lower())
        error_count = sum(1 for line in log_lines if 'ERROR' in line.upper() or 'error' in line.lower())
        debug_count = sum(1 for line in log_lines if 'DEBUG' in line.upper() or 'debug' in line.lower())
        
        # Find errors and important messages
        error_lines = [line for line in log_lines if 'ERROR' in line.upper() or 'error' in line.lower()]
        recent_errors = error_lines[-5:] if error_lines else []
        
        # Find crash/restart indicators
        crash_indicators = ['panic', 'fatal', 'crashed', 'killed', 'exit code', 'segfault']
        crash_lines = [line for line in log_lines if any(indicator in line.lower() for indicator in crash_indicators)]
        
        resource_info = f" - {resource_name}" if resource_name else " (first pod)"
        result = [f" Log Analysis for '{app_name}'{resource_info} (last {lines} lines)", "=" * 60, ""]
        
        result.append(" Log Level Distribution:")
        result.append(f"  • Total log lines: {total_lines}")
        if total_lines > 0:
            result.append(f"  • INFO:  {info_count} ({info_count*100//total_lines}%)")
            result.append(f"  • WARN:  {warn_count} ({warn_count*100//total_lines}%)")
            result.append(f"  • ERROR: {error_count} ({error_count*100//total_lines}%)")
            result.append(f"  • DEBUG: {debug_count} ({debug_count*100//total_lines}%)")
        result.append("")
        
        # Health assessment
        if crash_lines:
            result.append(f" CRITICAL: Crash/Fatal errors detected ({len(crash_lines)} occurrences)")
        elif error_count == 0:
            result.append("✓ Health: No errors detected in recent logs")
        elif error_count < 5:
            result.append(f"⚠ Health: {error_count} error(s) detected - review recommended")
        else:
            result.append(f"✗ Health: {error_count} errors detected - immediate attention needed")
        result.append("")
        
        # Show crash indicators if found
        if crash_lines:
            result.append(f" Critical Issues (last {min(3, len(crash_lines))}):")
            for i, crash in enumerate(crash_lines[-3:], 1):
                crash_preview = crash[:120] + "..." if len(crash) > 120 else crash
                result.append(f"  {i}. {crash_preview}")
            result.append("")
        
        # Show recent errors
        if recent_errors:
            result.append(f" Recent Errors (last {len(recent_errors)}):")
            for i, error in enumerate(recent_errors, 1):
                error_preview = error[:100] + "..." if len(error) > 100 else error
                result.append(f"  {i}. {error_preview}")
            result.append("")
        
        # Activity summary
        result.append(" Activity Summary:")
        if total_lines > 0:
            first_line = log_lines[0][:80] + "..." if len(log_lines[0]) > 80 else log_lines[0]
            last_line = log_lines[-1][:80] + "..." if len(log_lines[-1]) > 80 else log_lines[-1]
            result.append(f"  • First log: {first_line}")
            result.append(f"  • Last log:  {last_line}")
        result.append("")
        
        # Recommendations
        result.append(" Recommendations:")
        if crash_lines:
            result.append("  • URGENT: Investigate crash/fatal errors immediately")
            result.append("  • Check application configuration and resource limits")
            result.append("  • Consider rolling back to previous version if issue persists")
        elif error_count > 10:
            result.append("  • High error rate detected - investigate root cause")
            result.append("  • Consider triggering application sync")
            result.append("  • Check application health status")
        elif error_count > 0:
            result.append("  • Review error messages above for specific issues")
            result.append("  • Monitor application for recurring errors")
        else:
            result.append("  • Application logs look healthy")
            result.append("  • Continue normal monitoring")
        
        if warn_count > total_lines * 0.3:
            result.append("  • High warning rate - may indicate configuration issues")
        
        return "\n".join(result)
        
    except ApplicationNotFoundError as e:
        return f"Application '{e.app_name}' not found"
    except ArgoCDConnectionError as e:
        return f"ArgoCD connection error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in analyze_application_logs")
        return "An unexpected error occurred. Check logs for details."


@tool
def get_application_resources(app_name: str) -> str:
    """Get detailed information about all Kubernetes resources in an application."""
    if argocd_client is None:
        return "ArgoCD server is not accessible. Please ensure ArgoCD is running."
    
    try:
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
        
        return "\n".join(result)
        
    except ApplicationNotFoundError as e:
        return f"Application '{e.app_name}' not found"
    except ArgoCDConnectionError as e:
        return f"ArgoCD connection error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in get_application_resources")
        return "An unexpected error occurred. Check logs for details."


def create_agent() -> Agent:
    """Create and configure the ArgoCD monitoring agent."""
    return Agent(
        model=OllamaModel(
            model=OLLAMA_MODEL_ID,
            base_url=OLLAMA_BASE_URL
        ),
        tools=[
            get_application_status,
            check_application_health,
            get_application_logs,
            sync_application,
            analyze_application_logs,
            get_application_resources
        ],
        system_prompt="""You are an ArgoCD application health monitoring assistant.
You can check application status, verify health, retrieve logs, sync applications, and analyze resource states.

Use the available tools to help users monitor and manage their ArgoCD applications.
When users ask for log summaries or analysis, use the analyze_application_logs tool.
When users ask about resources or want to see what's deployed, use get_application_resources.
Provide clear, helpful responses and explain what actions you're taking.

Key capabilities:
- Monitor application sync and health status
- Analyze application logs for errors and issues
- View detailed resource information (deployments, pods, services, etc.)
- Trigger application syncs
- Provide recommendations for unhealthy applications"""
    )


def main():
    """Main entry point for the simple ArgoCD agent."""
    print("=" * 60)
    print("ArgoCD Application Health Monitor - Simple Agent")
    print("=" * 60)
    print()
    
    if argocd_client is None:
        print("ERROR: Could not connect to ArgoCD server.")
        print("Please ensure ArgoCD is running and accessible.")
        print()
        print("Configuration:")
        print(f"  Server: {OLLAMA_BASE_URL}")
        print()
        return
    
    print("Connected to ArgoCD server successfully!")
    print()
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
    
    agent = create_agent()
    
    while True:
        try:
            task = input("Enter task: ").strip()
            
            if task.lower() in ['quit', 'q', 'exit']:
                print("\nShutting down ArgoCD monitor. Goodbye!")
                break
            
            if not task:
                continue
            
            print("\nProcessing...")
            result = agent(task)
            print(f"\n{result}\n")
            
        except KeyboardInterrupt:
            print("\n\nShutting down ArgoCD monitor. Goodbye!")
            break
        except Exception as e:
            logger.exception("Error processing task")
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()
