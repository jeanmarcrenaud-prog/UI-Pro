# API Documentation

## Base URL
```
http://localhost:8000
```

## Endpoints

### 1. Chat

#### POST /api/chat

Send a chat message to the agent orchestrator.

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

Check API health status.

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

Get current model configuration. Requires API key.

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

### 4. WebSocket

#### WS /ws

Real-time streaming WebSocket endpoint.

**Client sends:**
```json
{"message": "Create a file"}
```

**Server sends (streaming):**
```
[STEP]planning:Planning the task
[TOOL]write_file:Writing hello.py
Hello World!
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
