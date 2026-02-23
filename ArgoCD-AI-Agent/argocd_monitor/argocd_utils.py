"""ArgoCD utilities for application health monitoring with structured data types."""

import sys
from pathlib import Path
import logging
import requests
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum

from argocd_monitor.config import (
    ARGOCD_SERVER,
    ARGOCD_AUTH_TOKEN,
    ARGOCD_INSECURE,
    SYNC_TIMEOUT_MINUTES,
    MAX_SYNC_FAILURES,
    DEGRADED_RESOURCE_THRESHOLD
)

logger = logging.getLogger(__name__)


class ArgoCDConnectionError(Exception):
    """Raised when unable to connect to ArgoCD server."""
    pass


class ApplicationNotFoundError(Exception):
    """Raised when specified application doesn't exist."""
    def __init__(self, app_name: str):
        self.app_name = app_name
        super().__init__(f"Application '{app_name}' not found")


class SyncStatus(str, Enum):
    """ArgoCD sync status values."""
    SYNCED = "Synced"
    OUT_OF_SYNC = "OutOfSync"
    UNKNOWN = "Unknown"


class HealthStatus(str, Enum):
    """ArgoCD health status values."""
    HEALTHY = "Healthy"
    PROGRESSING = "Progressing"
    DEGRADED = "Degraded"
    SUSPENDED = "Suspended"
    MISSING = "Missing"
    UNKNOWN = "Unknown"


@dataclass
class ApplicationInfo:
    """Information about an ArgoCD application."""
    name: str
    namespace: str
    project: str
    sync_status: str
    health_status: str
    repo_url: str
    target_revision: str
    path: str
    destination_server: str
    destination_namespace: str
    created_at: Optional[datetime] = None
    sync_started_at: Optional[datetime] = None
    sync_finished_at: Optional[datetime] = None
    
    def __post_init__(self):
        if not self.name:
            raise ValueError("Application name cannot be empty")
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'namespace': self.namespace,
            'project': self.project,
            'sync_status': self.sync_status,
            'health_status': self.health_status,
            'repo_url': self.repo_url,
            'target_revision': self.target_revision,
            'path': self.path,
            'destination_server': self.destination_server,
            'destination_namespace': self.destination_namespace,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sync_started_at': self.sync_started_at.isoformat() if self.sync_started_at else None,
            'sync_finished_at': self.sync_finished_at.isoformat() if self.sync_finished_at else None,
        }
    
    def format_summary(self) -> str:
        """Format application info as a readable summary."""
        sync_icon = "✓" if self.sync_status == "Synced" else "✗"
        health_icon = "✓" if self.health_status == "Healthy" else ("⚠" if self.health_status == "Progressing" else "✗")
        
        lines = [
            f"Application: {self.name}",
            f"  Project: {self.project}",
            f"  Namespace: {self.destination_namespace}",
            f"  {sync_icon} Sync Status: {self.sync_status}",
            f"  {health_icon} Health Status: {self.health_status}",
            f"  Repository: {self.repo_url}",
            f"  Path: {self.path}",
            f"  Target Revision: {self.target_revision}",
            f"  Destination: {self.destination_server}",
        ]
        
        if self.created_at:
            lines.append(f"  Created: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(lines)


@dataclass
class ResourceInfo:
    """Information about a Kubernetes resource in ArgoCD."""
    kind: str
    name: str
    namespace: str
    status: str
    health: str
    sync_status: str
    message: Optional[str] = None
    
    def format_summary(self) -> str:
        health_icon = "✓" if self.health == "Healthy" else ("⚠" if self.health == "Progressing" else "✗")
        sync_icon = "✓" if self.sync_status == "Synced" else "✗"
        
        summary = f"  {health_icon} {self.kind}/{self.name} (ns: {self.namespace}) - Health: {self.health}, Sync: {self.sync_status}"
        if self.message:
            summary += f"\n    Message: {self.message}"
        return summary


@dataclass
class ApplicationHealth:
    """Detailed health status of an ArgoCD application."""
    app_name: str
    is_healthy: bool
    sync_status: str
    health_status: str
    resources: List[ResourceInfo] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    degraded_resources: int = 0
    out_of_sync_resources: int = 0
    total_resources: int = 0
    last_sync_time: Optional[datetime] = None
    sync_revision: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'app_name': self.app_name,
            'is_healthy': self.is_healthy,
            'sync_status': self.sync_status,
            'health_status': self.health_status,
            'degraded_resources': self.degraded_resources,
            'out_of_sync_resources': self.out_of_sync_resources,
            'total_resources': self.total_resources,
            'issues': self.issues,
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'sync_revision': self.sync_revision,
        }
    
    def format_summary(self) -> str:
        """Format health status as a readable summary."""
        health_icon = "✓" if self.is_healthy else "✗"
        health_text = "Healthy" if self.is_healthy else "Unhealthy"
        
        lines = [
            f"{health_icon} {self.app_name}: {health_text}",
            f"  Overall Health: {self.health_status}",
            f"  Sync Status: {self.sync_status}",
            f"  Resources: {self.total_resources} total"
        ]
        
        if self.degraded_resources > 0:
            lines.append(f"  ⚠ Degraded Resources: {self.degraded_resources}")
        
        if self.out_of_sync_resources > 0:
            lines.append(f"  ⚠ Out of Sync Resources: {self.out_of_sync_resources}")
        
        if self.last_sync_time:
            lines.append(f"  Last Sync: {self.last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if self.sync_revision:
            lines.append(f"  Revision: {self.sync_revision[:10]}...")
        
        if self.issues:
            lines.append(f"  Issues:")
            for issue in self.issues:
                lines.append(f"    • {issue}")
        
        if self.resources:
            lines.append(f"\n  Resources ({len(self.resources)}):")
            for resource in self.resources[:10]:  # Show first 10 resources
                lines.append(resource.format_summary())
            if len(self.resources) > 10:
                lines.append(f"  ... and {len(self.resources) - 10} more resources")
        
        return "\n".join(lines)


class ArgoCDClientWrapper:
    """Wrapper around ArgoCD API with consistent error handling."""
    
    def __init__(self, server: str = None, token: str = None, insecure: bool = None):
        self.server = server or ARGOCD_SERVER
        self.token = token or ARGOCD_AUTH_TOKEN
        self.insecure = insecure if insecure is not None else ARGOCD_INSECURE
        
        self.base_url = f"http{'s' if not self.insecure else ''}://{self.server}/api/v1"
        self.headers = {}
        
        if self.token:
            self.headers['Authorization'] = f'Bearer {self.token}'
        
        # Test connection
        try:
            self._test_connection()
            logger.info("Successfully connected to ArgoCD server")
        except Exception as e:
            logger.error(f"Failed to connect to ArgoCD server: {e}")
            raise ArgoCDConnectionError(
                f"ArgoCD server is not accessible at {self.server}. Please ensure ArgoCD is running."
            ) from e
    
    def _test_connection(self):
        """Test connection to ArgoCD server."""
        try:
            response = requests.get(
                f"{self.base_url}/applications",
                headers=self.headers,
                timeout=5,
                verify=not self.insecure
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ArgoCDConnectionError(f"Cannot connect to ArgoCD: {e}")
    
    def get_applications(self, project: str = None) -> List[ApplicationInfo]:
        """Get list of ArgoCD applications."""
        try:
            url = f"{self.base_url}/applications"
            if project:
                url += f"?project={project}"
            
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10,
                verify=not self.insecure
            )
            response.raise_for_status()
            
            data = response.json()
            applications = []
            
            for item in data.get('items', []):
                app = self._parse_application(item)
                applications.append(app)
            
            return applications
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get applications: {e}")
            raise ArgoCDConnectionError(f"Failed to retrieve applications: {e}")
    
    def get_application(self, app_name: str) -> ApplicationInfo:
        """Get details of a specific application."""
        try:
            response = requests.get(
                f"{self.base_url}/applications/{app_name}",
                headers=self.headers,
                timeout=10,
                verify=not self.insecure
            )
            
            if response.status_code == 404:
                raise ApplicationNotFoundError(app_name)
            
            response.raise_for_status()
            return self._parse_application(response.json())
            
        except ApplicationNotFoundError:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get application {app_name}: {e}")
            raise ArgoCDConnectionError(f"Failed to retrieve application: {e}")
    
    def _parse_application(self, data: dict) -> ApplicationInfo:
        """Parse application data from ArgoCD API."""
        metadata = data.get('metadata', {})
        spec = data.get('spec', {})
        status = data.get('status', {})
        
        source = spec.get('source', {})
        destination = spec.get('destination', {})
        
        created_at = None
        created_str = metadata.get('creationTimestamp')
        if created_str:
            try:
                created_at = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
            except:
                pass
        
        sync_started = None
        sync_finished = None
        operation_state = status.get('operationState', {})
        if operation_state:
            started_str = operation_state.get('startedAt')
            finished_str = operation_state.get('finishedAt')
            
            if started_str:
                try:
                    sync_started = datetime.fromisoformat(started_str.replace('Z', '+00:00'))
                except:
                    pass
            
            if finished_str:
                try:
                    sync_finished = datetime.fromisoformat(finished_str.replace('Z', '+00:00'))
                except:
                    pass
        
        return ApplicationInfo(
            name=metadata.get('name', 'unknown'),
            namespace=metadata.get('namespace', 'argocd'),
            project=spec.get('project', 'default'),
            sync_status=status.get('sync', {}).get('status', 'Unknown'),
            health_status=status.get('health', {}).get('status', 'Unknown'),
            repo_url=source.get('repoURL', ''),
            target_revision=source.get('targetRevision', 'HEAD'),
            path=source.get('path', ''),
            destination_server=destination.get('server', ''),
            destination_namespace=destination.get('namespace', ''),
            created_at=created_at,
            sync_started_at=sync_started,
            sync_finished_at=sync_finished
        )
    
    def check_application_health(self, app_name: str) -> ApplicationHealth:
        """Check detailed health status of an application."""
        try:
            response = requests.get(
                f"{self.base_url}/applications/{app_name}",
                headers=self.headers,
                timeout=10,
                verify=not self.insecure
            )
            
            if response.status_code == 404:
                raise ApplicationNotFoundError(app_name)
            
            response.raise_for_status()
            data = response.json()
            
            status = data.get('status', {})
            health = status.get('health', {})
            sync = status.get('sync', {})
            
            health_status = health.get('status', 'Unknown')
            sync_status = sync.get('status', 'Unknown')
            
            issues = []
            is_healthy = True
            
            # Check overall health
            if health_status not in ['Healthy', 'Progressing']:
                is_healthy = False
                issues.append(f"Application health is {health_status}")
            
            # Check sync status
            if sync_status != 'Synced':
                is_healthy = False
                issues.append(f"Application is {sync_status}")
            
            # Parse resources
            resources = []
            degraded_count = 0
            out_of_sync_count = 0
            
            for resource in status.get('resources', []):
                resource_health = resource.get('health', {}).get('status', 'Unknown')
                resource_sync = resource.get('status', 'Unknown')
                
                resource_info = ResourceInfo(
                    kind=resource.get('kind', 'Unknown'),
                    name=resource.get('name', 'unknown'),
                    namespace=resource.get('namespace', ''),
                    status=resource.get('status', 'Unknown'),
                    health=resource_health,
                    sync_status=resource_sync,
                    message=resource.get('health', {}).get('message')
                )
                resources.append(resource_info)
                
                if resource_health in ['Degraded', 'Missing']:
                    degraded_count += 1
                    issues.append(f"Resource {resource_info.kind}/{resource_info.name} is {resource_health}")
                
                if resource_sync != 'Synced':
                    out_of_sync_count += 1
            
            if degraded_count >= DEGRADED_RESOURCE_THRESHOLD:
                is_healthy = False
            
            # Get last sync time
            last_sync = None
            sync_result = status.get('operationState', {})
            finished_str = sync_result.get('finishedAt')
            if finished_str:
                try:
                    last_sync = datetime.fromisoformat(finished_str.replace('Z', '+00:00'))
                except:
                    pass
            
            sync_revision = sync.get('revision', '')
            
            return ApplicationHealth(
                app_name=app_name,
                is_healthy=is_healthy,
                sync_status=sync_status,
                health_status=health_status,
                resources=resources,
                issues=issues,
                degraded_resources=degraded_count,
                out_of_sync_resources=out_of_sync_count,
                total_resources=len(resources),
                last_sync_time=last_sync,
                sync_revision=sync_revision
            )
            
        except ApplicationNotFoundError:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to check health for {app_name}: {e}")
            raise ArgoCDConnectionError(f"Failed to check application health: {e}")
    
    def get_application_logs(self, app_name: str, resource_name: str = None, 
                            container: str = None, tail_lines: int = 100) -> str:
        """Get logs from application resources."""
        try:
            # First get the application to find resources
            app_data = requests.get(
                f"{self.base_url}/applications/{app_name}",
                headers=self.headers,
                timeout=10,
                verify=not self.insecure
            ).json()
            
            if not resource_name:
                # Get logs from first pod resource
                resources = app_data.get('status', {}).get('resources', [])
                pod_resources = [r for r in resources if r.get('kind') == 'Pod']
                
                if not pod_resources:
                    return f"No pod resources found in application '{app_name}'"
                
                resource_name = pod_resources[0].get('name')
                namespace = pod_resources[0].get('namespace', '')
            else:
                namespace = app_data.get('spec', {}).get('destination', {}).get('namespace', '')
            
            # Get pod logs via ArgoCD
            params = {
                'podName': resource_name,
                'namespace': namespace,
                'tailLines': str(tail_lines)
            }
            
            if container:
                params['container'] = container
            
            response = requests.get(
                f"{self.base_url}/applications/{app_name}/logs",
                headers=self.headers,
                params=params,
                timeout=15,
                verify=not self.insecure
            )
            
            if response.status_code == 404:
                return f"Logs not available for resource '{resource_name}'"
            
            response.raise_for_status()
            
            # ArgoCD returns logs in a specific format
            logs = response.text
            
            if not logs:
                return f"No logs found for resource '{resource_name}' in application '{app_name}'"
            
            return logs
            
        except ApplicationNotFoundError:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get logs for {app_name}: {e}")
            return f"Failed to retrieve logs: {e}"
    
    def sync_application(self, app_name: str, prune: bool = False, dry_run: bool = False) -> str:
        """Trigger sync for an application."""
        try:
            payload = {
                'revision': 'HEAD',
                'prune': prune,
                'dryRun': dry_run
            }
            
            response = requests.post(
                f"{self.base_url}/applications/{app_name}/sync",
                headers=self.headers,
                json=payload,
                timeout=30,
                verify=not self.insecure
            )
            
            if response.status_code == 404:
                raise ApplicationNotFoundError(app_name)
            
            response.raise_for_status()
            
            logger.info(f"Successfully triggered sync for {app_name}")
            return f"✓ Successfully triggered sync for application '{app_name}'"
            
        except ApplicationNotFoundError:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to sync application {app_name}: {e}")
            raise ArgoCDConnectionError(f"Failed to sync application: {e}")
    
    def get_application_events(self, app_name: str) -> List[Dict]:
        """Get recent events for an application."""
        try:
            response = requests.get(
                f"{self.base_url}/applications/{app_name}/events",
                headers=self.headers,
                timeout=10,
                verify=not self.insecure
            )
            
            if response.status_code == 404:
                raise ApplicationNotFoundError(app_name)
            
            response.raise_for_status()
            
            events = response.json().get('items', [])
            return events
            
        except ApplicationNotFoundError:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get events for {app_name}: {e}")
            return []

