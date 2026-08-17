import logging

import ollama
from close_friend_shared import ChatMessage, MessageStatus, conversation_messages_key

from close_friend_worker.config import CHAT_MODEL, OLLAMA_BASE_URL
from close_friend_worker.redis_client import redis_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "You are a helpful, friendly assistant."
OLLAMA_TIMEOUT_SECONDS = 120
FAILURE_MESSAGE = "Sorry, I couldn't generate a reply right now."


def load_messages(conversation_id: str) -> list[ChatMessage]:
    raw = redis_client.lrange(conversation_messages_key(conversation_id), 0, -1)
    return [ChatMessage.model_validate_json(item) for item in raw]


def save_message(conversation_id: str, index: int, message: ChatMessage) -> None:
    redis_client.lset(conversation_messages_key(conversation_id), index, message.model_dump_json())


def find_message_index(messages: list[ChatMessage], message_id: str) -> int:
    for index, message in enumerate(messages):
        if message.id == message_id:
            return index
    raise ValueError(f"message {message_id} not found")


def build_ollama_history(messages: list[ChatMessage], assistant_message_id: str) -> list[dict]:
    """Turn stored ChatMessages into Ollama's `messages=[{role, content}]` shape,
    prefixed with a generic system prompt. Excludes the still-empty placeholder
    being filled in and any other non-complete message."""
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    for message in messages:
        if message.id == assistant_message_id or message.status != MessageStatus.COMPLETE:
            continue
        history.append({"role": message.role.value, "content": message.content})
    return history


def call_ollama(history: list[dict]) -> str:
    client = ollama.Client(host=OLLAMA_BASE_URL, timeout=OLLAMA_TIMEOUT_SECONDS)
    response = client.chat(model=CHAT_MODEL, messages=history)
    return response["message"]["content"]


def _mark_failed(conversation_id: str, assistant_message_id: str) -> None:
    """Best-effort: re-read the conversation and mark the placeholder failed.
    Separate try/except so a Redis problem here doesn't crash the task
    ungracefully — if this also fails, the message is left `pending` and the
    frontend's bounded poll (see CLAUDE.md) will just time out."""
    try:
        messages = load_messages(conversation_id)
        index = find_message_index(messages, assistant_message_id)
        failed = messages[index].model_copy(
            update={"content": FAILURE_MESSAGE, "status": MessageStatus.FAILED}
        )
        save_message(conversation_id, index, failed)
    except Exception:
        logger.exception(
            "Could not mark message %s as failed either (conversation %s)",
            assistant_message_id,
            conversation_id,
        )


def respond_to_message(conversation_id: str, assistant_message_id: str) -> None:
    # Everything from the initial Redis read through the Ollama call is
    # wrapped here — not just call_ollama — so a Redis hiccup or a missing
    # placeholder also resolves to `failed` instead of leaving the message
    # `pending` forever.
    try:
        messages = load_messages(conversation_id)
        index = find_message_index(messages, assistant_message_id)
        placeholder = messages[index]
        history = build_ollama_history(messages, assistant_message_id)
        reply = call_ollama(history)
    except Exception:
        logger.exception(
            "Failed to generate reply for conversation %s, message %s",
            conversation_id,
            assistant_message_id,
        )
        _mark_failed(conversation_id, assistant_message_id)
        return

    save_message(
        conversation_id,
        index,
        placeholder.model_copy(update={"content": reply, "status": MessageStatus.COMPLETE}),
    )
