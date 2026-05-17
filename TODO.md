# TODO - UI-Pro Project

> **Liste des tâches en cours et à venir** du projet `ui-pro`.

## ✅ COMPLÉTÉ (Terminé)

### Refactoring Backend (2026-05-12)

| # | Tâche | Statut |
|---|-----|-|------|
| 1 | Migrer vers backend/ comme source de vérité | ✅ |
| 2 | Convertir core/ vers ré-exports | ✅ |
| 3 | Convertir services/ vers ré-exports | ✅ |
| 4 | Convertir api/ vers ré-exports | ✅ |
| 5 | Convertir views/ vers ré-exports | ✅ |
| 6 | Mettre à jour AGENTS.md | ✅ |
| 7 | Mettre à jour ARCHITECTURE.md | ✅ |

### Cleanup Final (2026-05-17)

| # | Tâche | Statut |
|---|-----|-|------|
| 1 | Supprimer les legacy folders (core/, services/, api/, views/, controllers/) | ✅ |
| 2 | Mettre à jour tous les imports vers backend/* | ✅ |
| 3 | Créer scripts/check_cleanup.py | ✅ |
| 4 | Nettoyer fichiers obsolètes (start_api.py, test.db, etc.) | ✅ |
| 5 | Déplacer kill_port.py vers scripts/ | ✅ |
| 6 | Mettre à jour documentation (ARCHITECTURE.md, AGENTS.md, README.md) | ✅ |

### Refactoring Terminé (2026-04-28)

| # | Tâche | Statut |
|---|-----|-|------|
| 1 | Code Deduplication: Supprimé 10 fichiers | ✅ |
| 2 | Cleanup: Supprimé dead code, obsolètes | ✅ |
| 3 | Fixes: pyproject.toml, config.yaml.example | ✅ |

### Features Mai 2026

| # | Tâche | Statut |
|---|-----|-|------|
| 1 | Command Palette (Ctrl+K) | ✅ |
| 2 | Focus Mode toggle | ✅ |
| 3 | History multi-select | ✅ |
| 4 | Batch actions (pin/export/archive/delete) | ✅ |
| 5 | Contextual suggestions | ✅ |
| 6 | Code Minimap (VS Code-style) | ✅ |
| 7 | Minimap click+drag navigation | ✅ |
| 8 | Model description (GitHub/Ollama API) | ✅ |
| 9 | About link to GitHub | ✅ |
| 10 | Keyboard shortcuts on buttons | ✅ |
| 11 | Visual code improvements | ✅ |
| 12 | Update ARCHITECTURE.md | ✅ |
| 13 | Update requirements.txt | ✅ |

---

## 🔧 EN COURS

| # | Tâche | Priorité |
|---|-----|---------|
| 1 | Refactor HistoryView (trop long) | ✅ DONE |
| 2 | Fix Minimap scroll (fixed) | ✅ DONE |
| 3 | Add Status indicator to code | ✅ DONE |

---

## Nouvelles Features (Mai 2026)

### Command Palette
- **Ctrl+K** / **Cmd+K** pour ouvrir
- **Focus Mode** (Ctrl+Shift+F) - cache sidebar/header
- **Theme toggle** temporairement désactivé

### History Multi-Select
- Bouton "Select" pour activer mode sélection
- Checkbox sur chaque chat
- "Select All" / "Deselect All"
- Indicateur visuel **"X/Y selected"**
- Bouton Delete rouge vif

### Batch Actions
- **Pin** - Épingler les chats sélectionnés
- **Export** - Exporter en Markdown combiné
- **Archive** - Archiver les chats
- **Delete** - Supprimer (danger rouge)

### Contextual Suggestions
5 suggestions sous chaque réponse IA:
- "Improve code" - Améliorer le code
- "Add tests" - Ajouter des tests
- "FastAPI version" - Créer endpoint FastAPI
- "Make robust" - Rendre plus robuste
- "Convert to package" - Convertir en package

### Code Minimap
- Affichée si **> 15 lignes**
- **Fixed** pendant scroll (absolute)
- **Click** pour naviguer vers ligne
- **Click + drag** pour scrolling continu
- Indicateur violet de position

### Settings Améliorations
- Description du modèle via **GitHub/Ollama API**
- Lien "À propos" → **https://github.com/jeanmarcrenaud-prog/UI-Pro**

### Code Action Buttons
- **Copy** - Bouton violet avec raccourci **Ctrl+C**
- **Download** - Bouton gris avec raccourci **Ctrl+S**

---

## Structure Actuelle (Post-Refactoring)

```
ui-pro/                           # Projet principal
├── run.py                        # Launcher principal
├── app/launcher.py              # Multi-service launcher
│
├── backend/                      # SOURCE DE VÉRITÉ (SEUL)
│   ├── domain/                  # Business logic
│   │   └── core/                # Core modules
│   ├── infrastructure/          # Services layer
│   ├── application/              # App layer
│   └── transport/                # API endpoints
│
├── llm/                          # LLM clients (module séparé)
├── models/                       # Data types + Settings
├── tests/                        # Tests
├── scripts/                     # Scripts utilitaires
├── ui-pro-ui/                    # Next.js frontend
│   └── components/
│       ├── chat/                # 7 composants
│       └── markdown/             # 3 composants
└── workspace/                   # Code généré
```

---

## Paramètres de Configuration

### ExecutionConfig (executor.py)
```python
timeout: int = 30           # Timeout en secondes
workspace_dir: str = "workspace"
cleanup: bool = True
max_fix_attempts: int = 3    # Tentatives auto-fix
```

### State Metrics
```python
metrics = {
    "total_duration_ms": 0,
    "llm_calls": 0,
    "tokens": 0,
    "retry_count": 0,
    "max_retry_count": 3,
}
```

---

## Lancement

```bash
# FastAPI + Gradio
python run.py --all

# FastAPI uniquement
python run.py --api

# Next.js uniquement
python run.py --ui

#Vérifier status
python run.py --status
```

---

## Tests

```bash
# Tous les tests
pytest tests/ -v

# Tests spécifiques
pytest tests/test_execution.py -v
```

---

## Notes

- **Windows**: Compatible avec subprocess.DEVNULL
- **Auto-fix**: Boucle génère prompt LLM pour corriger les erreurs
- **State**: Persistence JSON optionnelle via save_json()
- **Memory**: Recherche vectorielle via FAISS
- **Next.js**: Frontend sur port 3000
- **FastAPI**: Backend sur port 8000
- **Gradio**: Dashboard sur port 7860

---

**Dernière mise à jour**: 2026-05-12
**Status**: Refactoring backend terminé ✅