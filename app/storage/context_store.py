import threading
from typing import Any, Dict, List, Optional, Tuple

class ContextStore:
    def __init__(self):
        self._lock = threading.Lock()
        # Storage key is (scope, context_id)
        # Value is a dictionary containing {"version": int, "payload": dict}
        self._store: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def push(self, scope: str, context_id: str, version: int, payload: Dict[str, Any]) -> Tuple[bool, int]:
        """
        Thread-safe push context method.
        Returns:
            Tuple[bool, int]: (accepted, current_stored_version)
            If accepted is False, the second element is the higher version already stored.
        """
        key = (scope, context_id)
        with self._lock:
            existing = self._store.get(key)
            if existing is not None:
                if existing["version"] > version:
                    # Incoming version is strictly older — reject as stale
                    return False, existing["version"]
                # Same version → idempotent upsert (accepted)
            
            # Store or overwrite with the new version
            self._store[key] = {
                "version": version,
                "payload": payload
            }
            return True, version

    def get(self, scope: str, context_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the payload of a specific context object."""
        key = (scope, context_id)
        with self._lock:
            entry = self._store.get(key)
            return entry["payload"] if entry else None

    def get_version(self, scope: str, context_id: str) -> Optional[int]:
        """Retrieve the version of a specific context object."""
        key = (scope, context_id)
        with self._lock:
            entry = self._store.get(key)
            return entry["version"] if entry else None

    def get_all(self, scope: str) -> List[Dict[str, Any]]:
        """Retrieve payloads for all context objects under a specific scope."""
        with self._lock:
            return [
                value["payload"]
                for (s, _), value in self._store.items()
                if s == scope
            ]

    def get_counts(self) -> Dict[str, int]:
        """Returns the number of loaded contexts per scope."""
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        with self._lock:
            for (scope, _), _ in self._store.items():
                if scope in counts:
                    counts[scope] += 1
                else:
                    counts[scope] = 1
        return counts

    def clear(self):
        """Wipes the entire store (for cleanup/teardown)."""
        with self._lock:
            self._store.clear()

# Singleton instance of the context store
store = ContextStore()
