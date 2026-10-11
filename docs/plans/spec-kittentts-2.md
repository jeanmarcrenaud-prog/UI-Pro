# Spec — Intégration KittenTTS 2 (synthèse vocale) pour ui-pro

## Objectif
Remplacer le TTS **dummy** de `ui-pro` par un moteur local **KittenTTS 2 réel**,
en mode **CPU** (ne touche PAS le GPU), avec fallback robuste vers le dummy
actuel si KittenTTS 2 n'est pas dispo. Ne casse PAS le contrat existant
de Mario.

## Contexte machine
- GPU RTX 5080: ~14,5 Go / 16 Go **déjà chargés** (LM Studio qwen3.8-27b).
  → KittenTTS 2 doit tourner en **CPU** (≈6Go RAM), ne rien charger sur GPU.
- Python `3.12`. Deps audio déjà présentes : `piper-tts`, `onnxruntime`,
  `soundfile`, `numpy`.

## API exacte de KittenTTS 2 (NE PAS DEVINER)
```python
from kittenml import KittenTTS
import soundfile as sf
m = KittenTTS("KittenML/kitten-tts-2", weights="emb4")   # 506Mo, quantisé
audio = m.generate(text, voice=voix)                     # -> np array (mono)
sr = m.sample_rate                                       # sample rate du model
sf.write("out.wav", audio, sr)
m.available_voices    # liste les 47 voix (inclut FR)
m.generate_to_file(text, "out.wav", voice=voix)          # variante directe
```
- `weights="emb4"` = 506Mo (moins que 947Mo), même qualité perçue. **À utiliser.**
- La voix **FR** : choisir dans `m.available_voices` une voix francophone
  naturelle (ex: Hugo, Bruno, Kiki — à confirmer au runtime ; ne hardcode PAS).

## Contrat existing de Mario (NE PAS CASSER)
1. `/tts` endpoint (`backend/transport/routers/mario.py`) :
   `audio_data = tts.synthesize(request.text)` puis
   `sf.write(out_path, audio_data, 22050)` → **attend un np array à 22050 Hz.**
2. `/tts/play` : `mario.tts.speak(request.text)` → retournée `bool`.
3. `/voices` : liste les voix disponibles.

## À créer / modifier — BACKEND
### 1. Adapter KittenTTS (`backend/infrastructure/voice/kittentts_service.py`)
- Classe `KittenTTS2Service` (ou étendre `TTSService`).
- **Lazy load** : charger le model au **premier appel** (pas au boot).
  Cache local + `m = KittenTTS("KittenML/kitten-tts-2", weights="emb4")`.
- **Forcer CPU** : n'importe pas de device GPU. Si torch dispo,
  `model.to("cpu")` ; sinon backend ONNX/`cpu` natif.
- Méthode `synthesize(text) -> Optional[np.ndarray]` (retourne **array numpy**,
  compatible avec `sf.write(..., 22050)`).
- **Resampler dynamique** : KittenTTS 2 retourne un sample rate différent de
  22050 (16k ou 24k). **NE PAS hardcoder**. Détection :
  ```python
  sr = model.sample_rate          # sample rate réel du model
  if sr != 22050:
      audio = resample_to_22050(audio, sr)   # voir helper ci-dessous
  ```
- **Choix de voix FR** : au runtime, `m.available_voices` → choisir une
  voix francophone (premier match dans liste d'explorateurs FR, sinon
  première disponible). Ne hardcode PAS la voix.

### 2. Helper resampler (`backend/infrastructure/voice/audio_utils.py`)
```python
def resample_to_22050(audio: np.ndarray, sr: int) -> np.ndarray:
    """Resample un mono np array vers 22050 Hz. Robuste, ne crash pas."""
    if sr == 22050: return audio
    # PRÉFÉRER scipy.signal.resample_poly si dispo (qualité), sinon downsample numpy
    try:
        import scipy.signal as sig
        factor = 22050 / float(sr)
        if factor < 1:  # upscale
            return sig.resample(audio, int(len(audio)*factor))
        else:          # downsample
            return sig.resample_poly(audio, num=round(factor), den=1)
    except Exception:
        # Fallback : decimation numpy simple (acceptable, note la dégradation)
        step = max(1, round(sr / 22050))
        return audio[::step] if step > 1 else audio
```

### 3. Intégration dans `TTSService` (`backend/infrastructure/voice/tts_service.py`)
- `synthesize(text) -> Optional[str]` : **contract existant** (retourne un
  **chemin**). Ne changer PAS la signature.
- Logique : si KittenTTS 2 dispo → générer, resample vers 22050,
  `sf.write(chemin, audio, 22050)`, return chemin. Sinon → fallback dummy
  actuel (retourne path).
- `/tts` endpoint de mario : `audio_data = tts.synthesize(...)`. Si on change
  la signature, **adapter** : garder une méthode `synthesize_array(text)` qui
  retourne le np array à 22050 pour mario.

### 4. requirements.txt
Ajouter (commenté avec version) :
```
kittenml>=0.1.0              # KittenTTS 2 TTS local (CPU/GPU)
scipy>=1.9.0                 # resampler audio (optionnel, fallback numpy)
```

## À créer — FRONTEND
- `/voices` endpoint : lister les voix KittenTTS 2 FR.
- Si dispo, permettre de **choir** la voix dans `MarioView.tsx` (dropdown).
  Sinon default FR.
- Ne pas ajouter de nouveau framework.

## Tests / validation
- Backend : `tests/test_kittentts.py` — tests mock (KittenTTS 2 dispo + sample
  rate différent → resample OK ; pas dispo → fallback dummy ; voix FR choisie).
- Frontend : `/voices` rend les voix sans crash.

## Hors-scope (NE PAS FAIRE pour l'instant)
- Clonage de voix / expression presets = feature à part, hors-scope ici.
- Pas d'install auto du model — juste lazy load + fallback.
- TTS KittenTTS 2 full (947Mo non-quantisé) — on utilise `emb4` (506Mo).
