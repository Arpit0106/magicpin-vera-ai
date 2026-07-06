from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.storage.context_store import store
from app.utils.suppression_manager import suppression_manager

class DecisionEngine:
    @staticmethod
    def evaluate_triggers(available_trigger_ids: List[str], current_time_str: str) -> List[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]], str]]:
        """
        Evaluates a batch of trigger IDs and returns a list of resolved contexts to compose.
        Each tuple contains: (category, merchant, trigger, customer, send_as)
        
        Optimizes for Decision Quality:
        - Filters out triggers that are expired.
        - Filters out triggers that are already suppressed (duplicate sends).
        - Sorts triggers by urgency (descending, 5 down to 1).
        - De-duplicates actions per merchant per tick (only send the highest urgency message to a merchant in a single tick to avoid spamming).
        """
        resolved_actions = []
        seen_merchants = set()
        
        # Parse current time
        try:
            current_time = datetime.fromisoformat(current_time_str.replace("Z", "+00:00"))
        except Exception:
            current_time = datetime.utcnow()

        # Step 1: Resolve contexts and filter out invalid/expired/suppressed triggers
        candidates = []
        for trigger_id in available_trigger_ids:
            trigger = store.get("trigger", trigger_id)
            if not trigger:
                continue

            # Check expiration
            expires_at_str = trigger.get("expires_at")
            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                    if current_time > expires_at:
                        # Skip expired trigger (Decision Quality)
                        continue
                except Exception:
                    pass

            # Check suppression key
            suppression_key = trigger.get("suppression_key")
            if suppression_key and suppression_manager.is_suppressed(suppression_key):
                # Skip suppressed trigger (Decision Quality)
                continue

            # Fetch merchant
            merchant_id = trigger.get("merchant_id")
            if not merchant_id:
                # Some triggers might have merchant_id inside the payload
                payload = trigger.get("payload", {})
                merchant_id = payload.get("merchant_id")
            
            if not merchant_id:
                continue

            merchant = store.get("merchant", merchant_id)
            if not merchant:
                continue

            # Fetch category
            category_slug = merchant.get("category_slug") or merchant.get("category")
            if not category_slug:
                continue
            
            category = store.get("category", category_slug)
            if not category:
                continue

            # Check customer scope
            customer_id = trigger.get("customer_id")
            customer = None
            send_as = "vera"
            
            # A trigger is customer-scoped if its scope is customer or customer_id is set
            if trigger.get("scope") == "customer" or customer_id:
                send_as = "merchant_on_behalf"
                if customer_id:
                    customer = store.get("customer", customer_id)

            candidates.append({
                "category": category,
                "merchant": merchant,
                "trigger": trigger,
                "customer": customer,
                "send_as": send_as,
                "urgency": trigger.get("urgency", 1),
                "merchant_id": merchant_id
            })

        # Step 2: Sort candidates by urgency descending
        candidates.sort(key=lambda x: x["urgency"], reverse=True)

        # Step 3: De-duplicate candidates per merchant (one message per merchant per tick)
        for cand in candidates:
            m_id = cand["merchant_id"]
            if m_id in seen_merchants:
                # Skip to avoid spamming the same merchant (Decision Quality)
                continue
            
            seen_merchants.add(m_id)
            resolved_actions.append((
                cand["category"],
                cand["merchant"],
                cand["trigger"],
                cand["customer"],
                cand["send_as"]
            ))

        return resolved_actions

decision_engine = DecisionEngine()
