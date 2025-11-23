"""MongoDB store for the integration layer POC."""

from __future__ import annotations

import os
from typing import List, Optional
from uuid import uuid4
from datetime import datetime

from pymongo import MongoClient
from pymongo.collection import Collection

from .models import ContextCreate, ContextEntry, Member, MemberCreate, Topic, TopicCreate


def get_mongo_client() -> MongoClient:
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    return MongoClient(uri)


class IntegrationStore:
    """Thin wrapper around Mongo collections."""

    def __init__(self, client: Optional[MongoClient] = None, db_name: str = "langmanus_poc") -> None:
        self.client = client or get_mongo_client()
        db = self.client[db_name]
        self.topics: Collection = db["topics"]
        self.members: Collection = db["members"]
        self.contexts: Collection = db["contexts"]

        self.topics.create_index("topic_id", unique=True)
        self.members.create_index([("topic_id", 1), ("user_id", 1)], unique=True)
        self.contexts.create_index("topic_id")

    # Topic ops
    def create_topic(self, payload: TopicCreate) -> Topic:
        topic_id = payload.topic_id or str(uuid4())
        doc = {
            "topic_id": topic_id,
            "title": payload.title,
            "description": payload.description,
            "goal": payload.goal,
        }
        self.topics.insert_one(doc)
        return Topic(**doc)

    def list_topics(self) -> List[Topic]:
        return [Topic(**doc) for doc in self.topics.find({}).sort("title")]

    def get_topic(self, topic_id: str) -> Optional[Topic]:
        doc = self.topics.find_one({"topic_id": topic_id})
        return Topic(**doc) if doc else None

    # Member ops
    def add_member(self, topic_id: str, payload: MemberCreate) -> Member:
        doc = {
            "topic_id": topic_id,
            "user_id": payload.user_id,
            "display_name": payload.display_name,
            "role": payload.role,
            "responsibilities": payload.responsibilities,
        }
        self.members.update_one(
            {"topic_id": topic_id, "user_id": payload.user_id},
            {"$set": doc},
            upsert=True,
        )
        return Member(**doc)

    def list_members(self, topic_id: str) -> List[Member]:
        return [Member(**doc) for doc in self.members.find({"topic_id": topic_id}).sort("user_id")]

    # Context ops
    def add_context(self, topic_id: str, payload: ContextCreate) -> ContextEntry:
        doc = {
            "_id": str(uuid4()),
            "topic_id": topic_id,
            "author": payload.author,
            "text": payload.text,
            "tags": payload.tags,
            "source": payload.source,
            "created_at": datetime.utcnow(),
        }
        self.contexts.insert_one(doc)
        return ContextEntry(**doc)

    def list_context(self, topic_id: str, limit: int = 50) -> List[ContextEntry]:
        cursor = self.contexts.find({"topic_id": topic_id}).sort("created_at", -1).limit(limit)
        return [ContextEntry(**doc) for doc in cursor]

    def list_context_range(
        self, topic_id: str, start_date: datetime, end_date: datetime
    ) -> List[ContextEntry]:
        cursor = self.contexts.find(
            {
                "topic_id": topic_id,
                "created_at": {"$gte": start_date, "$lte": end_date},
            }
        ).sort("created_at", 1)
        return [ContextEntry(**doc) for doc in cursor]

    def reset(self) -> None:
        self.topics.drop()
        self.members.drop()
        self.contexts.drop()
        self.topics = self.client[self.topics.database.name]["topics"]
        self.members = self.client[self.members.database.name]["members"]
        self.contexts = self.client[self.contexts.database.name]["contexts"]
        self.topics.create_index("topic_id", unique=True)
        self.members.create_index([("topic_id", 1), ("user_id", 1)], unique=True)
        self.contexts.create_index("topic_id")
