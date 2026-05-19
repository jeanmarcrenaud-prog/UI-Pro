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
- **Visible Agent** with live step-by-step progress ("Thinking Process")
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
- **Thinking Process Display** — animated step progress with visual prominence
- **Persistent Checkpointing** — SQLite-backed session resumption across restarts
- **Model Presets** — light / balanced / heavy for automatic model selection
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
| **Backend**    | FastAPI, Python 3.10+, Pydantic v2               |
| **Config**     | pydantic-settings (YAML + env + runtime)       |
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
cd frontend
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

## 📁 Project Structure (2026-05)

> **NOTE**: `backend/domain/settings.py` is the single source of truth for configuration using pydantic-settings.

```
ui-pro/                    # Project root
├── run.py                    # Main launcher
├── setup.py                  # Automated setup
├── settings.py               # Config wrapper (backward compat)
├── requirements.txt
├── .env.example
├── config.yaml.example      # YAML configuration template
├── data/                     # Checkpoint DB (gitignored)
│   └── checkpoints.db
│
├── backend/                  # SOURCE OF TRUTH
│   ├── domain/
│   │   ├── settings.py      # Unified config (pydantic-settings)
│   │   └── core/           # Business logic
│   │       ├── langgraph_orchestrator.py  # Agent pipeline
│   │       ├── orchestrator_async.py      # Async orchestrator
│   │       ├── code_review.py            # Static analysis
│   │       ├── events.py                 # Event bus
│   │       └── langgraph/               # LangGraph nodes
│   ├── infrastructure/       # Services
│   │   ├── llm_router.py    # LLM routing + streaming
│   │   ├── model_discovery.py  # Model discovery + presets
│   │   ├── streaming.py     # SSE/WebSocket streaming
│   │   ├── code_execution.py # Sandbox execution
│   │   └── memory.py        # FAISS vector store
│   └── transport/           # API layer
│       ├── views_api.py     # FastAPI app
│       └── routers/        # API endpoints
│           ├── ws.py        # WebSocket
│           ├── stream.py    # SSE
│           ├── logs.py      # Log management
│           └── health.py    # Health + settings
│
├── models/                   # Data models (re-exports backend/)
│   └── settings.py
│
└── frontend/                # Next.js frontend
    ├── components/
    │   ├── settings/        # Modular settings components
    │   │   ├── SettingsView.tsx
    │   │   ├── LanguageSelector.tsx
    │   │   ├── TimeoutSettings.tsx
    │   │   ├── LogLevelSettings.tsx
    │   │   ├── ModelSelector.tsx
    │   │   ├── BackendStatusGrid.tsx
    │   │   └── hooks/       # Custom hooks
    │   ├── chat/
    │   │   ├── AgentSteps.tsx   # Thinking Process display
    │   │   └── StepProgress.tsx
    │   └── SystemStats.tsx   # Live metrics
    ├── services/
    │   └── modelDiscovery.ts
    └── lib/
        ├── i18n.ts          # EN + FR translations
        └── stores/          # Zustand state
```

## ⚙️ Configuration

### Configuration Priority

Settings are loaded in this order (later sources override earlier):
1. **config.yaml** - Application defaults
2. **Environment variables** - User overrides
3. **Runtime (UI)** - Live changes from Settings UI

### Model Presets

Three presets are available for automatic model selection:

| Preset | Models | Use Case |
|-------|--------|----------|
| **light** | qwen3.5:0.8b | Quick tasks, low resources |
| **balanced** | qwen3.5:9b | General use, good balance |
| **heavy** | qwen3.6:latest | Complex reasoning, large codebases |

### Settings UI

All settings are configurable via the **Settings UI** at http://localhost:3000:

- **Language** — English / French
- **Timeouts** — LLM and Executor timeouts
- **Log Level** — DEBUG / INFO / WARNING / ERROR / CRITICAL
- **Model Selection** — Choose from discovered models
- **Backend Status** — Live connectivity check

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | http://localhost:11434 | Ollama server URL |
| `MODEL_FAST` | (from preset) | Fast model for simple tasks |
| `MODEL_REASONING` | (from preset) | Reasoning model for complex tasks |
| `MODEL_CODE` | (from preset) | Code-specific model |
| `ACTIVE_PRESET` | balanced | Model preset (light/balanced/heavy) |
| `LLM_TIMEOUT` | 300s | Max time for LLM responses |
| `EXECUTOR_TIMEOUT` | 60s | Max time for code execution |
| `LOG_LEVEL` | INFO | Logging level |
| `LANGSMITH_API_KEY` | (none) | Enable LangSmith tracing |

## 🔐 Security

- Sandboxed code execution with static review
- Input sanitization
- Configurable timeout protection
- No secrets committed (`.env` is gitignored)
- Restricted `exec()` globals in sandbox

## 📝 License

MIT License — feel free to use, modify, and contribute.