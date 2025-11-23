"""Core logic for the memory layer POC."""

from __future__ import annotations

from typing import List, Optional
from uuid import uuid4
import json
from datetime import datetime

from .models import (
    ContextDelta,
    ContextItem,
    MeetingDelta,
    PersonalizedView,
    TaskDelta,
    TopicMember,
    TopicState,
    utc_now,
)
from .store import MemoryStore
from .mongo_store import MemoryMongoStore
from src.agents.llm import get_llm_by_type


class MemoryService:
    """Orchestrates topic memory creation and updates."""

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        llm=None,
        mongo_store: Optional[MemoryMongoStore] = None,
    ) -> None:
        self.store = store or MemoryStore()
        self.llm = llm or get_llm_by_type("basic")
        self.mongo_store = mongo_store or MemoryMongoStore()

    def create_topic(
        self,
        title: str,
        goal: Optional[str] = None,
        members: Optional[List[TopicMember]] = None,
        topic_id: Optional[str] = None,
    ) -> TopicState:
        topic = TopicState(
            topic_id=topic_id or str(uuid4()),
            title=title,
            goal=goal,
            members=members or [],
        )
        return self.store.upsert_topic(topic)

    def ingest_meeting_delta(
        self, topic_id: str, delta: MeetingDelta
    ) -> TopicState:
        topic = self.store.get_topic(topic_id)
        if not topic:
            raise ValueError(f"Topic {topic_id} not found")

        normalized: List[ContextItem] = []
        normalized.extend(
            self._normalize_group("fact", delta.facts, delta.meeting_id)
        )
        normalized.extend(
            self._normalize_group("decision", delta.decisions, delta.meeting_id)
        )
        normalized.extend(
            self._normalize_group("risk", delta.risks, delta.meeting_id)
        )
        normalized.extend(self._normalize_tasks(delta.tasks, delta.meeting_id))
        normalized.extend(self._normalize_group("note", delta.notes, delta.meeting_id))

        if delta.summary:
            topic.recent_notes.insert(
                0, delta.summary.strip()
            )
            topic.recent_notes = topic.recent_notes[:10]

        topic.context.extend(normalized)
        topic.context.sort(key=lambda item: item.created_at)
        # persist
        if self.mongo_store:
            self.mongo_store.save_items(topic_id, normalized)
        return self.store.upsert_topic(topic)

    def get_topic(self, topic_id: str) -> TopicState:
        topic = self.store.get_topic(topic_id)
        if not topic:
            raise ValueError(f"Topic {topic_id} not found")
        return topic

    def reset(self) -> None:
        """Clear in-memory topics."""
        self.store.clear()
        if self.mongo_store:
            self.mongo_store.clear()

    def list_topics(self) -> List[TopicState]:
        return self.store.list_topics()

    def build_personal_view(self, topic_id: str, user_id: str) -> PersonalizedView:
        topic = self.get_topic(topic_id)
        member = next((m for m in topic.members if m.user_id == user_id), None)

        highlights: List[str] = []
        action_items: List[str] = []
        risks: List[str] = []
        decisions: List[str] = []
        mentions: List[str] = []

        for item in reversed(topic.context):
            if len(highlights) >= 8:
                break
            relevance = self._is_relevant(item, user_id, member)
            formatted = self._format_item(item)
            if not relevance and len(highlights) < 3:
                highlights.append(formatted)
            if relevance:
                mentions.append(formatted)
                if item.type == "task":
                    action_items.append(formatted)
                if item.type == "risk":
                    risks.append(formatted)
                if item.type == "decision":
                    decisions.append(formatted)
                if item.type in {"fact", "note"} and formatted not in highlights:
                    highlights.append(formatted)

        return PersonalizedView(
            topic_id=topic_id,
            user_id=user_id,
            highlights=highlights[:8],
            action_items=action_items[:5],
            risks=risks[:5],
            decisions=decisions[:5],
            mentions=mentions[:10],
        )

    def generate_delta_with_llm(
        self, topic_id: str, transcript: str, meeting_id: Optional[str] = None
    ) -> MeetingDelta:
        """Use LLM to summarize a meeting transcript into a MeetingDelta."""
        topic = self.get_topic(topic_id)
        member_lines = [
            f"- {m.user_id} ({m.role or 'member'}): {', '.join(m.responsibilities) if m.responsibilities else '无职责标签'}"
            for m in topic.members
        ]
        member_ids = [m.user_id for m in topic.members]
        recent_notes = "\n".join(topic.recent_notes[:5])
        prompt = f"""
将会议内容压缩为 JSON，字段：facts, decisions, risks, tasks, notes。
- facts/decisions/risks/notes: 数组，元素 {{"text":"…","actors":["user_id"],"tags":["…"]}}
- tasks: 数组，元素 {{"title":"…","owner":"user_id","due":"YYYY-MM-DD","notes":"…","tags":["…"],"related_actors":["user_id"]}}
过滤要求：
- 仅保留与这些成员相关的内容（actors/owner/related_actors/文本提到）：{member_ids or '无'}
- 不相关的内容直接丢弃
- 尽量精简，每个字段最多 5 条
只输出 JSON，无解释，无代码块。内容要短。
会议内容：
{transcript}
"""
        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            data = json.loads(content)
            data["meeting_id"] = meeting_id
            return MeetingDelta(**data)
        except Exception as exc:
            raise ValueError(f"LLM 生成 MeetingDelta 失败: {exc}")

    def ingest_context_entries(self, topic_id: str, entries) -> TopicState:
        """Ingest existing context entries (e.g., from Mongo) as notes."""
        topic = self.get_topic(topic_id)
        normalized: List[ContextItem] = []
        for entry in entries:
            normalized.append(
                ContextItem(
                    type="note",
                    text=entry.text,
                    actors=[entry.author] if entry.author else [],
                    tags=entry.tags,
                    source=entry.source,
                    created_at=getattr(entry, "created_at", utc_now()),
                )
            )
        topic.context.extend(normalized)
        topic.context.sort(key=lambda item: item.created_at)
        if self.mongo_store:
            self.mongo_store.save_items(topic_id, normalized)
        return self.store.upsert_topic(topic)

    def list_memory_entries(
        self, topic_id: str, start: Optional[str] = None, end: Optional[str] = None, limit: int = 200
    ) -> List[ContextItem]:
        """List persisted memory entries (Mongo) or fallback to in-memory context."""
        topic = self.get_topic(topic_id)
        if self.mongo_store:
            try:
                start_dt = datetime.fromisoformat(start) if start else datetime.min
                end_dt = datetime.fromisoformat(end) if end else datetime.max
                # if only date provided (YYYY-MM-DD), end_dt should include the whole day
                if end and len(end) == 10:
                    end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                if start and len(start) == 10:
                    start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                results = self.mongo_store.list_between(topic_id, start_dt, end_dt)
                if results:
                    return results[:limit]
            except Exception:
                pass
            return self.mongo_store.list_recent(topic_id, limit=limit)

        return topic.context[:limit]

    def _normalize_group(
        self, item_type: str, deltas: List[ContextDelta], source: Optional[str]
    ) -> List[ContextItem]:
        normalized: List[ContextItem] = []
        for delta in deltas:
            normalized.append(
                ContextItem(
                    type=item_type,
                    text=delta.text.strip(),
                    actors=delta.actors,
                    tags=delta.tags,
                    source=source,
                )
            )
        return normalized

    def _normalize_tasks(
        self, tasks: List[TaskDelta], source: Optional[str]
    ) -> List[ContextItem]:
        normalized: List[ContextItem] = []
        for task in tasks:
            meta = {}
            if task.owner:
                meta["owner"] = task.owner
            if task.due:
                meta["due"] = task.due
            if task.notes:
                meta["notes"] = task.notes

            text = task.title
            if task.due:
                text = f"{text} (due {task.due})"
            if task.notes:
                text = f"{text} - {task.notes}"

            normalized.append(
                ContextItem(
                    type="task",
                    text=text.strip(),
                    actors=[task.owner] if task.owner else task.related_actors,
                    tags=task.tags,
                    source=source,
                    meta=meta,
                )
            )
        return normalized

    def _is_relevant(
        self, item: ContextItem, user_id: str, member: Optional[TopicMember]
    ) -> bool:
        if user_id in item.actors:
            return True
        if item.meta.get("owner") == user_id:
            return True
        text_lower = item.text.lower()
        if member and any(
            resp.lower() in text_lower for resp in member.responsibilities
        ):
            return True
        return False

    def _format_item(self, item: ContextItem) -> str:
        prefix = item.type.upper()
        suffix = f" [source={item.source}]" if item.source else ""
        return f"{prefix}: {item.text}{suffix}"
