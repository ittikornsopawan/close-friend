import uuid
from datetime import UTC, datetime

from close_friend_shared import ChatMessage, MessageRole, MessageStatus, conversation_messages_key
from fastapi import APIRouter
from pydantic import BaseModel

from close_friend_api.celery_client import celery_client
from close_friend_api.redis_client import redis_client

router = APIRouter(prefix="/conversations", tags=["conversations"])


class PostMessageRequest(BaseModel):
    content: str


class PostMessageResponse(BaseModel):
    user_message: ChatMessage
    assistant_message: ChatMessage


class GetMessagesResponse(BaseModel):
    messages: list[ChatMessage]


@router.post("/{conversation_id}/messages", status_code=201)
def post_message(conversation_id: str, body: PostMessageRequest) -> PostMessageResponse:
    now = datetime.now(UTC)
    user_message = ChatMessage(
        id=f"msg_{uuid.uuid4()}",
        role=MessageRole.USER,
        content=body.content,
        status=MessageStatus.COMPLETE,
        created_at=now,
    )
    assistant_message = ChatMessage(
        id=f"msg_{uuid.uuid4()}",
        role=MessageRole.ASSISTANT,
        content="",
        status=MessageStatus.PENDING,
        created_at=now,
    )

    redis_client.rpush(
        conversation_messages_key(conversation_id),
        user_message.model_dump_json(),
        assistant_message.model_dump_json(),
    )

    celery_client.send_task(
        "close_friend_worker.respond_to_message",
        args=[conversation_id, assistant_message.id],
    )

    return PostMessageResponse(user_message=user_message, assistant_message=assistant_message)


@router.get("/{conversation_id}/messages")
def get_messages(conversation_id: str) -> GetMessagesResponse:
    raw = redis_client.lrange(conversation_messages_key(conversation_id), 0, -1)
    return GetMessagesResponse(messages=[ChatMessage.model_validate_json(item) for item in raw])
