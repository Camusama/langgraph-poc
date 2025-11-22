"""FastAPI router for the integration layer POC."""

from typing import List

from fastapi import APIRouter, HTTPException, Query

from .models import ContextCreate, ContextEntry, Member, MemberCreate, Topic, TopicCreate
from .service import IntegrationService

router = APIRouter(prefix="/api/poc/integration", tags=["poc-integration"])
service = IntegrationService()


@router.post("/topics", response_model=Topic)
def create_topic(payload: TopicCreate) -> Topic:
    return service.create_topic(payload)


@router.get("/topics", response_model=List[Topic])
def list_topics() -> List[Topic]:
    return service.list_topics()


@router.get("/topics/{topic_id}", response_model=Topic)
def get_topic(topic_id: str) -> Topic:
    try:
        return service.get_topic(topic_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/topics/{topic_id}/members", response_model=Member)
def add_member(topic_id: str, payload: MemberCreate) -> Member:
    try:
        return service.add_member(topic_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/topics/{topic_id}/members", response_model=List[Member])
def list_members(topic_id: str) -> List[Member]:
    try:
        return service.list_members(topic_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/topics/{topic_id}/context", response_model=ContextEntry)
def add_context(topic_id: str, payload: ContextCreate) -> ContextEntry:
    try:
        return service.add_context(topic_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/topics/{topic_id}/context", response_model=List[ContextEntry])
def list_context(
    topic_id: str,
    limit: int = Query(50, ge=1, le=200),
) -> List[ContextEntry]:
    try:
        return service.list_context(topic_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

