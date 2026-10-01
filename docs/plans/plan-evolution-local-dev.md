# Plan d'évolution UI-Pro — "Le copilot local du dev solo avec GPU"

> Cible : dev solo, machine Windows/Linux + GPU (RTX 3060 → 5090), Ollama ou LM Studio.
> Promesse : **chaque décision de l'agent est visible, chaque étape inspectable, 100% local.**
> Date : 01/10/2026 — statut : à exécuter

---

## Vision en une phrase

Un dev avec un GPU clone le repo, remplit UNE config, et voit son agent corriger ses tests
échoués en boucle auto-fix — sans cloud, sans abonnement, sans black box.

---

## Phase 1 — Setup en 5 min (priorité absolue)

Objectif : `docker compose up` → UI fonctionnelle, zéro friction.

### Tâches

- [ ] **T1.1** Créer `docker-compose.yml` :
      - service `api` : image du Dockerfile existant (port 8000), healthcheck déjà OK
      - service `ui` : build Next.js (`frontend/`, port 3000, `next start`)
      - service `sandbox` : conteneur d'exécution isolé pour le code généré (python:3.12-slim)
      - variable `host.docker.internal` documentée pour pointer Ollama/LM Studio sur le host
- [ ] **T1.2** Config unique : un seul `.env.example` à la racine avec 3 variables seulement :
      - `LLM_BASE_URL` (Ollama ou LM Studio)
      - `LLM_MODEL_FAST` / `LLM_MODEL_REASONING`
      - `API_KEY` (optionnel, local = vide par défaut)
      - Le reste (memory, logging, metrics…) garde ses valeurs par défaut de config.yaml.example.
- [ ] **T1.3** Endpoint `/health` enrichi : renvoyer l'état LLM (ping Ollama/LM Studio,
      modèle chargé ? tokens/s estimé ?) + état sandbox. Le frontend affiche un bandeau
      "GPU prêt ✅ / LLM injoignable ❌" avant même de chat.
- [ ] **T1.4** `make setup` : une commande qui fait install + build + healthcheck, et dit
      exactement quoi corriger si ça échoue (message d'erreur guidé).

### Critère d'acceptation Phase 1
Un dev avec Docker + Ollama arrive à la page de chat en < 5 min, sans lire plus que le README.

---

## Phase 2 — Le workflow killer : "Fix mes tests qui échouent"

Objectif : UN workflow fiable de bout en bout plutôt que 7 features à 60%.

### Tâches

- [ ] **T2.1** Script d'entrée `scripts/fix_tests.py` (ou endpoint dédié) :
      - capture la sortie pytest du projet cible (fichier workspace monté dans le conteneur)
      - alimente l'intention vers `IntelligenceService.process_user_intent()`
- [ ] **T2.2** Boucle auto-fix existante (max 3 iters, déjà en place via ActionExecutor +
      reviewing_node) : vérifier qu'elle re-lance pytest dans la sandbox après chaque patch,
      et que l'état "vert" est détecté de façon fiable (exit code, pas du parsing de texte).
- [ ] **T2.3** UI : afficher les étapes en direct — erreurs capturées → plan → patch → re-test,
      avec le diff coloré de chaque modification (le pipeline visible est l'argument n°1).
- [ ] **T2.4** Mode "lecture seule" (review) : l'agent propose des actions, le dev valide ou
      rejette avant exécution. Flag `executor.read_only: true` dans la config.
- [ ] **T2.5** Tests e2e du workflow : 3 scénarios (1 test simple à fixer / 2 tests liés /
      échec après 3 iters → rapport clair).

### Critère d'acceptation Phase 2
Démo reproductible : repo de démo avec 4 tests rouges → `make demo` → vert en < 2 min,
étapes visibles dans l'UI.

---

## Phase 3 — Preuve publique (crédibilité)

- [ ] **T3.1** README : remplacer les placeholders screenshots par 2-3 vraies captures
      (pipeline visible + diff de fix + bandeau santé GPU).
- [ ] **T3.2** GIF ou vidéo démo 3 min : "depuis zéro, un dev avec une RTX 5080 corrige
      4 tests en 90 s, 100% local". Héberger sur GitHub (user-attachments) pour éviter les liens morts.
- [ ] **T3.3** Section "Hardware requis" honnête dans le README :
      - minimum : 8 GB VRAM → qwen2.5-coder:7b Q4
      - recommandé : 16 GB VRAM → qwen3.8-27b Q4_K_M (~14 GB, ~50 tok/s avec MTP)
      - KV cache ≤ Q8 (Q14 overflow VRAM → draft ~5 tok/s — leçon déjà mesurée)
- [ ] **T3.4** Badge "self-hosted • no cloud" + lien vers la vidéo en tête de README.

### Critère d'acceptation Phase 3
Un visiteur GitHub comprend ce que c'est et comment ça tourne en < 60 s sans ouvrir le code.

---

## Phase 4 — Différenciation & confiance

- [ ] **T4.1** Page "Comment l'agent décide" : doc du pipeline (Analyze→Plan→Code→Review→
      Execute) avec exemples réels de logs, pour rassurer les solos méfiants.
- [ ] **T4.2** Mode lecture seule par défaut sur les premiers runs (voir T2.4), puis
      "confiance progressive" : après N validations, l'agent passe en auto.
- [ ] **T4.3** Rapport post-run : fichier markdown généré (actions effectuées, itérations,
      tokens consommés) — utile pour la review et le partage.
- [ ] **T4.4** (Optionnel) Export du run vers LangSmith OFF ou un simple JSON local —
      garder le tracing 100% local par défaut.

---

## Ce qu'on met de côté (pas supprimé, juste pas prioritaire)

| Élément | Raison |
|---|---|
| FAISS memory | Nice-to-have ; le workflow killer n'en a pas besoin |
| LangSmith tracing | Cloud = contre-productif pour du local-first (T4.4 en version locale) |
| Gradio dashboard (port 7860) | Le frontend Next.js suffit, deux UIs = double maintenance |
| Prometheus / metrics JSON | Garder l'endpoint, pas de dashboard dédié |

---

## Ordre d'exécution & estimation

1. **T1.1 → T1.4** (Phase 1) — ~2-3 jours : c'est la fondation, tout le reste en dépend
2. **T2.1 → T2.5** (Phase 2) — ~3-5 jours : le cœur de valeur
3. **T3.1 → T3.4** (Phase 3) — ~1 jour : à faire APRÈS la Phase 2 pour que les captures soient vraies
4. **T4.x** (Phase 4) — au fil de l'eau, après la première démo publique

Règle : pas de feature hors-liste avant que le critère d'acceptation de la phase courante soit validé.

---

## Risques connus

- **Sandbox Docker sur Windows** : WSL2 requis ; documenter clairement (le dev solo Windows est la cible, c'est LE point de friction).
- **Modèle trop petit** : < 7B, le pipeline Plan/Review dégrade → afficher un avertissement dans l'UI si le modèle configuré est sous le seuil.
- **Timeout LLM local** : les timeouts actuels (30s config) sont courts pour du Q4 sur GPU mid-range ; rendre configurable par étape.
