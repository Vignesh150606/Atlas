from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.utils.time import utc_now

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message text")
    conversation_id: Optional[int] = Field(None, description="Optional conversation ID")
    # Phase 12 (ARCH-TZ): the client's IANA zone name (e.g. "Asia/Kolkata").
    # Optional - a request that omits it (an older client, a test, a direct
    # API call) falls back to settings.DEFAULT_TIMEZONE (see
    # app/utils/timezone.py::resolve_zone), so this is purely additive and
    # breaks no existing caller.
    client_timezone: Optional[str] = Field(
        None, description="IANA timezone name from the client, e.g. 'Asia/Kolkata'. Falls back to DEFAULT_TIMEZONE if omitted."
    )
    # Optional client-reported local wall-clock "now", for the rare case
    # where the server's own clock and the phone's clock have drifted
    # enough to matter. Not required - by default "now" is derived from the
    # server clock converted into client_timezone, which is correct as long
    # as the two clocks roughly agree (true for NTP-synced phones and hosts).
    client_now: Optional[datetime] = Field(
        None, description="Optional client-reported local wall-clock time; defaults to server time converted into client_timezone."
    )

class DeviceActionSchema(BaseModel):
    """Phase 8: a directive for the Android app to execute locally (the
    backend has no device access - see app/tools/device_tools.py). At most
    one is ever attached to a ChatResponse; see Planner._build_device_tool_call
    for why this is one-per-turn."""
    tool: str = Field(..., description="Tool name that produced this directive, e.g. 'launch_app'")
    module: str = Field(..., description="Android automation module, e.g. 'app_manager'")
    action: str = Field(..., description="Action within that module, e.g. 'launch_app'")
    args: Dict[str, Any] = Field(default_factory=dict, description="Action arguments")
    requires_confirmation: bool = Field(
        False,
        description=(
            "Phase 9 / Security: True when this action has a real-world or "
            "data-loss consequence (e.g. dialing a number, overwriting the "
            "clipboard) and the client should get explicit user confirmation "
            "before executing it rather than firing it silently. The backend "
            "cannot itself present a confirmation dialog - this is a signal "
            "for the consuming client to act on."
        ),
    )

class ChatResponse(BaseModel):
    response: str = Field(..., description="Assistant response text")
    conversation_id: int = Field(..., description="Conversation ID")
    created_at: datetime = Field(default_factory=utc_now)
    device_action: Optional[DeviceActionSchema] = Field(
        None, description="Phase 8: device action for the Android client to execute, if this turn produced one."
    )

class DeviceActionResultRequest(BaseModel):
    """Phase 8: Android reports the outcome of a device_action back to the
    backend (the 'Result -> Memory' step of the automation flow), so it
    becomes part of conversation history and is available to future turns."""
    conversation_id: int = Field(..., description="Conversation this action belongs to")
    tool: str = Field(..., description="Tool name that produced the original directive")
    action: str = Field(..., description="Action that was executed")
    success: bool = Field(..., description="Whether the action succeeded on-device")
    summary: str = Field(..., description="Short human-readable outcome, e.g. 'Opened WhatsApp' or 'App not found'")
    details: Dict[str, Any] = Field(default_factory=dict, description="Optional structured extra data (e.g. now-playing track info)")

class MessageSchema(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
