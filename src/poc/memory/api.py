"""FastAPI router exposing the memory layer POC endpoints."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .models import MeetingDelta, TopicMember, TopicState
from .service import MemoryService

router = APIRouter(prefix="/api/poc/memory", tags=["poc-memory"])
memory_service = MemoryService()


class TopicCreatePayload(BaseModel):
    title: str
    goal: Optional[str] = None
    members: List[TopicMember] = Field(default_factory=list)
    topic_id: Optional[str] = None


class IngestRawPayload(BaseModel):
    meeting_id: Optional[str] = None
    transcript: str


@router.post("/topics", response_model=TopicState)
def create_topic(payload: TopicCreatePayload) -> TopicState:
    return memory_service.create_topic(
        title=payload.title,
        goal=payload.goal,
        members=payload.members,
        topic_id=payload.topic_id,
    )


@router.get("/topics", response_model=List[TopicState])
def list_topics() -> List[TopicState]:
    return memory_service.list_topics()


@router.get("/topics/{topic_id}", response_model=TopicState)
def get_topic(topic_id: str) -> TopicState:
    try:
        return memory_service.get_topic(topic_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/topics/{topic_id}/ingest", response_model=TopicState)
def ingest_delta(topic_id: str, payload: MeetingDelta) -> TopicState:
    try:
        return memory_service.ingest_meeting_delta(topic_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/topics/{topic_id}/ingest_raw", response_model=TopicState)
def ingest_raw(topic_id: str, payload: IngestRawPayload) -> TopicState:
    try:
        delta = memory_service.generate_delta_with_llm(
            topic_id=topic_id,
            transcript=payload.transcript,
            meeting_id=payload.meeting_id,
        )
        return memory_service.ingest_meeting_delta(topic_id, delta)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/topics/{topic_id}/view/{user_id}")
def personal_view(topic_id: str, user_id: str):
    try:
        return memory_service.build_personal_view(topic_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/reset")
def reset_memory():
    memory_service.reset()
    return {"status": "ok"}
