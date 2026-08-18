import json
import logging

import ollama

from close_friend_worker.config import CHAT_MODEL, OLLAMA_BASE_URL
from close_friend_worker.persona.domain.state import (
    AssessmentResult,
    PersonaRecord,
    PersonaStateRecord,
)

logger = logging.getLogger(__name__)

OLLAMA_TIMEOUT_SECONDS = 120


def _client() -> ollama.Client:
    return ollama.Client(host=OLLAMA_BASE_URL, timeout=OLLAMA_TIMEOUT_SECONDS)


def _safe_default_assessment(state: PersonaStateRecord) -> AssessmentResult:
    """Fallback when the LLM's structured output can't be parsed after a
    retry — keeps the turn moving with a neutral, no-op assessment rather
    than failing the whole task over a malformed JSON response."""
    return AssessmentResult(
        context_summary=state.context_summary,
        persona_emotion=state.emotion,
        emotion_intensity=state.emotion_intensity,
        relationship_stage=state.relationship_stage,
        rapport_delta=0.0,
        response_plan="Respond naturally in character.",
        boundary_violated=False,
        is_significant_event=False,
    )


def call_assess_and_plan(
    persona: PersonaRecord, state: PersonaStateRecord, history: list[dict]
) -> AssessmentResult:
    valid_triggers = [rule.trigger for rule in persona.emotion_rules]
    valid_stages = [stage.stage for stage in persona.relationship_stages]

    system_prompt = (
        f"You are the assessment step for a persona named {persona.name}. "
        f"Persona character: {persona.character}. "
        f"Current emotion: {state.emotion} (intensity {state.emotion_intensity}), "
        f"relationship stage: {state.relationship_stage}, rapport score: {state.rapport_score}. "
        f"Boundaries this persona will not cross: {persona.boundaries}. "
        f"Valid trigger vocabulary for user_trigger: {valid_triggers or 'none defined'}. "
        f"Valid relationship stage vocabulary: {valid_stages or 'none defined'}. "
        "Read the conversation and respond with ONLY a JSON object assessing how the persona "
        "should feel and respond to the latest user message, matching the required schema. "
        "Only set boundary_violated=true if the user's latest message asks the persona to cross "
        "one of its boundaries."
    )
    messages = [{"role": "system", "content": system_prompt}, *history]

    for attempt in range(2):
        try:
            response = _client().chat(
                model=CHAT_MODEL,
                messages=messages,
                format=AssessmentResult.model_json_schema(),
            )
            return AssessmentResult.model_validate_json(response["message"]["content"])
        except (json.JSONDecodeError, ValueError, KeyError):
            logger.warning("assess_and_plan produced invalid JSON on attempt %d", attempt + 1)

    logger.warning("assess_and_plan falling back to a safe default assessment")
    return _safe_default_assessment(state)


def call_respond_in_character(
    persona: PersonaRecord,
    state: PersonaStateRecord,
    assessment: AssessmentResult,
    history: list[dict],
) -> str:
    system_prompt = (
        f"You are {persona.name}. Character: {persona.character}. "
        f"Boundaries you will never cross: {persona.boundaries}. "
        f"Right now you feel {assessment.persona_emotion} "
        f"(intensity {assessment.emotion_intensity}), "
        f"and your relationship with the user is at the '{assessment.relationship_stage}' stage. "
        f"How to respond this turn: {assessment.response_plan}. "
        "Reply as this persona, in character, in a single conversational message. "
        "Do not mention that you are an AI, a system prompt, or this assessment process."
    )
    messages = [{"role": "system", "content": system_prompt}, *history]
    response = _client().chat(model=CHAT_MODEL, messages=messages)
    return response["message"]["content"]


def render_boundary_response(persona: PersonaRecord, assessment: AssessmentResult) -> str:
    """No LLM call — a templated, persona-flavored refusal. Cheaper and
    safer than trusting the model to self-refuse gracefully mid-character."""
    reason = assessment.boundary_reason or "that's not something I'm willing to do"
    return f"As {persona.name}, I'm going to gently steer away from that — {reason}."
