# Sisyphus — Anchored Summary

## Session 1: Human-in-the-loop execution approval (✅ done)
## Session 2: Cleanup legacy shims + Prometheus/Grafana monitoring (✅ done)

## Constraints & Preferences
- French user communication
- `Co-authored-by: Sisyphus <clio-agent@sisyphuslabs.ai>` commit trailer
- Conventional commits ENGLISH + SEMANTIC style (`type(scope): subject`) — NO EXCEPTIONS
- Atomic commits: 3+ files = 2+ commits, 10+ files = 5+ commits (NO EXCEPTIONS)
- `GIT_MASTER=1` env var for all git commands
- PowerShell: `$env:VAR='val'` per line, not inline
- Use `git commit -F file.txt` (inline `-m` with backslashes breaks)
- Type safety: no `as any`, no `try/except: pass`
- Python 3.12 strict escape handling: use `r"""..."""`
- "si j'ai un message d'erreur, tu t'arrêtes et tu me demandes quoi faire"

## Progress (Done — Session 1: Execution Approval)
- **Fix A (short-circuit)**: reviewing_node no-code short-circuit + should_continue Priority 0
- **Per-Node Routing default False** (`settings.py:190`)
- **Human-in-the-loop execution approval**:
  - Backend: state.py (approval fields), parser.py ([AWAITING_APPROVAL] prefix), streaming.py (Phase 1 interrupt_before, Phase 2 execute/correct/cancel), streamer.py (decision passthrough, WS kept alive), ws.py (execute_decision handler)
  - Frontend: events.ts (type), types.ts (callback), MessageHandler.ts (onApproval), chatService.ts (sendExecuteDecision), ExecutionApproval.tsx (UI), ChatInterface.tsx (wired)
  - Tests: test_interrupt.py, test_approval_unit.py

## Progress (Done — Session 2: Cleanup + Monitoring)
- **Cleanup legacy shims** (5 commits pushed):
  - Migrated 20+ imports: `from settings`/`from models.settings` → `from backend.domain.settings`
  - Deleted: `settings.py` (root), `models/`, `config/`, `adapters/` (root)
  - Updated `verify_imports.py` + `check_cleanup.py`
  - 40/40 tests pass, imports verified clean
- **Prometheus + Grafana monitoring** (5 commits pushed):
  - `chore(deps): add prometheus-client dependency`
  - `feat(monitoring): add system metrics module with Prometheus gauges`
  - `feat(monitoring): add LLM metrics instrumentation`
  - `feat(monitoring): expose /metrics endpoint and instrument LLMWrapper`
  - `docs(monitoring): add Grafana dashboard and monitoring README`
  - 6 Prometheus gauges (GPU, VRAM, temp, CPU, RAM), 4 LLM metric types, importable Grafana dashboard (11 panels)

## Progress (Done — Session 3: Canvas Refactor + Bugs + Setup)
- **Canvas refactor**: extracted `CustomNode` and `nodeStyles` from monolith `GraphVisualization.tsx` → `CustomNode.tsx` + `nodeStyles.ts`
- **Stale event fix**: generalized detection in `handleAgentStep` — intercept ALL steps, not just `lastActiveStepRef` matches (`useMessageHandler.ts`)
- **Pygments dependency**: added `Pygments>=2.18.0` to `requirements.txt` (missing dep for `multi_lang_executor.py`)
- **`setup.py` overhaul** (uncommitted):
  - Added `check_git()` function
  - Improved `check_node()` with version parsing, enforces Node.js >= 18.17
  - Improved `setup_frontend()`: prefers `npm ci` over `npm install` when lockfile exists, detects `package.json` changes, prints subprocess output
  - Added orphan root `package-lock.json` cleanup in `main()`
  - Fixed duplicate function definition bug (leftover from partial edit)

## Key Decisions
- **`interrupt_before=["execute"]`** at `astream()` runtime (not compile time) — avoids graph rebuild
- **Phase 2 "execute"** → `app.astream(None, ...)` to resume checkpoint
- **WS kept alive** after Phase 1 — `WebSocketTransport.close()` removed
- **Import chain removal**: Root `settings.py` → `models/settings` → `backend.domain.settings` was 3-deep shim. Removed both upper layers.
- **Prometheus metrics lazy-init**: registry created on first import, graceful fallback when `prometheus_client` not installed.
- **GPU metrics dual path**: `update_system_metrics()` feeds Prometheus gauges AND existing `/health/deep` JSON endpoint.
- **LLM instrumentation at wrapper level**: `llm_wrapper.py` records latency/tokens/errors — covers both `generate()` and `stream_generate()`.
- **`npm ci` over `npm install`**: deterministic install when `package-lock.json` exists — prevents version drift
- **Stale event detection generalized**: match ANY agent step event (not just step matching `lastActiveStepRef`) to catch late-arriving stale steps
- **Orphan lockfile cleanup**: root `package-lock.json` exists without a root `package.json` — likely artifact, cleaned up automatically in `setup.py`

## Remaining Recommendations (from original user list)
1. ❌ Clean legacy dirs — **DONE**
2. ❌ Monitoring (Prometheus + Grafana) — **DONE**
3. ⏳ `backend/transport/` → `frontend/api/` renaming?
4. ⏳ E2E tests with Playwright
5. ⏳ Rate limiting + prompt injection protection

## Key Files (Session 2 — Monitoring)
- `backend/infrastructure/monitoring/prometheus.py` — 6 Prometheus gauges, lazy registry
- `backend/infrastructure/monitoring/llm_metrics.py` — 4 metric types (histogram, counter x2, gauge)
- `backend/infrastructure/monitoring/__init__.py` — public API exports
- `backend/transport/routers/health.py` — added `GET /metrics` endpoint
- `backend/domain/core/langgraph/llm_wrapper.py` — instrumented generate/stream_generate/run_node
- `docs/monitoring/grafana-dashboard.json` — 11-panel Grafana dashboard (UID: `ui-pro-system-llm`)
- `docs/monitoring/README.md` — metrics reference + Prometheus scrape config

## Key Files (Session 3 — Refactor + Bugs + Setup)
- `frontend/components/agent/CustomNode.tsx` — extracted CustomNode component
- `frontend/components/agent/nodeStyles.ts` — extracted node style definitions
- `frontend/components/canvas/GraphVisualization.tsx` — reduced after extraction
- `frontend/hooks/useMessageHandler.ts` — stale event detection fix
- `setup.py` — enhanced setup with git check, Node.js version gate, npm ci, orphan cleanup
- `requirements.txt` — added Pygments dependency

## Additional Context
- **20 commits total** across 3 sessions (7 approval flow + 10 cleanup+monitoring + 3 bugs+setup)
- **Working tree**: `setup.py` changes uncommitted (ready for review)
- **Pre-existing LSP errors**: `health.py:73-75` (pynvml type op), `fallback.py:85-179` (str|None), `views_api.py:354,446` (langgraph attr, CodeExecutor)
- **Test suite**: 62/63 pass (1 pre-existing: lmstudio not running in local env)
