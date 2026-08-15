# 🔍 Investigation — Human-in-the-Loop (HITL) Approval Flow

> **Date**: 2026-08-15 · **HEAD vérifié**: `7ff6a63` · **Statut**: ✅ Vérifié contre le code actuel

## Question d'investigation

> **Est-ce que la Phase 1 du streaming s'arrête réellement avant `execute` pour demander une approbation humaine ?**

## Verdict

**NON — le flux est actuellement en AUTO-APPROVE.** Le graphe LangGraph exécute
`analyze → plan → code → review → execute` de bout en bout, sans interruption
et sans gate d'approbation. Le commit `e959b53` a explicitement retiré
l'interrupt :

```
e959b53 | fix: remove interrupt_before execute to auto-approve execution
```

## Preuves (code actuel, HEAD `7ff6a63`)

### 1. Le graphe n'a pas d'interrupt et va directement de review → execute

`backend/domain/core/langgraph/__init__.py` :

```python
workflow.add_edge("review", "execute")          # arête DIRECTE (l.111)
app = workflow.compile(checkpointer=checkpointer)  # PAS d'interrupt_before (l.126)
```

Nœuds construits (vérifié à l'exécution) :

```
['__start__', 'analyze', '__error_handler__plan', 'plan', '__error_handler__code',
 'code', '__error_handler__review', 'review', 'execute', '__error_handler__fixing',
 'fixing', 'error_node', '__end__']
```

→ **Aucun nœud d'approbation, aucun interrupt.**

### 2. `executing_node` exécute sans gate sur `approval_status`

`backend/domain/core/langgraph/nodes/__init__.py` (l.491) :

- `_step_start` → `CodeExecutionService` → `asyncio.wait_for(..., timeout=settings.executor_timeout)`
- Timeout/erreur → `error_fatal=False` + `execution_result={"success": False, ...}`
- Aucune lecture de `approval_status` / `approval_requested_at` avant d'exécuter.

### 3. `stream_agent` émet `AWAITING_APPROVAL` par heuristique, pas par interrupt

`backend/domain/core/langgraph/streaming.py` (l.375-384) :

```python
# If execution_result was NOT emitted, the graph was interrupted
# before "execute" — yield AWAITING_APPROVAL instead of completed.
if "execution_result" not in _state_emitted:
    await _update_approval_timestamp(app, session_id)
    yield f"[AWAITING_APPROVAL]stream_id:{stream_id}"
else:
    yield "[STEP]completed:Task completed successfully"
```

→ Le signal d'approbation est **déduit de l'absence de `execution_result`**
dans les events streamés. Comme le graphe exécute réellement, `execution_result`
est présent → `AWAITING_APPROVAL` n'est **jamais émis** dans le flux normal.

### 4. Les champs d'approbation existent dans le state mais ne bloquent rien

`backend/domain/core/langgraph/state.py` (l.181-185) :

```python
approval_status: Literal["PENDING", "APPROVED", "REJECTED", None]
approval_reason: str | None
approval_requested_at: str | None  # ISO-8601, pour le timeout
```

→ Déclarés, mais **aucun nœud ne les consomme** pour gater l'exécution.

### 5. Le timeout d'approbation est câblé mais inatteignable

`backend/domain/settings.py` (l.196) : `approval_timeout_minutes: int = Field(default=10, ge=1, le=60)`.
`streaming.py` : `_check_approval_timeout()` (l.126) + `_update_approval_timestamp()` (l.114).
→ Ne se déclenchent que si un `AWAITING_APPROVAL` a été émis (donc jamais en flux normal).

### 6. Le frontend est prêt mais ne reçoit jamais le signal

- `frontend/services/MessageHandler.ts` (l.80) : gère `type === 'awaiting_approval'`
- `frontend/components/agent/CustomNode.tsx` (l.135) : boutons Execute/Correct/Cancel
- `frontend/components/agent/AgentCanvas.tsx` (l.61) : bridge `AWAITING_APPROVAL` → MessageHandler
- `backend/transport/routers/ws.py` (l.105-125) : accepte `execute_decision` (execute/correct/cancel)

→ Toute la chaîne UI existe, mais le backend ne produit plus le signal.

## Incohérences détectées

| # | Incohérence | Localisation |
|---|---|---|
| 1 | Docstring de `stream_agent` dit « interrupt BEFORE execute » alors que le code auto-approuve | `streaming.py` l.163-178 |
| 2 | Log « Phase 1 — interrupt before execute » obsolète | `streaming.py` l.232 |
| 3 | `AWAITING_APPROVAL` + `_handle_decision` + `_resume_execution/_resume_correct` = code mort en flux normal | `streaming.py` l.375-384, 408-678 |
| 4 | `approval_status`/`approval_reason`/`approval_requested_at` jamais lus par un nœud | `state.py` l.181-185 |
| 5 | `approval_timeout_minutes` + `_check_approval_timeout` inatteignables | `settings.py` l.196, `streaming.py` l.126 |

## Historique des commits (streaming.py)

| Commit | Date | Message |
|---|---|---|
| `76b5416` | 2026-07-08 | feat(stability): add approval timeout for human-in-the-loop |
| `e0ae640` | 2026-06-21 | fix: update streaming handler for fix loop code extraction |
| `08ad2e9` | 2026-06-15 | fix(stream): re-emit code events in fix loop using content hash dedup |
| `e959b53` | 2026-06-15 | fix: remove interrupt_before execute to auto-approve execution |
| `e909db3` | 2026-06-13 | feat(state): add approval_status/approval_reason and merge_steps reducer |
| `c4c8a56` | 2026-06-13 | feat(debug): add State tab with step/error history, pipeline metrics |
| `94fa5f8` | 2026-06-11 | fix: respect user-requested language instead of forcing python |
| `4dc03c7` | 2026-06-11 | feat(exec-output): integrate node timing decorator and streaming refactor |

## Vérifications exécutées

- ✅ Import `streaming.py` : OK
- ✅ `build_graph()` : OK — 13 nœuds, pas d'interrupt
- ✅ Tests : `test_streaming_infra.py` + `test_streaming_verification.py` + `test_pipeline_nodes.py` → **117 passed**

## Recommandations

1. **Décider du comportement voulu** : auto-approve (état actuel) ou vrai HITL (interrupt).
2. Si **auto-approve** (recommandé pour l'autonomie) :
   - Mettre à jour le docstring de `stream_agent` (l.163-178) et le log l.232.
   - Supprimer ou désactiver le bloc `AWAITING_APPROVAL` (l.375-384) et les helpers Phase 2 morts.
   - Retirer `approval_status`/`approval_requested_at` du state ou les documenter comme réservés.
3. Si **vrai HITL** :
   - Réintroduire `interrupt_before=["execute"]` dans `compile()`.
   - Gater `executing_node` sur `approval_status == "APPROVED"`.
   - Le bloc `AWAITING_APPROVAL` redevient alors le chemin principal (pas du code mort).