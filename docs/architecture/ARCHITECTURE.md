# Architecture UI-Pro

## 📁 Structure du Projet (Post-Refactoring)

### Source de Vérité: `backend/`

```
ui-pro/                           # Racine projet
+-- run.py                        # Launcher principal
+-- setup.py                      # Automated setup
+-- pyproject.toml                # Python project config
+-- requirements.txt              # Dependances
+-- Dockerfile                    # Container build
+-- Makefile                      # Dev commands
+-- conftest.py                   # Pytest config
+-- pytest.ini                    # Config pytest
+-- .env.example
|
+-- backend/                      # SOURCE DE VERITE
|   +-- domain/                  # Business logic
|   |   +-- core/                # Core modules
|   |   |   +-- action_executor.py   # Code actions (insert, delete, rename)
|   |   |   +-- code_review.py       # Bandit code review
|   |   |   +-- constants.py         # WSEvent, AgentStep
|   |   |   +-- editor_service.py    # Editor orchestration
|   |   |   +-- editor_state.py      # Editor state management
|   |   |   +-- errors.py            # DomainError hierarchy
|   |   |   +-- events.py            # Event bus
|   |   |   +-- executor.py          # CodeExecutor (sandbox)
|   |   |   +-- filesystem_service.py # Safe file I/O
|   |   |   +-- langgraph/           # Pipeline nodes
|   |   |   +-- logger.py            # Logging
|   |   |   +-- metrics.py           # Metriques
|   |   |   +-- models.py            # Domain models (EditorState, Action, etc.)
|   |   |   +-- orchestrator_async.py # Async pipeline orchestrator
|   |   |   +-- planner.py           # Local task planner
|   |   |   +-- prompts.py           # LLM prompts
|   |   |   +-- state_manager.py     # Etat pipeline
|   |   +-- errors.py            # Domain errors
|   |
|   +-- infrastructure/           # Services layer
|   |   +-- llm/                  # LLM clients (Ollama, LM Studio, etc.)
|   |   |   +-- hermes.py         # Hermes LLM integration
|   |   |   +-- ollama.py         # Ollama client
|   |   |   +-- lmstudio.py       # LM Studio client
|   |   |   +-- llamacpp.py       # llama.cpp client
|   |   |   +-- lemonade.py       # Lemonade client
|   |   +-- mcp/                  # MCP server (Hermes)
|   |   |   +-- server.py         # FastMCP server with tools
|   |   +-- opencode_connector/   # OpenCode headless integration
|   |   |   +-- manager.py        # Subprocess lifecycle + JSON protocol
|   |   |   +-- client.py         # OpenCode client
|   |   |   +-- models.py         # Connector models
|   |   +-- streaming/            # SSE/WebSocket streaming
|   |   +-- executors/            # Code executors
|   |   +-- voice/                # Voice services (STT/TTS/VAD)
|   |   +-- terminal/             # Terminal emulation
|   |   +-- tools/                # Tool registry & execution
|   |   +-- monitoring/           # Tracing & metrics
|   |   +-- adapters/             # FAISS memory adapter
|   |   +-- llm_router.py         # Multi-model routing
|   |   +-- model_discovery.py    # Model discovery
|   |   +-- memory.py             # FAISS wrapper
|   |   +-- checkpointer.py       # SQLite checkpointing
|   |   +-- code_execution.py     # Python sandbox execution
|   |   +-- rate_limit.py         # Rate limiting
|   |
|   +-- application/             # App layer
|   |   +-- intelligence/         # Intent processing
|   |   |   +-- intelligence_service.py # Intent to plan to delegate/execute
|   |   |   +-- task_planner.py        # Plan generation
|   |   +-- editor_manager.py     # Editor coordination
|   |   +-- voice_manager.py      # Voice flow management
|   |   +-- websocket.py          # WebSocket handling
|   |
|   +-- transport/               # API endpoints
|       +-- main.py               # FastAPI entry point
|       +-- views_api.py          # FastAPI app
|       +-- websocket_manager.py  # WebSocket connection manager
|       +-- routers/              # API routers
|           +-- chat.py
|           +-- ws.py
|           +-- stream.py
|           +-- execute.py
|           +-- health.py
|           +-- logs.py
|           +-- mario.py           # Mario agent router
|           +-- node_metrics.py
|
+-- frontend/                    # Next.js frontend
|   +-- app/                     # Next.js app router
|   |   +-- page.tsx              # Page principale
|   |   +-- layout.tsx
|   |   +-- globals.css
|   +-- components/               # Composants React
|   |   +-- chat/                 # Composants chat
|   |   |   +-- ChatMessages.tsx
|   |   |   +-- HistoryBatchActions.tsx
|   |   |   +-- HistoryFilters.tsx
|   |   |   +-- HistoryItem.tsx
|   |   |   +-- MessageBubble.tsx
|   |   |   +-- MessageSuggestions.tsx
|   |   +-- markdown/             # Composants markdown
|   |   |   +-- CodeBlock.tsx
|   |   |   +-- CodeMinimap.tsx
|   |   |   +-- MarkdownRenderer.tsx
|   |   +-- CommandPalette.tsx
|   |   +-- HistoryView.tsx
|   |   +-- SettingsView.tsx
|   |   +-- Sidebar.tsx
|   |   +-- ChatContainer.tsx
|   +-- features/                 # Logique metier
|   +-- services/                # Services HTTP/WS
|   +-- lib/                     # Stores, i18n, types
|   |   +-- stores/
|   |   +-- i18n.ts
|   |   +-- types.ts
|   |   +-- constants.ts
|   +-- styles/                  # Design tokens
|   +-- public/
|
+-- scripts/                     # Dev tooling
+-- tests/                        # Tests pytest
+-- docs/                         # Documentation
+-- data/                         # Runtime data (gitignored)
+-- logs/                         # Application logs
+-- workspace/                    # Code genere
```

## 🔄 Règles d'Import (Dependency Graph)

> **NOTE**: La structure legacy a été supprimée. Tout importe maintenant depuis `backend/`.

```
backend/transport/views_api.py ──→ backend/application/* ──→ backend/infrastructure/* ──→ backend/domain/core/*
     │                              │                              │                                │
     └─────────────────────────────┴──────────────────────────────┴────────────────────────────────┘
                                                  ↓
                                           models/* (settings)

# RÈGLES:
# - backend/transport N'IMPORTE PAS backend/infrastructure directement (via application/)
# - backend/infrastructure N'IMPORTE PAS backend/transport
# - Tout importe depuis backend/domain/core/
# - settings via models/ ou backend/domain/settings
```

### Import autorisées

| Module | Peut importer |
|--------|---------------|
| `backend/transport/*` | `backend/application/*`, `backend/domain/core/*`, `models/*` |
| `backend/application/*` | `backend/infrastructure/*`, `backend/domain/core/*`, `models/*` |
| `backend/infrastructure/*` | `backend/domain/core/*`, `models/*` |
| `backend/domain/core/*` | `models/*` |

### Import INTERDITES

```python
# ❌ INTERDIT - transport ne doit pas importer infrastructure directement
from backend.infrastructure.llm_router import LLMRouter  # NON!

# ✅ AUTORISÉ - via application layer
from backend.application.websocket import WebSocketController  # OUI!

# ✅ AUTORISÉ - tout importe domain/core
from backend.domain.core.events import emit_agent_step  # OUI!
```

## 🎯 Structure backend/

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

### Frontend (frontend/lib/constants.ts)
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

### Domain Models (backend/domain/core/models.py)

> **Settings** est la SOURCE UNIQUE de configuration dans `backend/domain/core/models.py`. Les valeurs sont overridées via variables d'environnement (fichier `.env` gitignore).

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
cd frontend && npm run lint
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
backend/transport/views_api.py (FastAPI)
    ↓
backend/transport/routers/*.py (endpoints)
    ↓
backend/infrastructure/streaming/ (async generator)
    ↓
backend/infrastructure/llm_router.py (LLMRouter)
    ↓
Ollama API
```

## 📱 Frontend Structure

```
frontend/
+-- components/       # UI pure (boutons, inputs, etc.)
|   +-- chat/
|   |   +-- HistoryItem.tsx     # Single chat in list
|   |   +-- HistoryFilters.tsx  # Search, sort, filters
|   |   +-- HistoryBatchActions.tsx  # Batch toolbar
|   |   +-- MessageBubble.tsx   # Message with actions
|   |   +-- MessageSuggestions.tsx   # Contextual suggestions
|   |   +-- ChatSuggestions.tsx  # Welcome examples
|   +-- markdown/
|   |   +-- CodeBlock.tsx       # Code with run/validate
|   |   +-- CodeMinimap.tsx      # VS Code-style minimap
|   |   +-- MarkdownRenderer.tsx
|   +-- CommandPalette.tsx      # Ctrl+K palette
|   +-- HistoryView.tsx         # History page
|   +-- SettingsView.tsx        # Settings + model desc
|   +-- Sidebar.tsx              # Navigation sidebar
+-- features/         # Logique metier (ChatInput, AgentSteps)
+-- services/        # HTTP/WS/SSE (apiClient, streamService)
+-- stores/          # Zustand (chatStore, settingsStore)
+-- lib/
    +-- constants.ts # Constants centralisees
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
| `controllers/llm_client.py` | SUPPRIME | `infrastructure/llm/` (LLM clients) |
| `controllers/team.py` | SUPPRIME | `infrastructure/tools/` |
| `templates/*.html` | SUPPRIME | Gradio dashboard |
| `services/code_execution1.py` | SUPPRIME | `infrastructure/code_execution.py` |
| `config.yaml` | ❌ SUPPRIMÉ | `.env` uniquement |

## Streaming Service (infrastructure/streaming/)

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