"""Core logic for the memory layer POC."""

from __future__ import annotations

from typing import List, Optional
from uuid import uuid4
import json

from .models import (
    ContextDelta,
    ContextItem,
    MeetingDelta,
    PersonalizedView,
    TaskDelta,
    TopicMember,
    TopicState,
)
from .store import MemoryStore
from src.agents.llm import get_llm_by_type


class MemoryService:
    """Orchestrates topic memory creation and updates."""

    def __init__(self, store: Optional[MemoryStore] = None, llm=None) -> None:
        self.store = store or MemoryStore()
        self.llm = llm or get_llm_by_type("basic")

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
        return self.store.upsert_topic(topic)

    def get_topic(self, topic_id: str) -> TopicState:
        topic = self.store.get_topic(topic_id)
        if not topic:
            raise ValueError(f"Topic {topic_id} not found")
        return topic

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
        recent_notes = "\n".join(topic.recent_notes[:5])
        prompt = f"""
你是项目记忆提取助手。根据会议内容提炼结构化增量，输出 JSON，字段：facts, decisions, risks, tasks, notes。
- facts/decisions/risks/notes: 数组，元素形如 {{"text": "...", "actors": ["user"], "tags": ["..."]}}
- tasks: 数组，元素形如 {{"title": "...", "owner": "user_id", "due": "YYYY-MM-DD", "notes": "...", "tags": ["..."], "related_actors": ["user_id"]}}
要求：
- 只填有用内容，没提到就留空数组
- 文本精简，不要添加额外解释

项目信息：
- topic: {topic.title}
- goal: {topic.goal or "未提供"}
- members:
{chr(10).join(member_lines) or '无'}
- 最近摘要:
{recent_notes or '无'}

会议内容：
{transcript}

请直接输出 JSON，不要包裹代码块。
"""
        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            data = json.loads(content)
            data["meeting_id"] = meeting_id
            return MeetingDelta(**data)
        except Exception as exc:
            raise ValueError(f"LLM 生成 MeetingDelta 失败: {exc}")

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
