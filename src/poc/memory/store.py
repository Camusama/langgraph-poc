"""A lightweight in-memory store for topic states."""

from typing import Dict, List, Optional

from .models import TopicMember, TopicState


class MemoryStore:
    """Holds topic states in-process for the POC."""

    def __init__(self) -> None:
        self._topics: Dict[str, TopicState] = {}

    def list_topics(self) -> List[TopicState]:
        return list(self._topics.values())

    def get_topic(self, topic_id: str) -> Optional[TopicState]:
        return self._topics.get(topic_id)

    def upsert_topic(self, topic: TopicState) -> TopicState:
        self._topics[topic.topic_id] = topic
        return topic

    def create_topic(
        self, topic_id: str, title: str, goal: Optional[str], members: List[TopicMember]
    ) -> TopicState:
        topic = TopicState(topic_id=topic_id, title=title, goal=goal, members=members)
        self._topics[topic_id] = topic
        return topic

