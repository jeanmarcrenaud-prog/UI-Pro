# 🔍 ANALYSE DES PROBLÈMES UI-PRO

## 🐛 Problème 1 : DebugPanel - Tokens non mis à jour

### Description
Le DebugPanel affiche "0" Tokens même après génération de réponse, alors que le store montre correctement la valeur.

### Causes racines identifiées

1. **Store persistence bug** :
   - `persist()` middleware ne persiste que `history` (explicité dans chatStore.ts:164)
   - `tokenCount` n'est pas dans `partialize()`, donc non-persisted
   - ✅ OK c'est voulu

2. **React Memoization** :
   - Le DebugPanel reçoit `tokenCount` comme prop
   - Pas de `useEffect` pour écouter les changements de store
   - Le component ne se pas re-render quand la prop change
   - **CRITICAL BUG**

3. **Prop drilling pas optimisé** :
   - page.tsx passe `tokenCount={tokenCount}`
   - Mais le DebugPanel ne force pas re-render

### Solution recommandée
```typescript
// Dans DebugPanel.tsx
const [localTokenCount, setLocalTokenCount] = useState(tokenCount || 0)

useEffect(() => {
  if (tokenCount !== localTokenCount) {
    setLocalTokenCount(tokenCount)
  }
}, [tokenCount])

// Utilisation dans UI
<Tokens>{localTokenCount}</Tokens>
```

---

## 🐛 Problème 2 : WebSocket - JSON brut affiché

### Description
Dans le chat, on voit :
```json
{"model":"qwen3.5:0.8b","created_at":"2026-04-19..."
```
Au lieu de texte streaming.

### Cause racine
**Backend bug dans /api/stream** :

Dans `api/main.py`, le endpoint `/api/stream` :

```python
async def stream(prompt: str, ...):
    async def event_generator():
        # Envoie JSON dans data field
        yield f"data: {json.dumps({'type': 'step', ...})}\n\n"
```

**Frontend** (`chatService.ts`) attend soit :
- SSE format : `event: token\ndata: {...}`
- OU JSON simple : `{type: 'token', data: '...'}`

**Le backend envoie** `data: {JSON}` mais le frontend essaye de parser
- Si parsing échoue → fallback affiche JSON brut

### Solution
**Option A** : Fix backend JSON format (recommandé)
```python
yield f"data: {json.dumps(parsed)}\n\n"  # Pas de wrapper
```

**Option B** : Fix frontend parsing
```typescript
// Dans chatService.ts
const parsed = JSON.parse(data)
const text = parsed.data || parsed.content || parsed.message || parsed.text || ''
if (text) {
  this.currentContent += text
}
```

---

## Test Plan

### Test 1 : DebugPanel Tokens
1. Ouvrir http://localhost:3000
2. Ouvrir Debug Panel
3. Faire une requête
4. Attendre que tokens > 0
5. ✅ Attendu : Tokens affichées correctement

### Test 2 : Streaming texte
1. Faire une requête simple
2. ✅ Attendu : Texte fluide pas JSON
3. ✅ Attendu : Pas d'erreur de parsing

### Test 3 : DebugPanel force-update
1. Changer tokenCount côté store
2. ✅ Attendu : DebugPanel update immédiatement

---

## Plan d'implémentation

### Sous-tâche A : Fix DebugPanel
- ✅ Modifier DebugPanel.tsx pour sync tokenCount
- ✅ Ajouter force-update key
- ✅ Tester avec requête

### Sous-tâche B : Fix WebSocket JSON
- ✅ Check /api/stream format
- ✅ Standardiser sur SSE ou JSON simple
- ✅ Update frontend parsing si besoin

### Sous-tâche C : Tests manuels
- ✅ Lancer frontend
- ✅ Faire une requête
- ✅ Vérifier DebugPanel
- ✅ Vérifier streaming

---

## Agents à utiliser

1. **visual-engineering** : Fix composants React
2. **ultrabrain** : Logique state management
3. **direct** : Tests manuels
