import pytest
from close_friend_shared.db.models import Base, EpisodicEvent, Persona
from close_friend_worker.persona.domain.state import (
    AssessmentResult,
    PersonaRecord,
    PersonaStateRecord,
)
from close_friend_worker.persona.infrastructure import persona_repository as repo
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def seeded_persona(db_session):
    persona = Persona(
        id="nova",
        name="Nova",
        avatar_initials="N",
        character={"tone": "dry"},
        boundaries=["no explicit content"],
        emotion_rules=[
            {
                "trigger": "insult",
                "reaction_emotion": "annoyed",
                "intensity_delta": 0.4,
                "decay_per_turn": 0.0,
            }
        ],
        relationship_stages=[{"stage": "stranger", "min_rapport": 0, "tone": "guarded"}],
        baseline_state={
            "emotion": "guarded",
            "emotion_intensity": 0.2,
            "relationship_stage": "stranger",
            "rapport_score": 0,
        },
    )
    db_session.add(persona)
    db_session.commit()
    return persona


def test_get_persona_returns_none_for_missing(db_session):
    assert repo.get_persona(db_session, "missing") is None


def test_get_persona_returns_none_for_inactive(db_session):
    db_session.add(
        Persona(
            id="x", name="X", avatar_initials="X", character={}, baseline_state={}, is_active=False
        )
    )
    db_session.commit()

    assert repo.get_persona(db_session, "x") is None


def test_get_persona_parses_nested_rules(db_session, seeded_persona):
    persona = repo.get_persona(db_session, "nova")

    assert persona is not None
    assert persona.emotion_rules[0].trigger == "insult"
    assert persona.relationship_stages[0].stage == "stranger"


def test_get_or_init_state_initializes_from_baseline(db_session, seeded_persona):
    persona = repo.get_persona(db_session, "nova")

    state = repo.get_or_init_state(db_session, "conv-1", persona)

    assert state.emotion == "guarded"
    assert state.emotion_intensity == 0.2
    assert state.turn_count == 0


def test_get_or_init_state_returns_existing_row(db_session, seeded_persona):
    persona = repo.get_persona(db_session, "nova")
    initial = repo.get_or_init_state(db_session, "conv-1", persona)
    updated = repo.apply_assessment(
        persona,
        initial,
        AssessmentResult(
            context_summary="chatted",
            persona_emotion="annoyed",
            emotion_intensity=0.5,
            relationship_stage="stranger",
            rapport_delta=2.0,
            response_plan="respond",
        ),
    )
    repo.persist_state(db_session, updated)
    db_session.commit()

    reloaded = repo.get_or_init_state(db_session, "conv-1", persona)

    assert reloaded.emotion == "annoyed"
    assert reloaded.turn_count == 1
    assert reloaded.rapport_score == 2.0


def _persona_record(**overrides) -> PersonaRecord:
    defaults = dict(
        id="p",
        name="Test",
        character={},
        boundaries=[],
        emotion_rules=[],
        relationship_stages=[
            {"stage": "stranger", "min_rapport": 0, "tone": ""},
            {"stage": "familiar", "min_rapport": 15, "tone": ""},
            {"stage": "close", "min_rapport": 40, "tone": ""},
        ],
        baseline_state={"relationship_stage": "stranger"},
    )
    defaults.update(overrides)
    return PersonaRecord.model_validate(defaults)


def test_apply_assessment_clamps_intensity():
    state = PersonaStateRecord(
        conversation_id="c",
        persona_id="p",
        emotion="neutral",
        emotion_intensity=0.5,
        relationship_stage="stranger",
        rapport_score=0,
    )
    assessment = AssessmentResult(
        context_summary="",
        persona_emotion="ecstatic",
        emotion_intensity=5.0,
        relationship_stage="stranger",
        response_plan="respond",
    )

    updated = repo.apply_assessment(_persona_record(), state, assessment)

    assert updated.emotion_intensity == 1.0


def test_apply_assessment_derives_relationship_stage_from_rapport_thresholds():
    """relationship_stage must come from personas.relationship_stages'
    min_rapport thresholds, not be trusted verbatim from the LLM — a
    regression test for a bug where the LLM's raw guess was persisted as-is
    even when it contradicted the numeric rapport score."""
    state = PersonaStateRecord(
        conversation_id="c",
        persona_id="p",
        emotion="neutral",
        emotion_intensity=0.2,
        relationship_stage="stranger",
        rapport_score=10,
    )
    # LLM claims "close" even though rapport (10 + 5 = 15) only qualifies for
    # "familiar" per the thresholds above — the derived stage must win.
    assessment = AssessmentResult(
        context_summary="",
        persona_emotion="warm",
        emotion_intensity=0.4,
        relationship_stage="close",
        rapport_delta=5.0,
        response_plan="respond",
    )

    updated = repo.apply_assessment(_persona_record(), state, assessment)

    assert updated.rapport_score == 15
    assert updated.relationship_stage == "familiar"


def test_record_episodic_event_only_when_significant(db_session, seeded_persona):
    persona = repo.get_persona(db_session, "nova")
    state = repo.get_or_init_state(db_session, "conv-1", persona)
    repo.persist_state(db_session, state)
    db_session.commit()

    not_significant = AssessmentResult(
        context_summary="",
        persona_emotion="guarded",
        emotion_intensity=0.2,
        relationship_stage="stranger",
        response_plan="respond",
        is_significant_event=False,
    )
    repo.record_episodic_event(db_session, "conv-1", "msg-1", 1, not_significant)
    db_session.commit()
    assert db_session.query(EpisodicEvent).count() == 0

    significant = AssessmentResult(
        context_summary="",
        persona_emotion="annoyed",
        emotion_intensity=0.5,
        relationship_stage="stranger",
        response_plan="respond",
        is_significant_event=True,
        event_description="user was rude",
    )
    repo.record_episodic_event(db_session, "conv-1", "msg-2", 2, significant)
    db_session.commit()

    events = db_session.query(EpisodicEvent).all()
    assert len(events) == 1
    assert events[0].description == "user was rude"
