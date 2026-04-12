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

| Code | Meaning |
|------|---------|
| 400 | Invalid input |
| 401 | Unauthorized (missing API key) |
| 422 | Validation error |
| 500 | Internal server error |
| 504 | Timeout |

---

## Headers de response

L'API ajoute des headers pour le debugging:

```
x-request-id: req-1234567890      # Request ID unique
x-duration-ms: 1234.56          # Durée en ms
```
