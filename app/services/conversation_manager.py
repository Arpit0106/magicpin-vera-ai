import threading
from typing import Any, Dict, List, Optional

class ConversationManager:
    def __init__(self):
        self._lock = threading.Lock()
        # Key: conversation_id
        # Value: Dict of conversation details
        self._conversations: Dict[str, Dict[str, Any]] = {}
        # Key: merchant_id
        # Value: count of consecutive auto-replies
        self._merchant_auto_replies: Dict[str, int] = {}

    def get_or_create_conversation(
        self,
        conversation_id: str,
        merchant_id: str,
        customer_id: Optional[str] = None,
        trigger_id: Optional[str] = None,
        suppression_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Gets existing conversation or initializes a new one thread-safely."""
        with self._lock:
            if conversation_id not in self._conversations:
                self._conversations[conversation_id] = {
                    "conversation_id": conversation_id,
                    "merchant_id": merchant_id,
                    "customer_id": customer_id,
                    "trigger_id": trigger_id,
                    "suppression_key": suppression_key,
                    "state": "qualifying",  # "qualifying", "action", "ended", "waiting"
                    "history": [],
                    "last_message_from_bot": "",
                    "turn_number": 0,
                    "auto_reply_count": 0
                }
            return self._conversations[conversation_id]

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve conversation by ID without creating it."""
        with self._lock:
            return self._conversations.get(conversation_id)

    def add_message(self, conversation_id: str, role: str, message: str):
        """Appends a message to the conversation history and updates turn count."""
        with self._lock:
            if conversation_id in self._conversations:
                conv = self._conversations[conversation_id]
                conv["history"].append({
                    "role": role,
                    "message": message
                })
                conv["turn_number"] += 1
                if role in ("vera", "merchant_on_behalf"):
                    conv["last_message_from_bot"] = message

    def update_state(self, conversation_id: str, state: str):
        """Updates the conversation flow state (e.g. action, ended, waiting)."""
        with self._lock:
            if conversation_id in self._conversations:
                self._conversations[conversation_id]["state"] = state

    def increment_auto_reply(self, merchant_id: str) -> int:
        """Increments and returns the count of consecutive auto-replies for a merchant."""
        with self._lock:
            self._merchant_auto_replies[merchant_id] = self._merchant_auto_replies.get(merchant_id, 0) + 1
            return self._merchant_auto_replies[merchant_id]

    def reset_auto_reply(self, merchant_id: str):
        """Resets the consecutive auto-reply counter for a merchant."""
        with self._lock:
            self._merchant_auto_replies[merchant_id] = 0

    def get_history_text(self, conversation_id: str) -> str:
        """Serializes the conversation history for LLM prompting context."""
        with self._lock:
            if conversation_id not in self._conversations:
                return ""
            history = self._conversations[conversation_id]["history"]
            lines = []
            for turn in history:
                role_label = "Vera" if turn["role"] in ("vera", "merchant_on_behalf") else "User"
                lines.append(f"{role_label}: {turn['message']}")
            return "\n".join(lines)

    def clear(self):
        """Clears all conversation session states."""
        with self._lock:
            self._conversations.clear()

conversation_manager = ConversationManager()
