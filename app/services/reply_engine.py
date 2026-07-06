import re
import json
from typing import Any, Dict, Optional
from app.storage.context_store import store
from app.utils.llm_client import llm_client
from app.services.conversation_manager import conversation_manager

AUTO_REPLY_PATTERNS = [
    r"thank you for contacting",
    r"will respond shortly",
    r"automated assistant",
    r"currently closed",
    r"office is closed",
    r"jaankari ke liye.*shukriya",
    r"automated message",
    r"auto-reply",
    r"canned reply"
]

HOSTILE_PATTERNS = [
    r"stop messaging",
    r"useless spam",
    r"fuck off",
    r"don't message",
    r"dont message",
    r"stop text",
    r"stop send"
]

class ReplyEngine:
    REPLY_SYSTEM_PROMPT = """You are the reply composer for "Vera", magicpin's merchant AI assistant.
You are in a live multi-turn WhatsApp conversation. Given the Category context, Merchant context, Conversation History, and the user's Latest Message, you must decide the next move.
You must return a valid JSON object with the exact keys:
{
  "action": "send", // "send", "wait", or "end"
  "body": "The WhatsApp reply body text. DO NOT include any URLs/links. Enforce Hinglish code-mix if requested.",
  "cta": "The CTA kind: open_ended, binary_yes_no, binary_confirm_cancel, or none",
  "rationale": "One sentence explaining why this reply structure was chosen."
}

CRITICAL RULES:
1. INTENT TRANSITION (10/10 Rubric Target):
   - If the merchant has shown commitment (e.g. "let's do it", "go ahead", "send the abstract", "whats next"), you MUST transition from qualifying to action execution.
   - Do NOT ask qualifying questions. Instead, draft the actual post or content (e.g. GBP post, patient WhatsApp draft) and ask the merchant to reply CONFIRM to publish/send.
   - Example action mode: "Great! Drafting your patient WhatsApp now... Reply CONFIRM to send."

2. STAY ON MISSION / CURVEBALLS:
   - If the user asks an unrelated question (e.g. "help with GST filing"), politely decline as out-of-scope and redirect back to the topic.
   - Do not hallucinate capabilities we don't have.

3. SPECIFICITY & VOICE FIT:
   - Enforce category voice tone (clinical peer for dentists, warm for salons).
   - Use concrete stats and actual pricing if relevant.
   - NO URLs or web links.
"""

    @staticmethod
    def process_reply(
        conversation_id: str,
        merchant_id: str,
        customer_id: Optional[str],
        from_role: str,
        message: str,
        turn_number: int
    ) -> Dict[str, Any]:
        """
        Processes an incoming message from the merchant or customer and returns the next ReplyResponse dict.
        """
        # Get or create conversation state
        conv = conversation_manager.get_or_create_conversation(
            conversation_id=conversation_id,
            merchant_id=merchant_id,
            customer_id=customer_id
        )

        # 1. Rule-Based Hostile Check
        message_lower = message.lower().strip()
        if any(re.search(pat, message_lower) for pat in HOSTILE_PATTERNS):
            conversation_manager.update_state(conversation_id, "ended")
            return {
                "action": "end",
                "rationale": "Merchant opted out or expressed hostility."
            }

        # 2. Rule-Based Auto-Reply Check
        is_auto = False
        if any(re.search(pat, message_lower) for pat in AUTO_REPLY_PATTERNS):
            is_auto = True
        
        # Check if the incoming message is identical to the last message received from this user
        history = conv["history"]
        user_msgs = [turn["message"] for turn in history if turn["role"] == from_role]
        if len(user_msgs) >= 2 and user_msgs[-1] == message:
            is_auto = True

        if is_auto:
            auto_count = conversation_manager.increment_auto_reply(merchant_id)
            if auto_count == 1:
                # Prompt the owner to take over
                body = "Looks like an auto-reply. When the owner sees this, just reply to let us know."
                conversation_manager.add_message(conversation_id, from_role, message)
                conversation_manager.add_message(conversation_id, "vera", body)
                return {
                    "action": "send",
                    "body": body,
                    "cta": "binary_yes_no",
                    "rationale": "Detected first auto-reply, prompting owner to take over."
                }
            elif auto_count == 2:
                # Backoff 4 hours (14400 seconds)
                conversation_manager.update_state(conversation_id, "waiting")
                return {
                    "action": "wait",
                    "wait_seconds": 14400,
                    "rationale": "Second consecutive auto-reply detected. Backing off for 4 hours."
                }
            else:
                # End conversation after 3+ consecutive auto-replies
                conversation_manager.update_state(conversation_id, "ended")
                conversation_manager.reset_auto_reply(merchant_id)
                return {
                    "action": "end",
                    "rationale": "Repeated auto-replies received. Gracefully closing conversation."
                }

        # Reset auto reply count on a real message
        conversation_manager.reset_auto_reply(merchant_id)

        # Add message to history
        conversation_manager.add_message(conversation_id, from_role, message)

        # 3. Resolve context information
        merchant = store.get("merchant", merchant_id)
        category = store.get("category", merchant.get("category_slug", "")) if merchant else None
        customer = store.get("customer", customer_id) if customer_id else None

        if not merchant or not category:
            # Safe fallback if contexts are missing
            body = "Got it. Let me prepare that for you."
            conversation_manager.add_message(conversation_id, "vera", body)
            return {
                "action": "send",
                "body": body,
                "cta": "open_ended",
                "rationale": "Missing merchant or category context fallback."
            }

        # 4. LLM-Based Reply Generation
        history_text = conversation_manager.get_history_text(conversation_id)
        
        user_prompt = f"""=== CATEGORY CONTEXT ===
Slug: {category.get('slug')}
Voice rules: {json.dumps(category.get('voice', {}))}
Offer Catalog: {json.dumps(category.get('offer_catalog', []))}

=== MERCHANT CONTEXT ===
Identity: {json.dumps(merchant.get('identity', {}))}
Active Offers: {json.dumps([o for o in merchant.get('offers', []) if o.get('status') == 'active'])}

=== CONVERSATION HISTORY ===
{history_text}

=== LATEST MESSAGE FROM USER ===
{message}

Please generate the reply. Enforce natural code-mix language (Hinglish) if languages include 'hi' or preference includes 'hi'."""

        messages = [
            {"role": "system", "content": ReplyEngine.REPLY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        llm_response = llm_client.complete(messages)

        if llm_response:
            try:
                json_match = re.search(r'\{[\s\S]*\}', llm_response)
                if json_match:
                    res_dict = json.loads(json_match.group())
                    body = res_dict.get("body", "")
                    # Strip any links from body
                    body = re.sub(r'https?://\S+', '', body).strip()
                    res_dict["body"] = body

                    # Update history and conversation state
                    conversation_manager.add_message(conversation_id, "vera", body)
                    action = res_dict.get("action", "send")
                    if action == "end":
                        conversation_manager.update_state(conversation_id, "ended")
                    elif action == "wait":
                        conversation_manager.update_state(conversation_id, "waiting")
                    else:
                        # If the reply drafts content, update state to "action"
                        if "confirm" in body.lower() or "schedule" in body.lower():
                            conversation_manager.update_state(conversation_id, "action")

                    return res_dict
            except Exception as e:
                print(f"[ReplyEngine Error] Parsing failed: {e}. Raw response: {llm_response}")

        # Fallback if LLM fails
        fallback_body = "Got it. Let me set that up for you. Would you like to proceed?"
        conversation_manager.add_message(conversation_id, "vera", fallback_body)
        return {
            "action": "send",
            "body": fallback_body,
            "cta": "binary_yes_no",
            "rationale": "Fallback reply due to LLM error."
        }
