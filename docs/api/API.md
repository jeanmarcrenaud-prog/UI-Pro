# API Documentation

> UI-Pro REST API et WebSocket endpoints.

## Base URL
```
http://localhost:8000
```

## Endpoints

---

### 1. Chat (REST)

#### POST /api/chat

Envoyer un message à l'agent orchestrator.

**Request:**
```json
{
  "message": "Create a hello world Python script"
}
```

**Response (200):**
```json
{
  "result": "Created hello.py with print('Hello World')",
  "status": "success",
  "error": null
}
```

**Response (500):**
```json
{
  "result": "Error: ...",
  "status": "error",
  "error": "LLM timeout"
}
```

---

### 2. Health

#### GET /health

Vérifier le statut de santé de l'API.

**Response (200):**
```json
{
  "status": "healthy",
  "timestamp": 1234567890.123,
  "version": "1.0.0",
  "services": {
    "api": "ok",
    "llm": "ok"
  },
  "system": {
    "cpu_percent": 45.2,
    "memory_percent": 62.1
  }
}
```

---

### 3. Status

#### GET /status

Obtenir la configuration des modèles. Requiert API key.

**Headers:**
```
x-api-key: <your-api-key>
```

**Response (200):**
```json
{
  "model_fast": "qwen3.5:9b",
  "model_reasoning": "qwen3.5:9b",
  "ollama_url": "http://localhost:11434"
}
```

---

### 4. WebSocket Streaming

#### WS /ws

Streaming temps réel avec events.

**Client → Server:**
```json
{"message": "Create a hello world file"}
```

**Server → Client (streaming events):**

```
[STEP]analyzing:Analyzing the task
[STEP]planning:Planning the implementation
[TOOL]write_file:Writing hello.py
[TOKEN]print("Hello World")
[TOKEN]print("Hello World!")
[DONE]
```

#### Format des Events WebSocket

| Event | Format | Description |
|-------|--------|------------|
| `[STEP]<step>:<message>` | Step agent | Étape en cours |
| `[TOOL]<tool_name>:<message>` | Tool call | Outil appelé |
| `[TOKEN]<text>` | Token | Token LLM streamé |
| `[ERROR]<code>:<message>` | Error | Erreur |
| `[DONE]` | Completion | Fin du stream |

#### Exemples d'Events

```python
# Step events
"[STEP]analyzing:Analyzing requirements..."
"[STEP]planning:Creating file structure..."

# Tool events
"[TOOL]write_file:Creating hello.py"
"[TOOL]run_code:Executing hello.py"

# Token stream
"[TOKEN]p" -> "[TOKEN]pr" -> "[TOKEN]pri" -> "[TOKEN]print"
```

---

### 5. Tool Calls

#### Format d'un tool call

Les tool calls sont encapsulés dans les réponses LLM:

```json
{
  "message": "I'll create that file for you.",
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "write_file",
        "arguments": "{\"filename\": \"hello.py\", \"content\": \"print('Hello World')\"}"
      }
    }
  ]
}
```

#### Tools disponibles

| Tool | Arguments | Description |
|------|-----------|-------------|
| `write_file` | `filename`, `content` | Écrire un fichier |
| `read_file` | `filename` | Lire un fichier |
| `run_code` | `filename`, `args?` | Exécuter du code |
| `list_files` | `path?` | Lister fichiers |

#### Exemple tool call complet

```python
# Request
{
  "message": "Create a test file and run it"
}

# LLM response with tool call
{
  "message": "I'll create test.py and run it.",
  "tool_calls": [
    {
      "id": "call_1",
      "type": "function", 
      "function": {
        "name": "write_file",
        "arguments": "{\"filename\": \"test.py\", \"content\": \"print('test')\"}"
      }
    },
    {
      "id": "call_2", 
      "type": "function",
      "function": {
        "name": "run_code",
        "arguments": "{\"filename\": \"test.py\"}"
      }
    }
  ]
}

# Tool results (returned as tokens)
[TOOL]write_file:test.py created
[TOOL]ran test.py: test
[DONE]
```

---

## Error Codes

| Code | Meaning | Détail |
|------|---------|--------|
| 400 | Invalid input | Payload malformé ou champ manquant |
| 401 | Unauthorized (missing API key) | Header `x-api-key` absent ou invalide |
| 422 | Validation error | Échec de validation Pydantic |
| 500 | Internal server error | Exception non gérée côté backend |
| 504 | Timeout | Voir [504 — LLM Timeout](#504--llm-timeout) ci-dessous |

---

### 504 — LLM Timeout

Le backend LLM (Ollama / Lemonade / LM Studio / llama.cpp) n'a pas répondu
avant la fin du `LLM_TIMEOUT` configuré. Cette erreur est le plus souvent
levée par:

- `analyzing_node` (étape 1 du pipeline) — classification de la tâche
- `planning_node` (étape 2) — génération du plan d'implémentation
- Tout autre appel LLM (review, code, self-correction, executing)

**Trace type** (extrait de `run_error.log`):

```
ERROR - backend.domain.core.langgraph.llm_wrapper - LLM call timed out after 30.0s (model_type=reasoning)
ERROR - backend.infrastructure.llm.ollama - Ollama async stream failed:
       HTTPConnectionPool(host='localhost', port=11434): Read timed out. (read timeout=30)
Traceback (most recent call last):
  ...
  File ".../backend/domain/core/langgraph/nodes.py", line 86, in analyzing_node
    full_response = await llm.run_node(prompt, model_type="reasoning")
  File ".../backend/domain/core/langgraph/llm_wrapper.py", line 121, in run_node
    raise TimeoutError(msg) from None
TimeoutError: LLM call timed out after 30.0s (model_type=reasoning)
```

**Cause racine — deux timeouts imbriqués**:

| Couche | Paramètre | Localisation | Défaut |
|--------|-----------|--------------|--------|
| Outer (wrapper LLM) | `LLM_TIMEOUT` | `backend/domain/settings.py` | **900s** (15 min) |
| Inner (backend HTTP) | `read_timeout` | `backends_template[*].timeout` | **900s** (15 min) |

Si `read_timeout < LLM_TIMEOUT`, le backend HTTP coupe la requête **avant**
que le wrapper LLM ne la complète. Ollama log alors
`Ollama async stream failed: Read timed out.` et le pipeline échoue.
Les deux valeurs doivent rester alignées — d'où le bump coordonné.

**Payload réel** (réponse REST `/api/chat`):

```json
{
  "result": "Error: LLM call timed out after 30.0s (model_type=reasoning)",
  "status": "error",
  "error": "LLM call timed out after 30.0s (model_type=reasoning)"
}
```

Côté WebSocket `/ws`, le stream se termine par:

```
[ERROR]timeout:LLM call timed out after 30.0s (model_type=reasoning)
```

suivi de la fermeture du socket (statut 1006 côté client).

**Mitigation**:

1. **Via l'UI Settings** (recommandé, sans redémarrage):
   `Settings → Timeouts → LLM timeout` puis Save → `POST /api/settings/timeouts`
   est appelé. Le `.env` est mis à jour atomiquement.
2. **Via `.env`** (redémarrage requis):
   ```env
   LLM_TIMEOUT=900
   ```
3. **Aligner `read_timeout` backend** sur `LLM_TIMEOUT` — voir
   `backend/domain/settings.py:208-238`. Si vous modifiez l'un, modifiez l'autre.
4. **Preset `heavy`** pour les modèles 14B+ (`qwen3.6:latest`):
   `Settings → Model Preset → heavy` puis augmentez `LLM_TIMEOUT=1800` (max).
5. **GPU partagé / réseau lent** entre Ollama et UI-Pro:
   envisager `LLM_TIMEOUT=1800` ET `read_timeout=1800`.

**Comportement du checkpoint**: les tokens émis avant le timeout sont
sauvegardés dans SQLite (`[checkpoint] Saved for stream <id>: N tokens`).
Une reprise de session via `thread_id` peut continuer depuis ce point
— mais la requête qui a timeout doit être relancée manuellement.

Voir aussi: `README.md` → "Troubleshooting → LLM_TIMEOUT" pour le guide
pas-à-pas et `docs/architecture/AGENTS.md` → "Critical Quirks" pour le
résumé rapide.

---

## Headers de response

L'API ajoute des headers pour le debugging:

```
x-request-id: req-1234567890      # Request ID unique
x-duration-ms: 1234.56          # Durée en ms
```
