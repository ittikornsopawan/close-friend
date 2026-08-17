from close_friend_shared import TaskMessage

from close_friend_worker import chat
from close_friend_worker.celery_app import celery_app


@celery_app.task(name="close_friend_worker.ping")
def ping(payload: dict) -> str:
    message = TaskMessage(task_id="ping", name="ping", payload=payload)
    return f"pong: {message.payload}"


@celery_app.task(name="close_friend_worker.respond_to_message")
def respond_to_message(conversation_id: str, assistant_message_id: str) -> None:
    chat.respond_to_message(conversation_id, assistant_message_id)
