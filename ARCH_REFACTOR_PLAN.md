# Architecture Refactoring Plan

## Current State (Problems)

- Duplicates: `core/memory` + `models/memory`, `views/dashboard` + `ui/dashboard`
- Mixed concerns: controllers/, core/, models/, views/ all mixed
- No clear separation between entry points, business logic, and adapters

## Target Structure

```
ui-pro/
├── app/                    # Entry points
│   ├── __init__.py
│   ├── launcher.py         # run.py (renamed)
│   └── cli.py             # CLI if needed
│
├── core/                   # Utilities & shared
│   ├── __init__.py
│   ├── config.py          # Configuration loader
│   ├── logger.py          # Logging setup
│   ├── state.py           # State management
│   └── metrics.py         # Metrics collection
│
├── services/               # Business logic
│   ├── __init__.py
│   ├── base.py            # BaseService
│   ├── orchestrator.py    # Main pipeline
│   ├── model_service.py   # LLM routing
│   ├── memory_service.py  # Memory/FAISS
│   ├── chat_service.py    # Chat orchestration
│   └── api.py             # Service facade
│
├── adapters/               # External integrations
│   ├── __init__.py
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py      # Ollama/HTTP client
│   ├── memory/
│   │   └── __init__.py    # FAISS adapter
│   └── executor/
│       ├── __init__.py
│       └── sandbox.py     # Code execution
│
├── models/                 # Data models
│   ├── __init__.py
│   ├── settings.py         # Settings dataclass
│   └── types.py            # Type definitions
│
├── config/                 # Configuration files
│   ├── __init__.py
│   └── settings.py         # Settings loader
│
├── views/                  # UI (keep for now)
│   ├── __init__.py
│   ├── dashboard.py        # Gradio UI
│   └── api.py              # FastAPI endpoints
│
├── tests/                  # Tests (keep)
├── data/                   # Runtime data (keep)
├── assets/                 # Static assets (keep)
├── .env.example
├── .gitignore
├── run.py                  # Legacy entry (redirect to app/)
├── README.md
└── requirements.txt
```

## Files to Move

| Source | Destination |
|--------|-------------|
| `run.py` | `app/launcher.py` |
| `services/base.py` | `services/base.py` (keep) |
| `services/orchestrator` | `services/orchestrator.py` (create from existing) |
| `services/model_service.py` | `services/model_service.py` (keep) |
| `services/memory_service.py` | `services/memory_service.py` (keep) |
| `services/chat_service.py` | `services/chat_service.py` (keep) |
| `services/api.py` | `services/api.py` (keep) |
| `controllers/llm_client.py` | `adapters/llm/client.py` |
| `models/settings.py` | `models/settings.py` (keep) |
| `core/config.py` | `core/config.py` (keep) |
| `core/logger.py` | `core/logger.py` (keep) |
| `core/state_manager.py` | `core/state.py` |
| `core/metrics.py` | `core/metrics.py` (keep) |
| `controllers/executor.py` | `adapters/executor/sandbox.py` |
| `models/memory.py` | `adapters/memory/faiss.py` |

## Duplicates to Remove

- `core/memory.py` → use `models/memory.py`
- `ui/dashboard.py` → remove (use `views/dashboard.py`)
- `orchestrator.py` (root) → remove (use `controllers/orchestrator.py`)
- `core/orchestrator_async.py` → consolidate into `services/orchestrator.py`
- `controllers/code_review.py` → consolidate into `services/`
- `core/code_review.py` → remove

## Import Updates Needed

After moving files, update imports in:
- `views/dashboard.py`
- `views/api.py`
- `app/launcher.py` (new)
- `services/`

## Execution Order

1. Create new folder structure
2. Move files
3. Update imports
4. Remove duplicates
5. Create `run.py` as redirect to `app/launcher.py`
6. Test everything works