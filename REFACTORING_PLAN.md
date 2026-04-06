# Plan de Refactorisation Architecturale - UI-Pro

## État Actuel (Problèmes Identifiés)

### 1. Architecture Trop Plate
- **Problème**: Mélange direct UI → Orchestrator → LLM dans `views/dashboard.py`
- **Exemple**: `orch.run()` appelé directement dans le handler Gradio
- **Risque**: Couplage fort, impossible de tester/développer séparément

### 2. Pas de Couche Service
- **Actuel**: `controllers/llm_client.py` (basique) + `models/llm_router.py` (routing)
- **Manquant**: `ChatService`, `ModelService`, `MemoryService`

### 3. Pas de Gestion Avancée des Modèles
- **Actuel**: Routing simple par mot-clé dans `LLMRouter`
- **Manquant**: Fallback automatique, latency tracking, retry intelligent

---

## Plan de Refactorisation (3 Phases)

### Phase 1: Couche Services (Semaine 1)

**-but1: Créer services/**
```
services/
├── __init__.py
├── base.py           # Interface commune + logging
├── chat_service.py   # Orchestration对话
├── model_service.py  # Gestion modèles (fallback, retry)
└── memory_service.py # FAISS encapsulé
```

**-but2: Remplacer appels directs**

| Avant | Après |
|-------|-------|
| `orch.run(text)` dans dashboard | `chat_service.execute(task)` |
| `router.generate(prompt, mode)` | `model_service.generate(prompt, mode)` |
| `memory.search(q, k)` | `memory_service.search(q, k)` |

**but3: Implémenter**

```python
# services/chat_service.py
class ChatService:
    def __init__(self, model_service, memory_service):
        self.model = model_service
        self.memory = memory_service
    
    async def execute(self, task: str) -> dict:
        # 1. Retrieval from memory
        # 2. Plan via model
        # 3. Execute
        # 4. Store in memory
        pass

# services/model_service.py  
class ModelService:
    def __init__(self, router, metrics):
        self.router = router
        self.metrics = metrics
    
    def generate(self, prompt: str, mode: str) -> str:
        # 1. Get model for mode
        # 2. Track latency
        # 3. Try primary model
        # 4. Fallback if needed
        pass
```

---

### Phase 2: Routing Avancé (Semaine 2)

**-but1: Améliorer `models/llm_router.py`**

```python
class AdvancedLLMRouter:
    """Router avec fallback + latency + metrics"""
    
    def __init__(self, config):
        self.models = {...}  # All available models
        self.fallback_chain = {...}  # Model fallback chains
        self.latency_history = {}  # Track per-model latency
    
    def select_model(self, task: str, context: dict) -> str:
        """Smart selection avec latency awareness"""
        # Exclude models with high latency
        # Prefer models with better success rate
        pass
    
    def get_fallback(self, failed_model: str) -> str:
        """Get next model in chain"""
        pass
```

**-but2: Métriques par modèle**

```python
# Track par modèle:
- latency_p50, latency_p95
- success_rate  
- token_usage
- failure_count
```

---

### Phase 3: Découplage UI (Semaine 3)

**-but1: API Interne**

```python
# services/api.py (interne, pas FastAPI)
class ServiceAPI:
    """API interne pour les services"""
    
    def __init__(self, chat_service):
        self.chat = chat_service
    
    async def chat(self, message: str) -> str:
        pass
    
    async def status(self) -> dict:
        pass
```

**-but2: Refactorer dashboard**

```python
# AVANT (views/dashboard.py)
orch = Orchestrator()
result = orch.run(text)

# APRÈS
from services import ChatService
chat = get_chat_service()
result = await chat.execute(text)
```

---

##Impact Métriques

| Métrique | Avant | Après |
|----------|-------|-------|
| Couplage | Fort (UI↔LLM) | Faible (via services) |
| Testabilité | Difficile | Unitaire par service |
| Extensibilité | Ajouter model = risqué | Nouveau service |
| Latence | Non trackée | Metrics intégrées |

---

##Risques et Mitigations

| Risque | Mitigation |
|--------|------------|
| Breaking changes | backward compat via facade |
| Temps de dev | Phase incremental |
| Perte features | Garder old code en fallback |

---

## Decision Requise

1. **Valider ce plan** ou proposer modifications ?
2. **Priorité**: Phase 1 suffisante, ou besoin 1+2+3 ?
3. **Timeline**: Combien de temps pour cette refactorisation ?

---