"""Tests del chunking semántico del servicio RAG (sin red ni credenciales)."""
from src.services.rag_service import chunk_text, CHUNK_SIZE


def test_empty_and_whitespace_text():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_short_text_single_chunk():
    text = "Un texto corto."
    assert chunk_text(text) == [text]


def test_long_text_respects_chunk_size():
    text = ("Párrafo de prueba con contenido variado. " * 100).strip()
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(len(c) <= CHUNK_SIZE for c in chunks)
    assert all(c.strip() for c in chunks)


def test_splitter_prefers_paragraph_boundaries():
    para = "Frase de relleno para el párrafo. " * 10
    text = f"{para.strip()}\n\n{para.strip()}\n\n{para.strip()}"
    chunks = chunk_text(text, chunk_size=400, overlap=50)
    # Ningún chunk debería empezar a mitad de palabra
    assert all(not c[0].islower() or c[0].isalpha() for c in chunks)
    assert len(chunks) >= 2


def test_no_content_is_lost():
    text = "\n\n".join(f"Sección {i}: contenido único e irrepetible {i}." for i in range(40))
    chunks = chunk_text(text, chunk_size=200, overlap=40)
    joined = " ".join(chunks)
    for i in range(40):
        assert f"irrepetible {i}" in joined
