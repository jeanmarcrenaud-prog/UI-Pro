# 🧠 **State Manager** (Gestion d'état global)
#
# ✅ State object
# ✅ Trace complète
# ✅ Debug possible
# ✅ Reprise après crash

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


# ==================== **1. STATE OBJECT** ====================

@dataclass
class State:
    """
    Object d'état global.
    
    Structure:
      {
        "task": "...",
        "plan": None,
        "architecture": None,  
        "code": None,
        "errors": [],
        "memory": [],
        "metrics": {
          "duration_ms": 0,
          "tokens": 0,
        }
      }
    """
    
    # Core task + execution
    task: str = ""
    task_id: str = ""  # Unique identifier
    
    # Pipeline steps
    plan: Optional[Dict[str, List[str]]] = field(default_factory=dict)
    architecture: Optional[Dict[str, str]] = field(default_factory=dict)
    code_generations: List[Dict[str, str]] = field(default_factory=list)
    tests: Optional[Dict[str, Any]] = field(default_factory=dict)  # Execution results
    review: Optional[Dict[str, Any]] = field(default_factory=dict)  # Code review
    
    # Quality
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Memory system
    memory: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metrics
    metrics: Dict[str, int] = field(default_factory=lambda: {
        "total_duration_ms": 0,
        "llm_calls": 0,
        "tokens": 0,
        "retry_count": 0,
        "max_retry_count": 3,
    })
    
    # Timestamp
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "initialized"  # "running", "completed", "failed"

    def to_dict(self) -> Dict[str, Any]:
        """Retourner état en dict"""
        return {
            "task": self.task,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "plan": self.plan,
            "architecture": self.architecture,
            "code_generations": self.code_generations,
            "errors": self.errors,
            "warnings": self.warnings,
            "memory": self.memory,
            "metrics": self.metrics,
        }

    def to_json(self) -> str:
        """JSON stringify"""
        return json.dumps(self.to_dict(), indent=2)

    def save_json(self, filename: str = "state.json"):
        """Sauvegarder state dans file"""
        try:
            with open(filename, "w") as f:
                f.write(self.to_json())
            logger.info(f"Saved state to {filename}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def clear(self):
        """Nettoyer state"""
        self.code_generations = []
        self.errors = []
        self.plans = {}
        self.architecture = {}


# ==================== **2. STATE MANAGER** ====================

class StateManager:
    """
    Singleton manager pour State.
    
    ✅ Accès lazy
    ✅ Thread-safe (simplifié)
    ✅ Persistence optionnel
    
    Usage:
      state_mgr = StateManager()
      state = state_mgr.get()
      state.task = "My task"
    """
    
    def __init__(self, auto_save: bool = False, save_dir: str = None):
        self.auto_save = auto_save
        self.save_dir = save_dir or "workspace"
        self._states: Dict[str, State] = {}
    
    def create(self, task_id: Optional[str] = None) -> State:
        """
        Créer nouveau state.
        
        Args:
            task_id: ID de tâche (optionnel)
            
        Returns:
            State object
        """
        state = State(task="New task")
        
        if task_id:
            state_id = task_id
        else:
            import uuid
            state_id = str(uuid.uuid4())[:8]
        
        state.task_id = state_id
        self._states[task_id] = state
        
        if self.auto_save:
            state.save_json(f"{self.save_dir}/{state_id}.json")
        
        return state
    
    def get(self, task_id: str = None) -> Optional[State]:
        """
        Récupérer existing state.
        
        Args:
            task_id: ID de tâche
            
        Returns:
            State ou None
        """
        if task_id:
            return self._states.get(task_id)
        else:
            # Return default or first state
            if self._states:
                return next(iter(self._states.values()), None)
            return State()
    
    def save(self, state: State):
        """
        Sauvegarder state.
        
        Args:
            state: State à sauvegarder
        """
        if state.task_id not in self._states:
            self._states[state.task_id] = state
            
        if self.auto_save:
            state.save_json(f"{self.save_dir}/{state.task_id}.json")
            
    def clear(self):
        """Clear all states"""
        self._states.clear()


# ==================== **3. UTILITY METHODS** ====================

def init_state(task: str = "My task") -> State:
    """
    Initialiser state.
    
    Usage:
      state = init_state("Write python app")
      state.task = task
    """
    manager = StateManager()
    state = manager.create(task_id=task[:4])
    state.task = task
    return state


def save_state(state: State, filename: str = None):
    """Sauvegarder state dans file"""
    state.save_json(filename or f"{state.task_id}.json")


def load_state(filename: str = "state.json") -> Optional[State]:
    """
    Charger state depuis file.
    
    Args:
        filename: Chemin file
        
    Returns:
        State ou None
    """
    try:
        with open(filename, "r") as f:
            data = json.loads(f.read())
        
        # Convert back to State object
        state = State(
            task=data.get("task", ""),
            plan=data.get("plan", {}),
            architecture=data.get("architecture", {}),
            code_generations=data.get("code_generations", []),
            errors=data.get("errors", []),
            memory=data.get("memory", []),
            metrics=data.get("metrics", {}),
        )
        return state
    except FileNotFoundError:
        logger.warning(f"State file not found: {filename}")
        return None


# ==================== **4. TEST STATE MANAGER** ====================

class TestStateManager:
    def test_create_state(self):
        """Test creation"""
        state = StateManager().create("test_task")
        assert state.task_id
        assert state.status == "initialized"
        
    def test_update_state(self):
        """Test update"""
        state = StateManager().create("test")
        state.task = "Updated task"
        assert state.task == "Updated task"
        
    def test_persistence(self):
        """Test persistence"""
        state = StateManager().create("persist_test")
        state.save_json("test_state.json")
        
        loaded = load_state("test_state.json")
        assert loaded.task == "persist_test"
        
        import os
        os.remove("test_state.json")
