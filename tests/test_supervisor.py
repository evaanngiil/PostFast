"""
Tests del supervisor determinista (supervisor_router_logic).

Es una función pura sobre el estado: estos tests demuestran formalmente el
determinismo del ruteo que la memoria del TFG reclama como decisión de diseño.
"""
from src.agents.multi_agent.nodes.supervisor import supervisor_router_logic


BASE_COMPLETE_STATE = {
    "edit_mode": False,
    "engagement_analysis": {"ok": True},
    "brand_persona_json": {"tone": "pro"},
    "existing_posts_on_topic": [],
    "industry_trends": "tendencias...",
    "fleshed_out_idea": {"topic": "x"},
    "draft_post": {"content": "post", "hashtags": [], "call_to_action": ""},
    "fact_check_report": {"overall_pass": True, "claims": []},
    "safety_report": {"approved": True, "severity": "none"},
}


def state_with(**overrides):
    state = dict(BASE_COMPLETE_STATE)
    state.update(overrides)
    return state


# ---------- Secuencia de fases ----------

def test_phase2_engagement_first():
    assert supervisor_router_logic(state_with(engagement_analysis=None)) == "engagement_analyzer"


def test_phase2_persona_after_engagement():
    assert supervisor_router_logic(state_with(brand_persona_json=None)) == "persona_analyst"


def test_phase3_parallel_fanout_duplicates_and_trends():
    result = supervisor_router_logic(state_with(existing_posts_on_topic=None, industry_trends=None))
    assert result == ["duplicate_detector", "trend_researcher"]


def test_phase3_only_duplicates_pending():
    assert supervisor_router_logic(state_with(existing_posts_on_topic=None)) == "duplicate_detector"


def test_phase3_empty_duplicates_list_counts_as_done():
    # [] significa "buscado, sin coincidencias"; None significa "pendiente".
    assert supervisor_router_logic(state_with(existing_posts_on_topic=[])) != "duplicate_detector"


def test_phase4_idea_then_writer():
    assert supervisor_router_logic(state_with(fleshed_out_idea=None)) == "idea_expander"
    assert supervisor_router_logic(state_with(draft_post=None, user_feedback=None)) == "content_writer"


def test_phase5_fact_check_then_safety():
    assert supervisor_router_logic(state_with(fact_check_report=None)) == "fact_checker"
    assert supervisor_router_logic(state_with(safety_report=None)) == "safety_guard"


def test_complete_state_goes_to_human_review():
    assert supervisor_router_logic(state_with()) == "human_review"


# ---------- Bucles de corrección ----------

def test_failed_fact_check_recycles_to_writer():
    state = state_with(fact_check_report={"overall_pass": False, "claims": [{"verified": False}]})
    assert supervisor_router_logic(state) == "content_writer"


def test_failed_safety_medium_or_higher_recycles_to_writer():
    for severity in ("medium", "high", "critical"):
        state = state_with(safety_report={"approved": False, "severity": severity})
        assert supervisor_router_logic(state) == "content_writer", severity


def test_failed_safety_low_severity_does_not_recycle():
    state = state_with(safety_report={"approved": False, "severity": "low"})
    assert supervisor_router_logic(state) == "human_review"


# ---------- Modo edición y HITL ----------

def test_edit_mode_routes_to_editor_then_review():
    assert supervisor_router_logic(state_with(edit_mode=True, draft_post=None)) == "content_editor"
    assert supervisor_router_logic(state_with(edit_mode=True)) == "human_review"


def test_hitl_feedback_routes_to_editor():
    state = state_with(
        draft_post=None,
        user_feedback="quita los hashtags",
        last_draft_content="borrador anterior",
    )
    assert supervisor_router_logic(state) == "content_editor"


def test_hitl_feedback_without_last_draft_falls_back_to_writer():
    state = state_with(draft_post=None, user_feedback="hazlo más corto", last_draft_content=None)
    assert supervisor_router_logic(state) == "content_writer"


# ---------- Ablación ----------

def test_ablation_skips_disabled_capabilities():
    state = state_with(
        engagement_analysis=None,
        brand_persona_json=None,
        existing_posts_on_topic=None,
        industry_trends=None,
        fleshed_out_idea=None,
        ablation_disabled=[
            "engagement_analyzer", "persona_analyst",
            "duplicate_detector", "trend_researcher",
        ],
    )
    assert supervisor_router_logic(state) == "idea_expander"


def test_ablation_disables_validators():
    state = state_with(
        fact_check_report=None,
        safety_report=None,
        ablation_disabled=["fact_checker", "safety_guard"],
    )
    assert supervisor_router_logic(state) == "human_review"


def test_ablation_single_branch_of_parallel_pair():
    state = state_with(
        existing_posts_on_topic=None,
        industry_trends=None,
        ablation_disabled=["trend_researcher"],
    )
    assert supervisor_router_logic(state) == "duplicate_detector"
