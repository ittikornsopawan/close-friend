import pytest
from close_friend_api.db import get_db
from close_friend_api.main import app
from close_friend_shared.db.models import Base, Persona
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)

    with TestSessionLocal() as session:
        session.add(
            Persona(
                id="general",
                name="Mali",
                tagline="Your endlessly upbeat friend",
                avatar_initials="M",
                tags=["friendly"],
                character={"backstory": "secret backstory"},
                boundaries=["a secret boundary"],
                emotion_rules=[{"trigger": "insult", "reaction_emotion": "hurt"}],
                baseline_state={"emotion": "cheerful"},
            )
        )
        session.add(
            Persona(
                id="inactive",
                name="Hidden",
                avatar_initials="H",
                character={},
                baseline_state={},
                is_active=False,
            )
        )
        session.commit()

    def override_get_db() -> Session:
        with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_list_personas_returns_narrow_read_model(client):
    response = client.get("/personas")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "personas": [
            {
                "id": "general",
                "name": "Mali",
                "tagline": "Your endlessly upbeat friend",
                "avatar_initials": "M",
                "tags": ["friendly"],
            }
        ]
    }
    # Never leak persona internals to the client.
    serialized = str(body)
    assert "secret backstory" not in serialized
    assert "secret boundary" not in serialized
    assert "emotion_rules" not in serialized


def test_list_personas_excludes_inactive(client):
    response = client.get("/personas")

    ids = [p["id"] for p in response.json()["personas"]]
    assert "inactive" not in ids
