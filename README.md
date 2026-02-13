# 🚀 MCP ChatBot - Professional Enterprise-Grade System

A production-ready, feature-rich chatbot integrated with Model Context Protocol (MCP) and multiple LLM providers.

## ✨ Key Features

- **Multi-LLM Support**: Seamlessly switch between DeepSeek, Ollama, Claude, and OpenAI.
- **MCP Integration**: Unified orchestrator for connecting to multiple external MCP servers.
- **Production-Grade Infrastructure**:
  - **Persistence**: PostgreSQL backend for users, conversations, and message history.
  - **Caching**: Redis-backed session management and rate limiting.
  - **Security**: JWT & API Key authentication with RBAC and Tier-based quotas.
  - **Streaming**: Token-by-token delivery via Server-Sent Events (SSE) and WebSockets.
  - **Observability**: Prometheus metrics, health checks, and structured JSON logging.
  - **Deployment**: Dockerized with Kubernetes manifests and CI/CD pipelines.

## 🛠️ Tech Stack

- **Framework**: FastAPI (Python 3.10+)
- **LLM SDKs**: OpenAI, Anthropic
- **Database**: PostgreSQL (SQLAlchemy Async), Redis
- **DevOps**: Docker, Kubernetes, GitHub Actions
- **Monitoring**: Prometheus, Structlog

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10+
- Docker & Docker Compose
- PostgreSQL & Redis (or use Docker)

### 2. Installation

```bash
git clone https://github.com/Debashish-deb/ChatBot.git
cd ChatBot
pip install -r requirements.txt
```

### 3. Configuration

Copy `.env.production.example` to `.env` and fill in your secrets:

```bash
cp .env.production.example .env
```

### 4. Running Locally

```bash
uvicorn app.main:app --reload
```

## 📖 API Documentation

Once running, visit:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Metrics**: `http://localhost:8000/metrics`

## 🧪 Testing

```bash
pytest
```

## 🚢 Deployment

See [QUICK_START_GUIDE.md](QUICK_START_GUIDE.md) for detailed deployment instructions for Docker and Kubernetes.
