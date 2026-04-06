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
├── controllers/            # Business logic
│   ├── orchestrator.py    # Pipeline: planner → architect → coder → reviewer → executor
│   ├── executor.py        # Code execution (sandbox with auto-fix loop)
│   ├── llm_client.py      # Ollama adapter
│   └── code_review.py    # Code review integration
├── models/                # Data layer
│   ├── state.py           # State manager
│   ├── memory.py          # FAISS memory
│   ├── llm_router.py      # Model routing
│   └── settings.py        # Configuration
└── views/                 # UI layer
    ├── dashboard.py       # Gradio interface
    └── api.py             # FastAPI endpoints
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
