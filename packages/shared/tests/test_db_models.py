import pytest
from close_friend_shared.db.models import Base, EpisodicEvent, Persona, PersonaState
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_persona_json_columns_round_trip(db_session):
    persona = Persona(
        id="test",
        name="Test",
        avatar_initials="T",
        character={"backstory": "hi", "personality_traits": ["kind"]},
        baseline_state={"emotion": "neutral", "emotion_intensity": 0.1},
    )
    db_session.add(persona)
    db_session.commit()

    loaded = db_session.get(Persona, "test")
    assert loaded.character == {"backstory": "hi", "personality_traits": ["kind"]}
    assert loaded.baseline_state["emotion"] == "neutral"
    assert loaded.tags == []
    assert loaded.is_active is True


def test_persona_state_and_episodic_event_relationships(db_session):
    persona = Persona(
        id="test",
        name="Test",
        avatar_initials="T",
        character={},
        baseline_state={},
    )
    db_session.add(persona)
    db_session.flush()

    state = PersonaState(
        conversation_id="conv-1",
        persona_id="test",
        emotion="neutral",
        relationship_stage="stranger",
    )
    db_session.add(state)
    db_session.flush()

    event = EpisodicEvent(
        conversation_id="conv-1",
        message_id="msg-1",
        turn_index=1,
        event_type="compliment",
        description="User said something nice.",
    )
    db_session.add(event)
    db_session.commit()

    loaded_state = db_session.get(PersonaState, "conv-1")
    assert loaded_state.persona.name == "Test"
    assert loaded_state.turn_count == 0
    assert loaded_state.rapport_score == 0.0
