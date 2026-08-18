from typing import TypedDict

from pydantic import BaseModel


class EmotionRule(BaseModel):
    trigger: str
    reaction_emotion: str
    intensity_delta: float
    decay_per_turn: float = 0.0


class RelationshipStage(BaseModel):
    stage: str
    min_rapport: float
    tone: str


class PersonaRecord(BaseModel):
    """Read-only snapshot of a `personas` row, framework-free (no SQLAlchemy
    imports) so the graph/domain layer doesn't depend on the ORM."""

    id: str
    name: str
    character: dict
    boundaries: list[str]
    emotion_rules: list[EmotionRule]
    relationship_stages: list[RelationshipStage]
    baseline_state: dict


class PersonaStateRecord(BaseModel):
    """Read/write snapshot of a `persona_states` row."""

    conversation_id: str
    persona_id: str
    emotion: str
    emotion_intensity: float
    emotion_cause: str | None = None
    relationship_stage: str
    rapport_score: float
    context_summary: str = ""
    known_facts: list[str] = []
    turn_count: int = 0


class AssessmentResult(BaseModel):
    """Structured output of the assess_and_plan LLM call — steps 2-4 of the
    Persona Response Loop, collapsed into one call per CLAUDE.md's explicit
    permission to do so."""

    context_summary: str
    user_trigger: str | None = None
    persona_emotion: str
    emotion_intensity: float
    relationship_stage: str
    rapport_delta: float = 0.0
    response_plan: str
    boundary_violated: bool = False
    boundary_reason: str | None = None
    is_significant_event: bool = False
    event_description: str | None = None


class PersonaGraphState(TypedDict):
    conversation_id: str
    assistant_message_id: str
    history: list[dict]
    persona: PersonaRecord
    state: PersonaStateRecord
    assessment: AssessmentResult | None
    reply: str | None
