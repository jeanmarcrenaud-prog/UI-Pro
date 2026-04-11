# UI-Pro - AI Agent Orchestration System

> **Système d'agents IA auto-hébergé** avec interface moderne comme ChatGPT.

![Status](https://img.shields.io/badge/status-beta-orange)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Next.js](https://img.shields.io/badge/Next.js-14-blue)

## 🚀 Présentation

`ui-pro` est un système d'orchestration d'agents IA moderne avec:

- **Interface UI moderne** (type ChatGPT) avec streaming temps réel
- **Agent intelligent** avec steps visibles en direct
- **Multi-modèles** supportés (Ollama, LM Studio, llama.cpp)
- **Tool calling** intégré
- **Architecture event-driven** pour une expérience fluide

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Next.js UI (port 3000)                   │
│              Interface moderne avec Tailwind               │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼ WebSocket/SSE
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (port 8000)              │
│                  API + Streaming Events                       │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    LLM Backends                             │
│         Ollama / LM Studio / llama.cpp                      │
└─────────────────────────────────────────────────────────────┘
```

## ✨ Features

- **Streaming temps réel** - Tokens affichés au fur et à mesure
- **Agent visible** - Timeline des étapes en direct
- **Tool calling** - Appels API visibles en temps réel
- **Découverte automatique** des modèles depuis Ollama/LM Studio
- **Settings** - Configuration des modèles et backends
- **Markdown** - Code highlighting dans les responses
- **Animations** - Transitions fluides avec Framer Motion

## 🛠️ Stack Technique

| Couche | Technologie |
|--------|-------------|
| **Frontend** | Next.js 14, React 18, Tailwind, Zustand |
| **Backend** | Python 3.10+, FastAPI |
| **LLM** | Ollama, LM Studio |
| **Streaming** | WebSocket + SSE |
| **Mémoire** | FAISS + SentenceTransformers |

## 🚀 Installation

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
python run.py
```

## 🎮 Utilisation

```bash
# Vérifier status des services
python run.py --status

# Lancer tous les services (recommandé)
python run.py

# FastAPI uniquement
python run.py --api

# Next.js UI uniquement
python run.py --ui

# Vérifier les dépendances
python run.py --check

# Lancer les tests
python run.py --test
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
├── app/
│   └── launcher.py          # Point d'entrée
├── api/
│   ├── main.py             # FastAPI backend
│   └── ...
├── controllers/            # Logique métier
├── models/                 # Types Python
├── views/                  # API views
├── ui-pro-ui/              # Next.js frontend
│   ├── app/
│   │   ├── page.tsx       # Page principale
│   │   └── layout.tsx      # Layout
│   ├── components/        # Composants React
│   │   ├── ChatContainer.tsx
│   │   ├── Sidebar.tsx
│   │   ├── SettingsView.tsx
│   │   └── ...
│   ├── features/           # Logique métier (controllers)
│   ├── services/           # Communication backend
│   ├── stores/            # Zustand stores
│   └── lib/               # Types, events
└── run.py                  #Launcher
```

## 🔧 Commandes

| Commande | Description |
|---------|-------------|
| `python run.py` | Lance FastAPI + Next.js |
| `python run.py --status` | Vérifie les services actifs |
| `python run.py --check` | Vérifie les dépendances |
| `cd ui-pro-ui && npm run dev` | Lance Next.js seul |

## 🔐 Sécurité

- **Sandbox**: Isolation par tempfile.TemporaryDirectory
- **Sanitization**: Désactive eval, exec, subprocess.Popen
- **Timeout**: Configurable pour éviter les boucles infinies
- **NE JAMAIS** commit le fichier `.env`

## 🌟 Fonctionnalités Détaillées

### Streaming en temps réel
Les tokens sont affichés au fur et à mesure de la génération, avec un curseur Animation.

### Agent visible
Pendant le traitement, les étapes sont affichées:
- 🧠 Analyzing
- ⚙️ Planning  
- 🔧 Executing
- ✅ Reviewing

### Découverte automatique des modèles
Le système détecte automatiquement les modèles disponibles:
- Ollama (localhost:11434)
- LM Studio (localhost:1234)
- llama.cpp (localhost:8080)

### Tool calling UI
Les appels outils sont affichés en temps réel avec indikator.

## 📝 Licence

MIT License