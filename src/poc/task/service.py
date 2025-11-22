"""Core logic for the task orchestrator POC."""

from __future__ import annotations

from typing import List, Optional

from src.poc.memory.models import MeetingDelta, TopicMember, TopicState
from src.poc.memory.service import MemoryService
from .models import NotificationAction, ProcessResult
from src.agents.llm import get_llm_by_type
import json


class TaskOrchestrator:
    """Very small rule-based orchestrator over meeting deltas."""

    def __init__(self, memory_service: Optional[MemoryService] = None, llm=None) -> None:
        self.memory_service = memory_service or MemoryService()
        self.llm = llm or get_llm_by_type("reasoning")

    def process_delta(self, topic_id: str, delta: MeetingDelta) -> ProcessResult:
        """Ingest meeting delta into memory and produce actions."""
        topic = self.memory_service.ingest_meeting_delta(topic_id, delta)
        actions: List[NotificationAction] = []
        actions.extend(self._llm_actions(topic, delta))
        if not actions:
            actions.extend(self._task_actions(topic, delta))
            actions.extend(self._risk_actions(topic, delta))
            actions.extend(self._decision_actions(topic, delta))
        return ProcessResult(topic=topic, actions=actions)

    def _task_actions(
        self, topic: TopicState, delta: MeetingDelta
    ) -> List[NotificationAction]:
        actions: List[NotificationAction] = []
        for task in delta.tasks:
            target = task.owner or None
            message = f"新任务: {task.title}"
            if task.due:
                message += f"，截止 {task.due}"
            if delta.meeting_id:
                message += f"（来自会议 {delta.meeting_id}）"
            actions.append(
                NotificationAction(
                    action_type="notify",
                    target_user=target,
                    message=message,
                    severity="info",
                    tags=task.tags,
                )
            )
        return actions

    def _risk_actions(
        self, topic: TopicState, delta: MeetingDelta
    ) -> List[NotificationAction]:
        actions: List[NotificationAction] = []
        pm_users = self._members_with_role(topic, {"pm", "owner", "admin"})
        targets = pm_users or [m.user_id for m in topic.members]

        for risk in delta.risks:
            for user in targets:
                msg = risk.text
                if delta.meeting_id:
                    msg = f"{msg}（会议 {delta.meeting_id}）"
                actions.append(
                    NotificationAction(
                        action_type="notify",
                        target_user=user,
                        message=f"风险提醒: {msg}",
                        severity="warning",
                        tags=risk.tags,
                    )
                )
        return actions

    def _decision_actions(
        self, topic: TopicState, delta: MeetingDelta
    ) -> List[NotificationAction]:
        actions: List[NotificationAction] = []
        members = [m.user_id for m in topic.members]
        for decision in delta.decisions:
            targets = decision.actors or members
            for user in targets:
                msg = decision.text
                if delta.meeting_id:
                    msg = f"{msg}（会议 {delta.meeting_id}）"
                actions.append(
                    NotificationAction(
                        action_type="notify",
                        target_user=user,
                        message=f"决策更新: {msg}",
                        severity="info",
                        tags=decision.tags,
                    )
                )
        return actions

    def _members_with_role(
        self, topic: TopicState, roles: set[str]
    ) -> List[str]:
        normalized = {r.lower() for r in roles}
        users: List[str] = []
        for member in topic.members:
            role = member.role.lower() if member.role else ""
            if role in normalized:
                users.append(member.user_id)
        return users

    def _llm_actions(
        self, topic: TopicState, delta: MeetingDelta
    ) -> List[NotificationAction]:
        """Use LLM to reason actions; fall back to rule-based if parse fails."""
        members_summary = [
            f"- {m.user_id} ({m.role or 'member'}): {', '.join(m.responsibilities) if m.responsibilities else '无职责标签'}"
            for m in topic.members
        ]
        prompt = f"""
你是项目经理助手，根据会议增量 + 主题上下文生成“动作列表”，用 JSON 数组返回，每个元素：
{{"action_type": "notify"|"ask"|"escalate", "target_user": "<user_id 或 all>", "message": "...", "severity": "info|warning|critical", "tags": ["..."]}}
规则：
- 高风险/阻塞用 warning/critical
- 不要编造未在上下文出现的用户
- 如需澄清，action_type 用 ask，message 用问题句
- 如果内容很普通，可返回空数组

主题信息：
- title: {topic.title}
- goal: {topic.goal or "未提供"}
- members:
{chr(10).join(members_summary) or '无'}
- 最近摘要:
{chr(10).join(topic.recent_notes[:5]) or '无'}

会议增量：
{delta.model_dump()}

只返回 JSON 数组，不要代码块。
"""
        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            parsed = json.loads(content)
            actions: List[NotificationAction] = []
            for item in parsed:
                actions.append(
                    NotificationAction(
                        action_type=item.get("action_type", "notify"),
                        target_user=item.get("target_user"),
                        message=item.get("message", ""),
                        severity=item.get("severity", "info"),
                        tags=item.get("tags", []),
                    )
                )
            return actions
        except Exception:
            return []
