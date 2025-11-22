"""Data models for the task orchestrator POC."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from src.poc.memory.models import MeetingDelta, TopicState


class NotificationAction(BaseModel):
    """Represents an action the orchestrator wants to trigger."""

    action_type: str = "notify"  # notify | ask | escalate
    target_user: Optional[str] = None
    message: str
    severity: str = "info"  # info | warning | critical
    tags: List[str] = Field(default_factory=list)


class ProcessResult(BaseModel):
    """Result of processing one meeting delta."""

    topic: TopicState
    actions: List[NotificationAction] = Field(default_factory=list)


class ProcessDeltaRequest(MeetingDelta):
    """Alias for clarity in the API layer."""

    pass

