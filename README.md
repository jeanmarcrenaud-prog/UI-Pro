# ui-pro - AI Agent Orchestration System

> **Système d'agents IA auto-hébergé** qui génère, debug et déploie des applications Python automatiquement.

![Status](https://img.shields.io/badge/status-beta-orange)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)

## Qu'est-ce que c'est?

`ui-pro` est un système multi-agents qui orchestre des agents spécialisés pour:

1. **Planifier** des tâches complexes
2. **Architecturer** des solutions
3. **Coder** des applications Python propres
4. **Reviewer** le code généré
5. **Exécuter** avec sandbox et auto-correction (max 3 tentatives)

TOUT EN LOCAL avec **Ollama** (pas de dépendance cloud!)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INPUT (Task)                        │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   Dashboard (Gradio)                         │
│              Interface utilisateur (port 7860)              │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              OrchestratorAsync.run()                        │
│         Pipeline async avec StateManager                    │
└────────────────────────────┬────────────────────────────────┘
                             │
         ┌───────────────────┴───────────────────┐
         ▼                                       ▼
   _planner()                              _memory()
   (LLM)                                    (FAISS)
         │                                       │
         └───────────────────┬───────────────────┘
                             ▼
                      _architect()
                             ▼
                        _coder()
                             ▼
                      _reviewer()
                             ▼
         ┌───────────────────┴───────────────────┐
         ▼                                       ▼
      SUCCESS                                 FAIL
         │                                       │
         ▼                               _runner() via CodeExecutor
    _runner()                            (sandbox + auto-fix loop, max 3)
    (sandbox)
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                   DEPLOYMENT COMPLETE                        │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **CodeExecutor**: Sandbox avec tempfile, timeout configurable, sanitization
- **Auto-fix loop**: Max 3 tentatives avec correction LLM
- **StateManager**: Typage complet, persistence JSON, metrics détaillées
- **Memory**: FAISS + SentenceTransformer pour recherche vectorielle
- **Logger**: Rotation logs (10MB, 5 backups), format JSON
- **Dashboard**: Gradio connecté au pipeline OrchestratorAsync
- **Multi-model**: LLM routing (fast/reasoning/code)

## Stack Technique

| Couche | Technologie |
|--------|-------------|
| **Backend** | Python 3.10+, FastAPI |
| **Interface** | Gradio |
| **LLM** | Ollama (qwen2.5-coder:32b, qwen-opus) |
| **Mémoire** | FAISS + SentenceTransformers |
| **Testing** | pytest, pytest-mock |
| **Linting** | black, isort, flake8, mypy |

## Installation

```bash
# Clone et setup
git clone https://github.com/username/ui-pro.git
cd ui-pro

# Virtual env
python -m venv .venv
.venv\Scripts\activate  # Windows

# Installer deps
pip install -r requirements.txt

# Configurer Ollama
ollama pull qwen2.5-coder:32b
ollama pull qwen-opus

# Configurer .env
cp .env.example .env

# Lancer avec le launcher (recommandé)
python run.py
```

## Environment Variables (.env)

```env
HF_TOKEN=your_huggingface_token_here
OLLAMA_URL=http://localhost:11434
MODEL_FAST=qwen2.5-coder:32b
MODEL_REASONING=qwen-opus
LLM_TIMEOUT=30
EXECUTOR_TIMEOUT=60
LOG_LEVEL=INFO
```

## Utilisation

### Via le Launcher (recommandé)

```bash
# Vérifier les dépendances
python run.py --check

# Lancer le dashboard Gradio
python run.py

# Lancer FastAPI uniquement
python run.py --api

# Lancer les deux services
python run.py --all

# Lancer les tests
python run.py --test
```

### Directement

```bash
# Dashboard Gradio
python dashboard.py
# → http://localhost:7860

# FastAPI
uvicorn main:app --reload
# → http://localhost:8000
```

## Testing

```bash
# Tous les tests
pytest tests/ -v

# Tests spécifiques
pytest tests/test_execution.py -v
# 13 passed

# Avec coverage
pytest --cov=ui-pro --cov-report=html
```

## Configuration

### CodeExecutor
```python
timeout=30           # secondes
workspace_dir="workspace"
cleanup=True
max_fix_attempts=3
```

### State Metrics
```python
{
    "total_duration_ms": 0,
    "llm_calls": 0,
    "tokens": 0,
    "retry_count": 0,
    "max_retry_count": 3,
}
```

## Sécurité

- **Sandbox**: tempfile.TemporaryDirectory isolation
- **Sanitization**: Désactive eval, exec, subprocess.Popen
- **Timeout**: Configurable pour éviter les boucles infinies
- **HF_TOKEN**: Via os.getenv(), jamais hardcodé
- **NE JAMAIS** commit le fichier `.env`

## Licence

MIT License