# UI-Pro - AI Agent Orchestration System

![UI-Pro Banner](https://github.com/user-attachments/assets/6d3f5ad0-1dee-4d03-80d3-da7281f66ebc)

> **Modern self-hosted AI Agent system** with a beautiful ChatGPT-like interface.

![Status](https://img.shields.io/badge/status-beta-orange)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Next.js](https://img.shields.io/badge/Next.js-16-blue)

## 🚀 Overview

**UI-Pro** is a full-featured AI Agent orchestration platform that combines:

- **Beautiful modern UI** (ChatGPT-style) with real-time streaming
- **Visible Agent** with live step-by-step progress
- **LangGraph Orchestrator** with persistent checkpointing
- **Multi-backend LLM support** (Ollama, LM Studio, llama.cpp, Lemonade)
- **Tool calling** & safe code execution
- **Vector memory** with FAISS
- **Distributed tracing** via LangSmith
- **Configurable timeouts** via Settings UI

## 🏗️ Architecture

```
┌─────────────────────┐
│   Next.js UI (3000) │ ← Beautiful frontend with streaming
└──────────┬──────────┘
            │
            ▼ WebSocket / SSE
┌──────────▼──────────┐
│   FastAPI (8000)    │ ← LangGraph Orchestrator + API
└──────────┬──────────┘
            │
            ▼
┌───────▼───────┐
│ LLM Backends  │ ← Ollama / LM Studio / llama.cpp / Lemonade
└───────────────┘
```

## ✨ Key Features

- **Real-time Token Streaming** — token-by-token with live tokens/s graph
- **Visible Agent** — animated step progress (Analyze → Plan → Code → Review → Execute)
- **Persistent Checkpointing** — SQLite-backed session resumption across restarts
- **Multi-Model Discovery** — automatic detection of available models
- **Configurable Timeouts** — LLM and Executor timeouts via Settings UI
- **Safe Code Execution** — sandboxed execution with static analysis
- **Distributed Tracing** — LangSmith integration for debugging and monitoring
- **i18n Support** — English + French
- **Settings Dashboard** — live backend metrics, model selection, timeout config

### Agent Pipeline
1. **Analyzing** — classifies task and selects strategy
2. **Planning** — creates implementation roadmap
3. **Coding** — generates code via LLM with token streaming
4. **Reviewing** — static analysis and security check
5. **Executing** — runs generated code in sandbox with retry loop

## 🛠️ Tech Stack

| Layer          | Technology                                      |
|----------------|-------------------------------------------------|
| **Frontend**   | Next.js 16, React 18, Tailwind, Framer Motion, Zustand |
| **Backend**    | FastAPI, Python 3.10+, Pydantic                 |
| **Orchestration** | LangGraph with AsyncSqliteSaver checkpointer  |
| **LLM**        | Ollama, LM Studio, llama.cpp, Lemonade         |
| **Memory**     | FAISS + SentenceTransformers                    |
| **Events**     | Thread-safe Pub/Sub                             |
| **Streaming**  | WebSocket + SSE                                 |
| **Tracing**    | LangSmith (optional)                             |

## 🚀 Quick Start

### Option 1: Automatic Setup (Recommended)

```bash
git clone https://github.com/jeanmarcrenaud-prog/UI-Pro.git
cd UI-Pro

python setup.py
```

The setup script will:
- Check Python 3.10+, Node.js, npm
- Create `.venv` virtual environment
- Install Python & Node.js dependencies
- Create `.env` from template
- Check for LLM backends (Ollama, LM Studio, Lemonade)
- **Offer to install Ollama** if no backend detected

### Option 2: Manual

```bash
git clone https://github.com/jeanmarcrenaud-prog/UI-Pro.git
cd UI-Pro

# Python
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt

# Frontend
cd ui-pro-ui
npm install
cd ..

# Launch
python run.py --all
```

Open http://localhost:3000

### Enable LangSmith Tracing (Optional)

1. Get your API key at https://smith.langchain.com
2. Edit `.env` and uncomment the LangSmith section:
```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_your_key_here
LANGSMITH_PROJECT=ui-pro-production
```
3. Restart the server

## 📋 Commands

| Command               | Description                    |
|-----------------------|--------------------------------|
| `python run.py --all` | Start everything              |
| `python run.py --api` | FastAPI only                  |
| `python run.py --ui`  | Next.js UI only               |
| `python run.py --status` | Show service status        |
| `python run.py --check` | Verify dependencies         |
| `python setup.py`     | Auto-setup environment        |
| `python setup.py --yes` | Non-interactive setup      |

## 📁 Project Structure

> **Note**: `backend/` is the source of truth. Legacy folders (`core/`, `services/`, `api/`, `views/`) are re-exports for backward compatibility.

```
ui-pro/
├── run.py                    # Main launcher
├── setup.py                  # Automated setup
├── requirements.txt
├── .env.example
├── data/                     # Checkpoint DB (gitignored)
│   └── checkpoints.db
│
├── backend/                  # SOURCE OF TRUTH
│   ├── domain/
│   │   └── core/            # Business logic
│   │       ├── langgraph_orchestrator.py  # Agent pipeline
│   │       ├── orchestrator_async.py      # Legacy orchestrator
│   │       ├── code_review.py            # Static analysis
│   │       ├── events.py                 # Event bus
│   │       └── settings.py               # Configuration
│   ├── infrastructure/       # Services
│   │   ├── llm_router.py    # LLM routing + streaming
│   │   ├── streaming.py     # SSE/WebSocket streaming
│   │   ├── code_execution.py # Sandbox execution
│   │   ├── model_service.py
│   │   └── memory.py        # FAISS vector store
│   └── transport/            # API layer
│       ├── views_api.py     # FastAPI app
│       ├── dashboard.py     # Gradio dashboard
│       └── routers/         # API endpoints
│           ├── ws.py         # WebSocket
│           ├── stream.py     # SSE
│           ├── chat.py       # REST fallback
│           └── health.py     # Health + settings
│
├── llm/                      # LLM clients
│   └── router.py           # OllamaClient (with astream)
│
├── models/                   # Data models (re-exports backend/)
│   └── settings.py
│
└── ui-pro-ui/                # Next.js frontend
    ├── components/
    │   ├── SettingsView.tsx  # Model selection + timeouts
    │   ├── SystemStats.tsx   # Live metrics
    │   └── ...
    ├── services/
    │   └── modelDiscovery.ts # Backend model discovery
    └── lib/
        ├── i18n.ts          # EN + FR translations
        └── stores/         # Zustand state
```

## ⚙️ Configuration

All settings are configurable via the **Settings UI** or `.env`:

| Setting              | Default | Description |
|----------------------|---------|-------------|
| `OLLAMA_URL`         | localhost:11434 | Ollama server URL |
| `MODEL_FAST`         | qwen3.5:9b | Fast model (coding) |
| `MODEL_REASONING`    | qwen3.5:9b | Reasoning model (planning) |
| `LLM_TIMEOUT`       | 300s | Max time for LLM responses |
| `EXECUTOR_TIMEOUT`   | 60s | Max time for code execution |
| `LANGSMITH_API_KEY`  | (none) | Enable LangSmith tracing |

## 🔐 Security

- Sandboxed code execution with static review
- Input sanitization
- Configurable timeout protection
- No secrets committed (`.env` is gitignored)
- Restricted `exec()` globals in sandbox

## 📝 License

MIT License — feel free to use, modify, and contribute.