# AGENTS.md - UI-Pro

Quick reference for agentic work in this repo.

## Quick Start

```bash
# Activate venv and run
python run.py --all        # FastAPI + Gradio dashboard
python run.py --check       # Verify dependencies

# Ports: FastAPI=8000, Gradio=7860
```

## Project Structure (Post-Refactoring)

### Source of Truth: `backend/`

```
backend/
├── domain/                 # Business logic (SOURCE OF TRUTH)
│   ├── core/              # Core modules
│   │   ├── executor.py    # CodeExecutor (sandbox with auto-fix loop)
│   │   ├── state_manager.py
│   │   ├── orchestrator_async.py
│   │   ├── events.py
│   │   ├── logger.py
│   │   ├── metrics.py
│   │   ├── prompts.py
│   │   ├── code_review.py
│   │   └── constants.py
│   └── errors.py          # Domain errors
├── infrastructure/        # External services
│   ├── streaming.py       # Token streaming
│   ├── model_service.py   # Model management
│   ├── model_discovery.py # Multi-backend discovery
│   ├── memory_service.py # Memory with compression
│   ├── memory.py         # FAISS memory
│   ├── llm_router.py     # Advanced LLM routing
│   ├── tools.py          # Tool execution
│   ├── error_handler.py  # Error handling
│   ├── code_execution.py # Code execution
│   └── base.py           # Service base class
├── application/           # Application layer
│   ├── launcher.py       # Multi-service launcher
│   └── websocket.py      # WebSocket handling
└── transport/             # API endpoints
    ├── main.py           # FastAPI entry point
    ├── views_api.py      # FastAPI app
    ├── dashboard.py      # Gradio dashboard
    ├── translations.py   # i18n
    └── routers/          # API routers
        ├── health.py
        ├── chat.py
        ├── ws.py
        ├── stream.py
        ├── execute.py
        └── logs.py
```

### Legacy Folders (Backward Compatibility Re-exports)

> **IMPORTANT**: These folders now re-export from `backend/`. Import from here for backward compatibility, or import directly from `backend/` for new code.

```
ui-pro/                    # Legacy root (re-exports to backend/)
├── core/                 # → backend/domain/core/
├── services/             # → backend/infrastructure/
├── api/                  # → backend/transport/
├── views/                # → backend/transport/
├── llm/                  # LLM clients (unchanged)
├── models/               # Data types (unchanged)
├── controllers/           # Business logic (unchanged)
├── app/                  # App layer (unchanged)
└── tests/                # Test suite
```

## Migration Status

| Legacy Folder | Target | Status |
|---------------|--------|--------|
| `core/` | `backend/domain/core/` | ✅ Re-export |
| `services/` | `backend/infrastructure/` | ✅ Re-export |
| `api/` | `backend/transport/` | ✅ Re-export |
| `views/` | `backend/transport/` | ✅ Re-export |

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

### 6. Import Pattern
- **New code**: Import directly from `backend/domain/core/`, `backend/infrastructure/`, etc.
- **Legacy code**: Import from `core/`, `services/`, etc. (re-exports work)

## Commands

```bash
# Test single module (new pattern)
python -c "from backend.domain.core import Orchestrator"

# Test single module (legacy pattern - still works)
python -c "from core import Orchestrator"

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
- Don't modify legacy folders directly - modify `backend/` instead