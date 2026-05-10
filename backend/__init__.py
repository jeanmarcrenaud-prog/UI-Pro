# backend/ - Clean Architecture Target for UI-Pro
"""
Target Architecture (migration progressive):

backend/
├── domain/      # Business logic, entities, value objects
│   └── (core/, models/)
├── application/ # Use cases, orchestration
│   └── (controllers/)
├── infrastructure/ # External services
│   └── (services/, llm/)
└── transport/  # API endpoints
    └── (api/, views/)

Les anciens emplacements restent fonctionnels.
Phase 1: Structure créée, migration optionnelle.
"""

__version__ = "1.0.0"