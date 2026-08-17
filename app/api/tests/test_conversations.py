import fakeredis
import pytest
from close_friend_api.main import app
from close_friend_api.routers import conversations
from fastapi.testclient import TestClient


class FakeCeleryClient:
    def __init__(self):
        self.sent = []

    def send_task(self, name, args=None, **kwargs):
        self.sent.append((name, args))


@pytest.fixture
def fake_redis(monkeypatch):
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(conversations, "redis_client", client)
    return client


@pytest.fixture
def fake_celery(monkeypatch):
    client = FakeCeleryClient()
    monkeypatch.setattr(conversations, "celery_client", client)
    return client


@pytest.fixture
def client(fake_redis, fake_celery):
    return TestClient(app)


def test_post_message_creates_user_and_pending_assistant_message(client, fake_celery):
    response = client.post("/conversations/general/messages", json={"content": "hi"})

    assert response.status_code == 201
    body = response.json()
    assert body["user_message"]["content"] == "hi"
    assert body["user_message"]["status"] == "complete"
    assert body["assistant_message"]["status"] == "pending"
    assert fake_celery.sent == [
        ("close_friend_worker.respond_to_message", ["general", body["assistant_message"]["id"]])
    ]


def test_get_messages_returns_in_order(client):
    client.post("/conversations/general/messages", json={"content": "first"})
    client.post("/conversations/general/messages", json={"content": "second"})

    response = client.get("/conversations/general/messages")

    assert response.status_code == 200
    user_contents = [m["content"] for m in response.json()["messages"] if m["role"] == "user"]
    assert user_contents == ["first", "second"]


def test_get_messages_on_new_conversation_is_empty(client):
    response = client.get("/conversations/never-used/messages")

    assert response.status_code == 200
    assert response.json() == {"messages": []}
