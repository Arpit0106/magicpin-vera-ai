import time
from datetime import datetime
from fastapi import APIRouter, HTTPException, Response, status
from typing import Any, Dict

from app.models.schemas import (
    ContextPushRequest,
    ContextPushResponse,
    ContextPushConflictResponse,
    TickRequest,
    TickResponse,
    ReplyRequest,
    ReplyResponse
)
from app.storage.context_store import store

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
    Delegates trigger evaluation to the DecisionEngine (stubbed for now).
    """
    # DecisionEngine integration will go here in Task 3
    return TickResponse(actions=[])

@router.post("/v1/reply", response_model=ReplyResponse)
async def reply(body: ReplyRequest):
    """
    Receive reply from the merchant or customer.
    Delegates processing to the ReplyEngine (stubbed for now).
    """
    # ReplyEngine integration will go here in Task 5
    return ReplyResponse(
        action="send",
        body="Stub: Hello, I am Vera. I received your message.",
        cta="open_ended",
        rationale="Stub response for contract validation."
    )
