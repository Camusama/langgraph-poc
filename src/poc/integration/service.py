"""Integration service exposing CRUD over Mongo-backed store."""

from __future__ import annotations

from typing import List, Optional

from .models import ContextCreate, ContextEntry, Member, MemberCreate, Topic, TopicCreate
from .mongo_store import IntegrationStore


class IntegrationService:
    """Simple CRUD façade."""

    def __init__(self, store: Optional[IntegrationStore] = None) -> None:
        self.store = store or IntegrationStore()

    def create_topic(self, payload: TopicCreate) -> Topic:
        return self.store.create_topic(payload)

    def list_topics(self) -> List[Topic]:
        return self.store.list_topics()

    def get_topic(self, topic_id: str) -> Topic:
        topic = self.store.get_topic(topic_id)
        if not topic:
            raise ValueError(f"Topic {topic_id} not found")
        return topic

    def add_member(self, topic_id: str, payload: MemberCreate) -> Member:
        self.get_topic(topic_id)
        return self.store.add_member(topic_id, payload)

    def list_members(self, topic_id: str) -> List[Member]:
        self.get_topic(topic_id)
        return self.store.list_members(topic_id)

    def add_context(self, topic_id: str, payload: ContextCreate) -> ContextEntry:
        self.get_topic(topic_id)
        return self.store.add_context(topic_id, payload)

    def list_context(self, topic_id: str, limit: int = 50) -> List[ContextEntry]:
        self.get_topic(topic_id)
        return self.store.list_context(topic_id, limit=limit)

