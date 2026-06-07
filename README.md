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
- **Visible Agent** with live step-by-step progress ("Thinking Process")
- **LangGraph Orchestrator** with persistent checkpointing
- **Multi-backend LLM support** (Ollama, LM Studio, llama.cpp, Lemonade)
- **Tool calling** & safe code execution
- **Vector memory** with FAISS
- **Distributed tracing** via LangSmith
- **Configurable timeouts** via Settings UI

## 🏗️ Architecture

```
┌─────────────────────┐
│   Next.js UI (3000) │ ← Beautiful frontend with streaming
└──────────┬──────────┘
            │
            ▼ WebSocket / SSE
┌──────────▼──────────┐
│   FastAPI (8000)    │ ← LangGraph Orchestrator + API
└──────────┬──────────┘
            │
            ▼
┌───────▼───────┐
│ LLM Backends  │ ← Ollama / LM Studio / llama.cpp / Lemonade
└───────────────┘
```

## ✨ Key Features

- **Real-time Token Streaming** — token-by-token with live tokens/s graph
- **Thinking Process Display** — animated step progress with visual prominence
- **Persistent Checkpointing** — SQLite-backed session resumption across restarts
- **Model Presets** — light / balanced / heavy for automatic model selection
- **Multi-Model Discovery** — automatic detection of available models
- **Configurable Timeouts** — LLM and Executor timeouts via Settings UI
- **Safe Code Execution** — sandboxed execution with static analysis
- **Distributed Tracing** — LangSmith integration for debugging and monitoring
- **i18n Support** — English + French
- **Settings Dashboard** — live backend metrics, model selection, timeout config

### Agent Pipeline (7-step)

The orchestrator runs a LangGraph pipeline with 5 main nodes + an auto-fix loop:

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  1. Analyze  │ → │  2. Plan  │ → │  3. Code  │ → │ 4. Review │ → │ 5. Execute │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └─────┬────┘
                                                                       │
                                                          ┌────────────▼────────────┐
                                                          │  6. should_fix_code ?    │
                                                          │  (conditional edge)      │
                                                          └────────────┬────────────┘
                                                               pass ▼         ▼ fail
                                                               ┌───┐    ┌──────────┐
                                                               │END│    │7. Re-code │
                                                               └───┘    └─────┬────┘
                                                                         (loop to 3)
```

| Step | Node | Rôle |
|------|------|------|
| **1** | `analyzing_node` | Classifie la tâche (code/reasoning/general) et sélectionne la stratégie LLM |
| **2** | `planning_node` | Crée un plan d'implémentation structuré (fichiers, étapes, approche) |
| **3** | `coding_node` | Génère le code Python via LLM avec extraction et validation Pydantic |
| **4** | `reviewing_node` | Revue de code automatique + vérification de sécurité statique |
| **5** | `executing_node` | Exécute le code dans le sandbox Docker isolé (timeout configurable) |
| **6** | `should_fix_code` | **Edge conditionnel** : si la review échoue et `attempt < max_attempts` → retour étape 3 |
| **7** | Re-code + Re-execute | Itération de correction automatique (jusqu'à `max_attempts=3` tentatives) |

- **Fichier source** : `backend/domain/core/orchestrator_async.py` (orchestrateur) + `backend/domain/core/langgraph/nodes.py` (nœuds)
- **Sources d'état** : `backend/domain/core/langgraph/state.py` (modèles `AgentState`, `PlanData`, `CodeData`, etc.)
- **Checkpointing** : SQLite via `AsyncSqliteSaver` — reprise de session après redémarrage

## 🛠️ Tech Stack

| Layer          | Technology                                      |
|----------------|-------------------------------------------------|
| **Frontend**   | Next.js 16, React 18, Tailwind, Framer Motion, Zustand |
| **Backend**    | FastAPI, Python 3.10+, Pydantic v2               |
| **Config**     | pydantic-settings (YAML + env + runtime)       |
| **Orchestration** | LangGraph with AsyncSqliteSaver checkpointer  |
| **LLM**        | Ollama, LM Studio, llama.cpp, Lemonade         |
| **Memory**     | FAISS + SentenceTransformers                    |
| **Events**     | Thread-safe Pub/Sub                             |
| **Streaming**  | WebSocket + SSE (Unified Protocol)              |
| **Tracing**    | LangSmith (optional)                             |

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
cd frontend
npm install
cd ..

# Launch
python run.py --all
```

Open http://localhost:3000

### Enable LangSmith Tracing (Optional)

1. Get your API key at https://smith.langchain.com
2. Edit `.env` and uncomment the LangSmith section:
```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_your_key_here
LANGSMITH_PROJECT=ui-pro-production
```
3. Restart the server

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

## 📁 Project Structure (2026-05)

> **NOTE**: `backend/domain/settings.py` is the single source of truth for configuration using pydantic-settings.

```
ui-pro/                    # Project root
├── run.py                    # Main launcher
├── setup.py                  # Automated setup
├── settings.py               # Config wrapper (backward compat)
├── requirements.txt
├── .env.example
├── config.yaml.example      # YAML configuration template
├── data/                     # Checkpoint DB (gitignored)
│   └── checkpoints.db
│
├── backend/                  # SOURCE OF TRUTH
│   ├── domain/
│   │   ├── settings.py      # Unified config (pydantic-settings)
│   │   │   └── cache.py     # Generic TTL cache utility
│   │   └── core/            # Business logic
│   │       ├── langgraph_orchestrator.py  # Agent pipeline
│   │       ├── orchestrator_async.py      # Async orchestrator
│   │       ├── code_review.py            # Static analysis
│   │       ├── events.py                 # Event bus
│   │       └── langgraph/               # LangGraph nodes
│   ├── infrastructure/       # Services
│   │   ├── llm_router.py    # LLM routing + streaming
│   │   ├── legacy_llm_router.py  # Legacy Ollama client
│   │   ├── model_discovery.py  # Model discovery + presets
│   │   ├── streaming_unified.py  # Unified SSE/WS protocol
│   │   ├── streaming.py     # ⚠️ Deprecated shim
│   │   ├── code_execution.py # Sandbox execution
│   │   ├── memory.py        # FAISS vector store
│   │   ├── cache.py         # TTL cache utility
│   │   ├── checkpointer.py  # LangGraph checkpoint mgmt
│   │   └── adapters/        # External integrations
│   │       └── faiss.py     # FAISS memory adapter
│   └── transport/           # API layer
│       ├── views_api.py     # FastAPI app
│       └── routers/        # API endpoints
│           ├── ws.py        # WebSocket
│           ├── stream.py    # SSE
│           ├── logs.py      # Log management
│           └── health.py    # Health + settings
│
├── models/                   # Data models (re-exports backend/)
│   └── settings.py
│
├── llm/                      # ⚠️ Legacy shim (moved to backend/)
│   └── router.py
│
├── adapters/                 # ⚠️ Legacy shim (moved to backend/)
│   └── memory/faiss.py
│
└── frontend/                # Next.js frontend
    ├── components/
    │   ├── settings/        # Modular settings components
    │   │   ├── SettingsView.tsx
    │   │   ├── LanguageSelector.tsx
    │   │   ├── TimeoutSettings.tsx
    │   │   ├── LogLevelSettings.tsx
    │   │   ├── ModelSelector.tsx
    │   │   ├── BackendStatusGrid.tsx
    │   │   └── hooks/       # Custom hooks
    │   ├── chat/
    │   │   ├── AgentSteps.tsx   # Thinking Process display
    │   │   └── StepProgress.tsx
    │   └── SystemStats.tsx   # Live metrics
    ├── services/
    │   └── modelDiscovery.ts
    └── lib/
        ├── i18n.ts          # EN + FR translations
        └── stores/          # Zustand state
```

## ⚙️ Configuration

### Configuration Priority

Settings are loaded in this order (later sources override earlier):
1. **config.yaml** - Application defaults
2. **Environment variables** - User overrides
3. **Runtime (UI)** - Live changes from Settings UI

### Model Presets

Three presets are available for automatic model selection:

| Preset | Models | Use Case |
|-------|--------|----------|
| **light** | qwen3.5:0.8b | Quick tasks, low resources |
| **balanced** | qwen3.5:9b | General use, good balance |
| **heavy** | qwen3.6:latest | Complex reasoning, large codebases |

### Settings UI

All settings are configurable via the **Settings UI** at http://localhost:3000:

- **Language** — English / French
- **Timeouts** — LLM and Executor timeouts
- **Log Level** — DEBUG / INFO / WARNING / ERROR / CRITICAL
- **Model Selection** — Choose from discovered models
- **Backend Status** — Live connectivity check

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | http://localhost:11434 | Ollama server URL |
| `MODEL_FAST` | (from preset) | Fast model for simple tasks |
| `MODEL_REASONING` | (from preset) | Reasoning model for complex tasks |
| `MODEL_CODE` | (from preset) | Code-specific model |
| `ACTIVE_PRESET` | balanced | Model preset (light/balanced/heavy) |
| `LLM_TIMEOUT` | 900s | Max time for LLM responses (see [Troubleshooting](#-troubleshooting)) |
| `EXECUTOR_TIMEOUT` | 60s | Max time for code execution |
| `LOG_LEVEL` | INFO | Logging level |
| `LANGSMITH_API_KEY` | (none) | Enable LangSmith tracing |

## 🛠️ Troubleshooting

### LLM_TIMEOUT — "LLM call timed out after Ns"

**Symptôme**: Le chat renvoie une erreur 504 ou le WebSocket se ferme
brutalement (status 1006) après plusieurs minutes. Le log contient:

```
ERROR - backend.domain.core.langgraph.llm_wrapper - LLM call timed out after Ns (model_type=reasoning)
ERROR - backend.infrastructure.llm.ollama - Ollama async stream failed: Read timed out.
TimeoutError: LLM call timed out after Ns (model_type=reasoning)
```

**Cause**: Deux timeouts doivent rester alignés:

| Variable | Défaut | Localisation | Rôle |
|----------|--------|--------------|------|
| `LLM_TIMEOUT` | **900s** (15 min) | `backend/domain/settings.py` | Délai max côté wrapper Python |
| `read_timeout` (Ollama/Lemonade/LM Studio/llama.cpp) | **900s** | `backends_template[*].timeout` | Délai max côté client HTTP |

Si `read_timeout < LLM_TIMEOUT`, le backend HTTP coupe la requête **avant**
le wrapper, et Ollama log `Ollama async stream failed: Read timed out.`
même si la réponse arriverait 1 seconde plus tard.

**Solutions par ordre de préférence**:

1. **Via l'UI Settings** (sans redémarrage):
   - Ouvrir http://localhost:3000 → Settings → Timeouts
   - Bouger `LLM timeout` (slider 10–1800s)
   - Cliquer Save → déclenche `POST /api/settings/timeouts`
   - Le `.env` est mis à jour atomiquement

2. **Via `.env`** (redémarrage requis):
   ```bash
   # Éditer .env à la racine
   LLM_TIMEOUT=900
   # Si vous modifiez cette valeur, alignez aussi les backends
   # dans backend/domain/settings.py (backends_template[*].timeout)
   ```

3. **Pour les modèles 14B+** (`qwen3.6:latest`, preset `heavy`):
   ```env
   ACTIVE_PRESET=heavy
   LLM_TIMEOUT=1800  # max
   ```
   Prévoir GPU dédié et 32 Go de RAM minimum.

4. **GPU partagé / Ollama distant**:
   Le `read_timeout` du backend HTTP peut se déclencher avant `LLM_TIMEOUT`
   à cause du réseau. Augmenter les **deux** valeurs.

**Pourquoi c'est long pour les modèles de raisonnement**:
Les modèles "thinking-mode" (Qwen3.5+, DeepSeek-R1, OpenAI o1/o3) passent
la majorité de leur budget `max_tokens` sur du raisonnement interne
**avant** toute sortie visible. Pour un `qwen3.5-9b` avec `max_tokens=8000`:
7999 tokens de raisonnement, 0 token visible. Désactiver le mode thinking
via `Settings → LLM Thinking Mode = OFF` (env: `LLM_ENABLE_THINKING=false`)
récupère 50% du temps.

**Vérification rapide**:
```bash
# Temps de réponse actuel
curl -w "\n%{time_total}s\n" http://localhost:8000/health

# Test Ollama direct (sans wrapper)
curl -X POST http://localhost:11434/api/generate \
  -d '{"model":"qwen3.5:9b","prompt":"hi","stream":false}' \
  -w "\n%{time_total}s\n"
```

Si Ollama répond en <5s directement mais que le chat timeout à 300s, c'est
le `read_timeout` du backend HTTP qui est trop court — voir l'alignement
ci-dessus.

**Ressources**:
- `docs/api/API.md` → section "504 — LLM Timeout" pour le détail API
- `docs/architecture/AGENTS.md` → "Critical Quirks" pour le résumé rapide

### Ollama "Read timed out" sur `/api/tags` (model discovery)

**Symptôme**: `/api/models` met >2s à répondre, `run_error.log` montre
`Read timed out` même pour des requêtes triviales.

**Cause**: Ollama charge le modèle en VRAM à la première requête. Les
requêtes suivantes pendant ce chargement (1–5s) sont lentes.

**Solution**: C'est le comportement normal d'Ollama. Si >5s systématiquement,
vérifier:
- VRAM disponible (`nvidia-smi`)
- Modèle pas trop gros pour le GPU
- Pas d'autre process qui utilise le GPU (`nvidia-smi pmon -s 1`)

### WebSocket droppé après 7 minutes

**Symptôme**: Client WebSocket se ferme, le serveur log:
```
INFO - backend.transport.routers.ws - WebSocket disconnected
```

**Cause**: Le navigateur/Uvicorn a un timeout WebSocket (souvent 10 min par
défaut) OU le `LLM_TIMEOUT` a expiré et le stream s'est arrêté sans envoyer
`[DONE]`.

**Solution**: Vérifier `run_error.log` pour `TimeoutError`. Si présent,
appliquer la section LLM_TIMEOUT ci-dessus.

### Faiss "AVX512 not available"

**Symptôme**: Au démarrage:
```
INFO - faiss.loader - Could not load library with AVX512 support due to:
ModuleNotFoundError("No module named 'faiss.swigfaiss_avx512')
INFO - faiss.loader - Successfully loaded faiss with AVX2 support.
```

**Cause**: Le CPU ne supporte pas AVX-512 (rare en 2026). FAISS fallback
sur AVX2 automatiquement. **Pas une erreur** — juste un INFO.

---

## 🔐 Security

- Sandboxed code execution with static review
- Input sanitization
- Configurable timeout protection
- No secrets committed (`.env` is gitignored)
- Restricted `exec()` globals in sandbox

## 📝 License

MIT License — feel free to use, modify, and contribute.