"""
Translation system for Gradio Dashboard.

Supports: French (fr), English (en)
"""

from typing import Dict

# Available languages
LANGUAGES = ["fr", "en"]
DEFAULT_LANGUAGE = "fr"


# Translation dictionaries
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "fr": {
        # Navigation
        "nav_task_input": "Tâche",
        "nav_realtime": "Sortie temps réel",
        "nav_logs": "Logs",
        "nav_status": "Statut",
        "nav_memory": "Mémoire",
        "nav_metrics": "Métriques",
        
        # Navigation items
        "nav_item_task_input": "Entrée de tâche",
        "nav_item_realtime": "Sortie temps réel",
        "nav_item_logs": "Logs temps réel",
        "nav_item_status": "Statut",
        "nav_item_memory": "Mémoire",
        "nav_item_metrics": "Métriques",
        
        # Task Input section
        "task_input_label": "Entrée de tâche",
        "task_input_placeholder": "Décrivez la tâche à exécuter... (ex: 'Créer une API FastAPI qui retourne [1,2,3]')",
        "current_task_id": "ID de tâche actuel",
        "submit_task": "Soumettre la tâche",
        "pipeline_desc": "La tâche exécutera via: Planificateur → Architecte → Développeur → Réviseur → Exécuteur (avec boucle auto-correction)",
        
        # Real-time Output
        "realtime_label": "Sortie d'exécution",
        "realtime_placeholder": "Aucune sortie. Soumettez une tâche pour voir l'exécution.",
        
        # Live Logs
        "logs_label": "Logs",
        "logs_placeholder": "Aucun log pour le moment.",
        
        # Status
        "status_label": "Statut",
        "state_label": "État",
        "status_idle": "inactif",
        "status_running": "en cours",
        "status_success": "succès",
        "status_error": "erreur",
        
        # Memory
        "memory_title": "Recherche mémoire FAISS",
        "memory_search": "Requête de recherche",
        "memory_placeholder": "Rechercher dans les tâches précédentes...",
        "memory_results": "Résultats",
        "memory_not_available": "⚠️ Mémoire non disponible (FAISS non installé)",
        
        # Metrics
        "metrics_title": "Métriques d'exécution",
        "metrics_success_rate": "Taux de réussite %",
        "metrics_total": "Total des exécutions",
        "metrics_avg": "Durée moyenne (ms)",
        "metrics_refresh": "Actualiser les métriques",
        "metrics_recent": "Exécutions récentes",
        "metrics_not_available": "⚠️ Métriques non disponibles",
        
        # Settings/Language
        "language": "Langue",
        "select_language": "Sélectionner la langue",
        
        # Common
        "btn_submit": "Soumettre",
        "btn_refresh": "Actualiser",
    },
    
    "en": {
        # Navigation
        "nav_task_input": "Task",
        "nav_realtime": "Real-time Output",
        "nav_logs": "Logs",
        "nav_status": "Status",
        "nav_memory": "Memory",
        "nav_metrics": "Metrics",
        
        # Navigation items
        "nav_item_task_input": "Task Input",
        "nav_item_realtime": "Real-time Output",
        "nav_item_logs": "Live Logs",
        "nav_item_status": "Status",
        "nav_item_memory": "Memory",
        "nav_item_metrics": "Metrics",
        
        # Task Input section
        "task_input_label": "Task Input",
        "task_input_placeholder": "Describe the task to run... (e.g., 'Create a FastAPI app that returns [1,2,3]')",
        "current_task_id": "Current Task ID",
        "submit_task": "Submit Task",
        "pipeline_desc": "Task will execute through: Planner → Architect → Coder → Reviewer → Executor (with auto-fix loop)",
        
        # Real-time Output
        "realtime_label": "Execution Output",
        "realtime_placeholder": "No output yet. Submit a task to see real execution.",
        
        # Live Logs
        "logs_label": "Live Logs",
        "logs_placeholder": "No logs yet.",
        
        # Status
        "status_label": "Status",
        "state_label": "State",
        "status_idle": "idle",
        "status_running": "running",
        "status_success": "success",
        "status_error": "error",
        
        # Memory
        "memory_title": "FAISS Memory Search",
        "memory_search": "Search query",
        "memory_placeholder": "Ask about previous tasks...",
        "memory_results": "Results",
        "memory_not_available": "⚠️ Memory not available (FAISS not installed)",
        
        # Metrics
        "metrics_title": "Execution Metrics",
        "metrics_success_rate": "Success Rate %",
        "metrics_total": "Total Executions",
        "metrics_avg": "Avg Duration (ms)",
        "metrics_refresh": "Refresh Metrics",
        "metrics_recent": "Recent Executions",
        "metrics_not_available": "⚠️ Metrics not available",
        
        # Settings/Language
        "language": "Language",
        "select_language": "Select language",
        
        # Common
        "btn_submit": "Submit Task",
        "btn_refresh": "Refresh",
    },
}


def get_translation(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Get a translation for the given key and language."""
    return TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE]).get(key, key)


def get_current_translations(lang: str = DEFAULT_LANGUAGE) -> Dict[str, str]:
    """Get the full translation dictionary for a language."""
    return TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE]).copy()


# Language display names (for dropdown)
LANGUAGE_OPTIONS = [
    ("Français", "fr"),
    ("English", "en"),
]