import fakeredis
import pytest
from close_friend_shared import ChatMessage, MessageRole, MessageStatus, conversation_messages_key
from close_friend_worker import chat


@pytest.fixture
def fake_redis(monkeypatch):
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(chat, "redis_client", client)
    return client


def _message(id_: str, role: MessageRole, content: str, status: MessageStatus) -> ChatMessage:
    return ChatMessage(
        id=id_,
        role=role,
        content=content,
        status=status,
        created_at="2026-01-01T00:00:00Z",
    )


def _seed(fake_redis, conversation_id: str, *messages: ChatMessage) -> None:
    key = conversation_messages_key(conversation_id)
    for message in messages:
        fake_redis.rpush(key, message.model_dump_json())


def test_build_ollama_history_excludes_pending_placeholder():
    messages = [
        _message("1", MessageRole.USER, "hi", MessageStatus.COMPLETE),
        _message("2", MessageRole.ASSISTANT, "", MessageStatus.PENDING),
    ]

    history = chat.build_ollama_history(messages, assistant_message_id="2")

    assert history == [{"role": "user", "content": "hi"}]


def test_respond_to_message_success(fake_redis, monkeypatch):
    _seed(
        fake_redis,
        "general",
        _message("1", MessageRole.USER, "hi", MessageStatus.COMPLETE),
        _message("2", MessageRole.ASSISTANT, "", MessageStatus.PENDING),
    )
    monkeypatch.setattr(chat, "generate_persona_reply", lambda *args: "hello there")

    chat.respond_to_message("general", "2")

    updated = chat.load_messages("general")
    assert updated[1].status == MessageStatus.COMPLETE
    assert updated[1].content == "hello there"


def test_respond_to_message_persona_failure_marks_message_failed(fake_redis, monkeypatch):
    _seed(
        fake_redis,
        "general",
        _message("1", MessageRole.USER, "hi", MessageStatus.COMPLETE),
        _message("2", MessageRole.ASSISTANT, "", MessageStatus.PENDING),
    )

    def boom(conversation_id, assistant_message_id, history):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(chat, "generate_persona_reply", boom)

    chat.respond_to_message("general", "2")

    updated = chat.load_messages("general")
    assert updated[1].status == MessageStatus.FAILED
    assert updated[1].content == chat.FAILURE_MESSAGE


def test_respond_to_message_redis_read_failure_does_not_raise(fake_redis, monkeypatch):
    """A Redis-level failure while loading the conversation (not just an
    Ollama failure) must not propagate out of the task unhandled — regression
    test for a bug where only the call_ollama() step was guarded."""
    _seed(
        fake_redis,
        "general",
        _message("1", MessageRole.USER, "hi", MessageStatus.COMPLETE),
        _message("2", MessageRole.ASSISTANT, "", MessageStatus.PENDING),
    )

    call_count = 0
    real_lrange = fake_redis.lrange

    def flaky_lrange(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("redis unavailable")
        return real_lrange(*args, **kwargs)

    monkeypatch.setattr(fake_redis, "lrange", flaky_lrange)

    chat.respond_to_message("general", "2")  # must not raise

    updated = chat.load_messages("general")
    assert updated[1].status == MessageStatus.FAILED
    assert updated[1].content == chat.FAILURE_MESSAGE


def test_respond_to_message_missing_placeholder_does_not_raise(fake_redis):
    """If the assistant placeholder id can't be found (e.g. cleared/expired),
    there's nothing to mark failed — respond_to_message must still not raise."""
    _seed(fake_redis, "general", _message("1", MessageRole.USER, "hi", MessageStatus.COMPLETE))

    chat.respond_to_message("general", "does-not-exist")  # must not raise
