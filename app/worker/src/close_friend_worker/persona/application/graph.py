from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from close_friend_worker.persona.domain.state import PersonaGraphState
from close_friend_worker.persona.infrastructure import llm
from close_friend_worker.persona.infrastructure import persona_repository as repo


def load_persona_context(state: PersonaGraphState) -> dict:
    # persona/state are already attached to the incoming state by
    # generate_persona_reply before graph.invoke() — this node exists as an
    # explicit step (per the documented Persona Response Loop's "Chat" step)
    # rather than doing nothing; it's a no-op pass-through today, kept as
    # the node persona-scope validation would extend if that's ever needed.
    return {}


def assess_and_plan(state: PersonaGraphState) -> dict:
    assessment = llm.call_assess_and_plan(state["persona"], state["state"], state["history"])
    return {"assessment": assessment}


def route_on_boundary(state: PersonaGraphState) -> str:
    assessment = state["assessment"]
    if assessment and assessment.boundary_violated:
        return "boundary_response"
    return "respond_in_character"


def boundary_response(state: PersonaGraphState) -> dict:
    reply = llm.render_boundary_response(state["persona"], state["assessment"])
    return {"reply": reply}


def respond_in_character(state: PersonaGraphState) -> dict:
    reply = llm.call_respond_in_character(
        state["persona"], state["state"], state["assessment"], state["history"]
    )
    return {"reply": reply}


def build_persona_graph():
    graph = StateGraph(PersonaGraphState)
    graph.add_node("load_persona_context", load_persona_context)
    graph.add_node("assess_and_plan", assess_and_plan)
    graph.add_node("boundary_response", boundary_response)
    graph.add_node("respond_in_character", respond_in_character)

    graph.set_entry_point("load_persona_context")
    graph.add_edge("load_persona_context", "assess_and_plan")
    graph.add_conditional_edges(
        "assess_and_plan",
        route_on_boundary,
        {"boundary_response": "boundary_response", "respond_in_character": "respond_in_character"},
    )
    graph.add_edge("boundary_response", END)
    graph.add_edge("respond_in_character", END)

    # No checkpointer: the graph runs synchronously start-to-finish within
    # one Celery task with no interrupt/resume need — persist_state (in
    # chat.py, after invoke() returns) is the single persistence mechanism.
    return graph.compile()


# Built once at import time — the compiled graph is stateless and safe to
# reuse across tasks/threads; per-invocation data flows through the state
# dict passed to invoke(), not through this module-level object.
persona_graph = build_persona_graph()


def run_persona_graph(
    session: Session,
    conversation_id: str,
    persona_id: str,
    assistant_message_id: str,
    history: list[dict],
) -> str:
    persona = repo.get_persona(session, persona_id)
    if persona is None:
        raise ValueError(f"no active persona found for id={persona_id!r}")
    persona_state = repo.get_or_init_state(session, conversation_id, persona)

    initial_state: PersonaGraphState = {
        "conversation_id": conversation_id,
        "assistant_message_id": assistant_message_id,
        "history": history,
        "persona": persona,
        "state": persona_state,
        "assessment": None,
        "reply": None,
    }
    result = persona_graph.invoke(initial_state)

    assessment = result["assessment"]
    updated_state = repo.apply_assessment(persona, persona_state, assessment)
    repo.persist_state(session, updated_state)
    repo.record_episodic_event(
        session,
        conversation_id=conversation_id,
        message_id=assistant_message_id,
        turn_index=updated_state.turn_count,
        assessment=assessment,
    )

    return result["reply"]
