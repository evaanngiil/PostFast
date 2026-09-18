"""
Pipeline de ingesta de URLs para la base de conocimiento RAG.

Flujo: validación anti-SSRF -> descarga -> limpieza de HTML (BeautifulSoup)
-> extracción del contenido principal -> chunking + embeddings -> upsert en
`company_knowledge` con source_type='web_page' (idempotente por URL).

El contenido queda disponible para el Content Writer, el Fact Checker (CRAG)
y el resto de agentes a través de search_knowledge.
"""
import ipaddress
import re
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from src.core.logger import logger

SOURCE_TYPE_WEB = "web_page"
MAX_CONTENT_CHARS = 20_000
FETCH_TIMEOUT = 15
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36 AIPost-RAG/1.0"
)

# Etiquetas que jamás contienen contenido editorial útil.
_NOISE_TAGS = ("script", "style", "noscript", "nav", "header", "footer",
               "aside", "form", "iframe", "svg", "button", "figure")


class URLIngestionError(Exception):
    """Error de validación o extracción en la ingesta de una URL."""


def validate_url(url: str) -> str:
    """
    Valida el esquema y bloquea destinos internos (anti-SSRF).

    :returns: La URL normalizada.
    :raises URLIngestionError: Si la URL es inválida o apunta a red interna.
    """
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise URLIngestionError("La URL debe ser http(s) válida.")

    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        raise URLIngestionError(f"No se pudo resolver el dominio '{parsed.hostname}'.")

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise URLIngestionError("La URL apunta a una dirección interna y no puede ingerirse.")
    return url


def extract_url_content(url: str) -> dict:
    """
    Descarga y extrae el contenido principal de una página web.

    :returns: {'title': str, 'text': str, 'url': str}
    :raises URLIngestionError: Si la descarga falla o no hay texto útil.
    """
    url = validate_url(url)

    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise URLIngestionError(f"No se pudo descargar la URL: {exc}")

    content_type = resp.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type:
        raise URLIngestionError(f"Tipo de contenido no soportado: {content_type}.")

    soup = BeautifulSoup(resp.text, "html.parser")
    title = (soup.title.get_text(strip=True) if soup.title else "") or url

    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    # Preferir el contenedor editorial principal si existe.
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n")

    # Normalizar espaciado: colapsar líneas vacías y espacios repetidos.
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if len(ln) > 1]
    clean_text = "\n".join(lines)[:MAX_CONTENT_CHARS]

    if len(clean_text) < 200:
        raise URLIngestionError(
            "La página no contiene texto extraíble suficiente "
            "(puede requerir JavaScript; prueba con otra URL o sube un PDF)."
        )

    return {"title": title[:300], "text": clean_text, "url": url}


def ingest_url(org_urn: str, url: str) -> dict:
    """
    Extrae e indexa una URL en la base de conocimiento vectorial de la organización.

    Idempotente: reingerir la misma URL actualiza sus chunks (upsert por source_id).

    :returns: {'url', 'title', 'chunks_indexed'}
    """
    from src.services.rag_service import index_document

    extracted = extract_url_content(url)
    content = f"{extracted['title']}\n\n{extracted['text']}"

    chunks = index_document(
        org_urn=org_urn,
        source_type=SOURCE_TYPE_WEB,
        source_id=extracted["url"],
        content=content,
        metadata={"url": extracted["url"], "title": extracted["title"]},
    )
    logger.info("[url_ingestion] '%s' indexada para %s (%d chunks).", extracted["url"], org_urn, chunks)
    return {"url": extracted["url"], "title": extracted["title"], "chunks_indexed": chunks}
