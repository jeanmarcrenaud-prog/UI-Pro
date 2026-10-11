# Spec — Check config Hermes-agent + proposition d'installation (ui-pro)

## Objectif
Quand ui-pro s'affiche, il **vérifie la configuration de son agent "Hermes"**
(les settings `hermes_llm_base_url` / `hermes_llm_model`) et :
- ✅ si c'est prêt → rien à faire (bandeau discret "prêt").
- ⚠️ si mal configuré ou LLM injoignable → **proposer** une installation/
  correction claire, **sans action automatique** (JM valide).

## Règles d'or (ne pas sur-architecter)
1. **Local-first**. Pas de cloud, pas de clé API par défaut. Le "backend" par
   défaut doit être LM Studio (`http://127.0.0.1:1234/v1`) ou Ollama local
   (`http://127.0.0.1:11434`), auto-détectés.
2. **Ne pas charger trop de modèle.** Recommandation VRAM-aware : si le GPU est
   déjà chargé (LM Studio a un model 27B), ne PAS proposer d'ajouter un autre
   gros model sur GPU — recommander soit le petit model déjà chargé, soit CPU.
3. **Pas d'action auto** côté config : ui-pro *lit* la config et *propose*. Le
   bouton "Corriger" appelle un endpoint existant (`set_hermes_llm_config`) mais
   seulement après validation.
4. Ne pas casser le contrat existant de `/api/hermes/*` ni `HermesView`.

## État actuel (verifié)
- Settings : `backend/domain/settings.py` → `hermes_llm_base_url` (str, défaut "")
  et `hermes_llm_model` (str, défaut "google/gemma-4-12b-qat").
- Méthode existante : `Settings.set_hermes_llm_config(base_url, model)`
  → écrit dans `.env` et invalide les singletons provider.
- Router Hermes : `backend/transport/routers/hermes.py` → `/status` retourne
  `{available: bool, tools:[{name,description}]}`. PAS d'endpoint config.
- Factory LLM : `backend/infrastructure/llm/factory.py` → `_detect_llm_provider()`
  détecte LM Studio (port 1234) / Ollama (port 11434) / NVIDIA API.
- Frontend : `frontend/components/HermesView.tsx` (tab Hermes, chat + status).
  Pas de bandeau config actuellement.

## À créer — BACKEND
### 1. Helper `backend/infrastructure/llm/hermes_config.py`
Une classe/fonctions stateless pour évaluer la config Hermes-agent :

```python
def evaluate_hermes_config(settings) -> dict:
    """Retourne un rapport de prêt, sans modifier rien."""
```
Retour (JSON, stable) :
```json
{
  "configured": true|false,            // base_url non vide ET model non vide
  "base_url": "",                       // valeur actuelle (ou null si vide)
  "model": "google/gemma-4-12b-qat",   // modèle actuel
  "backend": "lmstudio" | "ollama" | "none" | "nvidia",
  "llm_reachable": true|false,         // a-t-on pu appeler /v1/models (LM Studio)
                                         // ou /api/tags (Ollama) ? timeout 3s
  "available_models": ["qwen3.8-27b...", "aura-4b", ...],  // listés par l'API
  "recommended_model": "aura-4b",      // voir logique ci-dessous
  "gpu_headroom_ok": true|false,       // vu le contexte de la machine
  "needs_install": true|false,         // faut-il installer/déployer un model ?
  "message": "..."                    // message FR clair pour le bandeau
}
```

### 2. Logique de recommandation (`recommended_model`)
- Si `backend == "none"` (aucun LLM local détecté) → `needs_install=true`,
  message = "Aucun LLM local détecté. Installez LM Studio ou Ollama."
- Sinon :
  - **VRAM-aware** : si le model du GPU est un gros one (>15B), ne pas recommander
    d'ajouter un autre gros model sur GPU → recommander le **petit model déjà
    chargé** (ex. `aura-4b`) ou marquer `gpu_headroom_ok=false`.
  - Choisir le model le plus léger dans `available_models` qui a du contexte
    raisonnable (>4k), en favorisant les modèles FR/EN multi-use.
- **Pas d'appel GPU** : ne pas tenter de charger un model ; ne PAS faire de
  `nvidia-smi` bloquant (timeout max ~2s, catch).

### 3. Endpoint `/api/hermes/config`
Dans `backend/transport/routers/hermes.py` :
```python
@router.get("/config")
async def get_hermes_config() -> dict:
    """Rapport de prêt de la config Hermes-agent."""
    settings = get_settings()
    return evaluate_hermes_config(settings)
```

## À créer — FRONTEND (HermesView.tsx)
Ajouter un **bandeau "prêt" (readiness banner)** en haut du component, AVANT
le header, qui :
1. Appelle `fetchStatus()` existant + le nouveau `/config` à mount.
2. Affiche selon `needs_install` / `configured` / `llm_reachable` :
   - ✅ **Prêt** (discret) : "Hermes prêt · model: {model}".
   - ⚠️ **Mal configuré** : icône + message FR de `message`, le modèle
     recommandé, et un bouton **"Corriger"** qui ouvre un `ConfigModal`.
3. `ConfigModal` (nouveau component `frontend/components/agent/HermesConfigModal.tsx`) :
   - Champs read-only : base_url actuelle, model actuel.
   - Suggestion cliquable : "Utiliser {recommended_model} via LM Studio".
   - Bouton **"Appliquer"** → POST `/api/hermes/config` (ou réutiliser
     `set_hermes_llm_config` via un endpoint) + re-fetch du bandeau.
   - Bouton **"Annuler"**.
4. Style : utiliser le design system existant (glass-panel, var(--text-*),
   gradients violet/fuchsia). Ne pas introduire de nouveau framework.

## Tests / validation
- Backend : `tests/` — un test unitaire de `evaluate_hermes_config` avec mock
  (LM Studio reachable + model listé ; LM Studio down → needs_install=true).
- Frontend : le bandeau rend les 2 états (prêt / mal configuré) sans crash.

## Hors-scope (ne pas faire pour l'instant)
- Pas de feature d'install *automatique* de LM Studio/Ollama (juste proposer +
  guide).
- TTS KittenTTS 2 = feature à part, pas mélangée ici (voir spec-tts).
