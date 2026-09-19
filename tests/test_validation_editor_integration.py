from unittest.mock import patch, MagicMock
from src.agents.multi_agent.nodes.content_editor import _resolve_edit_inputs, run_content_editor_node
from src.agents.multi_agent.state import AgentState


def test_resolve_edit_inputs_from_failed_fact_check():
    state: AgentState = {
        "draft_post": {"content": "BBVA aumentó sus ingresos un 50% este trimestre.", "hashtags": [], "call_to_action": ""},
        "fact_check_report": {
            "overall_pass": False,
            "claims": [
                {"claim": "aumentó un 50%", "verified": False, "correction": "El aumento reportado fue del 15%."}
            ]
        },
        "safety_report": {"approved": True, "severity": "none"}
    }
    base_post, instructions = _resolve_edit_inputs(state)
    assert base_post == "BBVA aumentó sus ingresos un 50% este trimestre."
    assert "aumentó un 50%" in instructions
    assert "El aumento reportado fue del 15%." in instructions


def test_resolve_edit_inputs_from_failed_safety_guard():
    state: AgentState = {
        "draft_post": {"content": "Somos 100% infalibles y los mejores del mundo.", "hashtags": [], "call_to_action": ""},
        "fact_check_report": {"overall_pass": True, "claims": []},
        "safety_report": {
            "approved": False,
            "severity": "high",
            "issues": ["Superlativos no demostrables"],
            "suggestions": ["Moderar afirmaciones de infalibilidad"]
        }
    }
    base_post, instructions = _resolve_edit_inputs(state)
    assert base_post == "Somos 100% infalibles y los mejores del mundo."
    assert "Superlativos no demostrables" in instructions
    assert "Moderar afirmaciones de infalibilidad" in instructions


@patch("src.agents.multi_agent.nodes.content_editor.ChatGoogleGenerativeAI")
def test_run_content_editor_node_increments_loops_and_resets_reports(mock_llm_cls):
    mock_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "BBVA aumentó sus ingresos un 15% este trimestre. #Banca #Finanzas\n\n¿Qué opinas?"
    mock_instance.invoke.return_value = mock_response
    mock_llm_cls.return_value = mock_instance

    state: AgentState = {
        "draft_post": {"content": "BBVA aumentó sus ingresos un 50% este trimestre.", "hashtags": [], "call_to_action": ""},
        "fact_check_report": {
            "overall_pass": False,
            "claims": [{"claim": "aumentó un 50%", "verified": False, "correction": "aumento del 15%"}]
        },
        "safety_report": {"approved": True, "severity": "none"},
        "correction_loops": 0,
        "company_profile": {"urn": "urn:li:organization:123"},
    }

    result = run_content_editor_node(state)

    assert result["fact_check_report"] is None
    assert result["safety_report"] is None
    assert result["correction_loops"] == 1
    assert "node_metrics" in result
    assert "content_editor" in result["node_metrics"]
    assert result["node_metrics"]["content_editor"]["duration_sec"] >= 0.0
