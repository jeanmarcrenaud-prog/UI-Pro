# 🧭 ADR — Communication Hermes ↔ UI-Pro

> **Date**: 2026-08-16 · **HEAD vérifié**: `c9923da` · **Statut**: ✅ Phases 0-4 terminées (ADR, événements unifiés, native tool calling, sessions/cancel, transport ACP direct)

## Contexte

UI-Pro embarque **Hermes** comme moteur d'intelligence local : il exécute des
intentions utilisateur (lancer une app, lire/écrire des fichiers, interroger
OpenCode) via un serveur MCP. Deux chemins de communication coexistent
aujourd'hui, avec des conventions différentes et aucune visibilité croisée.

## Rôles (décision Phase 0)

| Acteur | Rôle | Chemin |
|---|---|---|
| **Hermes (MCP server)** | Agent d'actions machine — exécute des intentions, fichiers, statut OpenCode | `backend/infrastructure/mcp/server.py` |
| **UI-Pro LangGraph** | Orchestrateur de génération de code (analyze → plan → code → review → execute) | `backend/domain/core/langgraph/` |
| **Open Design daemon** | Bridge optionnel vers les CLIs d'agents (ACP JSON-RPC) — **pas un chemin critique** | `backend/infrastructure/llm/opendesign.py` |

## État actuel (cartographié le 2026-08-16)

### 1. HermesMCPServer — `backend/infrastructure/mcp/server.py`

- Client LLM OpenAI-compat : `HERMES_LLM_BASE_URL` (défaut `settings.lmstudio_url + "/v1"`),
  `HERMES_LLM_API_KEY` ("lm-studio"), `HERMES_LLM_MODEL` ("google/gemma-4-12b-qat") — **env vars, pas exposées dans Settings UI**.
- 5 outils : `execute_intent`, `get_opencode_status`, `read_file`, `write_file`, `chat`.
- **Tool calling par tags textuels** : `<|tool_call>call:TOOL_NAME{json}<tool_call|>`
  parsé par regex (`parse_tool_call_tag`, l.293) — **pas de native tool calling**.
- **1 seul tour de tool call max** (`_handle_chat` l.209-222, `stream_chat` l.266-286) — pas de boucle bornée.
- **Pas de timeout global** aligné sur `settings.llm_timeout` (le client HTTP OpenAI a son propre timeout).
- **Aucune émission EventBus** — les tool calls Hermes sont invisibles côté frontend.

### 2. Router HTTP — `backend/transport/routers/hermes.py`

- `GET /api/hermes/status`, `POST /api/hermes/conversation`, `POST /api/hermes/tool`,
  `POST /api/hermes/conversation/stream` (SSE).
- Expose `get_server().list_tools()` et `call_tool()` directement.

### 3. HermesBackend — `backend/infrastructure/llm/hermes.py`

- Chemin **inverse** : UI-Pro parle à Hermes via le daemon Open Design
  (`/api/chat` SSE, `agentId="hermes"` hardcodé l.48).
- Docstring : « Future: when Hermes exposes a direct ACP TCP server (`hermes acp`),
  this backend can be extended with a direct transport that bypasses the daemon ».

### 4. Settings — `backend/domain/settings.py`

- `hermes_url` = `opendesign_url` = `http://localhost:7456` (l.94-95).
- `backends["hermes"]` : `models_endpoint: "/api/agents"`, timeout aligné sur `llm_timeout` (l.238-243, 278-279).

### 5. Health — `backend/transport/routers/health.py`

- `/health/deep` → `_check_backends()` + `aggregate_health()`.
- **Pas de sonde Hermes dédiée** (ni agent présent, ni LLM client initialisé).

### 6. Frontend — `frontend/lib/events.ts`, `frontend/services/MessageHandler.ts`

- EventEmitter typé (`events`), `MessageHandler` parse WS/SSE → `onToken/onStep/onError/onComplete`.
- **Ne consomme pas les tool calls Hermes** (pas d'événement `toolCall` émis depuis le MCP server).

## Problèmes identifiés

| # | Problème | Impact |
|---|---|---|
| P1 | Tool calling par tags textuels (regex) | Fragile, pas de schémas JSON natifs, pas de `tool_choice` |
| P2 | 1 seul tour de tool call max | Un agent qui doit enchaîner 2 outils échoue |
| P3 | Pas de timeout global aligné | `LLM_TIMEOUT` (900s) ignoré côté MCP server |
| P4 | Pas d'émission EventBus | Tool calls Hermes invisibles dans le frontend / debug panel |
| P5 | `HERMES_LLM_*` en env vars | Pas configurable depuis Settings UI |
| P6 | Pas de sonde Hermes dans `/health/deep` | Pas de visibilité ops sur l'état du moteur |
| P7 | Double config LLM (env vs settings) | Dérive possible entre les deux chemins |

## Décisions

### D1 — Native tool calling (Phase 2, prioritaire)

Remplacer le parsing regex par le paramètre `tools=` OpenAI-compat :

- Construire `tools` depuis `list_tools()` (schémas JSON déjà présents dans `input_schema`).
- `tool_choice="auto"`, boucle bornée `max_tool_rounds=5`.
- **Fallback** : si le modèle ne renvoie pas de `tool_calls` natifs mais un tag textuel,
  conserver `parse_tool_call_tag` (compatibilité modèles sans tools).
- Timeout global aligné sur `settings.llm_timeout`.

### D2 — Événements EventBus (Phase 1)

Émettre `emit_tool()` / `emit_agent_step()` depuis le MCP server pour chaque
tool call → visibilité frontend + debug panel.

### D3 — Settings UI (quick win) ✅ `75d97f1`, `138c97d`, `34e34b9`, `2f2f092`

Exposer `HERMES_LLM_BASE_URL` / `HERMES_LLM_MODEL` dans Settings UI (champs
`hermes_*` dans `settings.py` + endpoint `/api/settings` + carte
`HermesSettings` dans le dashboard). Le serveur MCP lit ces champs à la
construction (premier `get_server()`), donc le changement est effectif au
redémarrage — noté dans l'UI.

### D4 — Sonde Hermes dans `/health/deep` (quick win) ✅ `138c97d`, `34e34b9`

Bloc `hermes_agent` report-only dans `/health/deep` : agent présent (LLM
client initialisé) + modèle/base_url configurés. Le backend `hermes` est
déjà sondé en HTTP par la boucle `_check_backends()` (via
`settings.backends["hermes"]` → `/api/agents`) ; le bloc ajoute la sonde
locale du serveur MCP in-process via `get_server_state()` (lazy singleton,
donc `not_initialized` sur boot frais — ne dégrade pas le statut global).

### D5 — Transport direct ACP stdio (Phase 4) ✅

Le backend `HermesACPBackend` parle le protocole ACP JSON-RPC 2.0 directement
sur les flux stdio du subprocess `hermes acp` (via `agent-client-protocol`).
Chaque appel spawn un processus, initialise la session, envoie le prompt,
stream les réponses textuelles, puis ferme la session — bypass complet du
daemon Open Design. Le `hermes acp` expose bien un transport **stdio**, pas TCP
(corrigé : la version 0.20.0 du binaire Hermes utilise stdio, conformément au
schéma ACP v0.11.2). Implémenté dans `backend/infrastructure/llm/hermes_acp.py`.
### D6 — Sessions & cancel (Phase 3) ✅

Sessions de conversation côté MCP server : `_sessions: Dict[str, List[...]]`
(historique multi-tours persisté), `_active_streams` pour le cancel, plafond
`_max_sessions = 100` (éviction du plus ancien). Le `session_id` est généré
côté router (`uuid4().hex[:12]`) et retourné au client via l'en-tête
`X-Session-Id` sur le SSE (pas dans le flux, pour ne pas casser le parsing
frontend `data: <token>`). Endpoints : `POST /conversation/cancel`,
`GET /sessions`, `DELETE /sessions/{session_id}`. Le frontend stocke le
`session_id` et l'envoie aux appels suivants (multi-tours).


## Plan d'implémentation

| Phase | Contenu | Statut |
|---|---|---|
| **0** | ADR + rôles | ✅ Ce document |
| **1** | Événements unifiés (D2) | ✅ `40afc03`, `1cac012`, `b4276fc` |
| **2** | Native tool calling (D1) | ✅ `a95c756`, `ffb5eca` |
| **3** | Session / cancel (D6) | ✅ |
| **4** | Transport abstraction (D5) | ✅ `hermes_acp.py` |
| **5** | LangGraph bridge | ⏳ |
| **6** | Health / metrics (D4) | ✅ `138c97d`, `34e34b9` |
| **7** | Sécurité | ⏳ |

## Fichiers concernés

| Fichier | Rôle |
|---|---|
| `backend/infrastructure/mcp/server.py` | MCP server — native tool calling (Phase 2) + sessions/cancel (Phase 3, D6) ✅ |
| `backend/infrastructure/llm/hermes.py` | HermesBackend (chemin inverse, daemon fallback) |
| `backend/infrastructure/llm/hermes_acp.py` | HermesACPBackend — transport ACP direct stdio (Phase 4, D5) ✅ |
| `backend/infrastructure/llm/opendesign.py` | Client SSE Open Design |
| `backend/transport/routers/hermes.py` | Router HTTP `/api/hermes/*` — sessions/cancel (Phase 3, D6) ✅ |
| `backend/infrastructure/llm/factory.py` | Enregistrement `hermes_acp` backend (Phase 4) ✅ |
| `backend/domain/settings.py` | `hermes_url`, `hermes_acp_command`, `backends["hermes"]`, `hermes_llm_*` (D3) |
| `backend/transport/routers/health.py` | `/health/deep` — sonde Hermes (D4) ✅ |
| `frontend/components/settings/HermesSettings.tsx` | Carte Settings UI Hermes (D3) ✅ |
| `frontend/components/settings/hooks/useHermesSettings.ts` | Hook carte Hermes (D3) ✅ |
| `frontend/lib/events.ts` | EventEmitter — consommation tool calls (D2) |
| `frontend/services/MessageHandler.ts` | Parse WS/SSE — tool calls Hermes (D2) |
| `frontend/components/HermesView.tsx` | Chat Hermes — session_id, cancel, New conversation (Phase 3, D6) ✅ |