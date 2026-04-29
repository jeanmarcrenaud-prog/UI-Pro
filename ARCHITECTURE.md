# Architecture UI-Pro

## 📁 Structure du Projet

```
ui-pro/
├── run.py                      # Launcher principal
├── models/
│   └── settings.py             # Configuration centralisée (SOURCE UNIQUE)
├── core/                       # Core modules (canonical)
│   ├── errors.py              # Hiérarchie d'exceptions
│   ├── logger.py             # Logging standardisé
│   ├── memory.py            # FAISS wrapper (canonical)
│   ├── metrics.py           # Métriques
│   ├── orchestrator_async.py # Pipeline agent (async)
│   ├── state_manager.py      # Gestion d'état (canonical)
│   ├── executor.py         # CodeExecutor (canonical)
│   ├── prompts.py          # Prompts centralisés
│   ├── constants.py        # Constantes
│   └── events.py          # Event bus
├── services/                  # Service layer
│   ├── model_service.py    # Service modèle LLM
│   ├── memory_service.py  # Service mémoire
│   ├── streaming.py      # Streaming SSE/WS (async generator)
│   ├── tools.py          # Registre d'outils
│   ├── llm_router.py    # Advanced routing
│   └── error_handler.py  # Error handling
├── llm/                     # LLM clients (canonical)
│   ├── router.py          # Multi-model routing + OllamaClient
│   └── __init__.py       # Re-exports depuis router
├── controllers/               # Coordination (legacy - en cours de migration)
│   └── websocket.py       # WebSocket handling
├── adapters/                  # Adapters
│   ├── llm/              # Re-exports depuis llm/
│   └── executor/         # Re-exports depuis core
├── models/                   # Types only (NO logic)
│   ├── settings.py        # Settings (SOURCE UNIQUE)
│   ├── config.py         # Pydantic config
│   └── metrics.py        # Metrics types
├── views/                    # Couche API
│   ├── api.py            # FastAPI app
│   ├── dashboard.py      # Gradio UI
│   └── components/       # Gradio components
├── api/
│   └── main.py          # FastAPI alternatif
├── agents/                 # Agent system (legacy)
│   ├── agent.py
│   ├── planner.py
│   └── react.py
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
views/api.py ──→ controllers/* ──→ services/* ──→ adapters/*
     │              │                 │               │
     └──────────────┴─────────────────┴───────────────┘
                         ↓
                      core/*
                         ↓
                    models/*

# RÈGLES:
# - views N'IMPORTE PAS services
# - controllers N'IMPORTE PAS views
# - services N'IMPORTE PAS views
# - adapters importé PAR services SEULEMENT
# - core importé PAR tous
```

### Import autorisées

| Module | Peut importer |
|--------|---------------|
| `views/api.py` | `controllers/*`, `core/*`, `models/*` |
| `controllers/*` | `services/*`, `core/*`, `models/*`, `adapters/*` |
| `services/*` | `adapters/*`, `core/*`, `models/*` |
| `adapters/*` | `core/*`, `models/*` |
| `core/*` | `models/*` |

### Import INTERDITES

```python
# ❌ INTERDIT - views ne doit pas importer services
from services.chat_service import ChatService  # NON!

# ✅ AUTORISÉ - controllers importe services
from services.chat_service import ChatService  # OUI!

# ✅ AUTORISÉ - tout importe core
from core.events import emit_agent_step  # OUI!
```

## 🎯 Frontière Controllers/ vs Services/

### Controllers (coordination requête/réponse)
- Reçoivent les requêtes HTTP/WS
- Valident les entrées
- Appellent les services
- Forment les réponses

### Services (orchestration pur)
- Contiennent la logique métier
- Orchestrent les adapters
- Ne font PAS d'I/O direct (sauf adapters)
- Stateless

## 📦 Constants Centralisées

### Backend (core/constants.py)
```python
class WSEvent:
    TOKEN = "token"
    STEP = "step"
    TOOL = "tool"
    DONE = "done"
    ERROR = "error"

class AgentStep:
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
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

### models/settings.py (Pydantic BaseSettings)

> **settings.py** est la SOURCE UNIQUE de configuration. Les valeurs sont overridées via variables d'environnement (fichier `.env` gitignore).

```
.env (override) ──→ Settings class
```

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM
    ollama_url: str = "http://localhost:11434"
    model_fast: str = "qwen2.5:7b"
    model_reasoning: str = "qwen2.5:32b"
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

## 🧪 Tests

### Commandes
```bash
# Python
pytest tests/ -v --cov=ui-pro --cov-report=html

# Frontend  
cd ui-pro-ui && npm run lint
```

## 🔧 Outils Qualité

### pyproject.toml
```toml
[tool.mypy]
strict = true
warn_return_any = true

[tool.black]
line-length = 120

[tool.isort]
profile = "black"
```

## 📡 Routes API

| Prefix | Router | Description |
|--------|---------|-------------|
| `/api/chat` | chat | Conversation |
| `/api/models` | models | Liste des modèles |
| `/api/tools` | tools | Outils disponibles |
| `/api/history` | history | Historique |
| `/ws` | ws | WebSocket streaming |
| `/health` | health | Health check |

## 🔄 Flux Backend

```
Request HTTP
    ↓
views/api.py (FastAPI)
    ↓
services/streaming.py (async generator)
    ↓
llm/router.py (OllamaClient)
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
| Sanitization | AST-based (eval/exec open bloqués) |
| Memory limit | 512MB cap |
| API key | Depends(verify_api_key) sur /status |
| CORS | Middleware configuré via env |

## 📝 Fichiers Supprimés (Refactoring)

| Ancien | Nouveau |
|--------|---------|
| `llm/client.py` | `llm/router.py` (OllamaClient, ModelConfig) |
| `core/config.py` | `models/settings.py` (Settings singleton) |
| `controllers/orchestrator.py` | `core/orchestrator_async.py` |
| `controllers/llm_client.py` | `services/model_service.py` |
| `controllers/team.py` | `services/tools.py` |
| `config.yaml` | `.env` uniquement |

## 🔥 Streaming Service (services/streaming.py)

### Async Generator Lifecycle

```python
async def stream_generate(...) -> AsyncIterator[StreamChunk]:
    # Lifecycle: STARTING → GENERATING → (COMPLETED | ERROR | CANCELLED)
    
    yield StreamChunk(status=StreamStatus.STARTING, ...)
    
    for chunk in client.stream(...):
        yield StreamChunk(status=StreamStatus.GENERATING, ...)
    
    yield StreamChunk(status=StreamStatus.COMPLETED, ...)
    # OU
    yield StreamChunk(status=StreamStatus.ERROR, ...)
    # OU
    yield StreamChunk(status=StreamStatus.CANCELLED, ...)
```

### Guarantees
- Exactly ONE terminal event (COMPLETED/ERROR/CANCELLED)
- Proper cleanup in `finally` block
- Safe cancellation via `current_task.cancelled()`

---

**Dernière mise à jour**: 2026-04-29