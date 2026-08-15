# 🔍 Investigation — Human-in-the-Loop (HITL) Approval Flow

> **Date**: 2026-08-15 · **HEAD vérifié**: `7ff6a63` · **Statut**: ✅ Vérifié contre le code actuel — code mort supprimé le 2026-08-15

## Question d'investigation

> **Est-ce que la Phase 1 du streaming s'arrête réellement avant `execute` pour demander une approbation humaine ?**

## Verdict

**NON — le flux est en AUTO-APPROVE.** Le graphe LangGraph exécute
`analyze → plan → code → review → execute` de bout en bout, sans interruption
et sans gate d'approbation. Le commit `e959b53` a explicitement retiré
l'interrupt :

```
e959b53 | fix: remove interrupt_before execute to auto-approve execution
```

## Décision (2026-08-15)

**Option A — Suppression complète du code mort Phase 2** (validée par l'utilisateur).
Tout le code lié au flux d'approbation (backend + frontend + tests) a été retiré :

| Élément supprimé | Fichier |
|---|---|
| `_update_approval_timestamp`, `_check_approval_timeout`, `_handle_decision`, `_resume_execution`, `_resume_correct`, bloc `AWAITING_APPROVAL`, params `decision`/`feedback` | `backend/domain/core/langgraph/streaming.py` (686 → 330 l.) |
| Champs `approval_status`/`approval_reason`/`approval_requested_at` | `backend/domain/core/langgraph/state.py` |
| Bloc `execute_decision` (execute/correct/cancel) | `backend/transport/routers/ws.py` |
| Params `decision`/`feedback` | `backend/infrastructure/streaming/streamer.py` |
| Mapping `[AWAITING_APPROVAL]` + handler `awaiting_approval` | `backend/infrastructure/streaming/parser.py` |
| Serializer `awaiting_approval` | `backend/infrastructure/streaming/models.py` |
| `approval_timeout_minutes` | `backend/domain/settings.py` |
| `test_awaiting_approval` | `tests/test_streaming_infra.py` |
| `ApprovalCallback`, `onApproval`, handler `awaiting_approval` | `frontend/services/MessageHandler.ts`, `frontend/services/types.ts` |
| `handleApproval`, `sendExecuteDecision` | `frontend/services/chatService.ts` |
| `approvalStatus`, `approvalReason`, `setApprovalStatus`, `sendApprovalDecision` | `frontend/lib/stores/agentCanvasStore.ts` |
| Bannière + useEffect d'approbation | `frontend/components/agent/AgentCanvas.tsx` |
| Indicateur « En attente d'approbation » | `frontend/components/agent/CustomNode.tsx` |
| Case `awaiting_approval` de `getStatusColor` | `frontend/components/agent/nodeStyles.ts` |
| Événement `awaitingApproval` | `frontend/lib/events.ts` |
| Clés i18n `approvalPending`/`approve`/`reject` | `frontend/lib/i18n-types.ts`, `frontend/lib/i18n-data.ts` |
| Fixture `awaitingApproval` | `frontend/lib/test/mockCanvasStore.ts` |
| Tests e2e T5-T8 (approbation) + helpers | `frontend/e2e/chat.spec.ts` |

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

### 3. Le streaming émet `[STEP]completed` de façon inconditionnelle

`backend/domain/core/langgraph/streaming.py` (après nettoyage) :

```python
yield "[STEP]completed:Task completed successfully"
```

→ L'ancien signal `AWAITING_APPROVAL` (déduit de l'absence de `execution_result`)
a été **supprimé** : il n'était jamais émis en flux normal puisque le graphe
exécute réellement.

### 4. Les champs d'approbation ont été retirés du state

`backend/domain/core/langgraph/state.py` : les champs
`approval_status`/`approval_reason`/`approval_requested_at` ont été supprimés.
Aucun nœud ne les consommait.

### 5. Le timeout d'approbation a été retiré

`backend/domain/settings.py` : `approval_timeout_minutes` supprimé.
`streaming.py` : `_check_approval_timeout()` et `_update_approval_timestamp()`
supprimés — ils ne se déclenchaient que si un `AWAITING_APPROVAL` était émis
(donc jamais en flux normal).

### 6. Le frontend a été nettoyé

Toute la chaîne UI d'approbation (boutons Execute/Correct/Cancel, bannière,
store, événements, i18n, tests e2e) a été retirée. Le frontend ne référence
plus aucun signal d'approbation.

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
- ✅ Tests : `test_streaming_infra.py` + `test_streaming_verification.py` + `test_pipeline_nodes.py` → **117 passed** (avant suppression de `test_awaiting_approval`)
- ✅ Grep backend + frontend : zéro référence à `approval`/`AWAITING_APPROVAL`/`execute_decision`
- ✅ `lsp_diagnostics` : aucun diagnostic sur les fichiers modifiés

## Recommandations

1. **Comportement actuel** : auto-approve (exécution autonome de bout en bout).
2. Si un **vrai HITL** est souhaité à l'avenir :
   - Réintroduire `interrupt_before=["execute"]` dans `compile()`.
   - Gater `executing_node` sur `approval_status == "APPROVED"`.
   - Réintroduire le bloc `AWAITING_APPROVAL` dans `streaming.py` (chemin principal, pas du code mort).
   - Réintroduire les champs `approval_*` dans `state.py` + `approval_timeout_minutes` dans `settings.py`.
   - Réintroduire la chaîne UI (boutons, bannière, store, événements, i18n).