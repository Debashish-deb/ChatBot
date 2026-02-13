# 🤖 MCP ChatBot

A high-performance, production-ready ChatBot built with **FastAPI** and integrated with the **Model Context Protocol (MCP)**. This project supports multiple LLM providers, including **DeepSeek**, **Ollama**, and **Claude**.

---

## 🚀 Key Features

- **Multi-LLM Support**: Seamlessly switch between **DeepSeek**, **Ollama**, **Claude**, and **OpenAI**.
- **Modular Architecture**: Clean separation of concerns with dedicated layers for API, Services, Models, and MCP logic.
- **MCP Integration**: Dynamic tool discovery and execution via the Model Context Protocol.
- **FastAPI Pro**: Lifespan management, structured logging, global exception handling, and Pydantic v2 validation.
- **RESTful API**: Versioned endpoints (`/api/v1`) with full OpenAPI documentation.
- **Containerized**: Ready-to-use `Dockerfile` and `docker-compose.yml`.

---

## 🛠️ Getting Started

### Prerequisites

- Python 3.10+
- [Docker](https://www.docker.com/) (optional)
- API Key for your preferred provider (DeepSeek, Claude, or OpenAI) OR local Ollama instance.

### Local Installation

1. **Clone the repository**:

   ```bash
   git clone <repo-url>
   cd ChatBot
   ```

2. **Create a virtual environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Setup**:

   ```bash
   cp .env.example .env
   # Edit .env and set LLM_PROVIDER and relevant API keys
   ```

5. **Run the application**:

   ```bash
   python -m app.main
   ```

---

## ⚙️ Configuration

Configure your LLM provider in the `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | `deepseek`, `ollama`, `anthropic`, or `openai` | `deepseek` |
| `DEEPSEEK_API_KEY` | Your DeepSeek API Key | - |
| `ANTHROPIC_API_KEY` | Your Anthropic (Claude) API Key | - |
| `OLLAMA_BASE_URL` | Base URL for your Ollama instance | `http://localhost:11434` |

---

## 📖 Usage

### API Endpoints

- **GET `/`**: Welcome message and version info.
- **GET `/api/v1/health`**: Service health status.
- **POST `/api/v1/chat`**: Primary chat interface.

### Example Request

```json
POST /api/v1/chat
{
  "messages": [
    {"role": "user", "content": "What is the status of my internal software budget?"}
  ]
}
```

---

## 🛠️ Extending with MCP Tools

This project features a sample `BudgetTool` in `app/mcp/tools/budget_tool.py`.

1. Create a class inheriting from `BaseMCPTool`.
2. Implement required properties and the `execute` async function.
3. Register it in `tool_registry`.

The `ChatService` orchestrator automatically manages tool detection and execution across all supported LLM providers.

---

## 🧪 Testing

Run tests using Pytest:

```bash
pytest
```

---

## 📜 License

Created with ❤️ using Antigravity.
