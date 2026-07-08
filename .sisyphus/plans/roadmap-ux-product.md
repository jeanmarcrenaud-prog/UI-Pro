# Roadmap UX & Product — Priorité Haute + Moyenne (3-16 semaines)

> Plan généré le 2026-07-07. Contexte: ui-pro v1.0.0, Next.js 16, FastAPI, LangGraph, React Flow.

---

## 1. Graph Visualization — Zoom/Pan + Collapsible Nodes + Export

### État actuel
- React Flow (`@xyflow/react`) avec layout horizontal fixe (`STEP_POSITIONS`)
- `Controls` intégré (zoom boutons) en bas à droite
- Export PNG via `html-to-image` + JSON via CanvasControls
- `nodesDraggable=false`, `nodesConnectable=false` — graphe statique

### Objectif
Zoom/pan fluide style Figma, nodes collapsibles, export image amélioré.

### Implémentation

**Fichiers:** `frontend/components/canvas/GraphVisualization.tsx`, `frontend/components/agent/CustomNode.tsx`, `frontend/components/agent/CanvasControls.tsx`

#### Step 1 — Améliorer Controls (jour 1)
- Remplacer le `Controls` basique React Flow par un panneau custom avec:
  - Zoom +/- avec slider
  - Bouton "Fit view" (réinitialiser)
  - Bouton "Center" (centrer sur node actif)
  - Mini-map toggle
- Utiliser `useReactFlow()` pour `zoomIn()`, `zoomOut()`, `fitView()`, `getViewport()`

#### Step 2 — Collapsible nodes (jour 1-2)
- Ajouter état `isCollapsed` dans `CustomNode`
- Node affiche titre + status, clique sur header → expand/collapse
- Content collapsible avec animation Framer Motion
- Stocker état dans `agentCanvasStore` (`collapsedNodes: Set<string>`)

#### Step 3 — Export image amélioré (jour 2)
- Export PNG avec fond sombre (actuellement transparent)
- Export SVG en plus de PNG
- Bouton "Copy to clipboard" pour le graphe
- Utiliser `toPng()` de `html-to-image` avec `backgroundColor`

#### Step 4 — Smooth pan/zoom (jour 2)
- Activer `panOnScroll`, `zoomOnScroll`, `zoomOnDoubleClick`
- Configurer `minZoom=0.1`, `maxZoom=2.0`
- Ajouter `wheel` event handler pour smooth zoom

**Effort:** ~2 jours | **Risque:** Faible

---

## 2. Streaming — TPS + ETA

### État actuel
- `StreamingTokenGraph.tsx` affiche: bar graph TPS + `{currentTps} t/s` + `{tokenCount} tok`
- Mise à jour toutes les 500ms

### Objectif
Ajouter estimation temps restant (ETA) basée sur token/s moyen.

### Implémentation

**Fichier:** `frontend/components/chat/StreamingTokenGraph.tsx`

- Tracker `totalTokensExpected` (si disponible du backend) ou calculer à partir de `tokenCount` + vitesse moyenne
- Afficher: `~{estimatedSeconds}s restant` ou `~{estimatedMinutes}min`
- Formule: `remainingTokens / avgTPS = eta`
- Afficher un badge "ETA" discret à côté du compteur TPS
- Si streaming terminé, afficher "Terminé en Xs" au lieu de l'ETA

**Effort:** ~0.5 jour | **Risque:** Faible

---

## 3. Theme — Dark/Light + Thème "Pro" (Cursor/Windsurf)

### État actuel
- 3 thèmes: `dark`, `light`, `purple-rain`
- CSS variables dans `globals.css` lignes 7-60
- `ThemeProvider` set `document.documentElement.className = theme`
- `uiStore.theme` avec persist

### Objectif
Ajouter un thème "Pro" inspiré Cursor/Windsurf (fond très sombre, accents cyan/violet, typographie moderne).

### Implémentation

**Fichier:** `frontend/app/globals.css`

#### Step 1 — Créer le thème "pro" (jour 1)
```css
.pro {
  --bg-primary: #0a0a0f;
  --bg-secondary: #111118;
  --bg-tertiary: rgba(10, 10, 15, 0.92);
  --surface-primary: #111118;
  --surface-secondary: #1a1a24;
  --surface-elevated: #22222e;
  --border-subtle: #2a2a3a;
  --border-default: #3a3a4a;
  --text-primary: #e8e8f0;
  --text-secondary: #a0a0b8;
  --text-muted: #606070;
  --accent: #00d4ff;        /* Cyan cyan */
  --accent-hover: #00b8e6;
  --accent-soft: #00d4ff22;
  --glass-bg: rgba(17, 17, 24, 0.8);
  --glass-border: rgba(58, 58, 74, 0.6);
}
```

#### Step 2 — Ajouter au theme switcher (jour 1)
- `uiStore.theme` → type étendu à `'dark' | 'light' | 'purple-rain' | 'pro'`
- Settings UI: ajouter "Pro" comme 4ème option
- Icône: palette ou gradient

**Effort:** ~1 jour | **Risque:** Faible

---

## 4. Historique — Fork de Session

### État actuel
- `HistoryView` avec search, filters, sort, tags, archive, pin, rename, export, multi-select
- `ChatHistoryItem` a `tags?: string[]`
- `loadChat(id)` recharge les messages
- Pas de fork

### Objectif
Permettre de "fork" une session — créer une copie indépendante avec nouveau ID.

### Implémentation

**Fichier:** `frontend/lib/stores/chatStore.ts`

#### Step 1 — Ajouter `forkChat` (jour 1)
```typescript
forkChat: (id: string) => {
  const chat = get().history.find(c => c.id === id)
  if (!chat) return
  const forked: ChatHistoryItem = {
    ...chat,
    id: `chat-${Date.now()}`,
    title: `${chat.title} (fork)`,
    messages: [...chat.messages],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    isPinned: false,
    archived: false,
  }
  set({ history: [forked, ...get().history] })
}
```

#### Step 2 — Bouton Fork dans HistoryItem (jour 1)
- Icône "GitFork" de lucide-react
- Dans `HistoryItem.tsx`: ajouter `onFork` prop + bouton
- Dans `HistoryView.tsx`: passer `onFork={forkChat}`

**Effort:** ~1 jour | **Risque:** Faible

---

## 5. Preview Mode — HTML/JS/CSS avant exécution

### État actuel
- Aucun preview
- ExecutionApproval affiche juste le code en texte (pre block)

### Objectif
Preview iframe sandbox pour HTML/JS/CSS — montrer le rendu avant exécution.

### Architecture

**Nouveau fichier:** `frontend/components/chat/CodePreview.tsx`

#### Step 1 — Détecter HTML/JS/CSS (jour 1)
- Dans `ExecutionApproval.tsx`:检测 fichiers avec extensions `.html`, `.js`, `.css`
- Si un fichier `.html` présent, afficher bouton "Preview"

#### Step 2 — Iframe sandbox (jour 1-2)
- Créer `<iframe sandbox="allow-scripts">` avec srcdoc
- Pour HTML seul: utiliser directement
- Pour HTML + JS + CSS: combiner en srcdoc complet
- Styles injectés dans `<style>`, JS dans `<script>`
- Limiter à 5s d'exécution (timeout)

#### Step 3 — Intégration ExecutionApproval (jour 2)
- Bouton "Preview" à côté de "Execute"
- Toggle pour basculer entre code view et preview
- Preview panel en dessous du code preview

**Sécurité:** `sandbox="allow-scripts"` (pas allow-same-origin, pas allow-forms)

**Effort:** ~2 jours | **Risque:** Moyen (isolation iframe)

---

## 6. Reviewer — Scoring Pondéré

### État actuel
- `CodeReviewer` dans `backend/domain/core/code_review.py`
- Bandit (sécurité) + Pylint (style)
- `fail_on = {"high", "medium"}` — tout aussi important

### Objectif
Scoring avec poids: sécurité (×3) > performance (×2) > lisibilité (×1).

### Implémentation

**Fichier:** `backend/domain/core/code_review.py`

#### Step 1 — Définir les poids (jour 1)
```python
SEVERITY_WEIGHTS = {
    "security": 3.0,   # Bandit: HIGH = security issue
    "performance": 2.0, # Pylint: convention/perf
    "readability": 1.0, # Pylint: refactor
}
```

#### Step 2 — Calculer score pondéré (jour 1)
```python
def calculate_weighted_score(self, issues: list[dict]) -> float:
    """Score 0-100, 100 = parfait"""
    if not issues:
        return 100.0
    total_weight = 0.0
    max_weight = 0.0
    for issue in issues:
        severity = issue.get("severity", "").lower()
        if "high" in severity or "security" in severity:
            w = SEVERITY_WEIGHTS["security"]
        elif "medium" in severity:
            w = SEVERITY_WEIGHTS["performance"]
        else:
            w = SEVERITY_WEIGHTS["readability"]
        total_weight += w
        max_weight += w * 5  # max 5 par issue
    return max(0, 100 - (total_weight / max_weight * 100))
```

#### Step 3 — Exposer le score (jour 1)
- Ajouter `weighted_score: float` à `ReviewResult`
- Dans `reviewing_node`: afficher le score avec couleur (vert >80, jaune 50-80, rouge <50)

**Effort:** ~1 jour | **Risque:** Faible

---

## 7. Templates — Système de Templates

### État actuel
- Aucun système de templates
- ChatContainer a des `DEFAULT_EXAMPLES` (prompts pré-remplis)

### Objectif
Permettre à l'utilisateur de choisir un template (Next.js app, FastAPI, Tauri, etc.) qui pré-configure le projet.

### Architecture

**Nouveau fichier:** `backend/domain/core/templates.py`
**Nouveau fichier:** `frontend/components/chat/TemplateSelector.tsx`

#### Step 1 — Définir les templates (jour 1)
```python
TEMPLATES = {
    "nextjs-app": {
        "name": "Next.js App Router",
        "description": "Full-stack Next.js 16 app with App Router",
        "files": {
            "package.json": "{...}",
            "app/page.tsx": "...",
            "app/layout.tsx": "...",
        },
        "prompt_suffix": "Create a Next.js App Router project with TypeScript.",
    },
    "fastapi": {
        "name": "FastAPI CRUD",
        "description": "FastAPI with Pydantic v2 and SQLite",
        "files": {...},
        "prompt_suffix": "Create a FastAPI application with CRUD endpoints.",
    },
    "tauri": {
        "name": "Tauri App",
        "description": "Rust + React Tauri desktop app",
        "files": {...},
        "prompt_suffix": "Create a Tauri desktop application.",
    },
}
```

#### Step 2 — Template Selector UI (jour 1-2)
- Modal/drawer avec grille de templates
- Chaque template: icône, nom, description, bouton "Use"
- Sélectionner → pré-remplit le prompt avec `prompt_suffix`
- Optionnel: pré-générer les fichiers du template en background

#### Step 3 — Intégration backend (jour 2)
- `POST /api/templates` → liste des templates
- `POST /api/templates/{id}/apply` → génère les fichiers dans workspace

**Effort:** ~3 jours | **Risque:** Moyen (prompts de génération complexes)

---

## 8. Memory — Graph Memory (Entités/Projets)

### État actuel
- `MemoryManager` dans `backend/infrastructure/memory.py`
- FAISS vector store (all-MiniLM-L6-v2, 384 dim)
- Pas de graph — juste recherche par similarité

### Objectif
Ajouter graph memory: entités (projets, fichiers, concepts) avec relations.

### Architecture

**Nouveau fichier:** `backend/infrastructure/graph_memory.py`

#### Step 1 — Entités et Relations (jour 1)
```python
@dataclass
class Entity:
    id: str
    type: str  # "project" | "file" | "concept" | "user"
    name: str
    description: str
    metadata: dict
    created_at: datetime

@dataclass
class Relation:
    source_id: str
    target_id: str
    relation_type: str  # "depends_on" | "implements" | "related_to"
    strength: float  # 0-1
```

#### Step 2 — Graph store (jour 1-2)
- Utiliser `networkx` pour le graph en mémoire
- Persister en JSON (`data/graph_memory.json`)
- Intégrer avec FAISS: quand un document est indexé, extraire les entités et créer des liens

#### Step 3 — Query graph (jour 2)
- `get_related_entities(entity_id)` → entités connectées
- `get_project_context(project_id)` → tous les fichiers + concepts liés
- Passer le context au LLM dans `planning_node`

**Effort:** ~3 jours | **Risque:** Élevé (design de graphe complexe)

---

## 9. Multi-Files — Édition Contextuelle

### État actuel
- `coding_node` génère des fichiers dans `CodeData.files` dict
- Pas de support pour éditer des fichiers existants dans le workspace

### Objectif
L'agent peut modifier plusieurs fichiers existants en plus d'en créer.

### Architecture

**Fichiers:** `backend/domain/core/langgraph/nodes.py` (coding_node)

#### Step 1 — Lire fichiers existants (jour 1)
- Ajouter un outil `ReadFile` que l'agent peut appeler
- Passer le contenu des fichiers du workspace dans le context LLM

#### Step 2 — Modifier plusieurs fichiers (jour 1-2)
-允許 agent 输出 `FileEdit` au lieu de `FileCreate`
- `FileEdit = { path: str, old_content: str, new_content: str, reason: str }`
- Appliquer les edits avec diff matching

#### Step 3 — Conflits et validation (jour 2)
- Si le fichier a changé depuis la lecture, détecter le conflit
- Demander confirmation avant d'appliquer

**Effort:** ~3 jours | **Risque:** Élevé (risque de corruption de fichiers)

---

## 11. Orchestration — LangGraph Persistent + Redis

### État actuel
- Checkpointing via `AsyncSqliteSaver` (fichier `checkpoints.db`)
- Pas de support multi-instance ni de cache distribué
- Reprise après crash uniquement via le fichier SQLite local

### Objectif
Passer à un backend Redis pour le checkpointing LangGraph, permettant scalabilité horizontale, latence réduite, et reprise après crash fiable en environnement distribué.

### Architecture

**Fichiers:** `backend/domain/core/orchestrator_async.py`, `backend/infrastructure/checkpointer.py`, `backend/domain/settings.py`

#### Step 1 — Redis comme checkpointer (jour 1-2)
- Installer `redis` + `langgraph.checkpoint.redis`
- Remplacer `AsyncSqliteSaver` par `AsyncRedisSaver`
- Configurer via `settings.py` (`REDIS_URL`, `REDIS_TLS`)
- Garder SQLite comme fallback si Redis indisponible

#### Step 2 — Connection pooling + retry (jour 2)
- `redis.asyncio.ConnectionPool` avec `max_connections=50`
- Retry avec exponential backoff sur connexion perdue
- Health check endpoint `/health/redis`

#### Step 3 — Migration checkpoints (jour 1)
- Script de migration SQLite → Redis pour les sessions existantes
- Valider que les sessions migrées sont lisibles

**Effort:** ~3 jours | **Risque:** Moyen (migration de données, compatibilité)

---

## 12. Exécution — Multi-Sandbox (Docker + Firecracker micro-VM)

### État actuel
- Exécution dans un seul container Docker (`code_executor.py`)
- Pas de resource quotas (CPU/RAM)
- Isolation limitée à `ulimit` + `seccomp`

### Objectif
Support de plusieurs sandboxes isolés (Docker pool) + Firecracker micro-VM pour isolation forte. Ajouter des resource quotas (CPU, RAM, temps).

### Architecture

**Fichiers:** `backend/infrastructure/executors/docker_executor.py`, `backend/infrastructure/executors/firecracker_executor.py`, `backend/domain/settings.py`

#### Step 1 — Docker pool (jour 2)
- Pool de 3-5 containers pré-startés
- Attribution round-robin par exécution
- Nettoyage automatique après timeout
- `docker run --rm --cpus=1 --memory=512m --pids-limit=100`

#### Step 2 — Resource quotas (jour 1)
- CPU: `--cpus=1` (1 core)
- RAM: `--memory=512m`
- Processes: `--pids-limit=100`
- Temps: timeout configurable (défaut 60s)

#### Step 3 — Firecracker micro-VM (jour 3-4)
- Setup Firecracker binary + kernel + rootfs
- Micro-VM par exécution (isolation noyau)
- 50ms cold-start acceptable
- Fallback vers Docker si Firecracker non disponible

**Effort:** ~5 jours | **Risque:** Élevé (complexité Firecracker, setup infra)

---

## 13. LLM Layer — Tool Calling + Structured Output

### État actuel
- LLM appelé via `llm_wrapper.py` avec prompts textuels
- Parsing de la sortie LLM via regex/heuristiques
- Pas de tool calling natif

### Objectif
Ajouter tool calling natif (si supporté par le modèle) + structured output via Pydantic v2 pour les nodes `planning` et `coding`. Réduire les erreurs de parsing de 15% à <2%.

### Architecture

**Fichiers:** `backend/infrastructure/llm/ollama.py`, `backend/domain/core/langgraph/nodes.py`, `backend/domain/core/planning_schemas.py` (NEW)

#### Step 1 — Structured output Pydantic (jour 1-2)
- Définir `PlanningData`, `CodeData` comme `BaseModel` Pydantic
- Utiliser `model.with_structured_output(PlanningData)` si supporté
- Fallback: parser le JSON de la réponse LLM
- Tester avec qwen3.5:9b et ollama

#### Step 2 — Tool calling (jour 2-3)
- Définir les tools disponibles: `ReadFile`, `WriteFile`, `Bash`, `WebSearch`
- `model.bind_tools(tools)` pour Ollama >= 0.1.41
- Tool selection dans `coding_node` et `planning_node`
- Handle tool call loop (max 3 appels successifs)

#### Step 3 — Validation et fallback (jour 1)
- Si le modèle ne supporte pas tool calling, fallback sur prompts textuels
- Valider le JSON schema avant de passer à l'exécution

**Effort:** ~4 jours | **Risque:** Moyen (tous les modèles ne supportent pas tool calling)

---

## 14. Monitoring — Grafana + OpenTelemetry

### État actuel
- Logs dans `logs/app.log` (fichier texte)
- Pas de métriques structurées
- Pas de tracing distribué

### Objectif
Dashboard Grafana complet (LLM latency, sandbox failures, token usage) + OpenTelemetry tracing pour chaque requête. Alertes sur seuil (latence > 30s, failure rate > 5%).

### Architecture

**Fichiers:** `backend/infrastructure/monitoring/metrics.py` (NEW), `backend/infrastructure/monitoring/tracing.py` (NEW), `docker-compose.yml` (nouveau)

#### Step 1 — OpenTelemetry setup (jour 1-2)
- `pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp`
- Wrappers sur LLM calls, sandbox execution, WebSocket messages
- Trace ID propagé du frontend au backend
- Export vers OTLP endpoint (configurable)

#### Step 2 — Métriques Prometheus (jour 1-2)
- `prometheus_client` pour exposer `/metrics`
- Métriques: `llm_request_duration_seconds`, `llm_tokens_total`, `sandbox_executions_total`, `sandbox_failure_total`
- Labels: model, status, step_name

#### Step 3 — Grafana dashboards (jour 2)
- JSON dashboard pour Grafana (importable)
- Panels: LLM latency P50/P95/P99, TPS moyen, failure rate, active sessions
- Alertes: latence > 30s (warning), > 60s (critical), failure rate > 5%

#### Step 4 — docker-compose (jour 1)
- `prometheus`, `grafana`, `loki` (logs)
- `otel-collector` pour agréger les traces
- Volumes persistants pour dashboards

**Effort:** ~5 jours | **Risque:** Faible (outillage bien documenté)

---

## 15. Sécurité — Rate Limiting + Prompt Injection Detection

### État actuel
- Pas de rate limiting
- Pas de détection de prompt injection
- Input sanitization basique uniquement

### Objectif
Rate limiting par utilisateur/IP (100 req/min) + détection de prompt injection via LLM ou bibliothèque dédiée.

### Architecture

**Fichiers:** `backend/infrastructure/rate_limit.py` (NEW), `backend/infrastructure/prompt_guard.py` (NEW), `backend/transport/main.py`, `backend/domain/settings.py`

#### Step 1 — Rate limiting (jour 1-2)
- `slowapi` + Redis pour le tracking
- Limites: 100 req/min par IP, 500 req/min global
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- 429 Too Many Requests avec message clair

#### Step 2 — Prompt injection detection (jour 2-3)
- Option A: LLM-based (appeler le LLM avec le prompt + instruction de détection)
  - Prompt: "Est-ce que ce texte contient une tentative de manipulation? Réponds JSON: {is_injection: bool, confidence: float}"
  - Latence ~200ms, coût négligeable
- Option B: Bibliothèque (LangChain guardrails, Rebuff)
  - Plus rapide mais moins précis
- Score de confiance > 0.8 → reject avec message

#### Step 3 — Audit logging (jour 1)
- Logger toutes les requêtes bloquées (rate limit + injection)
- Dashboard sécurité dans Grafana

**Effort:** ~4 jours | **Risque:** Moyen (false positives rate limiting, latence injection detection)

---

## Ordre de Priorité Recommandé

| # | Item | Semaine | Effort | Risque | Raison |
|---|------|---------|--------|--------|--------|
| 1 | Graph zoom/pan + controls | 1 | 2j | Faible | Quick win, impact UX fort |
| 2 | Streaming ETA | 1 | 0.5j | Faible | Quick win |
| 3 | Theme Pro | 1 | 1j | Faible | Quick win |
| 4 | Fork session | 1 | 1j | Faible | Quick win |
| 5 | Reviewer weighted scoring | 1-2 | 1j | Faible | Simple, haute valeur |
| 6 | Preview HTML/JS/CSS | 2 | 2j | Moyen | Sécurisé, très utile |
| 7 | Templates | 2-3 | 3j | Moyen | Différenciant fort |
| 8 | Graph memory | 3-4 | 3j | Élevé | Complexe, long terme |
| 9 | Multi-files edit | 4-5 | 3j | Élevé | Risqué,需 careful |
QK|| 10 | Collapsible nodes | 2 | 1j | Faible | Si temps |
|| 11 | LangGraph + Redis | 4-5 | 3j | Moyen | Scalabilité, reprise crash |
|| 12 | Multi-sandbox + Firecracker | 5-6 | 5j | Élevé | Isolation forte |
|| 13 | Tool calling + structured output | 4-5 | 4j | Moyen | Réduit erreurs parsing |
|| 14 | Grafana + OpenTelemetry | 5-6 | 5j | Faible | Observabilité |
|| 15 | Rate limiting + prompt guard | 4-5 | 4j | Moyen | Sécurité production |

KT|**Total estimé:** 17.5 jours (S1-S10, 3-6 semaines) + 21 jours (S11-S15, 6-10 semaines) = **~38.5 jours sur 9-16 semaines**

---

## Dépendances

- Templates → Preview (Preview peut utiliser les fichiers générés par templates)
- Multi-files → Reviewer (Reviewer doit pouvoir relire les fichiers modifiés)
- Graph memory → Templates (context de projet aide à générer de meilleurs fichiers)
- Preview → Fork (Preview après fork de session)

---

## Tests

- Graph: Playwright test — zoom, pan, collapse node, export PNG
- Streaming: Playwright test — ETA s'affiche pendant streaming
- Theme: Playwright test — thème Pro visible dans Settings
- Fork: Playwright test — bouton fork crée nouveau chat
- Preview: Playwright test — iframe renders HTML
- Reviewer: pytest — score pondéré calculé correctement
- Templates: pytest + Playwright — template list + apply
- Memory: pytest — entité créée, relation trouvée
RR|- Multi-files: pytest — edit appliqué, conflit détecté
- LangGraph+Redis: pytest — session migrée, checkpoint lu/écrit sur Redis
- Multi-sandbox: pytest — pool de containers, quotas appliqués
- Tool calling: pytest — structured output parsé correctement
- Monitoring: pytest — métriques exposées sur /metrics
- Rate limiting: pytest — 429 après 100 req/min

---

## Fichiers Modifiés / Créés

### Backend
- `backend/domain/core/code_review.py` — scoring pondéré
- `backend/domain/core/templates.py` (NEW) — template definitions
- `backend/infrastructure/graph_memory.py` (NEW) — graph memory
NS|- `backend/domain/core/langgraph/nodes.py` — multi-file editing tools
- `backend/infrastructure/checkpointer.py` — Redis checkpointer
- `backend/infrastructure/executors/docker_executor.py` — Docker pool + quotas
- `backend/infrastructure/executors/firecracker_executor.py` (NEW) — micro-VM isolation
- `backend/domain/core/planning_schemas.py` (NEW) — Pydantic schemas pour structured output
- `backend/infrastructure/monitoring/metrics.py` (NEW) — Prometheus metrics
- `backend/infrastructure/monitoring/tracing.py` (NEW) — OpenTelemetry setup
- `backend/infrastructure/rate_limit.py` (NEW) — slowapi rate limiting
- `backend/infrastructure/prompt_guard.py` (NEW) — prompt injection detection
- `docker-compose.yml` (NEW) — prometheus, grafana, loki, otel-collector

### Frontend
- `frontend/components/canvas/GraphVisualization.tsx` — zoom/pan amélioré
- `frontend/components/agent/CustomNode.tsx` — collapsible
- `frontend/components/agent/CanvasControls.tsx` — export amélioré
- `frontend/components/chat/StreamingTokenGraph.tsx` — ETA
- `frontend/app/globals.css` — thème Pro
- `frontend/components/chat/CodePreview.tsx` (NEW) — iframe preview
- `frontend/components/chat/TemplateSelector.tsx` (NEW) — template UI
- `frontend/lib/stores/chatStore.ts` — forkChat
- `frontend/e2e/chat.spec.ts` — tests mis à jour

---

## Risques et Mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Preview iframe XSS | Faible | Élevé | sandbox="allow-scripts" only, pas allow-same-origin |
| Multi-files corruption | Moyen | Élevé | Backup avant edit, validation diff |
| Graph memory trop complexe | Moyen | Moyen | Commencer simple (3 types d'entités), itérer |
| Templates prompts质量 | Moyen | Moyen | Tester chaque template manuellement avant release |
BQ|| Templates prompts质量 | Moyen | Moyen | Tester chaque template manuellement avant release |
|| Redis unavailable | Moyen | Élevé | SQLite fallback automatique |
|| Firecracker setup complexe | Moyen | Élevé | Docker comme fallback, documentation détaillée |
|| Tool calling pas supporté | Moyen | Moyen | Fallback prompts textuels |
|| Monitoring overload | Faible | Moyen | Sampling, retention policy |
|| Rate limit false positives | Moyen | Moyen | Whitelist IPs internes, seuils ajustables |