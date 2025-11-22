"""FastAPI router exposing the task orchestrator POC."""

from fastapi import APIRouter, HTTPException

from src.poc.memory.api import memory_service
from src.poc.memory.models import MeetingDelta
from .models import ProcessResult
from .service import TaskOrchestrator

router = APIRouter(prefix="/api/poc/task", tags=["poc-task"])
orchestrator = TaskOrchestrator(memory_service=memory_service)


@router.post("/topics/{topic_id}/process", response_model=ProcessResult)
def process_delta(topic_id: str, payload: MeetingDelta) -> ProcessResult:
    """Ingest a meeting delta and get orchestrator actions."""
    try:
        return orchestrator.process_delta(topic_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

