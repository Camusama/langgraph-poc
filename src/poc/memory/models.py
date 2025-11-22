"""Data models for the memory layer POC."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC time for timestamps."""
    return datetime.utcnow()


class TopicMember(BaseModel):
    """Minimal representation of a user inside a topic."""

    user_id: str
    display_name: Optional[str] = None
    role: Optional[str] = None
    responsibilities: List[str] = Field(default_factory=list)


class ContextDelta(BaseModel):
    """Atomic delta extracted from a meeting or chat."""

    text: str
    actors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class TaskDelta(BaseModel):
    """Incoming task from a meeting delta."""

    title: str
    owner: Optional[str] = None
    due: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    related_actors: List[str] = Field(default_factory=list)


class MeetingDelta(BaseModel):
    """Structured payload representing one meeting's change set."""

    meeting_id: Optional[str] = None
    summary: Optional[str] = None
    facts: List[ContextDelta] = Field(default_factory=list)
    decisions: List[ContextDelta] = Field(default_factory=list)
    risks: List[ContextDelta] = Field(default_factory=list)
    tasks: List[TaskDelta] = Field(default_factory=list)
    notes: List[ContextDelta] = Field(default_factory=list)


class ContextItem(BaseModel):
    """Normalized context item stored in the super context."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str  # fact | decision | risk | task | note
    text: str
    actors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    meta: Dict[str, str] = Field(default_factory=dict)


class TopicState(BaseModel):
    """State of one project/topic."""

    topic_id: str
    title: str
    goal: Optional[str] = None
    members: List[TopicMember] = Field(default_factory=list)
    context: List[ContextItem] = Field(default_factory=list)
    recent_notes: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class PersonalizedView(BaseModel):
    """User-specific projection of the super context."""

    topic_id: str
    user_id: str
    highlights: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    mentions: List[str] = Field(default_factory=list)

