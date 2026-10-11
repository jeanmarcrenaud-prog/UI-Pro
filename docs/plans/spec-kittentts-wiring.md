# Spec — Branchement KittenTTS 2 sur les endpoints TTS de la UI (Mario) + dropdown voix

## Objectif
Faire **sonner réellement** le TTS de la UI. Actuellement `mario.tts = None`
(projet externe `src/` absent dans ce repo) → `/tts`, `/tts/play` retournent
503. Brancher notre moteur KittenTTS 2 (déjà créé et validé) + ajouter un
**dropdown de voix**.

## État actuel (verifié)
- `_get_mario()` (`backend/transport/routers/mario.py`) : cherche `src/` via
  `_ensure_mario_path()`. Si absent → retourne `MarioServices(available=False,
  tts=None)`. C'est le point à brancher.
- Le moteur local **prêt** (par OpenCode, tests OK) :
  `backend/infrastructure/voice/kittentts_service.py` → `KittenTTS2Service`
    - `.synthesize(text) -> Optional[np.ndarray]` (mono, 22050 Hz, CPU-only)
    - `.available_voices() -> list[str]`
    - `.select_french_voice() -> str|None`
- Le endpoint `/tts` (line ~249) appelle `src.models.text_to_speech.TextToSpeech()`
  directement (externes, non dispo) → à remplacer.
- Le frontend `frontend/components/MarioView.tsx` : badge TTS + textarea
  "Texte à prononcer" + bouton speak qui appelle `/tts/play`. Pas de dropdown voix.

## À faire — BACKEND
### 1. Adapter (`backend/infrastructure/voice/mario_adapter.py`)
Classe `MarioTTSAdapter` qui présente le contrat attendu par `mario.py`,
en deleguant vers `KittenTTS2Service` (lazy, CPU) :
- `speak(text) -> bool` : synthétise + joue si possible, else retourn
  `False`. Ne crash pas.
- `get_available_voices() -> list[str]` : délégué à `.available_voices()` ;
  fallback `[\"KittenTTS2\"]` si vide (ne pas retourner une liste vide qui
  casserait le dropdown).
- `synthesize_array(text) -> Optional[np.ndarray]` : délégué à `.synthesize()`.
- Propriété `.is_available` / méthode pour détecter si moteur dispo.

### 2. Branchement dans `_get_mario()` (`mario.py`)
```python
if not _ensure_mario_path():
    # Fallback local : brancher KittenTTS 2 (CPU) au lieu de None
    try:
        from backend.infrastructure.voice.mario_adapter import MarioTTSAdapter
        services.tts = MarioTTSAdapter()   # lazy-loadé, CPU
    except Exception:
        pass  # TTS indispo -> mario.tts reste None (comportement actuel)
    _mario = services
    return _mario
```
→ Ainsi si `src/` existe → TSS externe (pas de régression). Sinon → KittenTTS 2.

### 3. Endpoint `/tts` (`mario.py`)
Remplacer l'appel à `TextToSpeech()` (externes) par :
```python
audio_data = mario.tts.synthesize_array(request.text) if mario.tts else None
if audio_data is None: raise HTTPException(503, "TTS not available")
sf.write(out_path, audio_data, 22050)
```
→ Retourne un WAV réel à 22050 Hz.

## À faire — FRONTEND (MarioView.tsx)
- Ajouter un **dropdown de voix** au-dessus du textarea TTS :
  - Appelle `GET /voices` au mount → liste les voix KittenTTS 2.
  - Default = première voix FR (KittenTTS 2 auto-sélectionne).
  - Envoie la voix choisie dans le `voice` field de `/tts/play`.
- Si TSS indispo → dropdown désactivé + badge "503" (déjà géré par `tts:bool`).
- Utilise les design tokens existants. Ne pas ajouter de nouveau framework.

## Tests / validation
- Backend : `tests/test_mario_adapter.py` — adapter dispo, voix FR,
  synthesize_array → 22050, fallback indispo → 503.
- Frontend : dropdown rend la liste de voix sans crash ; envoie le `voice`.

## Hors-scope (NE PAS FAIRE)
- Clonage/expressions KittenTTS 2 — feature à part.
- Toucher le projet externe `src/` (absent) — on branche le fallback local.
- Changer le contract de `/tts/play` (le `voice` field existant).
