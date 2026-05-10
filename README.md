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
- **Multi-backend LLM support** (Ollama, LM Studio, llama.cpp, Lemonade)
- **Tool calling** & function execution
- **Vector memory** with FAISS
- **Event-driven architecture** for smooth real-time experience

## 🏗️ Architecture

```
┌─────────────────────┐
│   Next.js UI (3000) │ ← Beautiful frontend with streaming
└──────────┬──────────┘
            │
            ▼ WebSocket / SSE
┌──────────▼──────────┐
│   FastAPI (8000)    │ ← Orchestrator + API
└──────────┬──────────┘
            │
            ▼
┌───────▼───────┐
│ LLM Backends  │ ← Ollama / LM Studio / llama.cpp / Lemonade
└───────────────┘
```

## ✨ Key Features

- **Real-time Token Streaming** with live token/s graph
- **Visible Agent** with animated step progress
- **Multi-Model Discovery** — automatic detection of available models
- **Tool Calling** with execution visibility
- **Persistent Memory** via FAISS + rich metadata
- **Safe Code Execution** with sandboxing & review
- **i18n Support** (English + French)
- **Settings Dashboard** with live backend metrics

### UI Highlights
- Elegant dark theme with smooth animations
- Contextual message actions (Regenerate, Continue, Copy)
- Live agent steps with progress tracking
- Responsive and performant

## 🛠️ Tech Stack

| Layer          | Technology                                      |
|----------------|-------------------------------------------------|
| **Frontend**   | Next.js 16, React 18, Tailwind, Framer Motion, Zustand |
| **Backend**    | FastAPI, Python 3.10+, Pydantic                 |
| **LLM**        | Ollama, LM Studio, llama.cpp, Lemonade          |
| **Memory**     | FAISS + SentenceTransformers                    |
| **Events**     | Thread-safe Pub/Sub                             |
| **Streaming**  | WebSocket + SSE                                 |

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

```
ui-pro/
├── run.py                    # Main launcher
├── setup.py                  # Automated setup
├── requirements.txt
├── .env.example
│
├── core/                     # Core logic
│   ├── executor.py          # Safe code executor
│   ├── state_manager.py    # State management
│   ├── memory.py            # FAISS memory
│   └── events.py           # Thread-safe events
│
├── services/                 # Service layer
│   ├── llm_router.py       # LLM routing
│   ├── model_service.py    # Model management
│   ├── model_discovery.py  # Multi-backend discovery
│   ├── streaming.py        # Streaming service
│   └── tools.py            # Tool registry
│
├── controllers/              # Business logic
│   ├── orchestrator.py     # Pipeline orchestrator
│   └── websocket.py        # WebSocket handling
│
├── llm/                      # LLM clients
│   └── router.py           # OllamaClient
│
├── views/                    # API views
│   └── api.py              # FastAPI endpoints
│
├── models/                   # Data models
│   └── settings.py         # Configuration
│
└── ui-pro-ui/                # Next.js frontend
    ├── app/
    │   ├── page.tsx         # Main page
    │   └── layout.tsx       # Layout
    ├── components/
    │   ├── chat/            # Chat components
    │   ├── ui/              # UI components
    │   └── settings/        # Settings components
    ├── lib/
    │   ├── stores/          # Zustand stores
    │   ├── i18n.ts          # Internationalization
    │   └── events.ts       # Event system
    └── services/            # API services
```

## 🔐 Security

- Sandboxed code execution with review
- Input sanitization
- Timeout protection
- No secrets committed (`.env` is gitignored)

## 📝 License

MIT License — feel free to use, modify, and contribute.