# 🚀 AI Agents For DevOps

AI Agents For DevOps is a project that integrates **AI with DevOps tools** to automate monitoring, analysis, and orchestration using:

-  ArgoCD AI Agent (GitOps & Kubernetes monitoring)
-  Docker AI Agent (container monitoring & logs analysis)
-  Ollama (local LLM for AI reasoning)
-  Temporal (workflow orchestration engine)

This project enables intelligent automation for:
- Application health monitoring
- Log analysis
- Resource inspection
- Auto-sync deployments
- AI-driven recommendations

---

## ✨ Features

- AI-powered ArgoCD monitoring  
- Docker AI Agent for container insights  
- Temporal workflows & activities  
- Local AI inference using Ollama  
- Modular Python package structure  
- Secure API token usage  
- Easy to extend for more DevOps tools 


## 🛠️ Prerequisites

- Python 3.9+
- Docker installed
- Kubernetes cluster (for ArgoCD)
- ArgoCD server running
- Temporal server running
- Ollama installed (local LLM)

# 🚀 Run Commands for AI Agents For DevOps

---

## 📥 Clone Repository

```bash
git clone https://github.com/jayantmule03/AI-agents-For-DevOps.git
cd AI-agents-For-DevOps
```
 Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate      # Linux / Mac
venv\Scripts\activate         # Windows
```
 Install Ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
```
 Run ArgoCD AI Agent Worker
```bash
cd ArgoCD-AI-Agent
python3 argocd_worker.py
```
 Run ArgoCD AI Agent client
```bash
cd argocd_monitor 
python3 argocd_client.py
```
Run docker AI Agent Worker
```bash
cd Docker-Ai-Agent
python3 docker_worker.py
```
 Run docker AI Agent client
```bash
python3 docker_client.py
```
