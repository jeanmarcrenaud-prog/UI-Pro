# Stores - State Management (Zustand-like for Python)
# Simple reactive state management

from typing import Callable, Any, Dict, List
from dataclasses import dataclass, field
from datetime import datetime
import threading


@dataclass
class Store:
    """Simple store with subscriptions"""
    _state: Dict = field(default_factory=dict)
    _listeners: List[Callable] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def get(self, key: str = None) -> Any:
        """Get state or key"""
        with self._lock:
            if key is None:
                return dict(self._state)
            return self._state.get(key)
    
    def set(self, **kwargs):
        """Set state"""
        with self._lock:
            self._state.update(kwargs)
            self._notify()
    
    def subscribe(self, listener: Callable):
        """Subscribe to changes"""
        self._listeners.append(listener)
    
    def unsubscribe(self, listener: Callable):
        """Unsubscribe"""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def _notify(self):
        """Notify all listeners"""
        for listener in self._listeners:
            try:
                listener(self._state)
            except Exception:
                pass


# Global stores
chat_store = Store()
agent_store = Store()
ui_store = Store()


def get_chat_store() -> Store:
    return chat_store


def get_agent_store() -> Store:
    return agent_store


def get_ui_store() -> Store:
    return ui_store