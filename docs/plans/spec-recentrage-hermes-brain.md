# Spec — Recentrer ui-pro autour de Hermes (brain principal)

## Objectif
Le pipeline LangGraph (chat principal: analyze→plan→code→review→execute→fixing) doit
**appeler Hermes ACP par défaut** comme moteur LLM, avec fallback robuste vers Ollama.
Ollama/LM Studio restent disponibles en "mode rapide" (dropdown utilisateur).

## Contexte — état actuel (vérifié dans le code)
- `backend/domain/core/langgraph/nodes/_base.py:219` → `_get_model_info()` retourne
  `(model, provider)` avec **`provider` default = `"ollama"`**.
- `backend/transport/routers/ws.py:121` → le frontend envoie `parsed.get("provider", "ollama")`.
- Le router `LLMRouter.generate()/astream()` (llm_router.py) accepte déjà un paramètre
  `provider: str = "ollama"` et fait `get_backend(provider or "ollama")`.
- Le backend Hermes ACP est **déjà enregistré** dans `backend/infrastructure/llm/factory.py`
  : `register_backend("hermes_acp", HermesACPBackend)` (et `"hermes"` aussi via HermesBackend).
- `HermesACPBackend` (hermes_acp.py) :
  - `list_models()` → `[{"name": "hermes", "available": True}]`
  - `health_check()` → `{"status": "ok"|"error", ...}` — probe le subprocess `hermes acp`.
  - Si `settings.hermes_llm_base_url` et `model` sont **les deux vides**, il utilise son
    propre config Hermes (modèle choisi par Hermes). C'est le cas ici: `.env` a
    `HERMES_LLM_BASE_URL=` et `HERMES_LLM_MODEL=` vide.
- `backend/domain/core/langgraph/hermes_bridge.py` : `should_use_hermes(state)` et
  `hermes_execute_node()` existent mais sont **jamais appelés** par les nœuds (code mort).
- Le test `tests/test_hermes_bridge.py` existe déjà et valide le comportement de
  `should_use_hermes`.

## Ce qu'on doit faire — implémentation minimale

### 1. `llm_wrapper.py` : fallback Hermes→Ollama dans `_resolved()` (LE point d'intervention unique)
Quand `user_provider` est `"hermes"` (ou `"hermes_acp"`) et que le backend Hermes
**n'est pas sain**, on retombe sur Ollama.

- **FONCTION EXACTE À AJOUTER** (module-level, vers la ligne 30 de `llm_wrapper.py`):
  ```python
  _hermes_healthy_cache: dict[str, bool] = {}
  
  def _hermes_healthy() -> bool:
      \"\"\"Probe le backend Hermes ACP (cache 60s). Retourne True si sain.\"\"\"
      import time
      now = time.monotonic()
      for key in list(_hermes_healthy_cache):
          if _hermes_healthy_cache[key] and now - _hermes_healthy_cache.pop(key) > 60:
              pass
      if \"cached\" in _hermes_healthy_cache:
          return _hermes_healthy_cache[\"cached\"]
      try:
          from backend.infrastructure.llm.factory import get_backend
          from backend.domain.settings import settings
          backend = get_backend(\"hermes_acp\")  # ou \"hermes\"
          result = backend.health_check()
              _hermes_healthy_cache[\"cached\"] = (result.get(\"status\") == \"ok\")
              return _hermes_healthy_cache[\"cached\"]
      except Exception:
              _hermes_healthy_cache[\"cached\"] = False
              return False
  ```
- **MODIFICATION EXACTE** dans `LLMWrapper._resolved()` (lignes 98-107):
  ```python
  def _resolved(self) -> tuple[str, str]:
      if self.force_model:
          return self.force_model, self.force_provider
      # Recentrage Hermes: si le user a choisi hermes et que c'est sain → hermes;
      # sinon fallback Ollama.
      from ..hermes_bridge import is_hermes_provider  # late import — breaks circular dep
      if is_hermes_provider(self.user_provider) and _hermes_healthy():
          return (self.user_model or \"\"), \"hermes_acp\"
      return self.user_model, self.user_provider
  ```

### 2. `_base.py` : default provider = hermes
- **Ligne EXACTE** ~219: changer `(metadata or {}).get(\"provider\", \"ollama\")` en
  `(metadata or {}).get(\"provider\", _DEFAULT_PIPELINE_PROVIDER)`.
- **Constante À AJOUTER** (lignes 20-30, après `_node_token_counts`):
  ```python
  _DEFAULT_PIPELINE_PROVIDER = \"hermes\"
  ```
- C'est LE changement qui fait de Hermes le brain par défaut.

### 3. Frontend: dropdown Hermes + badge santé
- `frontend/app/page.tsx` + le provider list doit inclure une option **\"Hermes\"**
  (label: \"Hermes (copilot)\") avec un badge santé vert/rouge selon
  `/api/hermes/status`.
- **NE PAS** casser l'existing dropdown Ollama/LM Studio.

### 4. `/api/hermes/status` : déjà existant, ne pas changer
- Déjà dans `backend/transport/routers/hermes.py` (prefix `/api/hermes`).
- Retourne `{"available\": True, \"tools\": ...}` — le frontend lit ce champ pour
  afficher le badge santé.

## NE PAS faire (Do NOT)
- **NE PAS** créer de nouveaux endpoints, services, ou fichiers dans
  `backend/infrastructure/llm/`.
- **NE PAS** changer la signature des nœuds (`analyzing_node`, `coding_node`, etc.).
- **NE PAS** toucher à la Sandbox (executing_node, conteneur Docker).
- **NE PAS** ajouter de dépendances front.
- **NE PAS** supprimer les tests existants.

## Ce qui ne doit pas casser (contract)
- 51 tests dans `tests/` + `backend/domain/core/langgraph/` — tous doivent passer.
- Le test `tests/test_hermes_bridge.py` valide le contrat des tools Hermes
  (hermes_read_file, hermes_write_file, hermes_execute_intent).
- Les endpoints `/api/mario/*`, `/api/hermes/*`, `/api/health` inchangés.
- Le pipeline LangGraph (`run_agent()`) doit retourner un `state` valide même si
  Hermes n'est pas sain (→ fallback Ollama).

## Décision points (honnête)
1. **Fallback**: on retombe sur Ollama si Hermes non sain → Recommandation: **fallback**
   (ne casse pas les setups existants).
2. **Modèle**: quand Hermes est actif, on laisse `user_model` vide (Hermes choisit)
   → Recommandation: **vide**.
3. **Santé probe**: timeout max 5s — si la probe échoue, on retombe Ollama → OK.

## Test de validation
- `pytest tests/test_hermes_bridge.py -x` (devrait passer)
- `pytest backend/domain/core/langgraph/ -x` (devrait passer)
- `curl http://127.0.0.1:8000/api/hermes/status` (devrait retourner la santé)

## Risques connus
- Hermes ACP peut prendre 3-5s pour initialiser le subprocess — si c'est trop lent, on
  augmente le timeout de la probe ou on cache plus longtemps.
- Le frontend doit afficher \"Hermes non sain → mode Ollama\" si l'utilisateur a choisi
  Hermes mais que ce n'est pas disponible.

- Ajouter une fonction module-level `_hermes_healthy() -> bool`:
  - cache le résultat du `health_check()` d'un instance `HermesACPBackend` (lazy, avec un
    timeout court — ne pas re-probe à chaque call).
  - retourne `True` si `status == "ok"`, `False` sinon.
  - **IMPORTANT**: si `settings.hermes_llm_base_url` et `model` sont vides, on NE PAS
    force l'erreur: le backend utilise son config Hermes native. On ne peut pas garantir
    sans probe, donc on fait la probe mais avec un timeout court (5s max). Si la probe
    échoue → fallback Ollama.
- Dans `LLMWrapper._resolved()`:
  ```python
  def _resolved(self) -> tuple[str, str]:
      if self.force_model:
          return self.force_model, self.force_provider
      # Recentrage Hermes: si le user a choisi hermes et que c'est sain → hermes;
      # sinon fallback Ollama (on ne casse pas les setups Ollama existants).
      if is_hermes_provider(self.user_provider) and _hermes_healthy():
          return self.user_model, "hermes_acp"
      return self.user_model, self.user_provider
  ```
- **Le modèle** quand Hermes est actif: on le laisse vide (Hermes choisit son modèle).
  Si `user_model` est un nom Ollama type `qwen3.8-27b`, on le passe à Hermes comme
  "default model" dans son config — c'est OK car `HermesACPBackend._get_hermes_home_env()`
  gère déjà le cas "model vide" (config native).

### 2. `_base.py` : default provider = hermes
- Ligne ~219: changer `(metadata or {}).get("provider", "ollama")` en
  `(metadata or {}).get("provider", _DEFAULT_PIPELINE_PROVIDER)`.
- `DEFAULT_PIPELINE_PROVIDER = "hermes"` (ou `"hermes_acp"` — voir le test).
- **IMPORTANT**: c'est LE changement qui fait de Hermes le brain par défaut.

### 3. Frontend: dropdown Hermes + fallback affiché
- `frontend/app/page.tsx` + le provider list doit inclure une option **"Hermes"**
  (label: "Hermes (copilot)") avec un badge santé (vert/rouge selon `/api/hermes/status`).
- **NE PAS** casser l'existing dropdown Ollama/LM Studio.

### 4. `/api/hermes/status` : endpoint de santé pour le frontend
- Déjà existant dans `backend/transport/routers/hermes.py` (prefix `/api/hermes`).
- Vérifier qu'il retourne la santé du backend Hermes ACP **sans** casser si non configuré.

## NE PAS faire (Do NOT)
- **NE PAS** créer de nouveaux endpoints, de nouveaux services, ou de nouveaux fichiers
  dans `backend/infrastructure/llm/`.
- **NE PAS** changer la signature des nœuds (`analyzing_node`, `coding_node`, etc.).
- **NE PAS** toucher à la Sandbox (executing_node, conteneur Docker).
- **NE PAS** ajouter de dépendances front.
- **NE PAS** supprimer les tests existants.

## Ce qui ne doit pas casser (contract)
- 51 tests dans `tests/` + `backend/domain/core/langgraph/` — tous doivent passer.
- Les endpoints `/api/mario/*`, `/api/hermes/*`, `/api/health` inchangés.
- Le pipeline LangGraph (`run_agent()`) doit retourner un `state` valide même si Hermes
  n'est pas sain (→ fallback Ollama).

## Décision points (honnête)
1. **Fallback**: on retombe sur Ollama si Hermes non sain — ou on affiche une erreur
   dans l'UI? → Recommandation: **fallback Ollama** (ne casse pas les setups existants).
2. **Modèle**: quand Hermes est actif, on laisse `user_model` vide (Hermes choisit) —
   ou on force le modèle Ollama comme default? → Recommandation: **vide** (Hermes natif).
3. **Santé probe**: timeout max 5s — si la probe échoue, on considère Hermes non sain
   et on retombe Ollama. → OK.

## Test de validation
- `pytest tests/test_hermes_bridge.py -x` (devrait passer — valide le fallback)
- `pytest backend/domain/core/langgraph/ -x` (devrait passer — pipeline intact)
- `curl http://127.0.0.1:8000/api/hermes/status` (devrait retourner la santé)

## Risques connus
- Hermes ACP peut prendre 3-5s pour initialiser le subprocess — si c'est trop lent, on
  augmente le timeout de la probe ou on cache plus longtemps.
- Le frontend doit afficher "Hermes non sain → mode Ollama" si l'utilisateur a choisi
  Hermes mais que ce n'est pas disponible.
