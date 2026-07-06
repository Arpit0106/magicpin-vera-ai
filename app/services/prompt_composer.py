import json
import re
from typing import Any, Dict, List, Optional, Tuple
from app.utils.llm_client import llm_client

class PromptComposer:
    SYSTEM_PROMPT = """You are the composition engine for "Vera", magicpin's merchant AI assistant.
Your task is to write high-engagement WhatsApp messages based on four context layers: Category, Merchant, Trigger, and Customer (optional).
You must return a valid JSON object with the exact keys:
{
  "body": "The WhatsApp message text. DO NOT include any URLs/links. Enforce natural code-mix language if requested.",
  "cta": "The CTA kind: open_ended, binary_yes_no, multi_choice_slot, or none",
  "rationale": "One sentence explaining why this wording was chosen based on the contexts.",
  "template_name": "vera_generic_v1",
  "template_params": ["List of strings representing parameters to fill the WhatsApp template"]
}

CRITICAL SCORING RUBRICS:
1. SPECIFICITY (10/10):
   - Use concrete, verifiable facts from the contexts (numbers, dates, peer benchmark comparisons). Never say "increase your sales" generically.
   - For research digests, cite the source EXACTLY (e.g. "— JIDA Oct 2026, p.14") and mention specific metrics (e.g. "38% lower caries").
   - Use actual catalog prices/services from Category catalog (e.g. "Dental Cleaning @ ₹299"). Do not invent offers.
   
2. CATEGORY FIT (10/10):
   - Enforce voice rules strictly.
   - Dentists: Clinical-peer tone, collegial, respectful. Salutations must use "Dr. {first_name}" or "Doc". Taboos: NEVER use "guaranteed", "100% safe", "completely cure", "miracle", "best in city", "doctor approved".
   - Salons: Warm, friendly, growth-oriented.
   - Gyms: Motivational, coaching-peer.
   - Restaurants: Operator-to-operator, fast-paced.
   - Pharmacies: Precise, compliance-aware.

3. MERCHANT FIT (10/10):
   - Personalize with merchant's/customer's name.
   - Match language preference. If "hi" or "hi-en mix" (Hinglish) is in preferred languages/identity, mix Hindi-English naturally. If pure "en", use English.
   - Example Hinglish: "Dr. Meera, JIDA's Oct issue release hua hai. Apke adult patients ke liye ek important study aayi hai..."

4. TRIGGER RELEVANCE (10/10):
   - Explicitly connect why you are writing NOW using the trigger payload (e.g., calls dip by 50% vs baseline, upcoming Diwali festival, 6-month recall is due).

5. ENGAGEMENT COMPULSION (10/10):
   - Leverage loss aversion ("6,777 missed searches"), social proof ("3 dentists in Lajpat Nagar started this"), curiosity, or effort externalization ("I've drafted a post, reply YES to publish").
   - Land the call-to-action (CTA) in the last sentence. Make it a single, low-friction request.

6. SAFETY:
   - NEVER include any URLs or web links. Doing so will violate Meta policy and incur penalties.
"""

    @staticmethod
    def compose_proactive(
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any],
        customer: Optional[Dict[str, Any]] = None,
        send_as: str = "vera"
    ) -> Dict[str, Any]:
        """
        Formats contexts into a prompt, calls LLM, and returns the parsed Composed Message dict.
        """
        # Build user prompt
        user_prompt = f"""Generate a message to send as: '{send_as}'
=== CATEGORY CONTEXT ===
Slug: {category.get('slug')}
Voice rules: {json.dumps(category.get('voice', {}))}
Offer Catalog: {json.dumps(category.get('offer_catalog', []))}
Peer Stats: {json.dumps(category.get('peer_stats', {}))}
Digest: {json.dumps(category.get('digest', []))}
Seasonal Beats: {json.dumps(category.get('seasonal_beats', []))}
Trend Signals: {json.dumps(category.get('trend_signals', []))}

=== MERCHANT CONTEXT ===
ID: {merchant.get('merchant_id')}
Identity: {json.dumps(merchant.get('identity', {}))}
Subscription: {json.dumps(merchant.get('subscription', {}))}
Performance: {json.dumps(merchant.get('performance', {}))}
Active Offers: {json.dumps([o for o in merchant.get('offers', []) if o.get('status') == 'active'])}
Signals: {json.dumps(merchant.get('signals', []))}
Review Themes: {json.dumps(merchant.get('review_themes', []))}

=== TRIGGER CONTEXT ===
Kind: {trigger.get('kind')}
Payload: {json.dumps(trigger.get('payload', {}))}
Urgency: {trigger.get('urgency')}
Suppression Key: {trigger.get('suppression_key')}

=== CUSTOMER CONTEXT ===
{json.dumps(customer) if customer else "None"}

Please produce the JSON output. Enforce Hinglish mix if language list has 'hi' or customer preference has 'hi' or 'mix'."""

        messages = [
            {"role": "system", "content": PromptComposer.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        llm_response = llm_client.complete(messages)

        # Parse LLM response
        if llm_response:
            try:
                # Find JSON block
                json_match = re.search(r'\{[\s\S]*\}', llm_response)
                if json_match:
                    res_dict = json.loads(json_match.group())
                    # Strip any accidental URLs from body
                    body = res_dict.get("body", "")
                    body = re.sub(r'https?://\S+', '', body).strip()
                    res_dict["body"] = body
                    return res_dict
            except Exception as e:
                print(f"[PromptComposer Error] Parsing failed: {e}. Raw response: {llm_response}")

        # Fail-safe static composition fallback
        return PromptComposer._fallback_composition(category, merchant, trigger, customer, send_as)

    @staticmethod
    def _fallback_composition(
        category: Dict[str, Any],
        merchant: Dict[str, Any],
        trigger: Dict[str, Any],
        customer: Optional[Dict[str, Any]],
        send_as: str
    ) -> Dict[str, Any]:
        """Provides a safe, rubric-compliant fallback message if the LLM fails."""
        merchant_name = merchant.get("identity", {}).get("name", "partner")
        owner_name = merchant.get("identity", {}).get("owner_first_name", "Partner")
        category_slug = category.get("slug", "")

        # Category-appropriate greeting/names
        salutation = f"Dr. {owner_name}" if category_slug == "dentists" else owner_name
        
        # Build simple Hinglish or English based on pref
        languages = merchant.get("identity", {}).get("languages", ["en"])
        use_hinglish = "hi" in languages or (customer and "hi" in customer.get("identity", {}).get("language_pref", ""))

        if send_as == "merchant_on_behalf" and customer:
            cust_name = customer.get("identity", {}).get("name", "customer")
            if use_hinglish:
                body = f"Hi {cust_name}, {merchant_name} se message. Apka checkup recall due hai. Kya hum is week ke liye appointment book karein?"
            else:
                body = f"Hi {cust_name}, this is {merchant_name}. Your regular dental checkup is now due. Would you like to schedule an appointment this week?"
            return {
                "body": body,
                "cta": "binary_yes_no",
                "rationale": "Fallback customer recall reminder",
                "template_name": "merchant_recall_reminder_v1",
                "template_params": [cust_name, merchant_name]
            }
        else:
            # Merchant-facing fallback
            if use_hinglish:
                body = f"Hi {salutation}, aapse share karne ke liye new updates hain. Kya hum check karein?"
            else:
                body = f"Hi {salutation}, we have new performance updates ready for {merchant_name}. Would you like to review them?"
            return {
                "body": body,
                "cta": "binary_yes_no",
                "rationale": "Fallback merchant engagement pitch",
                "template_name": "vera_generic_v1",
                "template_params": [salutation]
            }