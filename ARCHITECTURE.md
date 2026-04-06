# 🏗️ **Architecture UI-Pro** (Stateful + Async + DI)

## 📁 **Structure Actuelle**

```
ui-pro/
├── run.py                   # Launcher (supervise tous les modules)
├── executor.py              # CodeExecutor (sandbox, timeout, auto-fix)
├── state_manager.py         # State + StateManager (typing complet)
├── orchestrator_async.py    # Pipeline async avec auto-fix loop
├── logger.py                # Logging + rotation + JSON
├── memory.py                # FAISS + SentenceTransformer
├── settings.py              # Configuration externalisée
├── dashboard.py             # Gradio UI (INTÉGRÉ au pipeline)
├── main.py                  # FastAPI entry point
├── llm_client.py            # Interface LLMClient (DI)
├── llm_router.py            # Multi-model routing
├── agents.py                # Agents (planner, architect, coder...)
├── requirements.txt         # + gradio, websockets
├── tests/                   # Test suite (85+ tests)
│   ├── test_execution.py    # 13 tests - TOUS PASSENT ✅
│   └── ...
└── workspace/               # Code généré
```

## 🔄 **Flux Dashboard → Orchestrator**

```
┌─────────────────┐
│  Dashboard.py   │  Gradio UI (port 7860)
│  (Task Input)   │
└────────┬────────┘
         │ Task Submit
         ▼
┌─────────────────────────────────────────┐
│  OrchestratorAsync.run()                 │
│  - StateManager.create(task_id)         │
└────────┬─────────────────────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
_planner()  _memory()  ← FAISS search
    │         │
    └────┬────┘
         ▼
   _architect()
         ▼
      _coder()
         ▼
     _reviewer()
         ▼
 ┌────┴────┐
 ▼         ▼
SUCCESS  FAIL (auto-fix loop, max 3)
         │
    _runner() via CodeExecutor
         │
    [Success/Fail]
```

## ✨ **Features**

| Feature | Implémentation |
|---------|----------------|
| **DI** | Settings injection via `settings.py` |
| **Async pipeline** | `orchestrator_async.py` avec asyncio |
| **Multi-model routing** | `llm_router.py` avec mode fast/reasoning/code |
| **State management** | `StateManager` avec State dataclass |
| **Dashboard** | `dashboard.py` connected to orchestrator_async |
| **Auto-fix loop** | Max 3 attempts avec correction LLM |
| **Memory** | FAISS + SentenceTransformer |

---

## 🔧 **Configuration**

### Environment Variables (.env)
```env
HF_TOKEN=your_token
OLLAMA_URL=http://localhost:11434
MODEL_FAST=qwen2.5-coder:32b
MODEL_REASONING=qwen-opus
LLM_TIMEOUT=30
EXECUTOR_TIMEOUT=60
LOG_LEVEL=INFO
```

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

---

## 🛡️ **Sécurité**

- **Sandbox**: tempfile.TemporaryDirectory isolation
- **Sanitization**: Désactive eval, exec, subprocess.Popen
- **Timeout**: Configurable pour éviter les boucles infinies
- **HF_TOKEN**: Via os.getenv(), jamais hardcodé

---

## 🧪 **Tests**

```bash
# Tous les tests passent
pytest tests/ -v
# 13 passed in 1.24s (test_execution.py)

# Couverture
pytest --cov=ui-pro --cov-report=html
```

---

## 📊 **Statut**

| Module | Status | Tests |
|--------|--------|-------|
| executor.py | ✅ DONE | 9 tests |
| state_manager.py | ✅ DONE | 3 tests |
| orchestrator_async.py | ✅ DONE | - |
| logger.py | ✅ DONE | 1 test |
| memory.py | ✅ DONE | - |
| dashboard.py | ✅ DONE | - |

---

**Dernière mise à jour**: 2026-04-06