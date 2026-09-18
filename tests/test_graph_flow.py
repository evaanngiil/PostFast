"""
Test de integración del grafo completo con nodos stub (sin llamadas LLM ni red).

Verifica:
- La secuencia de fases orquestada por el supervisor.
- La pausa HITL (interrupt_before=human_review).
- El ciclo feedback -> content_editor -> revalidación -> nueva pausa.
- El reset de correction_loops al recibir feedback humano.
"""
import uuid

import pytest

from src.agents.multi_agent.graph import build_graph


def make_stub(update: dict, calls: list, name: str):
    def _node(state):
        calls.append(name)
        return dict(update)
    return _node


@pytest.fixture()
def compiled_graph_and_calls():
    from langgraph.checkpoint.memory import MemorySaver

    calls: list[str] = []
    overrides = {
        "engagement_analyzer": make_stub({"engagement_analysis": {"ok": True}}, calls, "engagement_analyzer"),
        "persona_analyst": make_stub({"brand_persona_json": {"tone": "pro"}}, calls, "persona_analyst"),
        "duplicate_detector": make_stub({"existing_posts_on_topic": [], "duplicate_context": "nada"}, calls, "duplicate_detector"),
        "trend_researcher": make_stub({"industry_trends": "tendencias"}, calls, "trend_researcher"),
        "idea_expander": make_stub({"fleshed_out_idea": {"topic": "t"}}, calls, "idea_expander"),
        "content_writer": make_stub(
            {
                "draft_post": {"content": "borrador v1", "hashtags": ["#a"], "call_to_action": "cta"},
                "user_feedback": None,
                "fact_check_report": None,
                "safety_report": None,
            },
            calls, "content_writer",
        ),
        "content_editor": make_stub(
            {
                "draft_post": {"content": "borrador editado", "hashtags": [], "call_to_action": ""},
                "user_feedback": None,
                "fact_check_report": None,
                "safety_report": None,
            },
            calls, "content_editor",
        ),
        "fact_checker": make_stub({"fact_check_report": {"overall_pass": True, "claims": []}}, calls, "fact_checker"),
        "safety_guard": make_stub({"safety_report": {"approved": True, "severity": "none"}}, calls, "safety_guard"),
    }

    graph = build_graph(node_overrides=overrides).compile(
        checkpointer=MemorySaver(),
        interrupt_before=["human_review"],
    )
    return graph, calls


INITIAL_STATE = {
    "linkedin_access_token": "",
    "user_post_idea": "post sobre agricultura",
    "selected_account": {"urn": "urn:li:organization:1"},
}


def test_full_pipeline_sequence_and_hitl_pause(compiled_graph_and_calls):
    graph, calls = compiled_graph_and_calls
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    result = graph.invoke(INITIAL_STATE, config=config)

    # Secuencia completa de fases (los paralelos pueden intercambiar orden entre sí)
    assert calls[0] == "engagement_analyzer"
    assert calls[1] == "persona_analyst"
    assert set(calls[2:4]) == {"duplicate_detector", "trend_researcher"}
    assert calls[4:] == ["idea_expander", "content_writer", "fact_checker", "safety_guard"]

    # Pausa HITL antes de human_review con el borrador disponible
    snapshot = graph.get_state(config)
    assert snapshot.next and "human_review" in snapshot.next
    assert result["draft_post"]["content"] == "borrador v1"


def test_feedback_cycle_routes_through_editor_and_revalidates(compiled_graph_and_calls):
    graph, calls = compiled_graph_and_calls
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    graph.invoke(INITIAL_STATE, config=config)
    calls.clear()

    # El usuario deja feedback -> reanudar
    graph.update_state(config, {"user_feedback": "quita los hashtags", "correction_loops": 2})
    graph.invoke(None, config=config)

    # El feedback debe ir al EDITOR (no al writer) y revalidarse después
    assert calls == ["content_editor", "fact_checker", "safety_guard"]

    snapshot = graph.get_state(config)
    assert snapshot.next and "human_review" in snapshot.next
    assert snapshot.values["draft_post"]["content"] == "borrador editado"
    # human_review reseteó el presupuesto de correcciones al recibir feedback
    assert snapshot.values.get("correction_loops") == 0


def test_approval_ends_the_graph(compiled_graph_and_calls):
    graph, calls = compiled_graph_and_calls
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    graph.invoke(INITIAL_STATE, config=config)

    # Aprobación: sin feedback -> human_review corre y el grafo finaliza
    graph.update_state(config, {"user_feedback": None}, as_node="human_review")
    graph.invoke(None, config=config)

    snapshot = graph.get_state(config)
    assert not snapshot.next  # grafo terminado
    assert snapshot.values["draft_post"]["content"] == "borrador v1"


def test_edit_mode_skips_research_nodes(compiled_graph_and_calls):
    graph, calls = compiled_graph_and_calls
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    edit_state = {
        **INITIAL_STATE,
        "edit_mode": True,
        "original_post": "post original",
        "edit_instructions": "acórtalo",
    }
    graph.invoke(edit_state, config=config)

    assert calls == ["content_editor"]
    snapshot = graph.get_state(config)
    assert snapshot.next and "human_review" in snapshot.next
