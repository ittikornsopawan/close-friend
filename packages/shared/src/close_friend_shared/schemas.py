from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaskMessage(BaseModel):
    """Payload enqueued by app/api and consumed by app/worker."""

    task_id: str
    name: str
    payload: dict = {}


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(StrEnum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class ChatMessage(BaseModel):
    """A single message in a conversation, stored as one JSON element in the
    `cf:conv:{conversation_id}:messages` Redis list."""

    id: str
    role: MessageRole
    content: str
    status: MessageStatus
    created_at: datetime
