"""
Servicio RAG centralizado para PostFast.
Gestiona embedding, indexación y búsqueda semántica usando pgvector en Supabase.
Utiliza GoogleGenerativeAIEmbeddings de LangChain para mayor compatibilidad con el entorno de Poetry.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from src.services.supabase_client import get_supabase_admin
from src.core.constants import GENAI_API_KEY
from src.core.logger import logger
from src.services.custom_google_embeddings import CustomGoogleRestEmbeddings

EMBEDDING_DIMS = 768

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

# Cliente de embeddings inicializado de forma perezosa: evita que el simple
# import de este módulo falle sin GENAI_API_KEY (tests, CI, tooling).
_embeddings: CustomGoogleRestEmbeddings | None = None


def _get_embeddings() -> CustomGoogleRestEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = CustomGoogleRestEmbeddings(
            model="models/gemini-embedding-001",
            api_key=GENAI_API_KEY,
            dimensionality=EMBEDDING_DIMS,
        )
    return _embeddings


def generate_embedding(text: str) -> List[float]:
    """Genera embedding usando Gemini (gemini-embedding-001)."""
    if not text or not text.strip():
        return [0.0] * EMBEDDING_DIMS
    try:
        # embed_query es el método estándar de LangChain para obtener el embedding de una cadena
        return _get_embeddings().embed_query(text)
    except Exception as e:
        logger.error(f"Error generando embedding con Gemini: {e}")
        raise e


def generate_query_embedding(query: str) -> List[float]:
    """Genera embedding optimizado para queries de búsqueda."""
    # En GoogleGenerativeAIEmbeddings, embed_query maneja tanto queries como documentos
    return generate_embedding(query)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Divide texto en chunks con overlap para mantener contexto.

    Usa RecursiveCharacterTextSplitter: respeta límites semánticos (párrafos,
    frases) en lugar de cortar a un número fijo de caracteres, lo que mejora
    la calidad de los embeddings y de la recuperación.
    """
    if not text or not text.strip():
        return []
    if len(text) <= chunk_size:
        return [text]

    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [c.strip() for c in splitter.split_text(text) if c.strip()]


def index_document(
    org_urn: str,
    source_type: str,
    source_id: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """Indexa un documento en el vector store, dividiéndolo en chunks si es necesario."""
    if not content or not content.strip():
        return 0
    
    chunks = chunk_text(content)
    supabase = get_supabase_admin()
    indexed = 0
    
    # Si hay múltiples chunks, guardamos una copia completa sin partir para el visualizador / edición
    if len(chunks) > 1:
        try:
            full_emb = generate_embedding(content[:800])
            full_payload = {
                "org_urn": org_urn,
                "source_type": source_type,
                "source_id": source_id,
                "content": content,
                "metadata": {**(metadata or {}), "is_full_document": True},
                "embedding": full_emb,
            }
            supabase.table("company_knowledge").upsert(
                full_payload, on_conflict="org_urn,source_type,source_id,content_md5"
            ).execute()
        except Exception as e:
            logger.warning(f"Error indexando documento completo {source_id} para {org_urn}: {e}")
            
    for i, chunk in enumerate(chunks):
        chunk_source_id = f"{source_id}#chunk_{i}" if len(chunks) > 1 else source_id
        try:
            embedding = generate_embedding(chunk)
            
            payload = {
                "org_urn": org_urn,
                "source_type": source_type,
                "source_id": chunk_source_id,
                "content": chunk,
                "metadata": metadata or {},
                "embedding": embedding,
            }
            
            supabase.table("company_knowledge").upsert(
                payload, on_conflict="org_urn,source_type,source_id,content_md5"
            ).execute()
            indexed += 1
        except Exception as e:
            logger.warning(f"Error indexando chunk {chunk_source_id} para {org_urn}: {e}")
    
    return indexed


def index_post(
    org_urn: str,
    post_urn: str,
    content: str,
    summary: str = "",
    dominant_topic: str = "",
    tone: str = "",
    engagement_rate: float = 0.0,
    published_at: Optional[str] = None,
) -> None:
    """Indexa un post en post_embeddings para detección de duplicados."""
    if not content or not content.strip():
        return
    try:
        embedding = generate_embedding(content)
        supabase = get_supabase_admin()
        
        payload = {
            "org_urn": org_urn,
            "post_urn": post_urn,
            "content": content,
            "summary": summary,
            "dominant_topic": dominant_topic,
            "tone": tone,
            "engagement_rate": engagement_rate,
            "published_at": published_at,
            "embedding": embedding,
        }
        
        supabase.table("post_embeddings").upsert(
            payload, on_conflict="post_urn"
        ).execute()
        logger.info(f"Post {post_urn} indexado en post_embeddings exitosamente.")
    except Exception as e:
        logger.error(f"Error al indexar post {post_urn} para {org_urn}: {e}")


def search_knowledge(
    query: str,
    org_urn: str,
    source_type: Optional[str] = None,
    threshold: float = 0.7,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Búsqueda semántica en el knowledge base de una organización."""
    if not query or not query.strip():
        return []
    try:
        query_emb = generate_query_embedding(query)
        supabase = get_supabase_admin()
        
        result = supabase.rpc("match_company_knowledge", {
            "query_embedding": query_emb,
            "target_org_urn": org_urn,
            "match_threshold": threshold,
            "match_count": limit,
            "filter_source_type": source_type,
        }).execute()

        rows = result.data or []
        # Defensa en profundidad: la RPC ya excluye las copias de documento
        # completo (migración 002), pero filtramos también en cliente por si
        # se ejecuta contra una BD sin la migración aplicada.
        return [
            r for r in rows
            if (r.get("metadata") or {}).get("is_full_document") is not True
        ]
    except Exception as e:
        logger.error(f"Error en search_knowledge para {org_urn}: {e}")
        return []


def search_similar_posts(
    query: str,
    org_urn: str,
    threshold: float = 0.75,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Busca posts similares ya publicados por la organización."""
    if not query or not query.strip():
        return []
    try:
        query_emb = generate_query_embedding(query)
        supabase = get_supabase_admin()
        
        result = supabase.rpc("match_similar_posts", {
            "query_embedding": query_emb,
            "target_org_urn": org_urn,
            "match_threshold": threshold,
            "match_count": limit,
        }).execute()
        
        return result.data or []
    except Exception as e:
        logger.error(f"Error en search_similar_posts para {org_urn}: {e}")
        return []


def evaluate_post_quality(content: str) -> int:
    """Evalúa la calidad del post en un rango de 0 a 100 usando Gemini."""
    if not content or not content.strip():
        return 0
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from src.core.constants import MEDIUM_LLM
        
        llm = ChatGoogleGenerativeAI(
            model=MEDIUM_LLM,
            google_api_key=GENAI_API_KEY,
            temperature=0.0
        )
        
        prompt = f"""
        Evalúa la calidad de la siguiente publicación de LinkedIn del 0 al 100.
        Ten en cuenta:
        1. Estructura y legibilidad (uso de espacios, párrafos cortos).
        2. Gancho inicial (hook) que atraiga la atención.
        3. Aportación de valor y claridad del mensaje.
        4. Llamada a la acción (CTA) clara.

        Publicación a evaluar:
        \"\"\"{content}\"\"\"

        Responde EXCLUSIVAMENTE con un número entero entre 0 y 100. Ningún otro texto.
        """
        res = llm.invoke(prompt)
        res_text = res.content
        if isinstance(res_text, list):
            res_text = "".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in res_text)
        score_str = res_text.strip()
        import re
        digits = re.findall(r'\d+', score_str)
        if digits:
            score = int(digits[0])
            return max(0, min(100, score))
        return 70  # Fallback si no parsea
    except Exception as e:
        logger.warning(f"Error evaluating post quality: {e}")
        return 70


def index_and_manage_reference_posts(
    org_urn: str,
    post_id: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Indexa un post en company_knowledge y maneja la lógica de Top 5 de referencia:
    - Evalúa la calidad del post de 0 a 100.
    - Obtiene los posts de referencia actuales de la empresa (source_type='linkedin_post' y is_reference=True).
    - Si son menos de 5, marca este post como is_reference=True.
    - Si ya son 5 o más, lo compara con el de menor puntaje. Si es mayor, promueve este post y degrada el menor.
    - Guarda el post en la base vectorial con su metadata (is_reference, score).
    """
    if not content or not content.strip():
        return 0
        
    score = evaluate_post_quality(content)
    supabase = get_supabase_admin()
    
    # Obtener referencias actuales
    result = supabase.table("company_knowledge").select("id, source_id, metadata").eq("org_urn", org_urn).eq("source_type", "linkedin_post").execute()
    rows = result.data or []
    
    # Agrupar chunks por source_id para identificar posts de referencia únicos
    ref_posts = []
    for r in rows:
        meta = r.get("metadata") or {}
        if meta.get("is_reference") is True:
            # Extraer base ID
            sid = r["source_id"]
            base_id = sid.split("#chunk_")[0] if "#chunk_" in sid else sid
            if base_id not in [p["id"] for p in ref_posts]:
                ref_posts.append({
                    "id": base_id,
                    "score": meta.get("score", 0),
                    "row_ids": [r["id"]]
                })
            else:
                for p in ref_posts:
                    if p["id"] == base_id:
                        p["row_ids"].append(r["id"])
                        
    # Ordenar referencias por score ascendente
    ref_posts.sort(key=lambda x: x["score"])
    
    is_reference = False
    if len(ref_posts) < 5:
        is_reference = True
    else:
        # Comparar con el menor score del Top 5
        lowest = ref_posts[0]
        if score > lowest["score"]:
            is_reference = True
            # Degradamos el lowest en Supabase (establecer is_reference = False)
            for row_id in lowest["row_ids"]:
                # Obtener la fila para no perder otros campos de metadata
                try:
                    old_row = supabase.table("company_knowledge").select("metadata").eq("id", row_id).single().execute()
                    old_meta = old_row.data.get("metadata") or {} if old_row.data else {}
                    old_meta["is_reference"] = False
                    supabase.table("company_knowledge").update({"metadata": old_meta}).eq("id", row_id).execute()
                except Exception as e:
                    logger.warning(f"Error demoting post row {row_id}: {e}")
            logger.info(f"Demoted reference post {lowest['id']} (score {lowest['score']}) because new post {post_id} has score {score}.")
            
    final_metadata = {
        **(metadata or {}),
        "score": score,
        "is_reference": is_reference
    }
    
    # Indexar el nuevo documento
    return index_document(
        org_urn=org_urn,
        source_type="linkedin_post",
        source_id=post_id,
        content=content,
        metadata=final_metadata
    )
