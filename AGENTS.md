# AGENTS.md - UI-Pro

Quick reference for agentic work in this repo.

## Quick Start

```bash
# Activate venv and run
python run.py --all        # FastAPI + Gradio dashboard
python run.py --check       # Verify dependencies

# Ports: FastAPI=8000, Gradio=7860
```

## Project Structure (MVC)

```
ui-pro/
├── run.py                  # Entry point
├── core/                   # Core modules
│   ├── executor.py        # CodeExecutor (sandbox with auto-fix loop)
│   ├── state_manager.py  # StateManager
│   ├── memory.py         # FAISS memory
│   ├── metrics.py         # MetricsManager
│   ├── logger.py          # Logging + rotation
│   ├── events.py          # Thread-safe event pub/sub
│   ├── orchestrator_async.py  # Async orchestrator
│   └── config.py          # YAML loader + env overrides
├── controllers/            # Business logic
│   ├── orchestrator.py    # Pipeline orchestrator (DEPRECATED)
│   ├── websocket.py       # WebSocket handling
│   ├── code_review.py     # Code review logic
│   └── executor.py        # CodeExecutor
├── services/               # Service layer
│   ├── llm_router.py      # Advanced LLM routing
│   ├── model_service.py   # Model management
│   ├── memory_service.py  # Memory with compression
│   ├── streaming.py       # Token streaming
│   ├── tools.py           # Tool execution
│   └── error_handler.py   # Error handling
├── llm/                    # LLM clients
│   ├── router.py          # Basic model routing
│   └── client.py          # OllamaClient
├── models/                 # Data models (schemas)
│   ├── settings.py        # Configuration (SOURCE OF TRUTH)
│   ├── config.py          # Pydantic config models
│   ├── metrics.py         # Metrics dataclasses
│   └── memory.py          # Memory dataclasses
├── app/                    # App layer
│   └── launcher.py        # Multi-service launcher
├── views/                  # View layer
│   ├── api.py             # Main API
│   ├── dashboard.py       # Dashboard
│   └── components/        # Gradio components
├── templates/             # Static templates
├── tests/                 # Test suite (85+ tests)
├── workspace/             # Generated code
└── configs/               # YAML/JSON configs
```
ui-pro/
├── run.py                  # Entry point
├── core/                   # Core modules
│   ├── executor.py        # CodeExecutor (sandbox with auto-fix loop)
│   ├── state_manager.py  # StateManager
│   ├── memory.py         # FAISS memory
│   └── orchestrator_async.py  # Async orchestrator
├── controllers/            # Business logic
│   └── orchestrator.py  # Pipeline: planner → architect → coder → reviewer → executor
├── services/             # Service layer
│   ├── llm_router.py   # Advanced LLM routing
│   ├── model_service.py
│   └── memory_service.py
├── llm/                  # LLM clients
│   ├── router.py       # Basic model routing
│   └── client.py       # Ollama client
├── models/               # Data types (NOT logic)
│   └── settings.py     # Configuration
└── views/               # API layer
    ├── api.py          # FastAPI endpoints
    └── dashboard.py    # Gradio interface
```

## Structure Après Refactoring

```
models/              → types ONLY (settings, config)
core/               → core logic (memory, state, executor, config)
llm/                → LLM routing et clients
services/            → service layer
controllers/         → orchestrator, workflow
```

## Critical Quirks

### 1. Circular Import Trap
NEVER import from `models` → `views` → `controllers` → `models`. If you need a cross-layer import, do it inside functions, not at module level.

### 2. Gradio 6 Navigation
Use `gr.update(visible=...)` NOT boolean values:
```python
def _on_nav_change(tab):
    return [gr.update(visible=tab == "Task Input"), ...]
```

### 3. LLMRouter Config
Settings uses `model_fast`/`model_reasoning`, NOT `fast`/`reasoning`. The `.env` file is gitignored - check actual values with `Settings()` instance.

### 4. Executor Code Format
`executor.run()` expects code dict like `{"files": {"main.py": "..."}}` - handle both string and dict in `_prepare_code()`.

### 5. Ollama Models
Available models are shown at startup. Default `.env` uses `gemma4:latest`. Other configured models may not exist.

## Commands

```bash
# Test single module
python -c "from controllers.orchestrator import Orchestrator"

# Run app
python run.py --all

# Lint
mypy . && black --check . && isort --check-only .

# Tests
pytest tests/ -v
```

## What NOT to Do

- Don't commit `.env` (it's in `.gitignore`)
- Don't use bare `except:` - catch specific exceptions
- Don't import at module level across MVC layers
- Don't assume all Ollama models exist - check startup output
