# Architecture UI-Pro

## 📁 Structure du Projet

```
ui-pro/
├── run.py                      # Launcher principal
├── settings.py                 # Configuration centralisée
├── app/
│   └── launcher.py             # Démarrage des services
├── core/                       # Core modules (canonical)
│   ├── config.py               # Configuration
│   ├── errors.py              # Hiérarchie d'exceptions
│   ├── logger.py             # Logging standardisé
│   ├── memory.py             # FAISS wrapper (canonical)
│   ├── metrics.py           # Métriques
│   ├── orchestrator_async.py # Pipeline agent
│   ├── prompts.py            # Prompts centralisés
│   ├── state_manager.py      # Gestion d'état (canonical)
│   ├── executor.py           # CodeExecutor (canonical)
│   ├── code_review.py        # Code review (canonical)
│   ├── constants.py           # Constantes
│   └── events.py             # Event bus
├── controllers/               # Coordination
│   └── orchestrator.py       # Orchestrateur principal
├── services/                  # Service layer
│   ├── model_service.py     # Service modèle LLM
│   ├── memory_service.py    # Service mémoire
│   ├── streaming.py        # Streaming SSE/WS
│   ├── tools.py            # Registre d'outils
│   ├── llm_router.py      # Advanced routing
│   └── agents.py           # Agent definitions
├── llm/                     # LLM clients (canonical)
│   ├── client.py           # OllamaClient (canonical)
│   └── router.py           # Basic routing (canonical)
├── models/                   # Types only (NO logic)
│   ├── settings.py        # Settings
│   └── metrics.py         # Metrics types
├── agents/                   # Agent system
│   ├── agent.py           # Base agent
│   ├── planner.py         # Planner
│   └── react.py           # ReAct agent
├── adapters/                  # Legacy adapters (deprecated)
│   ├── executor/         # Re-exports from core
│   ├── llm/             # Re-exports from llm/
│   └── memory/           # FAISS adapter
└── tests/                   # Test suite
```
├── views/                    # Couche API
│   ├── api.py              # FastAPI app
│   ├── dashboard.py        # Gradio UI
│   └── logger.py
├── api/
│   └── main.py             # FastAPI alternatif
└── ui-pro-ui/               # Frontend Next.js
    ├── components/
    ├── features/
    ├── services/
    ├── stores/
    └── lib/
        └── constants.ts
```

## 🔄 Règles d'Import (Dependency Graph)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     DEPENDENCY FLOW                            │
├─────────────────────────────────────────────────────────────────────────┤
│  views/api.py ──→ controllers/* ──→ services/* ──→ adapters/*  │
│       │              │                 │               │          │
│       └──────────────┴─────────────────┴───────────────┘      │
│                         ↓                                   │
│                      core/*                                  │
│                         ↓                                   │
│                    models/*                                 │
└─────────────────────────────────────────────────────────────────────────┘

# TEXTE DIAGRAM EQUIVALENT:

views → controllers → services → adapters
   ↓       ↓           ↓           ↓
  core ←──────────────┼───────────┘
   ↓
models

# RÈGLES:
# - views N'IMPORTE PAS services
# - controllers N'IMPORTE PAS views
# - services N'IMPORTE PAS views
# - adapters importé PAR services SEULEMENT
# - core importé PAR tous
# - agents N'IMPORTE PAS views
```

### Import autorisées

| Module | Peut importer |
|--------|---------------|
| `views/api.py` | `controllers/*`, `core/*`, `models/*` |
| `controllers/*` | `services/*`, `core/*`, `models/*`, `adapters/*` |
| `services/*` | `adapters/*`, `core/*`, `models/*` |
| `adapters/*` | `core/*`, `models/*` |
| `core/*` | `models/*` |
| `agents/*` | `core/*`, `models/*` ( JAMAIS `views/*` ) |

### Import INTERDITES

```python
# ❌ INTERDIT - agents ne doit pas importer views
from views.api import app  # NON!

# ❌ INTERDIT - views ne doit pas importer services
from services.chat_service import ChatService  # NON!

# ✅ AUTORISÉ - controllers importe services
from services.chat_service import ChatService  # OUI!

# ✅ AUTORISÉ - tout importe core
from core.events import emit_agent_step  # OUI!
```

## 🎯 Frontière controllers/ vs services/

### Controllers (coordination requête/réponse)
- Reçoivent les requêtes HTTP/WS
- Valident les entrées
- appellent les services
-_forment les réponses

### Services (orchestration pur)
- Contiennent la logique métier
- Orchestrent les adapters
- Ne font PAS d'I/O direct (sauf adapters)
- stateless

## 📦 Constants Centralisées

### Backend (core/constants.py)
```python
# WebSocket event types
class WSEvent:
    TOKEN = "token"
    STEP = "step"
    TOOL = "tool"
    DONE = "done"
    ERROR = "error"

# Agent steps
class AgentStep:
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"

# Error codes
class ErrorCode:
    INVALID_INPUT = "INVALID_INPUT"
    LLM_ERROR = "LLM_ERROR"
    TOOL_ERROR = "TOOL_ERROR"
    MEMORY_ERROR = "MEMORY_ERROR"
```

### Frontend (ui-pro-ui/lib/constants.ts)
```typescript
export const WS_EVENTS = {
  TOKEN: 'token',
  STEP: 'step',
  TOOL: 'tool',
  DONE: 'done',
  ERROR: 'error',
} as const;

export const AGENT_STEPS = {
  ANALYZING: 'analyzing',
  PLANNING: 'planning', 
  EXECUTING: 'executing',
  REVIEWING: 'reviewing',
} as const;

export const ERROR_CODES = {
  INVALID_INPUT: 'INVALID_INPUT',
  LLM_ERROR: 'LLM_ERROR',
  TOOL_ERROR: 'TOOL_ERROR',
  MEMORY_ERROR: 'MEMORY_ERROR',
} as const;
```

## 🛡️ Gestion d'Erreurs

### core/errors.py
```python
class DomainError(Exception):
    """Erreur métier de base"""
    code: str

class LLMError(DomainError):
    """Erreur lors d'un appel LLM"""
    
class ToolExecutionError(DomainError):
    """Erreur lors de l'exécution d'un outil"""
    
class MemoryError(DomainError):
    """Erreur mémoire/FAISS"""
```

### Mapper vers FastAPI
```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    return JSONResponse(
        status_code=500,
        content={"error": exc.code, "message": str(exc)}
    )
```

## 📊 Configuration

### Config YAML + .env (settings.py)

> **config.yaml** est utilise par `settings.py` comme source principale. Les valeurs sont overridees via variables d'environnement (fichier `.env` gitignore).

```
config.yaml (base) ──→ .env (override) ──→ Settings class
```

### settings.py (Pydantic BaseSettings)
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM
    ollama_url: str = "http://localhost:11434/api/generate"
    model_fast: str = "qwen3.5:9b"
    model_reasoning: str = "qwen3.5:9b"
    llm_timeout: int = 30
    
    # Executor
    executor_timeout: int = 60
    memory_limit_mb: int = 512
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

### settings.local.yaml (git ignoré)
```yaml
# Override pour développement local
ollama_url: "http://localhost:11434/api/generate"
log_level: "DEBUG"
```

## 🧪 Tests

### Couverture cible
| Module | Cible |
|--------|-------|
| controllers/executor | 80%+ |
| services/chat_service | 70%+ |
| adapters/llm | 70%+ |
| adapters/faiss | 80%+ |

### Commandes
```bash
# Python
pytest tests/ -v --cov=ui-pro --cov-report=html

# Frontend  
cd ui-pro-ui && npm run lint
```

## 🔧 Outils Qualité

### mypy.ini
```ini
[mypy]
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false

[mypy-pytest.*]
ignore_missing_imports = true

[mypy-gradio.*]
ignore_missing_imports = true
```

### .flake8
```ini
[flake8]
max-line-length = 120
exclude = .git,__pycache__,.venv
ignore = E203,W503
```

## 📡 Routes API

| Prefix | Router | Description |
|--------|---------|-------------|
| `/api/chat` | chat | Conversation |
| `/api/models` | models | Liste des modèles |
| `/api/tools` | tools | Outils disponibles |
| `/api/history` | history | Historique |
| `/ws` | ws | WebSocket streaming |

## 🔄 Flux Backend

```
Request HTTP
    ↓
views/api.py (FastAPI)
    ↓
controllers/orchestrator.py
    ↓
services/chat_service.py
    ↓
adapters/llm/client.py (canonical)
    ↓
Ollama API
```

## 📱 Frontend Structure

```
ui-pro-ui/
├── components/       # UI pure (boutons, inputs, etc.)
├── features/         # Logique métier (ChatInput, AgentSteps)
├── services/        # HTTP/WS/SSE (apiClient, streamService)
├── stores/          # Zustand (chatStore, settingsStore)
└── lib/
    └── constants.ts # Constants centralisées
```

## 🛡️ Sécurité

| Feature | Implementation |
|---------|---------------|
| Sandbox | tempfile.mkdtemp + subprocess |
| Sanitization | AST-based (eval/exec/open bloqués) |
| Memory limit | resource.setrlimit (512MB) |
| API key | Depends(verify_api_key) sur /status |
| CORS | Middleware configuré via env |

---

**Dernière mise à jour**: 2026-04-12