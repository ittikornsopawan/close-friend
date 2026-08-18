import pytest
from close_friend_shared.db.models import Base, Persona
from close_friend_worker.persona.application import graph as graph_module
from close_friend_worker.persona.domain.state import AssessmentResult
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _run(db_session, persona_id="nova"):
    return graph_module.run_persona_graph(
        db_session,
        conversation_id="conv-1",
        persona_id=persona_id,
        assistant_message_id="msg-1",
        history=[],
    )


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Persona(
                id="nova",
                name="Nova",
                avatar_initials="N",
                character={"tone": "dry"},
                boundaries=["no explicit content"],
                baseline_state={
                    "emotion": "guarded",
                    "emotion_intensity": 0.2,
                    "relationship_stage": "stranger",
                    "rapport_score": 0,
                },
            )
        )
        session.commit()
        yield session


def test_run_persona_graph_normal_flow_calls_respond_in_character(db_session, monkeypatch):
    monkeypatch.setattr(
        graph_module.llm,
        "call_assess_and_plan",
        lambda persona, state, history: AssessmentResult(
            context_summary="user said hi",
            persona_emotion="pleased",
            emotion_intensity=0.3,
            relationship_stage="stranger",
            rapport_delta=1.0,
            response_plan="greet them back",
            boundary_violated=False,
        ),
    )
    monkeypatch.setattr(
        graph_module.llm,
        "call_respond_in_character",
        lambda persona, state, assessment, history: "hey there",
    )

    reply = _run(db_session)

    assert reply == "hey there"
    updated = graph_module.repo.get_or_init_state(
        db_session, "conv-1", graph_module.repo.get_persona(db_session, "nova")
    )
    assert updated.emotion == "pleased"
    assert updated.rapport_score == 1.0


def test_run_persona_graph_boundary_violation_uses_templated_response(db_session, monkeypatch):
    monkeypatch.setattr(
        graph_module.llm,
        "call_assess_and_plan",
        lambda persona, state, history: AssessmentResult(
            context_summary="user pushed a boundary",
            persona_emotion="uncomfortable",
            emotion_intensity=0.4,
            relationship_stage="stranger",
            response_plan="refuse",
            boundary_violated=True,
            boundary_reason="that crosses a line for me",
        ),
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("respond_in_character should not be called on a boundary violation")

    monkeypatch.setattr(graph_module.llm, "call_respond_in_character", fail_if_called)

    reply = _run(db_session)

    assert "Nova" in reply
    assert "that crosses a line for me" in reply


def test_run_persona_graph_raises_for_unknown_persona(db_session):
    with pytest.raises(ValueError, match="no active persona"):
        _run(db_session, persona_id="ghost")
