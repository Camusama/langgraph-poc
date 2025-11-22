"""Data models for the integration layer POC."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TopicCreate(BaseModel):
    topic_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    goal: Optional[str] = None


class Topic(BaseModel):
    topic_id: str
    title: str
    description: Optional[str] = None
    goal: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MemberCreate(BaseModel):
    user_id: str
    display_name: Optional[str] = None
    role: Optional[str] = None
    responsibilities: List[str] = Field(default_factory=list)


class Member(BaseModel):
    topic_id: str
    user_id: str
    display_name: Optional[str] = None
    role: Optional[str] = None
    responsibilities: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContextCreate(BaseModel):
    author: str
    text: str
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None


class ContextEntry(BaseModel):
    id: str = Field(alias="_id")
    topic_id: str
    author: str
    text: str
    tags: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True

