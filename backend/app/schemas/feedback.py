import uuid
from datetime import datetime as DateTime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str = "bug"  # bug | wish | question
    title: str
    description: str


class FeedbackUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Optional[str] = None  # open | in_progress | resolved | declined
    admin_note: Optional[str] = None


class FeedbackOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_by_user_id: uuid.UUID
    reporter_name: str
    category: str
    title: str
    description: str
    status: str
    admin_note: Optional[str]
    created_at: DateTime
    updated_at: DateTime

    model_config = ConfigDict(from_attributes=True)
