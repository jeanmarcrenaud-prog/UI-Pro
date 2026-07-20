# Plan de Test : Flux "Voix $\rightarrow$ Délégation $\rightarrow$ Feedback"

## 1. Objectif Global
Valider l'intégrité de la chaîne de traitement asynchrone : 
`Capture Audio` $\rightarrow$ `STT` $\rightarrow$ `Intelligence (LLM + Planner)` $\rightarrow$ `Action (Délégation OpenCode)` $\rightarrow$ `Feedback Vocal (TTS)`.

## 2. Scénarios de Test

### Scénario A : Délégation de tâche complexe (Happy Path)
*   **Input Voix** : "Crée une application FastAPI pour gérer une bibliothèque de livres avec une base de données SQLite."
*   **Attentes techniques** :
    1.  **STT** : Transcription correcte du texte.
    2.  **Intelligence** : Détection de complexité $\rightarrow$ Génération d'une `DelegateAction` avec `action_type="opencode_delegate"`.
    3.  **Connector** : Démarrage du processus `opencode` avec le prompt utilisateur.
    4.  **Feedback** : Le `VoiceManager` doit détecter le succès de démarrage et confirmer par la voix (TTS) : "Délégation en cours sur OpenCode."
    5.  **UI** : Le WebSocket doit envoyer un événement de type `opencode_delegate` avec le statut `delegated`.

### Scénario B : Échec d'exécution côté OpenCode (Error Path)
*   **Input Voix** : "Crée un fichier système critique avec des permissions root." (Simuler un échec d'autorisation).
*   **Attentes techniques** :
    1.  **Connector** : Capture d'une erreur du processus OpenCode (code de sortie non nul ou message d'erreur dans le flux `stderr`).
    2.  **Feedback** : Le `VoiceManager` doit intercepter l'événement `error` de priorité `critical`.
    3.  **TTS** : Hermes doit confirmer vocalement l'échec : "Désolé, une erreur est survenue lors de l'exécution de la tâche par OpenCode."

### Scénario C : Commande atomique (Direct Path)
*   **Input Voix** : "Ouvre le fichier backend/domain/core/models.py."
*   **Attentes techniques** :
    1.  **Intelligence** : Identification d'une action simple $\rightarrow$ Décomposition en `open_file`.
    2.  **Executor** : Appel de la méthode `open_file` sur l' `EditorService`.
    3.  **StateStore** : Mise à jour de `active_file` dans le store global.
    4.  **UI** : Mise à jour du curseur et du fichier actif dans l'interface.

## 3. Matrice de Validation des Données

| Composant | Point de contrôle | Type de donnée attendu |
| :--- | :--- | :--- |
| **STT Service** | Transcript | Texte nettoyé sans hésitations ("euh", "ah") |
| **Task Planner** | Plan d'actions | JSON Array contenant `opencode_delegate` pour tâches complexes |
| **OpenCode Manager** | Processus | Processus `opencode` actif avec PID correct |
| **Editor State** | `active_file` | Chemin du fichier mis à jour après action `open_file` |
| **Voice Manager** | Logs TTS | Confirmation vocale déclenchée sur événements `success` / `error` |
| **WebSocket** | Flux JSON | Événements `token` ou `file_update` reçus en temps réel |

## 4. Méthodologie de Test (Mocking)
Pour les tests unitaires, utiliser les mocks suivants :
- `MockOpenCodeConnector` : Simule le démarrage du processus et renvoie des événements `success` ou `error` après un délai arbitraire.
- `MockSTTService` : Renvoie un texte prédéfini pour tester la décomposition de l'intelligence.
- `MockEditorStateStore` : Vérifie que les changements d'état sont correctement persistés.
