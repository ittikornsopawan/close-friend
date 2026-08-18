from close_friend_worker.persona.domain.state import PersonaRecord, PersonaStateRecord
from close_friend_worker.persona.infrastructure import llm


class FakeOllamaClient:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls = 0

    def chat(self, **kwargs):
        self.calls += 1
        content = self._responses.pop(0)
        return {"message": {"content": content}}


def _persona() -> PersonaRecord:
    return PersonaRecord(
        id="nova",
        name="Nova",
        character={"tone": "dry"},
        boundaries=["no explicit content"],
        emotion_rules=[],
        relationship_stages=[],
        baseline_state={},
    )


def _state() -> PersonaStateRecord:
    return PersonaStateRecord(
        conversation_id="conv-1",
        persona_id="nova",
        emotion="guarded",
        emotion_intensity=0.2,
        relationship_stage="stranger",
        rapport_score=0,
    )


def test_call_assess_and_plan_parses_valid_json(monkeypatch):
    valid_json = (
        '{"context_summary": "hi", "persona_emotion": "pleased", "emotion_intensity": 0.3, '
        '"relationship_stage": "stranger", "response_plan": "greet back"}'
    )
    fake_client = FakeOllamaClient([valid_json])
    monkeypatch.setattr(llm, "_client", lambda: fake_client)

    result = llm.call_assess_and_plan(_persona(), _state(), [])

    assert result.persona_emotion == "pleased"
    assert fake_client.calls == 1


def test_call_assess_and_plan_retries_once_then_falls_back(monkeypatch):
    fake_client = FakeOllamaClient(["not valid json", "still not valid json"])
    monkeypatch.setattr(llm, "_client", lambda: fake_client)

    result = llm.call_assess_and_plan(_persona(), _state(), [])

    assert fake_client.calls == 2
    # Falls back to the current state unchanged, not a crash.
    assert result.persona_emotion == "guarded"
    assert result.boundary_violated is False
    assert result.is_significant_event is False


def test_call_assess_and_plan_recovers_after_one_bad_response(monkeypatch):
    valid_json = (
        '{"context_summary": "hi", "persona_emotion": "annoyed", "emotion_intensity": 0.5, '
        '"relationship_stage": "stranger", "response_plan": "push back"}'
    )
    fake_client = FakeOllamaClient(["garbage", valid_json])
    monkeypatch.setattr(llm, "_client", lambda: fake_client)

    result = llm.call_assess_and_plan(_persona(), _state(), [])

    assert fake_client.calls == 2
    assert result.persona_emotion == "annoyed"


def test_render_boundary_response_includes_persona_name_and_reason():
    from close_friend_worker.persona.domain.state import AssessmentResult

    assessment = AssessmentResult(
        context_summary="",
        persona_emotion="uncomfortable",
        emotion_intensity=0.4,
        relationship_stage="stranger",
        response_plan="refuse",
        boundary_violated=True,
        boundary_reason="I don't discuss that",
    )

    reply = llm.render_boundary_response(_persona(), assessment)

    assert "Nova" in reply
    assert "I don't discuss that" in reply
