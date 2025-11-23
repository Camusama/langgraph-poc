"""Core logic for the task orchestrator POC."""

from __future__ import annotations

from typing import List, Optional
import logging

from src.poc.memory.models import MeetingDelta, TopicMember, TopicState
from src.poc.memory.service import MemoryService
from .models import NotificationAction, ProcessResult
from src.agents.llm import get_llm_by_type
import json
from src.poc.assets_loader import load_assets_by_date
from src.poc.integration.service import IntegrationService

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


class TaskOrchestrator:
    """Very small rule-based orchestrator over meeting deltas."""

    def __init__(
        self,
        memory_service: Optional[MemoryService] = None,
        llm=None,
        integration_service: Optional[IntegrationService] = None,
    ) -> None:
        self.memory_service = memory_service or MemoryService()
        self.llm = llm or get_llm_by_type("reasoning")
        self.integration_service = integration_service or IntegrationService()

    def process_delta(self, topic_id: str, delta: MeetingDelta) -> ProcessResult:
        """Ingest meeting delta into memory and produce actions."""
        topic = self.memory_service.ingest_meeting_delta(topic_id, delta)
        actions: List[NotificationAction] = []
        actions.extend(self._llm_actions(topic_id, topic, delta))
        if not actions:
            actions.extend(self._task_actions(topic, delta))
            actions.extend(self._risk_actions(topic, delta))
            actions.extend(self._decision_actions(topic, delta))
        return ProcessResult(topic=topic, actions=actions)

    def process_for_user(self, topic_id: str, user_id: str) -> ProcessResult:
        """Generate actions for a user based on current memory + recent context (no new ingest)."""
        topic = self.memory_service.get_topic(topic_id)
        synthetic_delta = MeetingDelta(meeting_id="on-demand", summary="on-demand actions", notes=[])
        actions = self._llm_actions(
            topic_id, topic, synthetic_delta, extra_context=""
        )
        if not actions:
            # build a lightweight transcript from memory + recent context for heuristic extraction
            memory_slice = self.memory_service.list_memory_entries(topic_id, limit=40)
            memory_text = "\n".join([f"{item.type}: {item.text}" for item in memory_slice])
            recent_ctx_entries = []
            try:
                recent_ctx_entries = self.integration_service.list_context_recent(topic_id, limit=20)
            except Exception:
                recent_ctx_entries = []
            recent_ctx_text = "\n".join([f"{c.source or 'ctx'}: {c.text}" for c in recent_ctx_entries])
            transcript = "\n".join([memory_text, recent_ctx_text])
            actions = self._heuristic_actions(topic, transcript, user_id, "on-demand", [])
        if not actions:
            actions.append(
                NotificationAction(
                    action_type="notify",
                    target_user=user_id,
                    message="当前没有新的与您相关的动作。",
                    severity="info",
                    tags=["fallback"],
                )
            )
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
        self, topic_id: str, topic: TopicState, delta: MeetingDelta, extra_context: str = ""
    ) -> List[NotificationAction]:
        """Use LLM to reason actions; fall back to rule-based if parse fails.

        Inputs:
        - memory_slice: 持久的记忆（结构化、低噪）
        - recent_context: 最近的上下文原文片段（高新鲜度）
        """
        members_summary = [
            f"- {m.user_id} ({m.role or 'member'}): {', '.join(m.responsibilities) if m.responsibilities else '无职责标签'}"
            for m in topic.members
        ]
        memory_slice = self.memory_service.list_memory_entries(topic_id, limit=40)
        memory_text = "\n".join(
            [f"[{item.type}] {item.text}" for item in memory_slice]
        )
        recent_ctx_entries = []
        try:
            recent_ctx_entries = self.integration_service.list_context_recent(
                topic_id, limit=20
            )
        except Exception:
            recent_ctx_entries = []
        recent_ctx_text = "\n".join(
            [f"[{c.source or 'ctx'}] {c.text}" for c in recent_ctx_entries]
        )

        prompt = f"""
你是项目经理助手，基于“持久记忆 + 最近上下文”生成动作(JSON 数组)：
每个元素 {{"action_type":"notify|ask|escalate","target_user":"<user_id或all>","message":"...","severity":"info|warning|critical","tags":[],"source":"memory|context"}}
规则：优先用持久记忆判断影响，必要时用最近上下文细节；不编造用户；无关则返回空数组。

主题：
- title: {topic.title}
- goal: {topic.goal or "未提供"}
- members:
{chr(10).join(members_summary) or '无'}
- 最近摘要:
{chr(10).join(topic.recent_notes[:5]) or '无'}

持久记忆(裁剪):
{memory_text or '无'}

最近上下文(原文片段):
{recent_ctx_text or '无'}
额外上下文(当前批次):
{extra_context or '无'}

会议增量：
{delta.model_dump()}

只返回 JSON 数组。
"""
        try:
            logger.info("LLM input (actions): %s", prompt)
            content = self._call_llm(prompt)
            logger.info("LLM output (actions): %s", content)
            parsed = self._extract_json_array(content)
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
        except Exception as exc:
            logger.exception("LLM actions failed: %s", exc)
            return []

    def process_assets_for_user(
        self, topic_id: str, date_str: str, user_id: str
    ) -> ProcessResult:
        """Load assets for a date and produce user-focused actions. Ingest and action generation are decoupled."""
        assets = load_assets_by_date(date_str)
        if not assets:
            raise ValueError(f"No assets found for {date_str}")
        transcript = "\n\n".join([f"[{a['name']}] {a['content']}" for a in assets])

        # 1) Try to get a structured delta (once). If fails, fallback to synthetic.
        meeting_delta: Optional[MeetingDelta] = None
        try:
            meeting_delta = self.memory_service.generate_delta_with_llm(
                topic_id=topic_id, transcript=transcript, meeting_id=f"assets-{date_str}"
            )
        except Exception:
            meeting_delta = None

        # 2) Action generation based on current memory + recent context + extra_context transcript
        topic = self.memory_service.get_topic(topic_id)
        delta_for_actions = meeting_delta or MeetingDelta(
            meeting_id=f"assets-{date_str}", summary="assets batch", notes=[]
        )
        actions = self._llm_actions(
            topic_id, topic, delta_for_actions, extra_context=transcript
        )
        if not actions:
            actions = self._heuristic_actions(topic, transcript, user_id, date_str, assets)
        if not actions:
            titles = ", ".join([a["name"] for a in assets])
            actions.append(
                NotificationAction(
                    action_type="notify",
                    target_user=user_id,
                    message=f"今日({date_str}) 资产: {titles}。请查看是否有与你相关的事项。",
                    severity="info",
                    tags=["fallback"],
                )
            )

        # 3) Ingest best-effort (async-ish)
        try:
            if meeting_delta:
                self.memory_service.ingest_meeting_delta(topic_id, meeting_delta)
        except Exception:
            pass

        return ProcessResult(topic=topic, actions=actions)

    def _heuristic_actions(
        self, topic: TopicState, transcript: str, user_id: str, date_str: str, assets: list[dict]
    ) -> List[NotificationAction]:
        """Cheap fallback: extract actionable lines mentioning the user/email."""
        lines = [line.strip(" -•") for line in transcript.splitlines() if line.strip()]
        keywords = {user_id.lower(), user_id.split("@")[0].lower(), "marquez"}
        actions: List[NotificationAction] = []
        for line in lines:
            lower = line.lower()
            if lower.startswith("参与人") or lower.startswith("与会"):
                continue
            if ":" not in line and "：" not in line:
                continue
            if not any(k in lower for k in keywords):
                continue
            # take the part after the first colon (English or Chinese)
            parts = line.split(":", 1) if ":" in line else line.split("：", 1)
            content = parts[1].strip() if len(parts) > 1 else line
            if not content:
                continue
            actions.append(
                NotificationAction(
                    action_type="notify",
                    target_user=user_id,
                    message=f"{date_str} TODO: {content}",
                    severity="info",
                    tags=["heuristic"],
                )
            )
        return actions

    def _call_llm(self, prompt: str) -> str:
        """Call LLM with fallback to stream for models that require it."""
        try:
            resp = self.llm.invoke(prompt)
            return resp.content if hasattr(resp, "content") else str(resp)
        except Exception as exc:
            if hasattr(self.llm, "stream"):
                try:
                    chunks = []
                    for chunk in self.llm.stream(prompt):
                        part = getattr(chunk, "content", None)
                        if part:
                            chunks.append(part)
                    if chunks:
                        return "".join(chunks)
                except Exception:
                    pass
            raise exc

    def _extract_json_array(self, content: str):
        """Extract JSON array from raw model output, tolerant to code fences and preamble."""
        cleaned = content.strip()
        # strip code fences
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if "\n" in cleaned:
                cleaned = cleaned.split("\n", 1)[1]
        # find the first '[' or '{'
        idx_list = [pos for pos in (cleaned.find("["), cleaned.find("{")) if pos != -1]
        start = min(idx_list) if idx_list else 0
        cleaned = cleaned[start:]
        return json.loads(cleaned)
