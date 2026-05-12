# Architecture UI-Pro

## 📁 Structure du Projet (Post-Refactoring)

### Source de Vérité: `backend/`

```
ui-pro/                           # Racine projet
├── run.py                        # Launcher principal
├── settings.py                   # Settings standalone
├── conftest.py                    # Pytest config
├── README.md                     # Documentation
├── ARCHITECTURE.md               # Ce fichier
├── requirements.txt              # Dépendances
├── pytest.ini                    # Config pytest
│
├── backend/                      # SOURCE DE VÉRITÉ
│   ├── domain/                  # Business logic
│   │   ├── core/                # Core modules
│   │   │   ├── constants.py     # WSEvent, AgentStep
│   │   │   ├── errors.py        # DomainError hierarchy
│   │   │   ├── executor.py      # CodeExecutor (sandbox)
│   │   │   ├── code_review.py   # Code review with bandit
│   │   │   ├── events.py        # Event bus
│   │   │   ├── logger.py        # Logging
│   │   │   ├── metrics.py       # Métriques
│   │   │   ├── orchestrator_async.py  # Async pipeline
│   │   │   ├── prompts.py       # Prompts
│   │   │   └── state_manager.py # État
│   │   └── errors.py            # Domain errors
│   │
│   ├── infrastructure/           # Services layer
│   │   ├── base.py              # Service base
│   │   ├── code_execution.py    # Execution Python
│   │   ├── error_handler.py     # Error handling
│   │   ├── llm_router.py        # Advanced routing
│   │   ├── memory.py            # FAISS wrapper
│   │   ├── memory_service.py    # Service mémoire
│   │   ├── model_discovery.py   # Model discovery
│   │   ├── model_service.py     # Service modèle
│   │   ├── service_api.py       # API service
│   │   ├── streaming.py         # Streaming SSE/WS
│   │   └── tools.py              # Tools registry
│   │
│   ├── application/             # App layer
│   │   ├── launcher.py          # Multi-service launcher
│   │   └── websocket.py         # WebSocket handling
│   │
│   └── transport/               # API endpoints
│       ├── main.py              # FastAPI entry point
│       ├── views_api.py         # FastAPI app
│       ├── dashboard.py         # Gradio dashboard
│       ├── translations.py      # i18n
│       └── routers/             # API routers
│
├── core/                         # Legacy (ré-export → backend/domain/core/)
├── services/                     # Legacy (ré-export → backend/infrastructure/)
├── api/                          # Legacy (ré-export → backend/transport/)
├── views/                        # Legacy (ré-export → backend/transport/)
├── llm/                          # LLM clients
│   ├── __init__.py
│   └── router.py                # Multi-model routing (OllamaClient, LLMRouter)
│
├── models/                        # Types + Config
│   ├── __init__.py
│   ├── settings.py              # Settings (SOURCE UNIQUE)
│   └── ...
│
├── tests/                         # Tests pytest
│   ├── __init__.py
│   └── ...
│
├── workspace/                   # Code généré
│   ├── app.py
│   ├── test_app.py
│   ├── test_execution.py
│   └── Dockerfile
│
├── logs/                         # Logs rotate
│   └── app*.log
│
└── ui-pro-ui/                    # Frontend Next.js
    ├── app/                     # Next.js app router
    │   ├── page.tsx              # Page principale
    │   ├── layout.tsx
    │   └── api/                  # API routes
    ├── components/               # Composants React
    │   ├── CommandPalette.tsx
    │   ├── HistoryView.tsx      # + chat/ subcomponents
    │   ├── SettingsView.tsx
    │   ├── Sidebar.tsx
    │   ├── ChatContainer.tsx
    │   ├── chat/                 # Composants chat
    │   │   ├── ChatMessages.tsx
    │   │   ├── HistoryBatchActions.tsx
    │   │   ├── HistoryFilters.tsx
    │   │   ├── HistoryItem.tsx
    │   │   ├── MessageBubble.tsx
    │   │   └── MessageSuggestions.tsx
    │   └── markdown/              # Composants markdown
    │       ├── CodeBlock.tsx
    │       ├── CodeMinimap.tsx
    │       └── MarkdownRenderer.tsx
    ├── features/                 # Logique métier
    ├── services/                # Services HTTP/WS
    ├── stores/                  # Zustand stores
    ├── lib/                     # Types, config
    │   ├── types.ts
    │   ├── stores/
    │   ├── i18n.ts
    │   └── constants.ts
    └── styles/                  # Styles
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
│   ├── chat/
│   │   ├── HistoryItem.tsx     # Single chat in list
│   │   ├── HistoryFilters.tsx  # Search, sort, filters
│   │   ├── HistoryBatchActions.tsx  # Batch toolbar
│   │   ├── MessageBubble.tsx   # Message with actions
│   │   ├── MessageSuggestions.tsx   # Contextual suggestions
│   │   └── ChatSuggestions.tsx  # Welcome examples
│   ├── markdown/
│   │   ├── CodeBlock.tsx       # Code with run/validate
│   │   ├── CodeMinimap.tsx      # VS Code-style minimap
│   │   └── MarkdownRenderer.tsx
│   ├── CommandPalette.tsx      # Ctrl+K palette
│   ├── HistoryView.tsx         # History page
│   ├── SettingsView.tsx        # Settings + model desc
│   └── Sidebar.tsx              # Navigation sidebar
├── features/         # Logique métier (ChatInput, AgentSteps)
├── services/        # HTTP/WS/SSE (apiClient, streamService)
├── stores/          # Zustand (chatStore, settingsStore)
└── lib/
    └── constants.ts # Constants centralisées
```

## 🆕 Features Récentes (2026)

### Command Palette (Ctrl+K)
- Ouverte avec `Ctrl+K` / `Cmd+K`
- Focus Mode (toggle avec `Ctrl+Shift+F`)
- Theme toggle (temporairement désactivé)

### History Multi-Select
- Bouton "Select" pour activer le mode
- Checkbox sur chaque chat
- "Select All" / "Deselect All"
- Actions groupées: Pin, Export, Archive, Delete
- Indicateur visuel "X/Y selected"

### Contextual Suggestions
5 suggestions sous chaque réponse IA:
- "Improve code" - Améliorer le code
- "Add tests" - Ajouter des tests
- "FastAPI version" - Créer endpoint FastAPI
- "Make robust" - Rendre plus robuste
- "Convert to package" - Convertir en package

### Code Minimap
- Affichée si > 15 lignes
- Position fixed (absolute) pendant scroll
- Click pour naviguer
- Click + drag pour scrolling continu
- Indicateur violet de position

### Settings Améliorations
- Description du modèle via API (GitHub/Ollama)
- Lien "À propos" → GitHub repo

## 🛡️ Sécurité

| Feature | Implementation |
|---------|---------------|
| Sandbox | tempfile.mkdtemp + subprocess |
| Sanitization | AST-based (eval/exec open bloqués) |
| Memory limit | 512MB cap |
| API key | Depends(verify_api_key) sur /status |
| CORS | Middleware configuré via env |

## 📝 Fichiers Supprimés (Refactoring 2026-04-28)

> Ces fichiers ont été supprimés lors du refactoring. Ils ne doivent plus être recréés.

| Ancien | Statut | Remplacement |
|--------|--------|-------------|
| `llm/client.py` | ❌ SUPPRIMÉ | `llm/router.py` (OllamaClient, ModelConfig) |
| `core/config.py` | ❌ SUPPRIMÉ | `models/settings.py` (Settings singleton) |
| `controllers/orchestrator.py` | ❌ SUPPRIMÉ | `core/orchestrator_async.py` |
| `controllers/llm_client.py` | ❌ SUPPRIMÉ | `services/model_service.py` |
| `controllers/team.py` | ❌ SUPPRIMÉ | `services/tools.py` |
| `templates/*.html` | ❌ SUPPRIMÉ | Utiliser Gradio (`views/dashboard.py`) |
| `services/code_execution1.py` | ❌ SUPPRIMÉ | `services/code_execution.py` |
| `config.yaml` | ❌ SUPPRIMÉ | `.env` uniquement |

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

**Dernière mise à jour**: 2026-05-12