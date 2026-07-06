import threading
from typing import Set

class SuppressionManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._suppressed_keys: Set[str] = set()

    def is_suppressed(self, key: str) -> bool:
        """Checks if a given suppression key has already been dispatched."""
        if not key:
            return False
        with self._lock:
            return key in self._suppressed_keys

    def suppress(self, key: str):
        """Adds a suppression key to prevent future dispatches of the same key."""
        if not key:
            return
        with self._lock:
            self._suppressed_keys.add(key)

    def clear(self):
        """Resets the suppression manager."""
        with self._lock:
            self._suppressed_keys.clear()

# Singleton instance of the suppression manager
suppression_manager = SuppressionManager()
