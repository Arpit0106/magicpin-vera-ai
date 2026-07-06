import time
from datetime import datetime
from fastapi import APIRouter, HTTPException, Response, status
from typing import Any, Dict, List

from app.models.schemas import (
    ContextPushRequest,
    ContextPushResponse,
    ContextPushConflictResponse,
    TickRequest,
    TickResponse,
    ReplyRequest,
    ReplyResponse,
    ActionModel
)
from app.storage.context_store import store
from app.services.decision_engine import decision_engine
from app.services.prompt_composer import PromptComposer
from app.services.reply_engine import ReplyEngine
from app.services.conversation_manager import conversation_manager
from app.utils.suppression_manager import suppression_manager

router = APIRouter()
START_TIME = time.time()

@router.get("/healthz")
@router.get("/v1/healthz")
async def healthz():
    """Liveness probe. Returns current uptime and counts of all loaded contexts."""
    uptime = int(time.time() - START_TIME)
    counts = store.get_counts()
    return {
        "status": "ok",
        "uptime_seconds": uptime,
        "contexts_loaded": counts
    }

@router.get("/metadata")
@router.get("/v1/metadata")
async def metadata():
    """Bot metadata endpoint displaying team information and architecture approach."""
    return {
        "team_name": "Antigravity AI",
        "team_members": ["Asus", "AI Architect"],
        "model": "gpt-4o-mini",
        "approach": "Clean architecture with a customized thread-safe context warehouse, a priority-based Decision Engine, an anti-taboo Prompt Composer with natural Hinglish code-mixing, and a multi-turn Reply Engine.",
        "contact_email": "ai-engineer@example.com",
        "version": "1.0.0",
        "submitted_at": datetime.utcnow().isoformat() + "Z"
    }

@router.post("/v1/context", response_model=Any)
async def push_context(body: ContextPushRequest, response: Response):
    """
    Idempotent endpoint to receive context push from the judge.
    Returns HTTP 200 on success, or HTTP 409 Conflict if the version is stale.
    """
    accepted, current_version = store.push(
        scope=body.scope,
        context_id=body.context_id,
        version=body.version,
        payload=body.payload
    )
    
    if not accepted:
        response.status_code = status.HTTP_409_CONFLICT
        return ContextPushConflictResponse(
            accepted=False,
            reason="stale_version",
            current_version=current_version
        )
        
    return ContextPushResponse(
        accepted=True,
        ack_id=f"ack_{body.context_id}_v{body.version}",
        stored_at=datetime.utcnow().isoformat() + "Z"
    )

@router.post("/v1/tick", response_model=TickResponse)
async def tick(body: TickRequest):
    """
    Periodic wake-up endpoint.
    Evaluates available triggers, sorts by priority, and composes action items.
    """
    resolved_candidates = decision_engine.evaluate_triggers(body.available_triggers, body.now)
    actions = []

    for category, merchant, trigger, customer, send_as in resolved_candidates:
        merchant_id = merchant["merchant_id"]
        trigger_id = trigger["id"]
        suppression_key = trigger.get("suppression_key", "")
        
        # Build proactive message
        composition = PromptComposer.compose_proactive(
            category=category,
            merchant=merchant,
            trigger=trigger,
            customer=customer,
            send_as=send_as
        )

        if not composition or not composition.get("body"):
            continue

        # Enforce unique conversation id
        conversation_id = f"conv_{merchant_id}_{trigger_id}"
        
        # Initialize conversation in tracker
        conversation_manager.get_or_create_conversation(
            conversation_id=conversation_id,
            merchant_id=merchant_id,
            customer_id=customer.get("customer_id") if customer else None,
            trigger_id=trigger_id,
            suppression_key=suppression_key
        )

        # Log bot message in tracker
        conversation_manager.add_message(conversation_id, send_as, composition["body"])

        # Record suppression to avoid double sends
        if suppression_key:
            suppression_manager.suppress(suppression_key)

        actions.append(ActionModel(
            conversation_id=conversation_id,
            merchant_id=merchant_id,
            customer_id=customer.get("customer_id") if customer else None,
            send_as=send_as,
            trigger_id=trigger_id,
            template_name=composition.get("template_name") or "vera_generic_v1",
            template_params=composition.get("template_params") or [merchant["identity"].get("owner_first_name", "Partner")],
            body=composition["body"],
            cta=composition.get("cta", "open_ended"),
            suppression_key=suppression_key,
            rationale=composition.get("rationale", "Proactive notification trigger")
        ))

    return TickResponse(actions=actions)

@router.post("/v1/reply", response_model=ReplyResponse)
async def reply(body: ReplyRequest):
    """
    Receive reply from the merchant or customer and return the next response.
    """
    res = ReplyEngine.process_reply(
        conversation_id=body.conversation_id,
        merchant_id=body.merchant_id or "",
        customer_id=body.customer_id,
        from_role=body.from_role,
        message=body.message,
        turn_number=body.turn_number
    )
    
    return ReplyResponse(
        action=res.get("action", "send"),
        body=res.get("body"),
        cta=res.get("cta"),
        wait_seconds=res.get("wait_seconds"),
        rationale=res.get("rationale", "Advanced conversation turn.")
    )

