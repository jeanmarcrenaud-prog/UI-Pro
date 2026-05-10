# UI-Pro - AI Agent Orchestration System
<img width="863" height="295" alt="image" src="https://github.com/user-attachments/assets/6d3f5ad0-1dee-4d03-80d3-da7281f66ebc" />

> **Système d'agents IA auto-hébergé** avec interface moderne comme ChatGPT.

![Status](https://img.shields.io/badge/status-beta-orange)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Next.js](https://img.shields.io/badge/Next.js-16-blue)

## 🚀 Présentation

`ui-pro` est un système d'orchestration d'agents IA moderne avec:

- **Interface UI moderne** (type ChatGPT) avec streaming temps réel
- **Agent intelligent** avec steps visibles en direct
- **Multi-modèles** supportés (Ollama, LM Studio, llama.cpp, Lemonade)
- **Tool calling** intégré
- **Architecture event-driven** pour une expérience fluide

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Next.js UI (port 3000)                   │
│              Interface moderne avec Tailwind                │
└────────────────────────────┬────────────────────────────────┘
                              │
                              ▼ WebSocket/SSE
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (port 8000)               │
│                  API + Streaming Events                      │
└────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LLM Backends                              │
│         Ollama / LM Studio / llama.cpp / Lemonade           │
└─────────────────────────────────────────────────────────────┘
```

## ✨ Features

- **Streaming temps réel** - Tokens affichés au fur et à mesure avec graphe live
- **Agent visible** - Timeline des étapes avec progress bar
- **Tool calling** - Appels API visibles en temps réel
- **Découverte automatique** des modèles depuis Ollama/LM Studio
- **Settings dashboard** - Grille compacte avec métriques backends live
- **FAISS memory** - Vector search avec dimension sync automatique
- **Thread-safe events** - Pub/sub avec lock pour concurrence
- **Safe executor** - TempDirectory cleanup, import sanitization
- **i18n** - Support Français/English

### UI/UX
- **Token graph** - Mini graphe live tokens/second pendant streaming
- **AgentSteps** - Progress bar avec animations fluides
- **Settings** - Dashboard production-grade avec 3-layer depth

## 🛠️ Stack Technique

| Couche | Technologie |
|--------|-------------|
| **Frontend** | Next.js 16, React 18, Tailwind, Zustand, Framer Motion |
| **Backend** | Python 3.10+, FastAPI, Pydantic |
| **LLM** | Ollama, LM Studio, llama.cpp, Lemonade |
| **Streaming** | WebSocket + SSE |
| **Mémoire** | FAISS + SentenceTransformers |

## 🚀 Installation

### Option 1: Script automatique (recommandé)

```bash
# Clone
git clone https://github.com/jeanmarcrenaud-prog/UI-Pro.git
cd UI-Pro

# Setup automatique
python setup.py
```

Le script:
- Vérifie Python 3.10+, Node.js, npm
- Crée le virtual environment `.venv`
- Installe les dépendances Python et Node.js
- Crée le fichier `.env` depuis le template
- Vérifie les services (Ollama, LM Studio)
- **Propose d'installer Ollama** si aucun backend détecté

### Option 2: Manuel

```bash
# Clone
git clone https://github.com/jeanmarcrenaud-prog/UI-Pro.git
cd UI-Pro

# Setup Python
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Setup Node.js
cd ui-pro-ui
npm install
cd ..

# Lancez Ollama (si pas encore lancé)
ollama serve

# Lancez l'application
python run.py --all
```

## 🎮 Utilisation

```bash
# Lancer tous les services (recommandé)
python run.py --all

# FastAPI uniquement
python run.py --api

# Next.js UI uniquement
python run.py --ui

# Vérifier status des services
python run.py --status

# Vérifier les dépendances
python run.py --check
```

### URLs

| Service | URL |
|---------|-----|
| **Next.js UI** | http://localhost:3000 |
| **FastAPI** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |

## 📁 Structure

```
ui-pro/
├── run.py                  # Entry point
├── setup.py                # Setup automatique
├── requirements.txt        # Dépendances Python
├── .env.example           # Template configuration
│
├── core/                   # Core modules
│   ├── executor.py        # Safe code executor
│   ├── state_manager.py   # State management
│   ├── memory.py          # FAISS memory
│   ├── events.py          # Thread-safe events
│   └── config.py          # Lazy config
│
├── services/              # Service layer
│   ├── llm_router.py      # LLM routing
│   ├── model_service.py   # Model management
│   ├── model_discovery.py # Multi-backend discovery
│   ├── streaming.py        # Streaming service
│   └── tools.py           # Tool registry
│
├── controllers/            # Business logic
│   ├── orchestrator.py    # Pipeline orchestrator
│   └── websocket.py       # WebSocket handling
│
├── llm/                   # LLM clients
│   └── router.py          # OllamaClient
│
├── views/                 # API views
│   └── api.py             # FastAPI endpoints
│
├── models/                # Types Python
│   └── settings.py        # Configuration
│
└── ui-pro-ui/             # Next.js frontend
    ├── app/
    │   ├── page.tsx       # Page principale
    │   └── layout.tsx     # Layout
    ├── components/        # Composants React
    │   ├── chat/          # Chat components
    │   ├── ui/            # UI components
    │   └── settings/      # Settings components
    ├── lib/               # Types, stores, i18n
    ├── services/          # API services
    └── stores/            # Zustand stores
```

## 🔧 Commandes

| Commande | Description |
|---------|-------------|
| `python setup.py` | Setup automatique |
| `python setup.py --yes` | Setup non-interactif |
| `python run.py --all` | Lance FastAPI + Next.js |
| `python run.py --status` | Vérifie les services |
| `python run.py --check` | Vérifie les dépendances |
| `python run.py --api` | FastAPI seul |
| `python run.py --ui` | Next.js seul |

## 🔐 Sécurité

- **Sandbox**: Isolation par tempfile.TemporaryDirectory
- **Sanitization**: Désactive eval, exec, subprocess.Popen
- **Timeout**: Configurable pour éviter les boucles infinies
- **NE JAMAIS** commit le fichier `.env`

## 🌟 Fonctionnalités Détaillées

### Streaming en temps réel
Les tokens sont affichés au fur et à mesure avec un mini graphe live (tokens/second).

### Agent visible
Pendant le traitement, les étapes sont affichées avec progress bar:
- 🧠 Analyzing
- ⚙️ Planning  
- 🔧 Executing
- ✅ Reviewing

### Découverte automatique des modèles
Le système détecte automatiquement les modèles disponibles:
- Ollama (localhost:11434)
- LM Studio (localhost:1234)
- llama.cpp (localhost:8080)
- Lemonade (localhost:8080)

### Settings Dashboard
- Grille compacte 3-colonnes
- Cartes backends live avec latence et nombre de modèles
- Progress bar et animations fluides

### i18n
- Support Français/English
- Traductions dans `ui-pro-ui/lib/i18n.ts`

## 📝 Licence

MIT License