# Projet ui-pro

Ce projet est une application complète comprenant un frontend, un backend et des outils de déploiement.

## Stack Technologique
- **Frontend** : Situé dans le dossier `/frontend`. (Architecture moderne, favorisant la réutilisabilité des composants).
- **Backend** : Situé dans le dossier `/backend`. Dépendances gérées par `requirements.txt` et `pyproject.toml`.
- **Infrastructure** : Supporte le déploiement via Docker (`Dockerfile`) et des commandes de construction via `Makefile`.

## Règles de Développement
- **Qualité du code** : Priorité à la lisibilité, à la modularité et à la performance.
- **Backend** : Respecter les conventions de nommage Python. Utiliser les scripts dans `/scripts` pour les tâches utilitaires complexes.
- **Frontend** : Maintenir une cohérence visuelle et une séparation claire entre la logique métier et l'affichage.
- **Documentation** : Toujours mettre à jour le dossier `/docs` après des modifications majeures de l'architecture.
- **Tests** : Utiliser `pytest` pour garantir la non-régression des fonctionnalités critiques.

## Instructions Spécifiques pour les Agents
- Toujours vérifier les dépendances dans `requirements.txt` avant de suggérer des bibliothèques.
- Utiliser le `Makefile` pour exécuter les commandes de build ou de test standard si elles existent.
- Lors de la création de nouveaux fichiers, respecter la structure existante des répertoires `/frontend` et `/backend`.
