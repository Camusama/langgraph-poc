"""Mongo persistence for memory context items."""

from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional

from pymongo import MongoClient

from .models import ContextItem


def get_mongo_client() -> MongoClient:
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    return MongoClient(uri)


class MemoryMongoStore:
    def __init__(self, client: Optional[MongoClient] = None, db_name: str = "langmanus_poc") -> None:
        self.client = client or get_mongo_client()
        self.collection = self.client[db_name]["memory_entries"]
        self.collection.create_index([("topic_id", 1), ("created_at", 1)])

    def save_items(self, topic_id: str, items: List[ContextItem]) -> None:
        if not items:
            return
        docs = []
        for item in items:
            doc = item.model_dump()
            doc["text"] = item.text
            doc["created_at"] = item.created_at or datetime.utcnow()
            doc["topic_id"] = topic_id
            docs.append(doc)
        self.collection.insert_many(docs)

    def list_between(self, topic_id: str, start: datetime, end: datetime) -> List[ContextItem]:
        cursor = self.collection.find(
            {"topic_id": topic_id, "created_at": {"$gte": start, "$lte": end}}
        ).sort("created_at", 1)
        return [ContextItem(**doc) for doc in cursor]

    def list_recent(self, topic_id: str, limit: int = 200) -> List[ContextItem]:
        cursor = self.collection.find({"topic_id": topic_id}).sort("created_at", -1).limit(limit)
        return [ContextItem(**doc) for doc in cursor]

    def clear(self) -> None:
        self.collection.drop()
        self.collection = self.client[self.collection.database.name]["memory_entries"]
        self.collection.create_index([("topic_id", 1), ("created_at", 1)])
