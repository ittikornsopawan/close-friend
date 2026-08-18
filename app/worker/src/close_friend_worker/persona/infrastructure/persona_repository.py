from close_friend_shared.db.models import EpisodicEvent, Persona, PersonaState
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from close_friend_worker.persona.domain.state import (
    AssessmentResult,
    EmotionRule,
    PersonaRecord,
    PersonaStateRecord,
    RelationshipStage,
)


def get_persona(session: Session, persona_id: str) -> PersonaRecord | None:
    row = session.get(Persona, persona_id)
    if row is None or not row.is_active:
        return None
    return PersonaRecord(
        id=row.id,
        name=row.name,
        character=row.character,
        boundaries=row.boundaries,
        emotion_rules=[EmotionRule.model_validate(r) for r in row.emotion_rules],
        relationship_stages=[RelationshipStage.model_validate(r) for r in row.relationship_stages],
        baseline_state=row.baseline_state,
    )


def _select_locked(session: Session, conversation_id: str):
    stmt = select(PersonaState).where(PersonaState.conversation_id == conversation_id)
    return session.execute(stmt.with_for_update())


def _to_record(row: PersonaState) -> PersonaStateRecord:
    return PersonaStateRecord(
        conversation_id=row.conversation_id,
        persona_id=row.persona_id,
        emotion=row.emotion,
        emotion_intensity=row.emotion_intensity,
        emotion_cause=row.emotion_cause,
        relationship_stage=row.relationship_stage,
        rapport_score=row.rapport_score,
        context_summary=row.context_summary,
        known_facts=list(row.known_facts),
        turn_count=row.turn_count,
    )


def get_or_init_state(
    session: Session, conversation_id: str, persona: PersonaRecord
) -> PersonaStateRecord:
    """Get-or-create, row-locked for the rest of this transaction.

    Concurrent Celery tasks for the *same* conversation_id (a fast
    double-send, or just >1 worker per docker-compose's --scale worker=N)
    would otherwise race here: two SELECTs both seeing no row and both
    INSERTing raise IntegrityError on the second commit; two SELECTs both
    seeing an existing row and both UPDATEing silently lose whichever
    committed first. Locking the row (or the freshly-inserted row) with
    SELECT ... FOR UPDATE for the remainder of this transaction serializes
    same-conversation turns instead — a second concurrent task blocks here
    until the first's transaction commits or rolls back, which is also the
    behavior you want anyway (two replies shouldn't interleave incoherently
    for one conversation). No-op on SQLite (no row-level locking support,
    silently ignored by the dialect) — fine for the single-threaded test
    suite; real locking only matters against Postgres.
    """
    row = _select_locked(session, conversation_id).scalar_one_or_none()

    if row is None:
        baseline = persona.baseline_state
        try:
            with session.begin_nested():
                row = PersonaState(
                    conversation_id=conversation_id,
                    persona_id=persona.id,
                    emotion=baseline.get("emotion", "neutral"),
                    emotion_intensity=baseline.get("emotion_intensity", 0.0),
                    relationship_stage=baseline.get("relationship_stage", "stranger"),
                    rapport_score=baseline.get("rapport_score", 0.0),
                )
                session.add(row)
                session.flush()
        except IntegrityError:
            # Another concurrent transaction inserted first — the savepoint
            # rollback above discarded our attempt; lock its row instead.
            row = _select_locked(session, conversation_id).scalar_one()

    return _to_record(row)


def _derive_relationship_stage(persona: PersonaRecord, rapport_score: float) -> str:
    """Pick the highest-threshold stage this rapport_score qualifies for,
    rather than trusting the LLM's raw `assessment.relationship_stage`
    verbatim — keeps `personas.relationship_stages[].min_rapport` the
    authoritative source instead of dead data the LLM could drift from."""
    eligible = [s for s in persona.relationship_stages if rapport_score >= s.min_rapport]
    if not eligible:
        return persona.baseline_state.get("relationship_stage", "stranger")
    return max(eligible, key=lambda stage: stage.min_rapport).stage


def apply_assessment(
    persona: PersonaRecord, state: PersonaStateRecord, assessment: AssessmentResult
) -> PersonaStateRecord:
    """Pure function: fold an LLM assessment into the persona's persisted
    state — clamps intensity, accumulates rapport, derives the relationship
    stage from thresholds, advances the turn count. No I/O, easy to unit
    test independently of the database."""
    rapport_score = state.rapport_score + assessment.rapport_delta
    return state.model_copy(
        update={
            "emotion": assessment.persona_emotion,
            "emotion_intensity": max(0.0, min(1.0, assessment.emotion_intensity)),
            "emotion_cause": assessment.user_trigger,
            "relationship_stage": _derive_relationship_stage(persona, rapport_score),
            "rapport_score": rapport_score,
            "context_summary": assessment.context_summary,
            "turn_count": state.turn_count + 1,
        }
    )


def persist_state(session: Session, updated_state: PersonaStateRecord) -> None:
    row = session.get(PersonaState, updated_state.conversation_id)
    if row is None:
        row = PersonaState(
            conversation_id=updated_state.conversation_id, persona_id=updated_state.persona_id
        )
        session.add(row)

    row.emotion = updated_state.emotion
    row.emotion_intensity = updated_state.emotion_intensity
    row.emotion_cause = updated_state.emotion_cause
    row.relationship_stage = updated_state.relationship_stage
    row.rapport_score = updated_state.rapport_score
    row.context_summary = updated_state.context_summary
    row.known_facts = updated_state.known_facts
    row.turn_count = updated_state.turn_count


def record_episodic_event(
    session: Session,
    conversation_id: str,
    message_id: str,
    turn_index: int,
    assessment: AssessmentResult,
) -> None:
    if not assessment.is_significant_event:
        return
    session.add(
        EpisodicEvent(
            conversation_id=conversation_id,
            message_id=message_id,
            turn_index=turn_index,
            event_type=assessment.user_trigger or "unspecified",
            description=assessment.event_description or assessment.context_summary,
            emotion_impact={
                "emotion": assessment.persona_emotion,
                "intensity_delta": assessment.emotion_intensity,
            },
        )
    )
