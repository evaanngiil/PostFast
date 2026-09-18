"""Tests de la resolución de entradas del Content Editor (lógica pura)."""
import pytest

from src.agents.multi_agent.nodes.content_editor import (
    parse_legacy_edit_prompt,
    _resolve_edit_inputs,
    LEGACY_EDIT_PREFIX,
    LEGACY_INSTRUCTIONS_MARKER,
)


def test_parse_legacy_protocol():
    text = f"{LEGACY_EDIT_PREFIX} Mi post original aquí. {LEGACY_INSTRUCTIONS_MARKER} Hazlo más corto."
    parsed = parse_legacy_edit_prompt(text)
    assert parsed == ("Mi post original aquí.", "Hazlo más corto.")


def test_parse_legacy_returns_none_for_normal_ideas():
    assert parse_legacy_edit_prompt("Escribe un post sobre IoT agrícola") is None
    assert parse_legacy_edit_prompt("") is None
    assert parse_legacy_edit_prompt(None) is None


def test_resolve_prefers_hitl_feedback():
    state = {
        "user_feedback": "quita el enlace",
        "last_draft_content": "borrador con enlace",
        "original_post": "otro post",
        "edit_instructions": "otras instrucciones",
    }
    base, instructions = _resolve_edit_inputs(state)
    assert base == "borrador con enlace"
    assert instructions == "quita el enlace"


def test_resolve_uses_structured_fields():
    state = {"original_post": "post original", "edit_instructions": "añade emojis"}
    assert _resolve_edit_inputs(state) == ("post original", "añade emojis")


def test_resolve_falls_back_to_legacy_in_idea():
    state = {
        "fleshed_out_idea": f"{LEGACY_EDIT_PREFIX} Post viejo. {LEGACY_INSTRUCTIONS_MARKER} Mejora el hook.",
    }
    assert _resolve_edit_inputs(state) == ("Post viejo.", "Mejora el hook.")


def test_resolve_raises_without_inputs():
    with pytest.raises(ValueError):
        _resolve_edit_inputs({"user_post_idea": "idea normal sin protocolo de edición"})
