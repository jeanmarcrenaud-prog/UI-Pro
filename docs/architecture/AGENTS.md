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
+-- domain/                 # Business logic (SOURCE OF TRUTH)
|   +-- core/              # Core modules
|   |   +-- action_executor.py   # Code actions (insert, delete, rename)
|   |   +-- code_review.py       # Bandit-based code review
|   |   +-- constants.py         # Agent step enums
|   |   +-- editor_service.py    # Editor orchestration
|   |   +-- editor_state.py      # Editor state management
|   |   +-- events.py            # Event bus (Pub/Sub)
|   |   +-- executor.py          # Code sandbox executor
|   |   +-- filesystem_service.py # Safe file I/O
|   |   +-- langgraph/           # Pipeline nodes
|   |   +-- logger.py            # Logging
|   |   +-- metrics.py           # Performance metrics
|   |   +-- models.py            # Domain models (EditorState, Action, etc.)
|   |   +-- orchestrator_async.py # Async pipeline orchestrator
|   |   +-- planner.py           # Local task planner
|   |   +-- prompts.py           # LLM prompts
|   |   +-- state_manager.py     # Pipeline state management
|   +-- errors.py          # Domain error hierarchy
+-- infrastructure/        # External services & backends
|   +-- llm/               # LLM clients (Ollama, LM Studio, etc.)
|   |   +-- hermes.py      # Hermes LLM integration
|   |   +-- ollama.py      # Ollama client
|   |   +-- lmstudio.py    # LM Studio client
|   |   +-- llamacpp.py    # llama.cpp client
|   |   +-- lemonade.py    # Lemonade client
|   |   +-- ...            # Other LLM backends
|   +-- mcp/               # MCP server (Hermes)
|   |   +-- server.py      # FastMCP server with tools
|   +-- opencode_connector/ # OpenCode headless integration
|   |   +-- manager.py     # Subprocess lifecycle + JSON protocol
|   |   +-- client.py      # OpenCode client
|   |   +-- models.py      # Connector models
|   +-- streaming/         # SSE/WebSocket streaming
|   +-- executors/         # Code executors
|   +-- voice/             # Voice services (STT/TTS/VAD)
|   +-- terminal/          # Terminal emulation
|   +-- tools/             # Tool registry & execution
|   +-- monitoring/        # Tracing & metrics
|   +-- adapters/          # FAISS memory adapter
|   +-- llm_router.py     # Multi-model routing
|   +-- model_discovery.py # Model discovery
|   +-- memory.py          # FAISS memory
|   +-- checkpointer.py    # SQLite checkpointing
|   +-- code_execution.py  # Python sandbox execution
|   +-- rate_limit.py      # Rate limiting
+-- application/           # Application layer
|   +-- intelligence/      # Intent processing
|   |   +-- intelligence_service.py # Intent to plan to delegate/execute
|   |   +-- task_planner.py        # Plan generation
|   +-- editor_manager.py  # Editor coordination
|   +-- voice_manager.py   # Voice flow management
|   +-- websocket.py       # WebSocket handling
+-- transport/             # API endpoints
    +-- main.py            # FastAPI entry point
    +-- views_api.py       # REST API routes
    +-- websocket_manager.py # WebSocket connection manager
    +-- routers/           # Route modules
        +-- chat.py
        +-- ws.py
        +-- stream.py
        +-- execute.py
        +-- health.py
        +-- logs.py
        +-- mario.py        # Mario agent router
        +-- node_metrics.py
```

### Project Structure (2026-05)

> **NOTE**: Legacy re-export folders (core/, services/, api/, views/, controllers/) have been **deleted**. All code now imports directly from `backend/`.

```
ui-pro/                    # Racine projet
-- backend/               # SOURCE DE VÉRITÉ (uniquement)
|   +-- domain/            # Business logic + settings
|   +-- infrastructure/    # Services: LLM, streaming, MCP, OpenCode, voice, terminal
|   +-- application/       # App layer: intelligence, editor, voice, WebSocket
|   +-- transport/         # API: FastAPI, routers, WebSocket manager
-- frontend/             # Frontend Next.js
-- scripts/              # Scripts utilitaires
-- tests/                # Tests pytest
-- docs/                 # Documentation
-- data/                 # Checkpoints DB + FAISS index
-- logs/                 # Application logs
-- workspace/            # Code généré
```

## Migration Status (COMPLETED)

| Legacy Folder | Target | Status |
|---------------|--------|--------|
| `core/` | `backend/domain/core/` | ✅ Supprimé |
| `services/` | `backend/infrastructure/` | ✅ Supprimé |
| `api/` | `backend/transport/` | ✅ Supprimé |
| `views/` | `backend/transport/` | ✅ Supprimé |
| `controllers/` | `backend/application/` | ✅ Supprimé |

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
- **Nouveau code**: Importez directement depuis `backend/domain/core/`, `backend/infrastructure/`, etc.
- **Plus de legacy folders**: Les dossiers re-export ont été supprimés.

### 7. LLM_TIMEOUT vs Ollama read_timeout (must stay aligned)
There are **TWO** timeout values that must stay in sync, or the backend
HTTP client kills the request before the LLM wrapper can finish:

| Layer | Setting | Default | Location |
|-------|---------|---------|----------|
| Outer (Python wrapper) | `LLM_TIMEOUT` | **900s** | `backend/domain/settings.py` (`Settings.llm_timeout`) |
| Inner (HTTP client) | `read_timeout` | **900s** | `backend/domain/settings.py` (`backends_template[*].timeout`) |

**Symptom of desync**: `Ollama async stream failed: Read timed out. (read timeout=300)`
in `run_error.log` followed by `TimeoutError: LLM call timed out after Ns`.

**Fix**: If you bump `LLM_TIMEOUT` (UI Settings or `.env`), bump all four
`backends_template[*].timeout` values in the same commit. The Settings
`set_timeout()` helper only touches `LLM_TIMEOUT`/`EXECUTOR_TIMEOUT`, NOT
the backend read timeouts — those are independent.

Full troubleshooting guide: `README.md` → "Troubleshooting → LLM_TIMEOUT".
API-level detail: `docs/api/API.md` → "504 — LLM Timeout".

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