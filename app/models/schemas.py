from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class ContextPushRequest(BaseModel):
    scope: str = Field(..., description="Scope of the context: category, merchant, customer, or trigger")
    context_id: str = Field(..., description="Unique identifier for the context object")
    version: int = Field(..., description="Version of the context data")
    payload: Dict[str, Any] = Field(..., description="Full context object payload")
    delivered_at: str = Field(..., description="ISO timestamp of delivery")

class ContextPushResponse(BaseModel):
    accepted: bool
    ack_id: str
    stored_at: str

class ContextPushConflictResponse(BaseModel):
    accepted: bool = False
    reason: str = "stale_version"
    current_version: int

class ActionModel(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: str = "vera"  # "vera" or "merchant_on_behalf"
    trigger_id: str
    template_name: Optional[str] = None
    template_params: Optional[List[str]] = None
    body: str
    cta: str
    suppression_key: str
    rationale: str

class TickRequest(BaseModel):
    now: str
    available_triggers: List[str] = Field(default_factory=list)

class TickResponse(BaseModel):
    actions: List[ActionModel] = Field(default_factory=list)

class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str  # "merchant" or "customer"
    message: str
    received_at: str
    turn_number: int

class ReplyResponse(BaseModel):
    action: str  # "send", "wait", "end"
    body: Optional[str] = None
    cta: Optional[str] = None
    wait_seconds: Optional[int] = None
    rationale: str
