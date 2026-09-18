"""
Nodo Content Writer para PostFast.
Redacta el borrador del post de LinkedIn utilizando herramientas RAG de la
organización (search_company_knowledge) y búsqueda web (web_search) para asegurar
relevancia de marca, actualidad editorial y factualidad impecable.

Implementa bucles de corrección automática para responder ante fallos factuales
(Fact Checker) o de compliance (Safety Guard). Las ediciones dirigidas por
feedback humano viven en el nodo `content_editor`.

La redacción final se genera en TEXTO LIBRE (el structured output JSON degrada
la calidad de la prosa: formato, saltos de línea, hashtags integrados) y se
estructura con un parseo determinista, sin llamadas LLM adicionales.
"""
import json

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from src.agents.multi_agent.state import AgentState, DraftPost
from src.agents.multi_agent.utils import slim_company_profile, parse_post_text
from src.core.constants import SMART_LLM, GENAI_API_KEY
from src.agents.multi_agent.tools.profiler_tools import web_search
from src.agents.multi_agent.tools.rag_tools import search_company_knowledge
from src.core.logger import logger


class AgentDecision(BaseModel):
    decision: str = Field(description="Must be 'SEARCH' if you need to look up information, or 'READY' if you have enough context.")
    tool: str = Field(default="", description="If decision is SEARCH, must be either 'search_company_knowledge' or 'web_search'. Otherwise leave empty.")
    query: str = Field(default="", description="If decision is SEARCH, the query string to search for. Otherwise leave empty.")
    reasoning: str = Field(description="Brief explanation of your current plan or findings.")


AGENT_SYSTEM_PROMPT = """Eres el Agente Autónomo de Redacción e Investigación de PostFast.
Tu objetivo es investigar y redactar un post de LinkedIn excepcional sobre el tema solicitado.
Tienes acceso a las siguientes herramientas de búsqueda para obtener contexto verídico y actualizado:
1. `search_company_knowledge(query)`: Busca en la base de conocimientos vectorial (PDFs, manuales de marca, catálogo de productos, etc.) de la empresa.
2. `web_search(query)`: Busca en internet información de actualidad, tendencias y comparativas del mercado.

Para ser verdaderamente autónomo y marcar la diferencia, no te limites a redactar con lo primero que sabes:
- Diseña una estrategia de búsqueda si el tema requiere detalles técnicos, comparativas de mercado o guías internas.
- Ejecuta búsquedas para contrastar qué soluciones o productos de la empresa encajan con la petición.
- Si los resultados son insuficientes, refina tu búsqueda en la siguiente iteración.

Debes responder en el formato estructurado requerido.
"""


def _broadcast(task_id, message: str):
    if task_id:
        from src.services.realtime_service import broadcast_task_status_sync
        broadcast_task_status_sync(task_id, "RUNNING", {
            "node": "Content Writer",
            "message": message,
        })


def _run_research_loop(idea, org_urn: str, task_id) -> list:
    """
    Bucle de investigación autónoma: el agente decide iterativamente si necesita
    buscar más contexto (RAG corporativo o web) antes de redactar.
    """
    search_history = []
    max_iterations = 3

    for iteration in range(1, max_iterations + 1):
        _broadcast(task_id, f"Agente analizando el contexto y decidiendo si requiere investigar más (Paso {iteration}/{max_iterations})...")

        prompt_messages = [
            ("system", AGENT_SYSTEM_PROMPT),
            ("human", f"""
            **Tema del post solicitado:**
            {json.dumps(idea, ensure_ascii=False)}

            **Historial de búsquedas realizadas hasta ahora en este turno:**
            {json.dumps(search_history, indent=2, ensure_ascii=False) if search_history else "Ninguna."}

            Decide si necesitas buscar más información para enriquecer la publicación (con search_company_knowledge o web_search) o si estás listo para redactar.
            """),
        ]

        try:
            decision_llm = ChatGoogleGenerativeAI(
                model=SMART_LLM,
                google_api_key=GENAI_API_KEY,
                temperature=0.1,
            )
            structured_llm = decision_llm.with_structured_output(AgentDecision)
            decision_result = structured_llm.invoke(prompt_messages)

            if not decision_result or not hasattr(decision_result, "decision"):
                logger.warning("No se pudo obtener una decisión estructurada válida, terminando bucle.")
                break

            decision = decision_result.decision.upper().strip()
            reasoning = decision_result.reasoning
            logger.info(f"Content Writer [Paso {iteration}]: Decisión: {decision} | Razonamiento: {reasoning}")

            if decision == "READY":
                _broadcast(task_id, f"Investigación completada: {reasoning}")
                break

            tool_name = decision_result.tool
            query = decision_result.query
            if not tool_name or not query:
                logger.warning("Decisión SEARCH sin herramienta o consulta especificada, terminando bucle.")
                break

            _broadcast(task_id, f"Agente investigando en {tool_name}: '{query}'...")
            logger.info(f"Ejecutando herramienta {tool_name} con query: '{query}'")

            if tool_name == "search_company_knowledge":
                tool_output = search_company_knowledge.invoke({"query": query, "org_urn": org_urn})
            elif tool_name == "web_search":
                tool_output = web_search.invoke({"query": query})
            else:
                tool_output = f"Error: Herramienta '{tool_name}' desconocida."

            search_history.append({
                "action": tool_name,
                "query": query,
                "reasoning": reasoning,
                "output": tool_output[:2500],  # Limitar tamaño para no desbordar el contexto
            })

        except Exception as e:
            logger.error(f"Error en el bucle de investigación autónoma: {e}", exc_info=True)
            break

    return search_history


def run_content_writer_node(state: AgentState) -> dict:
    logger.info("--- ✍️ EJECUTANDO ESCRITOR DE CONTENIDO ---")

    task_id = state.get("task_id")
    _broadcast(task_id, "Redactando borrador de contenido y ajustando el tono de voz de la marca...")

    persona = state.get("brand_persona_json")
    idea = state.get("fleshed_out_idea")
    company_profile = state.get("company_profile")
    org_urn = company_profile.get("urn", "") if company_profile else ""

    # Inyección de métricas de engagement al contexto
    engagement_analysis = state.get("engagement_analysis")

    # Inyección de contextos del RAG, Tendencias y Coherencia Editorial
    duplicate_context = state.get("duplicate_context")
    industry_trends = state.get("industry_trends")
    fact_report = state.get("fact_check_report")
    safety_report = state.get("safety_report")

    if not all([persona, idea, company_profile]):
        raise ValueError("Faltan datos base para redactar el contenido (persona, idea o perfil de empresa).")

    # Deducción de URLs mediante campos estables
    vanity_name = company_profile.get("vanity_name", "")
    website_url = company_profile.get("website", "")
    linkedin_page_url = f"https://www.linkedin.com/company/{vanity_name}" if vanity_name else ""
    
    # Si hay una URL de referencia provista, tiene prioridad máxima como CTA
    link_url_state = state.get("link_url")
    cta_link = link_url_state if link_url_state else (website_url if website_url else linkedin_page_url)

    # Construcción de sección analítica en el prompt si procede
    engagement_context = ""
    if engagement_analysis:
        top_posts = engagement_analysis.get("top_performing_examples", [])
        optimal_structure = engagement_analysis.get("optimal_post_structure", {})
        winning_patterns = engagement_analysis.get("winning_patterns", [])
        recommended_hashtags = engagement_analysis.get("recommended_hashtags", [])

        engagement_context = f"""
        **Datos de Rendimiento Histórico de LinkedIn (Patrones de Éxito):**
        - **Patrones Ganadores:** {json.dumps(winning_patterns, ensure_ascii=False) if winning_patterns else 'No disponible'}
        - **Estructura Óptima:** {json.dumps(optimal_structure, ensure_ascii=False) if optimal_structure else 'No disponible'}
        - **Hashtags Recomendados:** {', '.join(recommended_hashtags[:10]) if recommended_hashtags else 'No disponible'}
        - **Ejemplos de Éxito para Estilo (NO copiar):**
        {chr(10).join(f'  - Post #{i+1}: {p.get("commentary", "")[:150]}... (engagement rate: {p.get("engagement_rate", "N/A")})' for i, p in enumerate(top_posts[:3])) if top_posts else '  No hay datos históricos.'}
        """

    # Cargar Habilidad Base y Habilidad seleccionada
    from src.services.api_client import get_all_skills
    all_skills = get_all_skills(org_urn)
    base_skill = next((s for s in all_skills if s.get("name") == "Guía de Estilo y Generación (Base)"), None)

    selected_skills = state.get("selected_skills") or []
    selected_skill = state.get("selected_skill")
    if selected_skill and selected_skill not in selected_skills:
        selected_skills = list(selected_skills)
        selected_skills.append(selected_skill)

    skill_context_parts = []

    if base_skill:
        skill_context_parts.append(
            f"**Guía de Estilo Base (Obligatorio - Tono y Voz por Defecto):**\n"
            f"{base_skill.get('markdown_content')}"
        )

    base_id = base_skill.get("id") if base_skill else None
    for skill in selected_skills:
        if skill and skill.get("id") != base_id:
            skill_context_parts.append(
                f"**Habilidad Táctica Adicional Seleccionada (SKILL: {skill.get('name')}):**\n"
                f"{skill.get('markdown_content')}"
            )

    skill_context = ""
    if skill_context_parts:
        joined_skills = "\n\n".join(skill_context_parts)
        skill_context = f"""
        **Directrices y Habilidades de Escritura (Base y Personalizada):**
        {joined_skills}

        Debes seguir estrictamente todas estas directrices y pautas en la redacción de tu borrador.
        """

    # Recuperar Contexto RAG y Memorias semánticamente
    from src.services.rag_service import search_knowledge

    brand_guidelines_context = ""
    rag_docs_context = ""
    rag_posts_context = ""
    short_term_memory_context = ""
    reference_url_content = ""

    link_url = state.get("link_url")
    if org_urn and link_url:
        try:
            from src.services.supabase_client import get_supabase_admin
            sb = get_supabase_admin()
            res = sb.table("company_knowledge").select("content").eq("org_urn", org_urn).eq("source_type", "web_page").like("source_id", f"{link_url}%").execute()
            rows = res.data or []
            if rows:
                reference_url_content = "\n".join(f"- {row.get('content')}" for row in rows)
                logger.info("Content Writer: Encontrados %d chunks para la URL de referencia: %s", len(rows), link_url)
        except Exception as e:
            logger.warning(f"Error fetching reference URL content from DB: {e}")

    if isinstance(idea, dict):
        query_str = idea.get("topic") or str(idea)
    else:
        query_str = str(idea)

    if org_urn:
        # 0. Guías del Brand Book: las MISMAS reglas contra las que auditará el
        # Safety Guard (hashtags/emojis oficiales, do's & don'ts). Si el writer
        # no las ve, es imposible que las cumpla y se generan bucles de
        # corrección inútiles.
        try:
            brand_docs = search_knowledge(
                query="guía de estilo, tono de voz, do's y don'ts, hashtags y emojis oficiales de la marca",
                org_urn=org_urn,
                source_type="brand_book",
                threshold=0.3,
                limit=2,
            )
            if brand_docs:
                brand_guidelines_context = "\n".join(
                    f"- {d.get('content')}" for d in brand_docs
                )
        except Exception as e:
            logger.warning(f"Error fetching brand book guidelines: {e}")

        # 1. RAG Documentos (PDFs) + Enlaces de interés indexados (web_page)
        try:
            rag_docs = search_knowledge(query=query_str, org_urn=org_urn, source_type="pdf_document", threshold=0.4, limit=3)
            try:
                # Enlaces de interés (web_page): el usuario los añade a propósito y a
                # menudo pide hablar de ellos por su nombre. Consultamos con la petición
                # LITERAL del usuario (preserva entidades nombradas: partners, marcas)
                # y recuperamos más fragmentos, descartando los micro-chunks de "título"
                # (puntúan altísimo por coincidencia exacta de keyword pero no aportan
                # contenido) para dejar sitio a los fragmentos con sustancia real.
                web_query = (state.get("user_post_idea") or query_str)
                rag_web = search_knowledge(query=web_query, org_urn=org_urn, source_type="web_page", threshold=0.4, limit=6)
                rag_web = [d for d in rag_web if len((d.get("content") or "").strip()) >= 80][:4]
                rag_docs += rag_web
            except Exception as web_err:
                logger.warning(f"Error fetching RAG web pages: {web_err}")
            if rag_docs:
                rag_docs_context = "\n".join(
                    f"- Fragmento de {'Página Web' if d.get('source_type') == 'web_page' else 'Documento'} [{d.get('source_id', 'desconocido')}]:\n  {d.get('content')}"
                    for d in rag_docs
                )
            else:
                rag_docs_context = "No se encontró contexto documental específico relevante en la base de conocimientos."
        except Exception as e:
            logger.warning(f"Error fetching RAG documents: {e}")
            rag_docs_context = "Error al buscar documentos en la base de conocimientos."

        # 2. RAG Posts / Memoria a largo plazo
        try:
            rag_posts = search_knowledge(query=query_str, org_urn=org_urn, source_type="linkedin_post", threshold=0.4, limit=3)
            if rag_posts:
                rag_posts_context = "\n".join(
                    f"- Post Histórico Exitoso de Referencia:\n  {p.get('content')}"
                    for p in rag_posts
                )
            else:
                rag_posts_context = "No se encontraron posts de referencia históricos específicos relevantes en la base de conocimientos."
        except Exception as e:
            logger.warning(f"Error fetching RAG posts: {e}")
            rag_posts_context = "Error al buscar posts históricos en la base de conocimientos."

        # 3. Memoria a corto plazo (Posts y borradores recientes creados en la plataforma)
        try:
            from src.services.supabase_client import get_supabase_admin
            sb = get_supabase_admin()
            recent_res = (
                sb.table("posts")
                .select("content, created_at, status")
                .eq("account_id", org_urn)
                .order("created_at", desc=True)
                .limit(3)
                .execute()
            )
            recent_items = recent_res.data or []
            if recent_items:
                short_term_memory_context = "\n".join(
                    f"- Post Reciente en la Plataforma ({p.get('status', 'borrador')} | {p.get('created_at', '')[:10]}):\n  {p.get('content')}"
                    for p in recent_items
                )
            else:
                short_term_memory_context = "No hay publicaciones o borradores recientes en el historial de corto plazo."
        except Exception as e:
            logger.warning(f"Error fetching short-term memory: {e}")
            short_term_memory_context = "Error al recuperar el historial reciente de corto plazo."

    url_instruction = ""
    if link_url:
        url_instruction = f"\n    - **URL DE REFERENCIA OBLIGATORIA:** Se ha proporcionado la URL de referencia \"{link_url}\". Es OBLIGATORIO que bases parte del contenido del post en los datos e información extraídos de esta URL (provistos abajo en la sección 9 del contexto) y que la incluyas de forma natural como el enlace de la llamada a la acción (CTA) al final del post."

    # Crear prompt de sistema
    from datetime import date
    system_message = f"""
    Eres un Redactor de Contenidos de LinkedIn estrella para la empresa "{company_profile['name']}".
    Tu objetivo es escribir una publicación pulida, atractiva, completamente real y adaptada a LinkedIn.
    Fecha actual: {date.today().isoformat()} (año {date.today().year}). No menciones años anteriores como si fueran el presente.

    **Reglas de Contenido:**
    - **MISION DE RELEVANCIA DE MARCA:** El post debe sentirse escrito por y para "{company_profile['name']}". Conecta de manera natural el tema con la misión o los productos de la empresa.{url_instruction}
    - **ENTIDADES EXPLÍCITAS DE LA PETICIÓN (obligatorio):** Si la petición del usuario nombra entidades concretas —socios, partners, aliados, marcas, empresas, personas o productos (p. ej. "Hispatec", "Agrotech")— y aparecen en el Contexto RAG de Documentos, en los Enlaces de interés o en el contenido de la URL de referencia (secciones 6 y 9), es OBLIGATORIO mencionarlas por su nombre y desarrollar su relación con la empresa usando ESA información real. Nunca las sustituyas por generalidades ni las omitas.
    - **EVITAR DUPLICADOS:** Usa el contexto editorial para no repetir narrativas anteriores.
    - **USAR TENDENCIAS:** Enriquece el texto con datos reales y tendencias actuales del sector si están provistas.
    - **PRECISIÓN FACTUAL Y CITAS:** No inventes datos, cifras, estadísticas ni URLs. Usa exclusivamente los datos verídicos provistos en el Contexto RAG o en los resultados de investigación. Cuando utilices datos de los documentos, menciónalos de forma natural en el texto (ej. "según nuestro último catálogo", "en nuestro manual destacamos...").
    - **PRECISIÓN DE ATRIBUCIÓN:** atribuye cada capacidad, métrica o función al producto/servicio EXACTO que la posee según la documentación (ej. si un algoritmo calcula y un sensor mide, no digas que el sensor calcula). Las atribuciones cruzadas cuentan como error factual.
    - **APRENDIZAJE FEW-SHOT Y MEMORIA:** Adapta el estilo y la estructura de los posts presentados en la Memoria de Largo Plazo (RAG Posts) y utiliza la información documental provista. Evita repetir temas o ideas que ya se hayan redactado en la Memoria de Corto Plazo.

    **Reglas de Craft de LinkedIn (imprescindibles):**
    - **Hook:** la primera línea debe detener el scroll por sí sola (dato sorprendente, pregunta directa o afirmación contraintuitiva). LinkedIn corta el post tras ~2 líneas: el hook decide si se abre.
    - **Escaneabilidad:** párrafos de 1-2 líneas separados por líneas en blanco. Nada de bloques densos.
    - **Longitud objetivo:** entre 900 y 1600 caracteres.
    - **Emojis:** con moderación (2-5 en todo el post); si el Brand Book define emojis oficiales de marca, usa esos.
    - **CTA:** cierra con una llamada a la acción directa y natural (pregunta a la audiencia o invitación). Si incluyes un enlace web oficial, usa exactamente este: {cta_link} (estrictamente prohibido usar placeholders).
    - **Hashtags:** entre 3 y 5 hashtags EN LA ÚLTIMA LÍNEA del post; si el Brand Book define hashtags oficiales, tienen prioridad.
    - **Cumplimiento del Brand Book:** el post será auditado contra las guías del Brand Book (sección 2b): respeta sus do's & don'ts a rajatabla.

    **FORMATO DE SALIDA (crítico):**
    - Devuelve ÚNICAMENTE el texto final del post, empezando directamente con el hook.
    - PROHIBIDO cualquier preámbulo, saludo, explicación o comentario (nada de "Aquí tienes...", "Borrador:").
    - Sin bloques de código ni markdown estructural: texto plano de LinkedIn.

    {engagement_context}

    {skill_context}
    """

    # Bucle de investigación autónoma (solo para generación nueva, no en correcciones,
    # y desactivable vía configuración de ablación para la evaluación del TFG)
    search_history = []
    is_correction = bool(fact_report or safety_report)
    research_disabled = "research_loop" in (state.get("ablation_disabled") or [])
    if not is_correction and not research_disabled:
        logger.info("Content Writer: Iniciando bucle de investigación autónoma.")
        search_history = _run_research_loop(idea, org_urn, task_id)

    research_context = ""
    if search_history:
        research_context = "\n**Resultados de la Investigación Autónoma del Agente:**\n"
        for idx, h in enumerate(search_history, 1):
            research_context += f"- **Búsqueda {idx} ({h['action']})**: '{h['query']}'\n"
            research_context += f"  *Propósito:* {h['reasoning']}\n"
            research_context += f"  *Resultados:* {h['output']}\n\n"

    writer_temp = 0.15 if is_correction else 0.6

    llm = ChatGoogleGenerativeAI(
        model=SMART_LLM,
        google_api_key=GENAI_API_KEY,
        temperature=writer_temp,
    )

    # Perfil COMPACTO: el perfil completo arrastra recent_posts_analysis
    # (decenas de posts analizados) e infla el prompt en decenas de miles de
    # tokens; ese conocimiento ya llega destilado vía persona y engagement.
    input_context = f"""
    **Instrucciones de Redacción:**

    **0. PETICIÓN ORIGINAL DEL USUARIO (el contrato a cumplir):**
    "{state.get('user_post_idea', '')}"
    El post final debe responder DIRECTAMENTE a esta petición en propósito y formato:
    si pide un anuncio, redacta un anuncio; si pide datos o cifras, inclúyelos (verificables);
    si pide una comparativa, compara; si pide una historia, nárrala. La idea expandida (sección 3)
    es una guía estratégica, pero NUNCA debe desviarte del encargo literal del usuario.
    Si la petición exige un elemento CONCRETO (una mejora, un lanzamiento, un servicio, un caso),
    NO respondas en abstracto: selecciona el elemento REAL más relevante de la base de conocimientos
    (producto, servicio o caso con nombre propio) y construye el post alrededor de él. Jamás inventes
    el elemento ni lo dejes sin nombrar.

    **1. Perfil de la Organización:**
    {json.dumps(slim_company_profile(company_profile), indent=2, ensure_ascii=False)}

    **2. Guía de Tono de Marca:**
    {json.dumps(persona, indent=2, ensure_ascii=False)}

    **2b. Guías del Brand Book (OBLIGATORIAS — el post será auditado contra estas reglas):**
    {brand_guidelines_context or "Sin guías de brand book registradas."}

    **3. Concepto/Idea Aprobada:**
    {json.dumps(idea, indent=2, ensure_ascii=False)}

    **4. Historial Editorial de LinkedIn (Coherencia):**
    {duplicate_context or "Tema nuevo. Sin conflictos."}

    **5. Tendencias de la Industria Recientes:**
    {industry_trends or "Ninguna tendencia detectada. Redacta libre de contexto."}

    **6. Contexto Enriquecido de Documentos RAG (Base de Conocimientos):**
    {rag_docs_context or "Sin contexto adicional de documentos corporativos."}

    **7. Memoria de Largo Plazo (RAG Posts de Éxito / Few-Shot):**
    {rag_posts_context or "Sin posts históricos similares de referencia."}

    **8. Memoria de Corto Plazo (Historial Reciente en la Plataforma):**
    {short_term_memory_context or "Sin historial reciente en la plataforma."}

    **9. Contenido de la URL de Referencia ({link_url_state or "Ninguna"}):**
    {reference_url_content or "No se proporcionó URL de referencia o no tiene contenido."}

    {research_context}

    Por favor, redacta el borrador del post.
    """

    # Texto del borrador anterior para los bucles de corrección
    last_draft = state.get("last_draft_content") or (
        state.get("draft_post", {}).get("content", "") if state.get("draft_post") else ""
    )

    # Si hay feedback de fact-check (bucle de corrección automática)
    if fact_report and not fact_report.get("overall_pass"):
        logger.info("Content Writer: Iniciando bucle de corrección por fallos factuales (CRAG).")
        claims_to_fix = "\n".join(
            f"- Claim incorrecto: \"{c.get('claim')}\". Corrección verídica: \"{c.get('correction')}\" (Fuente: {c.get('source')})"
            for c in fact_report.get("claims", []) if not c.get("verified")
        )

        input_context += f"""

        **⚠️ INSTRUCCIÓN DE CORRECCIÓN FACTUAL URGENTE:**
        El verificador de hechos (Fact Checker) ha rechazado tu borrador anterior porque contenía datos inventados, imprecisos o alucinados.

        **BORRADOR ANTERIOR RECHAZADO:**
        ---
        {last_draft}
        ---

        **ERRORES FACTUALES DETECTADOS QUE DEBES CORREGIR:**
        {claims_to_fix}

        **INSTRUCCIONES DE CORRECCIÓN (estrictas):**
        1. Corrige o ELIMINA cada dato rechazado. Si no existe un sustituto respaldado por el Contexto RAG, elimina el dato en lugar de reemplazarlo.
        2. ABSOLUTAMENTE PROHIBIDO introducir datos, cifras, nombres, casos de estudio o ejemplos NUEVOS que no estén ya en el Contexto RAG o en la investigación provista: cada dato nuevo volverá a ser verificado y reiniciará el ciclo.
        3. Mantén intactos el resto del texto, su estructura y formato.
        """

    # Si hay feedback de safety-guard (bucle de corrección automática)
    elif safety_report and not safety_report.get("approved") and safety_report.get("severity") in ("medium", "high", "critical"):
        logger.info("Content Writer: Iniciando bucle de corrección por políticas de marca y compliance.")
        issues = "\n".join(f"- {issue}" for issue in safety_report.get("issues", []))
        suggestions = "\n".join(f"- {sug}" for sug in safety_report.get("suggestions", []))

        input_context += f"""

        **⚠️ INSTRUCCIÓN DE COMPLIANCE DE MARCA URGENTE:**
        El auditor de seguridad (Safety Guard) ha rechazado tu borrador por infringir políticas de marca, uso de lenguaje inadecuado, superlativos imprecisos, GDPR o competidores.

        **BORRADOR ANTERIOR RECHAZADO:**
        ---
        {last_draft}
        ---

        **INFRACCIONES DETECTADAS:**
        {issues}

        **SUGERENCIAS DE CORRECCIÓN:**
        {suggestions}

        **INSTRUCCIÓN:** Reescribe el post resolviendo todas las infracciones mencionadas. Modifica el tono o el vocabulario según las sugerencias de compliance.
        """

    # Generación en TEXTO LIBRE (máxima calidad de prosa) + parseo determinista.
    logger.info("Content Writer: Invocando al modelo de generación en texto libre.")
    raw = llm.invoke([("system", system_message), ("human", input_context)]).content
    if isinstance(raw, list):
        raw = "\n".join(p if isinstance(p, str) else p.get("text", str(p)) for p in raw)

    draft: DraftPost = parse_post_text(raw)
    logger.info(
        "✅ Borrador generado (%d caracteres, %d hashtags).",
        len(draft["content"]), len(draft["hashtags"]),
    )

    # IMPORTANTE: Al generar un NUEVO borrador (o corregido), LIMPIAMOS
    # los reportes anteriores para que el supervisor los envíe a validar de nuevo.
    return {
        "draft_post": draft,
        "user_feedback": None,
        "fact_check_report": None,
        "safety_report": None,
    }
