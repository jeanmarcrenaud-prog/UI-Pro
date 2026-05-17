# 🔍 Audit Technique Complet - UI-Pro

## Vue d'ensemble
L'architecture est bien structurée avec une séparation frontend/backend propre via WebSocket. Les stores Zustand gèrent bien l'état. Cependant, il y a des problèmes de robustesse et d'optimisation.

---

## 🔴 Problèmes Critiques

### 1. **Race Condition: Sélection de modèle**
**Problème:** Le modèle peut changer entre `sendMessage()` et l'envoi réel du payload.

```typescript
// useChatActions.ts ligne 112
await initializeNewGeneration(content, messageId, assistantId)
// Entre ici, l'utilisateur peut changer de modèle
// Le payload est envoyé avec un ancien modèle
```

**Impact:** Les utilisateurs obtiennent des résultats du mauvais modèle.

**Solution:**
```typescript
// Capturer le modèle au moment du sendMessage
const sendMessage = useCallback(async (content: string) => {
  const { model, provider } = getCurrentModelInfo() // 👈 IMMÉDIATEMENT
  
  try {
    await initializeNewGeneration(content, messageId, assistantId, model, provider)
  }
}, [getCurrentModelInfo, ...])
```

---

### 2. **Handler Leak: EventEmitter sans limite**
**Problème:** Les handlers s'accumulent indéfiniment dans `chatService.handlers`.

```typescript
// services/chatService.ts
private handlers = new Set<(message: Message) => void>()

onMessage(handler: (message: Message) => void): () => void {
  this.handlers.add(handler)
  return () => this.handlers.delete(handler) // Pas appelé si le composant ne cleanup pas
}
```

**Impact:** Fuite mémoire après plusieurs reconnexions.

**Solution:** Ajouter un max et nettoyer automatiquement:
```typescript
private handlers = new Set<(message: Message) => void>()
private MAX_HANDLERS = 10

onMessage(handler: (message: Message) => void): () => void {
  if (this.handlers.size >= this.MAX_HANDLERS) {
    console.warn('[chatService] Max handlers reached, clearing old ones')
    this.handlers.clear()
  }
  this.handlers.add(handler)
  return () => this.handlers.delete(handler)
}
```

---

### 3. **Token Estimation inexacte**
**Problème:** `Math.ceil(text.length / 4)` est très imprécis (diff de 50%).

**Solution recommandée:** Faire estimer côté backend et envoyer le count réel:
```typescript
// Backend: ws.py
yield {
  "type": "token",
  "content": content,
  "token_count": calculate_tokens(accumulated_content)  # 👈
}
```

---

### 4. **Pas de Error Boundary**
**Problème:** Une erreur React dans un composant crash toute l'app.

**Solution:** Ajouter une ErrorBoundary en haut niveau:
```typescript
// app/layout.tsx
export default function RootLayout() {
  return (
    <ErrorBoundary>
      <main>{children}</main>
    </ErrorBoundary>
  )
}
```

---

## 🟡 Problèmes de Robustesse

### 5. **Fallback REST sans streaming**
**Problème:** Quand WebSocket échoue, le fallback (`chatService.ts` ligne 251-286) utilise REST, qui n'a pas de streaming token-by-token.

**Symptôme:** Si WebSocket échoue, l'utilisateur voir toute la réponse d'un coup au lieu de streaming progressif.

**Solution:** Implémenter streaming SSE (Server-Sent Events) comme fallback:
```typescript
private async fallbackWithSSE() {
  const response = await fetch(`${API_CONFIG.apiUrl}/api/chat/stream`, {
    method: 'POST',
    body: JSON.stringify({ message, model, provider })
  })
  
  const reader = response.body?.getReader()
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    this.emit({ type: 'token', content: new TextDecoder().decode(value) })
  }
}
```

---

### 6. **Message Format Bridge incomplète**
**Problème:** Le backend envoie `[TOKEN]content` mais `chatService` l'adapte à `{delta}`, puis `useMessageHandler` accepte les deux. Fragile.

**Solution:** Créer un adapter unifié:
```typescript
// services/messageAdapter.ts
export function normalizeMessage(msg: any): NormalizedMessage {
  return {
    type: msg.type || (msg.delta ? 'token' : msg.status === 'done' ? 'done' : 'unknown'),
    content: msg.content || msg.delta || msg.response || '',
    messageId: msg.message_id || msg.id,
    status: msg.status,
  }
}
```

---

## 🟢 Optimisations

### 7. **Virtualisation des logs/messages**
**Problème:** Si 1000 logs s'affichent, React rend 1000 divs. Ralentit l'UI.

**Solution:** Utiliser `react-window`:
```typescript
import { FixedSizeList } from 'react-window'

<FixedSizeList
  height={400}
  itemCount={logs.length}
  itemSize={20}
  width="100%"
>
  {({ index, style }) => (
    <div style={style}>{logs[index]}</div>
  )}
</FixedSizeList>
```

---

### 8. **Refs vs Store Redux**
**Problème:** `useMessageHandler` utilise 5 refs pour l'état mutable. Difficile à tester.

**Solution:** Créer un `streamingStore`:
```typescript
// lib/stores/streamingStore.ts
export const useStreamingStore = create((set) => ({
  isActive: false,
  content: '',
  setActive: (active) => set({ isActive: active }),
  appendContent: (delta) => set(state => ({ 
    content: state.content + delta 
  })),
}))
```

---

### 9. **i18n sans traductions réelles**
**Problème:** Les fallbacks anglais s'affichent (ex: "Debug", "Logs").

**Solution:** Charger les traductions au démarrage:
```typescript
// hooks/useI18n.ts
const loadTranslations = async (locale: string) => {
  const translations = await import(`@/locales/${locale}.json`)
  return translations.default
}
```

---

### 10. **Memory Limit dans stores**
**Problème:** Les logs et messages s'accumulent indéfiniment (`.slice(-100)` n'est pas assez).

**Solution:** Ajouter un CircularBuffer:
```typescript
class CircularBuffer<T> {
  private items: T[] = []
  constructor(private max: number) {}
  
  push(item: T) {
    if (this.items.length >= this.max) {
      this.items.shift()
    }
    this.items.push(item)
  }
}
```

---

## 📊 Priorités de Correction

| # | Problème | Impact | Effort | Priorité |
|---|----------|--------|--------|----------|
| 1 | Race condition modèle | Haute (résultats erronés) | Bas | 🔴 P0 |
| 4 | Error Boundary | Haute (crash app) | Bas | 🔴 P0 |
| 2 | Handler leak | Moyenne (perf) | Bas | 🟡 P1 |
| 6 | Message format | Moyenne (fragile) | Moyen | 🟡 P1 |
| 5 | Fallback SSE | Moyenne (UX) | Moyen | 🟡 P1 |
| 3 | Token estimation | Basse (cosmétique) | Bas | 🟢 P2 |
| 7 | Virtualisation | Basse (perf) | Moyen | 🟢 P2 |
| 8 | Refs vs Store | Basse (testabilité) | Moyen | 🟢 P2 |

---

## 🚀 Plan d'Action

### Phase 1 (Urgent - Ce sprint)
1. ✅ Fixer race condition modèle → **1h**
2. ✅ Ajouter Error Boundary → **30min**
3. ✅ Limiter handlers → **30min**

### Phase 2 (Important - Prochain sprint)  
4. Créer message adapter unifié → **2h**
5. Implémenter fallback SSE → **3h**
6. Ajouter tokenCount réel du backend → **1h**

### Phase 3 (Bonne pratique - Plus tard)
7. Virtualiser logs → **2h**
8. CircularBuffer pour memory → **1h**
9. Charger traductions → **1h**

---

## 📋 Checklist Vérification

- [ ] Changer de modèle rapidement ne cause pas de bug
- [ ] Fermer DevTools et rouvrir ne leak pas les handlers
- [ ] Les logs restent sous 1MB en mémoire
- [ ] Un crash dans un composant n'affiche pas une page blanche
- [ ] Les tokens affichés correspondent à la réalité
- [ ] WebSocket down → fallback fonctionne avec streaming
