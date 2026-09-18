"""
Indexa un histórico de posts de LinkedIn (JSON) en la memoria del agente:

1. `post_embeddings`  -> habilita el Duplicate Detector y la métrica de
   similitud de la evaluación comparativa.
2. `company_knowledge` (source_type='linkedin_post') -> habilita la memoria
   few-shot del Content Writer (los 5 mejores se marcan is_reference=True).

La puntuación de calidad usa una heurística determinista (longitud, hashtags,
estructura, CTA) para no consumir cuota LLM. Idempotente: los upserts por
post_urn permiten re-ejecutar sin duplicar.

Uso:
    python scripts/index_historic_posts.py --org-urn "urn:li:organization:111954663" \
        --file docs/formatted_agroproducciones_test_posts.json [--min-chars 50]
"""
import argparse
import json
import re
from datetime import datetime, timezone


def heuristic_score(content: str) -> int:
    """Puntuación 0-100 determinista de aptitud como post de referencia."""
    score = 40
    n = len(content)
    if 300 <= n <= 1800:
        score += 25
    elif 120 <= n < 300:
        score += 10
    hashtags = re.findall(r"#\w+", content)
    if 2 <= len(hashtags) <= 6:
        score += 15
    if "?" in content:
        score += 10
    if content.count("\n") >= 2:
        score += 10
    return min(score, 100)


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa posts históricos en la memoria del agente.")
    parser.add_argument("--org-urn", required=True)
    parser.add_argument("--file", required=True, help="JSON con lista de posts (id, publishedAt, commentary).")
    parser.add_argument("--min-chars", type=int, default=50,
                        help="Posts más cortos se omiten (contenido sin valor semántico).")
    parser.add_argument("--top-references", type=int, default=5)
    args = parser.parse_args()

    from src.services.rag_service import index_post, index_document
    from src.core.logger import logger

    with open(args.file, encoding="utf-8") as fh:
        raw_items = json.load(fh)

    posts = []
    skipped = 0
    for item in raw_items:
        if item.get("_notes"):
            continue
        content = (item.get("commentary") or item.get("content") or "").strip()
        if len(content) < args.min_chars:
            skipped += 1
            logger.info("[index_historic] Omitido post con contenido mínimo: %r", content[:40])
            continue
        published_ms = item.get("publishedAt") or item.get("published_at")
        published_iso = (
            datetime.fromtimestamp(published_ms / 1000, tz=timezone.utc).isoformat()
            if isinstance(published_ms, (int, float)) else None
        )
        posts.append({
            "urn": item.get("id") or item.get("urn"),
            "content": content,
            "published_at": published_iso,
            "score": heuristic_score(content),
        })

    posts.sort(key=lambda p: p["score"], reverse=True)
    logger.info("[index_historic] %d posts a indexar (%d omitidos por contenido mínimo).", len(posts), skipped)

    for rank, post in enumerate(posts):
        # 1. Detección de duplicados (embedding del texto completo)
        index_post(
            org_urn=args.org_urn,
            post_urn=post["urn"],
            content=post["content"],
            published_at=post["published_at"],
        )
        # 2. Memoria few-shot (top-N como referencia de estilo)
        is_reference = rank < args.top_references
        index_document(
            org_urn=args.org_urn,
            source_type="linkedin_post",
            source_id=post["urn"],
            content=post["content"],
            metadata={
                "published_at": post["published_at"],
                "score": post["score"],
                "is_reference": is_reference,
                "historic_import": True,
            },
        )
        logger.info(
            "[index_historic] %d/%d %s (score=%d, reference=%s)",
            rank + 1, len(posts), post["urn"], post["score"], is_reference,
        )

    print(f"\nIndexados {len(posts)} posts ({skipped} omitidos) para {args.org_urn}.")
    print(f"Top {args.top_references} marcados como referencia few-shot.")


if __name__ == "__main__":
    main()
