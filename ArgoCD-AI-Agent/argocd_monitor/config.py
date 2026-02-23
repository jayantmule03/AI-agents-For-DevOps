# Temporal Configuration
TEMPORAL_HOST = "localhost:7233"
ARGOCD_MONITOR_TASK_QUEUE = "argocd-monitor-queue"

# Ollama Configuration
OLLAMA_MODEL_ID = "qwen2.5:7b-instruct"
OLLAMA_BASE_URL = "http://localhost:11434"

# ArgoCD Configuration
ARGOCD_SERVER = "localhost:8080"  
ARGOCD_AUTH_TOKEN = ""  # Set via environment variable or config
ARGOCD_INSECURE = True  

# Thresholds for health checks
SYNC_TIMEOUT_MINUTES = 10
MAX_SYNC_FAILURES = 3
DEGRADED_RESOURCE_THRESHOLD = 2
