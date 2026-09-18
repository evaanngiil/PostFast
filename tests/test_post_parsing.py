"""Tests del parseo determinista de posts y del recorte de perfil (utils compartidas)."""
from src.agents.multi_agent.utils import parse_post_text, slim_company_profile


def test_parse_extracts_hashtags_and_keeps_them_in_content():
    raw = (
        "🚜 El riego inteligente ya no es futuro.\n\n"
        "Nuestros sensores reducen el consumo de agua un 30%.\n\n"
        "¿Quieres saber cómo? Escríbenos.\n\n"
        "#AgTech #RiegoInteligente #Sostenibilidad"
    )
    draft = parse_post_text(raw)
    assert draft["hashtags"] == ["#AgTech", "#RiegoInteligente", "#Sostenibilidad"]
    # Los hashtags permanecen dentro del contenido (formato nativo de LinkedIn)
    assert "#AgTech" in draft["content"]
    assert draft["content"].startswith("🚜")


def test_parse_cta_is_last_substantive_line_not_hashtags():
    raw = "Hook potente.\n\nCuerpo del post.\n\n¿Qué opinas tú?\n\n#Uno #Dos #Tres"
    draft = parse_post_text(raw)
    assert draft["call_to_action"] == "¿Qué opinas tú?"


def test_parse_strips_conversational_preamble():
    raw = "Aquí tienes el borrador del post:\nEl 80% de las pymes desperdicia agua.\n\n#Agua #Pymes #Ahorro"
    draft = parse_post_text(raw)
    assert draft["content"].startswith("El 80%")


def test_parse_strips_code_fences_and_escaped_newlines():
    raw = "```\nHook.\\n\\nCuerpo.\n```"
    draft = parse_post_text(raw)
    assert "```" not in draft["content"]
    assert "\\n" not in draft["content"]
    assert "Hook.\n\nCuerpo." in draft["content"]


def test_parse_deduplicates_hashtags():
    draft = parse_post_text("Texto #IA con repetido.\n\n#IA #Datos")
    assert draft["hashtags"] == ["#IA", "#Datos"]


def test_parse_empty_input():
    draft = parse_post_text("")
    assert draft == {"content": "", "hashtags": [], "call_to_action": ""}


def test_slim_profile_drops_token_heavy_fields():
    profile = {
        "name": "AgroProducciones",
        "urn": "urn:li:organization:1",
        "industry": "AgTech",
        "about_us_content": "x" * 5000,
        "recent_posts_analysis": [{"summary": "..."}] * 50,
        "raw_batch_data": {"huge": True},
        "brand_persona_json": {"tone": "pro"},
    }
    slim = slim_company_profile(profile)
    assert "recent_posts_analysis" not in slim
    assert "raw_batch_data" not in slim
    assert "brand_persona_json" not in slim
    assert len(slim["about_us_content"]) == 1200
    assert slim["name"] == "AgroProducciones"


def test_slim_profile_handles_none():
    assert slim_company_profile(None) == {}
