from src.celery_app import celery_app
from src.core.logger import logger
from src.social_apis import (
    post_to_instagram, post_to_linkedin_organization,
    get_linkedin_company_batch_data,
    get_linkedin_posts,
)
from src.agents.multi_agent.graph import aipost_graph
from src.services.realtime_service import broadcast_task_status_sync
from src.content_generation import ContentGenerationResult
from src.services.api_client import (
    create_post,
    update_post,
    save_company_profile,
    save_engagement_insights,
    get_company_profile,
    get_engagement_insights,
    get_latest_stored_snapshot,
    update_change_check_timestamp,
)
from src.agents.multi_agent.change_detector import detect_company_changes, ChangeReport
from src.agents.multi_agent.nodes.engagement_extractor import run_engagement_extractor_node
from src.agents.multi_agent.nodes.engagement_analyzer import run_engagement_analyzer_node

from celery.exceptions import Ignore
from datetime import datetime, timezone
import time
import uuid

try:
    # Contador de tokens de langchain-core: captura todas las llamadas LLM del
    # proceso mediante contextvars (incluye las de los nodos del grafo).
    from langchain_core.callbacks import get_usage_metadata_callback
except ImportError:  # Compatibilidad con versiones antiguas de langchain-core
    get_usage_metadata_callback = None


def _summarize_usage(usage_metadata: dict) -> dict:
    """Agrega el usage_metadata por modelo en un resumen total de tokens."""
    total_input = sum((u or {}).get("input_tokens", 0) for u in usage_metadata.values())
    total_output = sum((u or {}).get("output_tokens", 0) for u in usage_metadata.values())
    return {
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "by_model": usage_metadata,
    }


def _paginate_org_posts(access_token: str, org_urn: str, first_page: list, page_size: int, max_posts: int, log_tag: str) -> list:
    """
    Completa la paginación de posts de LinkedIn a partir de la primera página.

    Usa get_linkedin_posts directamente para las páginas adicionales (evita
    re-fetchar org_details y followers en cada página).
    """
    all_posts = list(first_page or [])
    start = page_size
    while len(all_posts) > 0 and len(all_posts) % page_size == 0 and len(all_posts) < max_posts:
        try:
            page_posts = get_linkedin_posts(
                access_token,
                target_urn=org_urn,
                count=page_size,
                start=start,
            ) or []
            if not page_posts:
                break
            all_posts.extend(page_posts)
            start += page_size
            logger.info(
                "[%s] Página adicional: +%d posts (total=%d) para %s",
                log_tag, len(page_posts), len(all_posts), org_urn,
            )
            if len(page_posts) < page_size:
                break
        except Exception as page_exc:
            logger.warning(
                "[%s] Error en paginación (start=%d) para %s: %s. Usando posts ya obtenidos.",
                log_tag, start, org_urn, page_exc,
            )
            break
    return all_posts


@celery_app.task(name="ingest_url_task", bind=True, max_retries=2, default_retry_delay=20)
def ingest_url_task(self, org_urn: str, url: str):
    """
    Ingesta asíncrona de una URL en la base de conocimiento RAG de la organización.

    Se encola automáticamente cuando el usuario aporta una 'URL de referencia'
    en el formulario de generación (persistencia a largo plazo), además de la
    ingesta manual desde la Base de Conocimiento.
    """
    from src.services.url_ingestion import ingest_url, URLIngestionError

    logger.info("[ingest_url][Task %s] Ingesta de %s para %s", self.request.id, url, org_urn)
    try:
        result = ingest_url(org_urn, url)
        return {"status": "COMPLETED", **result}
    except URLIngestionError as exc:
        # Error de contenido/validación: no tiene sentido reintentar.
        logger.warning("[ingest_url][Task %s] URL no ingerible: %s", self.request.id, exc)
        return {"status": "SKIPPED", "url": url, "reason": str(exc)}
    except Exception as exc:
        logger.exception("[ingest_url][Task %s] Error inesperado: %s", self.request.id, exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def publish_post_task(self, platform, account_id, access_token, content, **kwargs):
    """
    Despacha y persiste una publicación en redes sociales mediante workers de Celery.

    :param platform: Plataforma destino ('LinkedIn', 'Instagram').
    :param account_id: Identificador de la cuenta objetivo (ej. URN o IG ID).
    :param access_token: Token de sesión con permisos de publicación.
    :param content: Cuerpo de la publicación.
    :param kwargs: Argumentos opcionales (ej: 'page_access_token', 'image_url', 'post_id').
    :returns: Payload de confirmación del estado de publicación.
    :raises Exception: Si la API de red social rechaza el intento (excepto 422 duplicates).
    """
    logger.info(f"[Task ID: {self.request.id}] Iniciando publicacion de post en {platform} - Cuenta: {account_id}")

    post_id = kwargs.get('post_id')

    def save_or_update_post(status: str, published_time=None, image_url=None, link_url=None):
        if post_id:
            p_time = published_time.isoformat() if published_time else None
            update_post(post_id, {
                "status": status,
                "published_time": p_time,
                "image_url": image_url,
                "link_url": link_url
            })
        else:
            create_post(
                content=content,
                status=status,
                platform=platform,
                account_id=account_id,
                published_time=published_time,
                image_url=image_url,
                link_url=link_url
            )

    start_time = time.time()
    try:
        result = None
        plat_lower = platform.lower()

        if plat_lower == "instagram":
            page_access_token = kwargs.get('page_access_token', access_token)
            ig_user_id = account_id
            image_url = kwargs.get('image_url')
            if not page_access_token: raise ValueError("Falta page_access_token para el post de Instagram")
            if not image_url: raise ValueError("Falta image_url para el post de Instagram")
            result = post_to_instagram(ig_user_id, page_access_token, image_url=image_url, caption=content)
            save_or_update_post(
                status="published",
                published_time=datetime.now(timezone.utc),
                image_url=image_url
            )

        elif plat_lower == "linkedin":
            org_urn = account_id
            try:
                result = post_to_linkedin_organization(org_urn, access_token, content, link_url=kwargs.get('link_url'))
                # Publicación exitosa → registrar en BD
                save_or_update_post(
                    status="published",
                    published_time=datetime.now(timezone.utc),
                    link_url=kwargs.get('link_url')
                )
            except Exception as linkedin_exc:
                error_str = str(linkedin_exc)
                # LinkedIn 422 "duplicate" = el post YA está publicado en LinkedIn.
                # Registramos como publicado en BD y NO relanzamos el error.
                if "422" in error_str and "duplicate" in error_str.lower():
                    logger.warning(
                        f"[Task ID: {self.request.id}] LinkedIn reported duplicate (422) for "
                        f"{account_id}. Post was already published. Marking as published in DB."
                    )
                    save_or_update_post(
                        status="published",
                        published_time=datetime.now(timezone.utc),
                        link_url=kwargs.get('link_url')
                    )
                    result = {"id": "duplicate_already_published"}
                else:
                    raise linkedin_exc

        elapsed_time = time.time() - start_time
        post_id_val = result.get('id', 'N/A') if result else 'N/A'
        logger.info(f"[Task ID: {self.request.id}] Publicado exitosamente en {platform} - Cuenta: {account_id}. Post ID: {post_id_val}. Tiempo: {elapsed_time:.2f}s")

        return {"status": "Completado", "platform": platform, "account_id": account_id, "post_id": post_id_val, "elapsed_time": elapsed_time}

    except Exception as exc:
        logger.exception(f"[Task ID: {self.request.id}] Fallo la tarea de publicacion para {platform} - Cuenta: {account_id}. Error: {exc}")
        if post_id:
            try:
                update_post(post_id, {"status": "failed"})
            except Exception as db_err:
                logger.error(f"Error updating post to failed status: {db_err}")
        return {"status": "Fallido", "platform": platform, "account_id": account_id, "error": str(exc)}


# Validación heurística de pre-condiciones del tenant
_IDENTITY_FIELDS = ("name", "urn", "vanity_name")


def _ensure_complete_company_profile(
    profile_data: dict,
    stored_record: dict,
    selected_account: dict,
    access_token: str,
    org_urn: str,
) -> tuple:
    """
    Valida un perfil corporativo y orquesta la restitución de campos nulos en caso de ser necesario.

    Implementa una estrategia escalonada:
    1. Resuelve metadata básica (identidad) desde la sesión cacheada sin coste de API.
    2. Realiza fetching estructurado (API) de la red social si requiere claims de contenido ('about_us_content').
    3. Hace scraping web semántico con LLM como fallback extremo.

    :param profile_data: Snapshot del data_layer actual.
    :param stored_record: Fila consolidada de la DB.
    :param selected_account: Contexto de UI inyectado.
    :param access_token: JWT/OAuth Token vigente.
    :param org_urn: URN base de LinkedIn.
    :returns: Tupla (completed_profile, was_modified).
    """
    profile = dict(profile_data)
    modified = False

    fallback_map = {
        "name": selected_account.get("name", ""),
        "urn": selected_account.get("urn") or org_urn,
        "vanity_name": selected_account.get("vanityName", ""),
    }
    for field, fallback_value in fallback_map.items():
        if not profile.get(field) and fallback_value:
            profile[field] = fallback_value
            modified = True

    has_content = bool(profile.get("about_us_content") or profile.get("specialties"))

    if not has_content and access_token and org_urn:
        try:
            batch = get_linkedin_company_batch_data(
                access_token=access_token,
                org_urn=org_urn,
                posts_count=0,
            )
            org_details = batch.get("organization") or {}

            from src.agents.multi_agent.nodes.company_profiler import _merge_org_details
            _merge_org_details(profile, org_details)
            modified = True

            has_content = bool(
                profile.get("about_us_content") or profile.get("specialties")
            )
            logger.info(
                "[profile_completion] Org details fetched for %s — "
                "has_content=%s after merge.",
                org_urn, has_content,
            )
        except Exception as exc:
            logger.warning(
                "[profile_completion] Org details API failed for %s: %s",
                org_urn, exc,
            )

    is_personal_profile = org_urn and org_urn.startswith("urn:li:person:")
    if not has_content and not is_personal_profile:
        vanity = profile.get("vanity_name") or selected_account.get("vanityName", "")
        if vanity:
            try:
                from src.agents.multi_agent.nodes.company_profiler import (
                    _scrape_and_extract,
                    _merge_scraped,
                )
                from langchain_google_genai import ChatGoogleGenerativeAI
                from src.core.constants import MEDIUM_LLM, GENAI_API_KEY

                llm = ChatGoogleGenerativeAI(
                    model=MEDIUM_LLM,
                    google_api_key=GENAI_API_KEY,
                    temperature=0.0,
                )
                scraped = _scrape_and_extract(vanity, llm)
                if scraped:
                    _merge_scraped(profile, scraped)
                    modified = True
                    logger.info(
                        "[profile_completion] Scraped public page for '%s' — "
                        "about_us=%s specialties=%s.",
                        vanity,
                        bool(profile.get("about_us_content")),
                        bool(profile.get("specialties")),
                    )
            except Exception as exc:
                logger.warning(
                    "[profile_completion] Scraping failed for '%s': %s",
                    vanity, exc,
                )


    if modified:
        try:
            save_company_profile(
                org_urn=org_urn,
                org_name=profile.get("name", ""),
                raw_batch_data=stored_record.get("raw_batch_data"),
                company_profile_data=profile,
                follower_count=stored_record.get("follower_count"),
            )
            logger.info(
                "[profile_completion] Persisted completed profile for %s.",
                org_urn,
            )
        except Exception as exc:
            logger.warning(
                "[profile_completion] Failed to persist updated profile for %s: %s",
                org_urn, exc,
            )


    identity_ok = all(profile.get(f) for f in _IDENTITY_FIELDS)
    if not identity_ok:
        logger.warning(
            "[profile_completion] Profile for %s still missing identity fields. "
            "Falling back to company_profiler node.",
            org_urn,
        )
        return None, False

    return profile, modified


# Re-try decorators para estabilidad de la conexión PostgreSQL
def _invoke_with_retry(fn, *, logger, max_attempts=3, delay=3):
    """
    Wrapper transaccional que asegura robustez contra dead connections del connection-pool de PostgreSQL.

    :param fn: Closure / Lambda a ser ejecutado.
    :param logger: Handler de trace.
    :param max_attempts: Límite de reintentos en caso de Timeouts / OperationalErrors.
    :param delay: Segundos de pausa entre reintentos.
    :returns: El resultado orgánico del invoke.
    :raises psycopg.OperationalError: Si se agotan los reintentos.
    """
    import psycopg
    try:
        from psycopg_pool import PoolTimeout
    except ImportError:
        PoolTimeout = type(None)

    last_err = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except (psycopg.OperationalError, psycopg.InterfaceError, PoolTimeout) as db_err:
            last_err = db_err
            if attempt < max_attempts - 1:
                logger.warning(
                    "Error de conexion a Postgres en el intento %d/%d, "
                    "reintentando en %ds: %s",
                    attempt + 1, max_attempts, delay, db_err,
                )
                import time
                time.sleep(delay)
                continue
            raise


@celery_app.task(name="content_generation_task", bind=True)
def content_generation_task(self, payload_dict=None):
    """
    Instancia principal de dispatch para generación asistida usando LangGraph.

    Inyecta pre-carga de metadata (perfil de empresa y engagement) para minimizar 
    latencia y saltar etapas redundantes del grafo. Procesa estados suspendidos 
    como 'PENDING_USER_INPUT' devolviendo un checkpoint transaccional.
    """
    thread_id = payload_dict.get("thread_id") if payload_dict and payload_dict.get("thread_id") else str(uuid.uuid4())
    task_id = self.request.id
    logger.info(f"Iniciando nueva tarea de generacion Multi-Agente {task_id} | Thread ID: {thread_id}")

    # Emitir broadcast de inicio de tarea
    broadcast_task_status_sync(
        task_id, 
        'STARTED', 
        {"message": "Iniciando pipeline multi-agente de generación de contenido..."}
    )

    edit_mode = payload_dict.get("edit_mode", False)
    link_url = payload_dict.get("link_url")
    org_urn = payload_dict.get("selected_account", {}).get("urn", "")

    # Ingesta síncrona de la URL de referencia (si existe) para garantizar su presencia
    # en la base de conocimientos RAG antes de iniciar la generación en el grafo.
    if link_url and org_urn:
        try:
            from src.services.url_ingestion import ingest_url
            logger.info("[content_generation_task] Indexando URL de referencia de forma síncrona: %s", link_url)
            ingest_url(org_urn=org_urn, url=link_url)
            logger.info("[content_generation_task] URL de referencia indexada correctamente en RAG.")
        except Exception as e:
            logger.warning("[content_generation_task] Error indexando URL de referencia: %s", e)

    initial_state = {
        "linkedin_access_token": payload_dict.get("access_token", ""),
        "user_post_idea": payload_dict.get("query", ""),
        "selected_account": payload_dict.get("selected_account", {}),
        "link_url": link_url,
        "task_id": task_id,  # Inyectado para que cada nodo pueda emitir progresos
        "edit_mode": edit_mode,
        # Modo edición estructurado (sustituye al string mágico embebido en query)
        "original_post": payload_dict.get("original_post"),
        "edit_instructions": payload_dict.get("edit_instructions"),
        # Configuración de ablación para la evaluación comparativa del TFG
        "ablation_disabled": payload_dict.get("ablation_disabled") or [],
    }

    if edit_mode:
        logger.info("[AI LangGraph] Iniciando en MODO EDICIÓN RÁPIDA. Omitiendo nodos de investigación.")
        initial_state.update({
            "knowledge_indexed": True,
            "engagement_insights": {"skipped": True},
            "engagement_analysis": {"skipped": True},
            "brand_persona_json": {
                "name": payload_dict.get("account_name", "AIPost User"),
                "tone_description": payload_dict.get("tone", "Profesional")
            },
            "existing_posts_on_topic": [],
            "industry_trends": "skipped",
            "fleshed_out_idea": payload_dict.get("query", ""),
            "draft_post": None,
            "fact_check_report": {"overall_pass": True, "claims": [], "skipped": True},
            "safety_report": {"approved": True, "issues": [], "suggestions": [], "skipped": True}
        })

    # Reconciliación de dependencias (Supabase -> Graph).
    org_urn = initial_state["selected_account"].get("urn", "")
    access_token = initial_state["linkedin_access_token"]

    if org_urn:
        stored_record = get_company_profile(org_urn)
        profile_data = (stored_record or {}).get("company_profile") or (stored_record or {}).get("company_profile_data")

        if profile_data and isinstance(profile_data, dict):
            completed, was_modified = _ensure_complete_company_profile(
                profile_data=profile_data,
                stored_record=stored_record,
                selected_account=initial_state["selected_account"],
                access_token=access_token,
                org_urn=org_urn,
            )
            if completed:
                initial_state["company_profile"] = completed
                logger.info(
                    "Se inyecto company_profile desde Supabase para %s "
                    "(modificado=%s) — omitiendo el nodo company_profiler.",
                    org_urn, was_modified,
                )
                if "brand_persona_json" in completed and completed["brand_persona_json"]:
                    initial_state["brand_persona_json"] = completed["brand_persona_json"]
                    logger.info(
                        "Se inyecto brand_persona_json desde Supabase para %s.",
                        org_urn,
                    )
                # Check if we already have indexed knowledge in Supabase to skip knowledge_ingester
                try:
                    from src.services.supabase_client import get_supabase_admin
                    supabase_adm = get_supabase_admin()
                    res_knowledge = supabase_adm.table("company_knowledge").select("id").eq("org_urn", org_urn).limit(1).execute()
                    if res_knowledge.data:
                        initial_state["knowledge_indexed"] = True
                        logger.info(
                            "Se detecto base de conocimientos ya indexada para %s. "
                            "Omitiendo knowledge_ingester.",
                            org_urn,
                        )
                except Exception as rag_err:
                    logger.warning(
                        "No se pudo comprobar si la base de conocimientos RAG ya estaba indexada: %s",
                        rag_err,
                    )
        else:
            if edit_mode:
                initial_state["company_profile"] = {
                    "name": payload_dict.get("account_name", "AIPost User"),
                    "urn": org_urn
                }
                logger.info("Modo edición: Inyectando perfil de empresa de respaldo.")
            else:
                logger.info(
                    "No hay company_profile_data utilizable en Supabase para %s — "
                    "el nodo company_profiler se ejecutara.",
                    org_urn,
                )

        if not edit_mode:
            existing_engagement = get_engagement_insights(org_urn)
            if existing_engagement:
                if existing_engagement.get("aggregate_metrics"):
                    initial_state["engagement_insights"] = existing_engagement
                    logger.info(
                        "Se inyectaron insights de engagement desde Supabase para %s.",
                        org_urn,
                    )
                if existing_engagement.get("top_performing_posts"):
                    initial_state["top_performing_posts"] = existing_engagement["top_performing_posts"]
                if existing_engagement.get("engagement_analysis"):
                    initial_state["engagement_analysis"] = existing_engagement["engagement_analysis"]
                    logger.info(
                        "Se inyecto analisis de engagement desde Supabase para %s.",
                        org_urn,
                    )

    selected_skill_ids = payload_dict.get("selected_skills") or []
    single_skill_id = payload_dict.get("skill_id")
    if single_skill_id and single_skill_id not in selected_skill_ids:
        selected_skill_ids = list(selected_skill_ids)
        selected_skill_ids.append(single_skill_id)

    selected_skills_list = []
    from src.services.api_client import get_skill_by_id
    for sid in selected_skill_ids:
        skill_data = get_skill_by_id(sid)
        if skill_data:
            selected_skills_list.append(skill_data)
            logger.info(f"Inyectada habilidad seleccionada: {skill_data.get('name')} ({sid})")
        else:
            logger.warning(f"No se encontró la habilidad con ID: {sid}")

    initial_state["selected_skills"] = selected_skills_list
    if selected_skills_list:
        initial_state["selected_skill"] = selected_skills_list[0]
    else:
        initial_state["selected_skill"] = None

    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Invoca el worker de LangGraph midiendo el consumo real de tokens
        # de todas las llamadas LLM del pipeline (observabilidad de coste).
        usage_summary = {}
        if get_usage_metadata_callback is not None:
            with get_usage_metadata_callback() as usage_cb:
                result_state = _invoke_with_retry(
                    lambda: aipost_graph.invoke(initial_state, config=config),
                    logger=logger,
                )
            usage_summary = _summarize_usage(usage_cb.usage_metadata)
            logger.info(
                "[tokens] Tarea %s: %s tokens totales (in=%s / out=%s)",
                task_id,
                usage_summary.get("total_tokens"),
                usage_summary.get("total_input_tokens"),
                usage_summary.get("total_output_tokens"),
            )
        else:
            result_state = _invoke_with_retry(
                lambda: aipost_graph.invoke(initial_state, config=config),
                logger=logger,
            )

        state_snapshot = aipost_graph.get_state(config)

        if state_snapshot.next and "human_review" in state_snapshot.next:
            logger.info("Grafo pausado para revision humana")

            draft_post = result_state.get("draft_post", {})
            draft_content = draft_post.get("content", "Borrador NO disponible.") if draft_post else "Borrador NO disponible."

            if isinstance(draft_content, str):
                draft_content = draft_content.replace("\\n", "\n")

            # Emitir broadcast de pausa interactiva HITL
            broadcast_task_status_sync(
                task_id,
                'PENDING_USER_INPUT',
                {
                    'checkpoint': {'thread_id': thread_id},
                    'draft_content': draft_content,
                    'fact_check_report': result_state.get('fact_check_report'),
                    'safety_report': result_state.get('safety_report'),
                    'knowledge_gap': result_state.get('knowledge_gap'),
                }
            )

            self.update_state(
                state='PENDING_USER_INPUT',
                meta={
                    'status': 'PENDING_USER_INPUT',
                    'checkpoint': {'thread_id': thread_id},
                    'draft_content': draft_content
                }
            )
            raise Ignore()

        final_post = result_state.get("draft_post", {}).get("content", "") if result_state.get("draft_post") else ""

        if isinstance(final_post, str):
            final_post = final_post.replace("\\n", "\n")

        # Emitir broadcast de completado
        broadcast_task_status_sync(
            task_id,
            'COMPLETED',
            {
                'final_post': final_post,
                'fact_check_report': result_state.get('fact_check_report'),
                'safety_report': result_state.get('safety_report'),
                'knowledge_gap': result_state.get('knowledge_gap'),
                'token_usage': usage_summary,
            }
        )

        return {
            "final_post": final_post,
            "status": "COMPLETED",
            "token_usage": usage_summary,
        }

    except Ignore:
        raise
    except Exception as e:
        logger.exception(f"Error en el grafo multi-agente: {e}")
        # Emitir broadcast de fallo
        broadcast_task_status_sync(
            task_id,
            'FAILED',
            {
                'error': str(e)
            }
        )
        raise


@celery_app.task(
    name="company_batch_extraction_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def company_batch_extraction_task(self, org_urn: str, org_name: str, access_token: str):
    """
    Pipeline asíncrono para ingesta en masa de datos del tenant (batch extraction).

    Flujo operativo tolerante a fallos:
    1. Idempotencia: Bypass temprano si la sincronía ya está finalizada.
    2. LinkedIn API: Recolección y paginación masiva.
    3. FASE A: Ingesta relacional atómica de los datos crudos (salvaguarda de progreso).
    4. FASE B: LLM Processing vía el broker de LangGraph (company_profiler_node).
    5. FASE C: Analítica secundaria de Engagement.

    :param org_urn: URN objetivo.
    :param org_name: Alias descriptivo.
    :param access_token: LinkedIn OAuth Token.
    :returns: Confirmación estructurada del proceso de ingesta.
    """
    logger.info(
        "[company_batch][Task %s] Iniciando extraccion batch para org '%s' (%s)",
        self.request.id, org_name, org_urn,
    )

    # Resolver idempotencia y cache en estados fraccionarios de ingesta

    existing_profile = get_company_profile(org_urn)
    if existing_profile:
        posts_stored    = existing_profile.get("posts_stored_count") or 0
        posts_analyzed  = existing_profile.get("posts_analyzed_count") or 0
        total_available = existing_profile.get("total_posts_available") or 0

        # Fallback legacy: registros creados antes de los contadores.
        # Si tiene recent_posts_analysis con datos, el perfil está completo.
        has_llm_analysis = bool(
            existing_profile.get("recent_posts_analysis")
            or (
                isinstance(existing_profile.get("company_profile"), dict)
                and existing_profile["company_profile"].get("recent_posts_analysis")
            )
            or (
                isinstance(existing_profile.get("company_profile_data"), dict)
                and existing_profile["company_profile_data"].get("recent_posts_analysis")
            )
        )

        # Fallback legacy: perfiles con pocos/cero posts reales (ej. empresa nueva
        # con 0-1 posts). Si company_profile_data tiene campos enriquecidos (name, industry,
        # about_us_content...) el perfil ya fue procesado aunque recent_posts_analysis esté
        # vacío y los contadores sean 0.
        cpd = existing_profile.get("company_profile") or existing_profile.get("company_profile_data") or {}
        has_enriched_profile = isinstance(cpd, dict) and bool(
            cpd.get("industry")
            or cpd.get("about_us_content")
            or cpd.get("specialties")
            or cpd.get("company_type")
        )

        profile_complete = (
            # Caso normal: contadores en orden
            (posts_stored > 0 and posts_stored == posts_analyzed)
            # Caso legacy: sin contadores pero análisis LLM presente
            or (posts_stored == 0 and has_llm_analysis)
            # Caso legacy: perfil enriquecido con datos de org aunque no haya posts
            or (posts_stored == 0 and has_enriched_profile)
        )

        if profile_complete:
            logger.info(
                "[batch_extraction] Perfil completo para '%s' "
                "(stored=%d analyzed=%d has_llm=%s). SKIPPED.",
                org_name, posts_stored, posts_analyzed, has_llm_analysis,
            )
            return {
                "status": "SKIPPED",
                "reason": "profile_complete",
                "org_urn": org_urn,
            }

        # Perfil incompleto: stored>0 pero analyzed<stored significa que la API
        # ya se llamó (FASE A OK) pero el LLM falló (FASE B pendiente).
        # En ese caso reutilizamos raw_batch_data de Supabase para no volver
        # a consumir cuota de la LinkedIn API.
        reuse_cached_batch = (
            posts_stored > 0
            and posts_analyzed < posts_stored
            and bool(existing_profile.get("raw_batch_data"))
        )

        logger.info(
            "[batch_extraction] Perfil incompleto para '%s': "
            "stored=%d analyzed=%d total_available=%d reuse_cache=%s -> re-ejecutando.",
            org_name, posts_stored, posts_analyzed, total_available, reuse_cached_batch,
        )
        # NO hacer return -> continuar con la extracción (o reutilización de caché)

    if not existing_profile:
        reuse_cached_batch = False

    try:
        # 1. LinkedIn API batch (con paginación hasta MAX_POSTS)
        # Si hay raw_batch_data cacheado en Supabase (FASE A previa OK, FASE B fallida),
        # lo reutilizamos directamente para no consumir cuota de LinkedIn API.
        MAX_POSTS = 1000  # límite razonable; LinkedIn /posts devuelve máx 20 por página
        PAGE_SIZE = 20

        cached_batch = existing_profile.get("raw_batch_data") if (existing_profile and reuse_cached_batch) else None

        if cached_batch:
            logger.info(
                "[company_batch] Reutilizando raw_batch_data cacheado para '%s' (evita re-llamada API)",
                org_name,
            )
            batch_data = cached_batch
        else:
            logger.info("[company_batch] Llamando a LinkedIn API batch para %s", org_urn)

            batch_data = get_linkedin_company_batch_data(
                access_token=access_token,
                org_urn=org_urn,
                posts_count=PAGE_SIZE,
            )
            batch_data["posts"] = _paginate_org_posts(
                access_token, org_urn,
                first_page=batch_data.get("posts"),
                page_size=PAGE_SIZE,
                max_posts=MAX_POSTS,
                log_tag="company_batch",
            )

        org_details    = batch_data.get("organization") or {}
        posts          = batch_data.get("posts") or []
        follower_count = batch_data.get("follower_count")
        vanity_name    = org_details.get("vanityName")

        logger.info(
            "[company_batch] Batch recibido: org_details=%s, posts=%d, followers=%s",
            "OK" if org_details else "VACIO", len(posts), follower_count,
        )

        # Fase A: Snapshot atómico temprano de la ingesta (raw payload base) para resiliencia del pipeline.
        from src.agents.multi_agent.change_detector import (
            _extract_latest_post as _cd_extract_post,
            _compute_profile_hash as _cd_compute_hash,
        )
        _fase_a_post_urn, _fase_a_post_published_at = _cd_extract_post(posts)
        _fase_a_profile_hash = _cd_compute_hash(org_details)
        logger.info("[company_batch] [FASE A] Guardando datos base en Supabase para '%s'", org_name)
        record_id = save_company_profile(
            org_urn=org_urn,
            org_name=org_name,
            raw_batch_data=batch_data,
            company_profile_data=None,
            follower_count=follower_count,
            posts_stored_count=len(posts),
            total_posts_available=len(posts),
            last_post_urn=_fase_a_post_urn,
            last_post_published_at=_fase_a_post_published_at,
            profile_hash=_fase_a_profile_hash,
            followers_at_last_check=follower_count,
        )
        logger.info(
            "[company_batch] [FASE A] Datos base guardados (id=%s) para '%s'",
            record_id, org_name,
        )

        # Fase B: Handshake con el nodo LLM (company_profiler). 
        # Inyecta payload crudo para procesado masivo y clausura callbacks (save_profile_fn) hacia la DB relacional.
        company_profile_data = None

        if vanity_name:
            try:
                from src.agents.multi_agent.nodes.company_profiler import run_company_profiler_node
                from src.agents.multi_agent.state import AgentState

                def _save_profile_fn(
                    org_urn,
                    org_name,
                    raw_batch_data,
                    company_profile_data,
                    follower_count,
                    **kwargs,
                ):
                    """Closure que delega en save_company_profile (upsert por org_urn)."""
                    return save_company_profile(
                        org_urn=org_urn,
                        org_name=org_name,
                        raw_batch_data=raw_batch_data,
                        company_profile_data=company_profile_data,
                        follower_count=follower_count,
                        **kwargs,
                    )

                mock_state: AgentState = {
                    "linkedin_access_token": access_token,
                    "user_post_idea": "",
                    "selected_account": {
                        "urn": org_urn,
                        "name": org_name,
                        "vanityName": vanity_name,
                    },
                    "company_profile": None,
                    "brand_persona_json": None,
                    "fleshed_out_idea": None,
                    "draft_post": None,
                    "engagement_insights": None,
                    "top_performing_posts": None,
                    "engagement_analysis": None,
                    # Inyectamos el batch ya extraído (con paginación completa)
                    # para que el profiler no vuelva a llamar a LinkedIn API.
                    "raw_batch_data": batch_data,
                    # Hook de persistencia incremental:
                    # El nodo llama a esto en FASE A (datos base) y FASE B
                    # (perfil completo + posts analizados).
                    "save_profile_fn": _save_profile_fn,
                }

                node_result = run_company_profiler_node(mock_state)
                company_profile_dict = node_result.get("company_profile")
                if company_profile_dict:
                    company_profile_data = dict(company_profile_dict)
                    n_posts = len(company_profile_data.get("recent_posts_analysis") or [])
                    logger.info(
                        "[company_batch] Perfil enriquecido para '%s' (%d posts analizados)",
                        org_name, n_posts,
                    )

            except Exception as profiler_exc:
                logger.warning(
                    "[company_batch] Fallo en company_profiler LLM para %s: %s. "
                    "Los datos base (FASE A) ya estan en Supabase.",
                    org_urn, profiler_exc,
                )
        else:
            logger.warning(
                "[company_batch] vanityName no disponible para %s; se omite enriquecimiento LLM.",
                org_urn,
            )

        # Upsert final de seguridad: Garantiza la persistencia del perfil enriquecido si hubo excepciones
        # intermedias (FASE B), e inyecta la metadata completa para el change-detection (v2).
        if company_profile_data is not None:
            n_analyzed = len((company_profile_data or {}).get("recent_posts_analysis") or [])
            record_id = save_company_profile(
                org_urn=org_urn,
                org_name=org_name,
                raw_batch_data=batch_data,
                company_profile_data=company_profile_data,
                follower_count=follower_count,
                posts_stored_count=len(posts),
                posts_analyzed_count=n_analyzed,
                total_posts_available=len(posts),
                last_post_urn=_fase_a_post_urn,
                last_post_published_at=_fase_a_post_published_at,
                profile_hash=_fase_a_profile_hash,
                followers_at_last_check=follower_count,
            )
            logger.info(
                "[company_batch][Task %s] Perfil completo guardado (id=%s) para '%s'",
                self.request.id, record_id, org_name,
            )

        # FASE C: Extracción y Analítica LLM del Engagement
        engagement_record_id = None
        try:
            if company_profile_data is not None:
                mock_state["company_profile"] = company_profile_data

                extractor_result = run_engagement_extractor_node(mock_state)
                mock_state.update(extractor_result)
                logger.info(
                    "[company_batch][Task %s] FASE C extractor done for '%s' — "
                    "%d top posts identified",
                    self.request.id, org_name,
                    len(extractor_result.get("top_performing_posts") or []),
                )

                analyzer_result = run_engagement_analyzer_node(mock_state)
                mock_state.update(analyzer_result)
                logger.info(
                    "[company_batch][Task %s] FASE C analyzer done for '%s'",
                    self.request.id, org_name,
                )

                engagement_record_id = save_engagement_insights(
                    org_urn=org_urn,
                    engagement_insights=extractor_result.get("engagement_insights", {}),
                    top_performing_posts=extractor_result.get("top_performing_posts", []),
                    engagement_analysis=analyzer_result.get("engagement_analysis"),
                )
                logger.info(
                    "[company_batch][Task %s] FASE C persisted (engagement_id=%s) for '%s'",
                    self.request.id, engagement_record_id, org_name,
                )
            else:
                logger.info(
                    "[company_batch][Task %s] Skipping FASE C — no company_profile for '%s'",
                    self.request.id, org_name,
                )
        except Exception as eng_exc:
            logger.warning(
                "[company_batch][Task %s] FASE C engagement failed for %s: %s. "
                "FASE A+B data is safe in Supabase.",
                self.request.id, org_urn, eng_exc,
            )

        # FASE D: Ingesta en Vector Store RAG (Simulación corporativa y conocimiento)
        try:
            if company_profile_data is not None:
                logger.info(f"[company_batch][Task {self.request.id}] Iniciando Fase D: Indexación vectorial RAG...")
                from src.agents.multi_agent.nodes.knowledge_ingester import run_knowledge_ingester_node
                mock_state["company_profile"] = company_profile_data
                mock_state["top_performing_posts"] = mock_state.get("top_performing_posts", [])
                run_knowledge_ingester_node(mock_state)
                logger.info(f"[company_batch][Task {self.request.id}] Fase D: Indexación RAG completada.")
        except Exception as rag_exc:
            logger.warning(
                f"[company_batch][Task {self.request.id}] Error en Fase D (indexación RAG): {rag_exc}"
            )

        return {
            "status": "COMPLETED",
            "org_urn": org_urn,
            "org_name": org_name,
            "record_id": record_id,
            "engagement_record_id": engagement_record_id,
            "posts_extracted": len(posts),
            "follower_count": follower_count,
            "llm_profile_generated": company_profile_data is not None,
        }

    except Exception as exc:
        logger.exception(
            "[company_batch][Task %s] Error en extraccion batch para %s: %s",
            self.request.id, org_urn, exc,
        )
        raise self.retry(exc=exc)


@celery_app.task(
    name="company_batch_refresh_task",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def company_batch_refresh_task(self, org_urn: str, org_name: str, access_token: str, change_report_data: dict = None):
    """
    Ejecuta un ciclo integral de re-ingesta y actualización de modelado para el tenant corporativo.

    Se ejecuta condicionalmente post-verificación de cambios en los orígenes de datos, optimizando
    el procesamiento y limitándolo a entidades con drift demostrable.

    :param org_urn: URN identificador del tenant.
    :param org_name: Nombre semántico del tenant.
    :param access_token: Token de sesión vigente.
    :param change_report_data: Delta analítico opcional de mutaciones previas (ChangeReport DTO).
    :returns: Resumen del refresco, o dict de 'NO_CHANGES' si resultó ser un falso positivo.
    """
    from src.agents.multi_agent.nodes.company_profiler import run_company_profiler_node

    task_id = self.request.id
    logger.info(
        "[batch_refresh][Task %s] Iniciando refresco para '%s' (%s) | pre_checked=%s",
        task_id, org_name, org_urn, change_report_data is not None,
    )

    try:
        # Construcción o deducción de metadata de drifting
        if change_report_data:
            # Pre-checked by caller -- reconstruct ChangeReport without API call
            report = ChangeReport(
                has_changes=change_report_data["has_changes"],
                reasons=change_report_data.get("reasons", []),
                new_post_urn=change_report_data.get("new_post_urn"),
                new_post_published_at=change_report_data.get("new_post_published_at"),
                new_follower_count=change_report_data.get("new_follower_count"),
                new_profile_hash=change_report_data.get("new_profile_hash"),
            )
            logger.info(
                "[batch_refresh] Utilizando ChangeReport pre-calculado: reasons=%s",
                report.reasons,
            )
        else:
            # Legacy/fallback: ejecuta sondeo + deteccion dentro de la tarea
            logger.info("[batch_refresh] No hay datos pre-check. Ejecutando sondeo para %s", org_urn)
            probe_batch = get_linkedin_company_batch_data(
                access_token=access_token,
                org_urn=org_urn,
                posts_count=5,
            )
            stored_snapshot = get_latest_stored_snapshot(org_urn)
            report = detect_company_changes(stored_snapshot, probe_batch)
            logger.info(
                "[batch_refresh] Fallback probe: has_changes=%s, reasons=%s",
                report.has_changes, report.reasons,
            )
            if not report.has_changes:
                update_change_check_timestamp(org_urn, change_reason=None)
                logger.info(
                    "[batch_refresh][Task %s] No changes detected for '%s'. Skipping.",
                    task_id, org_name,
                )
                return {"status": "NO_CHANGES", "org_urn": org_urn, "org_name": org_name}

        # Extracción profunda en tenant mutado
        logger.info(
            "[batch_refresh] Changes confirmed (%s). Running full batch for %s...",
            report.reason_str(), org_urn,
        )
        MAX_POSTS = 1000
        PAGE_SIZE = 20
        full_batch = get_linkedin_company_batch_data(
            access_token=access_token,
            org_urn=org_urn,
            posts_count=PAGE_SIZE,
        )

        org_details    = full_batch.get("organization") or {}
        follower_count = full_batch.get("follower_count")

        posts = _paginate_org_posts(
            access_token, org_urn,
            first_page=full_batch.get("posts"),
            page_size=PAGE_SIZE,
            max_posts=MAX_POSTS,
            log_tag="batch_refresh",
        )
        full_batch["posts"] = posts

        logger.info(
            "[batch_refresh] Full batch: org=%s, posts=%d, followers=%s",
            "OK" if org_details else "EMPTY", len(posts), follower_count,
        )

        # Restitución de profile cacheado para merges en el pipeline
        existing_profile = get_company_profile(org_urn) or {}

        # URNs of posts already stored — profiler will skip LLM for these
        known_post_urns: set = {
            p.get("id") or p.get("urn") or p.get("$URN", "")
            for p in (existing_profile.get("raw_batch_data") or {}).get("posts") or []
            if p.get("id") or p.get("urn") or p.get("$URN")
        }
        logger.info(
            "[batch_refresh] Known post URNs from stored profile: %d", len(known_post_urns)
        )

        # Inyección del profiler orientado a nuevas mutaciones
        mock_state = {
            "selected_account": {
                "urn": org_urn,
                "name": org_name,
                "vanityName": org_details.get("vanityName") or org_urn.split(":")[-1],
            },
            "linkedin_access_token": access_token,
            "raw_batch_data": full_batch,
            "existing_company_profile": existing_profile,
            "save_profile_fn": None,  # we save manually below with v2 fields
            # TAREA 2: Engagement fields
            "engagement_insights": None,
            "top_performing_posts": None,
            "engagement_analysis": None,
        }

        profiler_result = run_company_profiler_node(
            mock_state,
            new_posts_only=True,
            known_post_urns=known_post_urns,
        )
        company_profile_data = (profiler_result.get("company_profile") or {})
        if hasattr(company_profile_data, "__iter__") and not isinstance(company_profile_data, dict):
            company_profile_data = dict(company_profile_data)

        # Upsert final con tracking de change-detection
        record_id = save_company_profile(
            org_urn=org_urn,
            org_name=org_name,
            raw_batch_data=full_batch,
            company_profile_data=company_profile_data,
            follower_count=follower_count,
            posts_stored_count=len(posts),
            posts_analyzed_count=len(
                (company_profile_data or {}).get("recent_posts_analysis") or []
            ),
            total_posts_available=len(posts),
            last_post_urn=report.new_post_urn,
            last_post_published_at=report.new_post_published_at,
            profile_hash=report.new_profile_hash,
            followers_at_last_check=report.new_follower_count,
            change_reason=report.reason_str(),
        )

        logger.info(
            "[batch_refresh][Task %s] Refresh complete for '%s' | record_id=%s | reasons=%s",
            task_id, org_name, record_id, report.reason_str(),
        )

        # FASE C: Analítica de Engagement Post-Refresh
        engagement_record_id = None
        try:
            if company_profile_data:
                mock_state["company_profile"] = company_profile_data

                # C.1 — Extract raw engagement metrics from LinkedIn API
                extractor_result = run_engagement_extractor_node(mock_state)
                mock_state.update(extractor_result)
                logger.info(
                    "[batch_refresh][Task %s] FASE C extractor done for '%s' — "
                    "%d top posts identified",
                    task_id, org_name,
                    len(extractor_result.get("top_performing_posts") or []),
                )

                # C.2 — LLM analysis of engagement patterns
                analyzer_result = run_engagement_analyzer_node(mock_state)
                mock_state.update(analyzer_result)
                logger.info(
                    "[batch_refresh][Task %s] FASE C analyzer done for '%s'",
                    task_id, org_name,
                )

                # C.3 — Persist to engagement_insights table + denormalize
                engagement_record_id = save_engagement_insights(
                    org_urn=org_urn,
                    engagement_insights=extractor_result.get("engagement_insights", {}),
                    top_performing_posts=extractor_result.get("top_performing_posts", []),
                    engagement_analysis=analyzer_result.get("engagement_analysis"),
                )
                logger.info(
                    "[batch_refresh][Task %s] FASE C persisted (engagement_id=%s) for '%s'",
                    task_id, engagement_record_id, org_name,
                )
            else:
                logger.info(
                    "[batch_refresh][Task %s] Skipping FASE C — no company_profile for '%s'",
                    task_id, org_name,
                )
        except Exception as eng_exc:
            logger.warning(
                "[batch_refresh][Task %s] FASE C engagement failed for %s: %s. "
                "FASE A+B data is safe in Supabase.",
                task_id, org_urn, eng_exc,
            )

        # FASE D: Re-indexación RAG incremental
        try:
            if company_profile_data is not None:
                logger.info(f"[batch_refresh][Task {task_id}] Iniciando re-indexación RAG incremental...")
                from src.agents.multi_agent.nodes.knowledge_ingester import run_knowledge_ingester_node
                mock_state["company_profile"] = company_profile_data
                mock_state["top_performing_posts"] = mock_state.get("top_performing_posts", [])
                run_knowledge_ingester_node(mock_state)
                logger.info(f"[batch_refresh][Task {task_id}] Re-indexación RAG incremental completada.")
        except Exception as rag_exc:
            logger.warning(
                f"[batch_refresh][Task {task_id}] Error durante re-indexación RAG incremental: {rag_exc}"
            )

        return {
            "status": "REFRESHED",
            "org_urn": org_urn,
            "org_name": org_name,
            "record_id": record_id,
            "engagement_record_id": engagement_record_id,
            "reasons": report.reasons,
            "posts_extracted": len(posts),
            "follower_count": follower_count,
        }

    except Exception as exc:
        logger.exception(
            "[batch_refresh][Task %s] Error during refresh for %s: %s",
            task_id, org_urn, exc,
        )
        raise self.retry(exc=exc)


@celery_app.task(bind=True)
def resume_content_generation_task(self, checkpoint, payload):
    """
    Restablece un agente en pausa reactiva dentro del broker LangGraph aplicando mutaciones (feedback).

    Opera mediante re-inserción de state-deltas y ejecución explícita del pipeline desde 
    el nodo de 'human_review'. Si el revisor demanda mayores ajustes, suspende 
    nuevamente la tarea delegando el control a Celery.
    """
    thread_id = checkpoint.get('thread_id')
    feedback = payload.get('feedback', '')
    task_id = self.request.id
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    logger.info(f"Renaudando la tarea {task_id} con feedback: {feedback} | Thread ID: {thread_id}")

    # Emitir broadcast de reanudación
    broadcast_task_status_sync(
        task_id,
        'STARTED',
        {"message": f"Procesando feedback recibido: '{feedback[:60]}...'"}
    )

    try:
        def _update_and_invoke(update_values):
            def _do():
                aipost_graph.update_state(
                    config, update_values, as_node="human_review",
                )
                return aipost_graph.invoke(None, config=config)
            return _invoke_with_retry(_do, logger=logger)

        usage_summary = {}

        def _run_resume():
            if feedback.strip().lower() == 'aprobar':
                return _update_and_invoke({"user_feedback": None})
            return _invoke_with_retry(
                lambda: (
                    aipost_graph.update_state(config, {"user_feedback": feedback}),
                    aipost_graph.invoke(None, config=config)
                )[1],
                logger=logger
            )

        if get_usage_metadata_callback is not None:
            with get_usage_metadata_callback() as usage_cb:
                final_state = _run_resume()
            usage_summary = _summarize_usage(usage_cb.usage_metadata)
        else:
            final_state = _run_resume()

        if final_state is None:
            state_snapshot = aipost_graph.get_state(config)
            final_state = state_snapshot.values if state_snapshot else {}

        state_snapshot = aipost_graph.get_state(config)
        if state_snapshot.next and "human_review" in state_snapshot.next:
            draft_post = final_state.get("draft_post", {})
            draft_content = draft_post.get("content", "Borrador NO disponible.") if draft_post else "Borrador NO disponible."

            if isinstance(draft_content, str):
                draft_content = draft_content.replace("\\n", "\n")

            logger.info(
                "Grafo pausado de nuevo para revision humana (post-feedback) | Thread ID: %s", 
                thread_id,
            )

            # Emitir broadcast de pausa interactiva HITL recurrente
            broadcast_task_status_sync(
                task_id,
                'PENDING_USER_INPUT',
                {
                    'checkpoint': {'thread_id': thread_id},
                    'draft_content': draft_content,
                    'fact_check_report': final_state.get('fact_check_report'),
                    'safety_report': final_state.get('safety_report'),
                    'knowledge_gap': final_state.get('knowledge_gap'),
                }
            )

            self.update_state(
                state='PENDING_USER_INPUT',
                meta={
                    'status': 'PENDING_USER_INPUT',
                    'checkpoint': {'thread_id': thread_id},
                    'draft_content': draft_content,
                }
            )
            raise Ignore()

        draft_post = final_state.get("draft_post") or {}
        final_content = draft_post.get("content", "Error recuperando el contenido final") if isinstance(draft_post, dict) else "Error recuperando el contenido final"

        if isinstance(final_content, str):
            final_content = final_content.replace("\\n", "\n")

        # Emitir broadcast de completado
        broadcast_task_status_sync(
            task_id,
            'COMPLETED',
            {
                'final_post': final_content,
                'fact_check_report': final_state.get('fact_check_report'),
                'safety_report': final_state.get('safety_report'),
                'knowledge_gap': final_state.get('knowledge_gap'),
                'token_usage': usage_summary,
            }
        )

        result = ContentGenerationResult(
            final_post=final_content,
            token_usage_per_node=usage_summary.get("by_model", {}),
            total_tokens_used=usage_summary.get("total_tokens", 0)
        )

        return result.__dict__

    except Ignore:
        raise
    except Exception as e:
        logger.exception(f"Error al reanudar la tarea {task_id}: {e}")
        # Emitir broadcast de fallo
        broadcast_task_status_sync(
            task_id,
            'FAILED',
            {
                'error': str(e)
            }
        )
        raise
