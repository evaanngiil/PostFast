import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import create_react_agent

from src.agents.multi_agent.state import AgentState, DraftPost
from src.core.constants import SMART_LLM, FAST_LLM, GENAI_API_KEY
from src.agents.multi_agent.tools.profiler_tools import web_search
from src.core.logger import logger

def run_content_writer_node(state: AgentState) -> dict:
    """
    Nodo de agente autonomo que redacta el contenido, usando herramientas de busqueda
    para asegurar que la informacion sea factual y completa.
    """
    logger.info("Ejecutando agente Content Writer (Drafting final).")

    persona = state.get("brand_persona_json")
    idea = state.get("fleshed_out_idea")
    company_profile = state.get("company_profile")
    # Inyección de métricas de engagement al contexto
    engagement_analysis = state.get("engagement_analysis")

    if not all([persona, idea, company_profile]):
        raise ValueError("Faltan datos para redactar el contenido (persona, idea o perfil de empresa).")

    # Deducción de URLs mediante campos estables (vanity_name y website)
    vanity_name = company_profile.get("vanity_name", "")
    website_url = company_profile.get("website", "")
    linkedin_page_url = f"https://www.linkedin.com/company/{vanity_name}" if vanity_name else ""
    cta_link = website_url if website_url else linkedin_page_url

    # Construcción de sección analítica en el prompt si procede
    engagement_context = ""
    if engagement_analysis:
        top_posts = engagement_analysis.get("top_performing_examples", [])
        optimal_structure = engagement_analysis.get("optimal_post_structure", {})
        winning_patterns = engagement_analysis.get("winning_patterns", [])
        recommended_hashtags = engagement_analysis.get("recommended_hashtags", [])

        engagement_context = f"""
            **Datos de Rendimiento Real (usa esto como referencia):**
            - **Patrones Ganadores:** {json.dumps(winning_patterns, ensure_ascii=False) if winning_patterns else 'No disponible'}
            - **Estructura Optima:** {json.dumps(optimal_structure, ensure_ascii=False) if optimal_structure else 'No disponible'}
            - **Hashtags con Mejor Rendimiento:** {', '.join(recommended_hashtags[:10]) if recommended_hashtags else 'No disponible'}
            - **Ejemplos de Posts Exitosos (para referencia de estilo, NO copiar):**
            {chr(10).join(f'  - Post #{i+1}: {p.get("commentary", "")[:150]}... (engagement rate: {p.get("engagement_rate", "N/A")})' for i, p in enumerate(top_posts[:3])) if top_posts else '  No hay datos historicos disponibles.'}

            IMPORTANTE: Usa estos datos como inspiracion para el estilo, tono y estructura. NO copies los posts de ejemplo.
        """

    system_message = f"""Eres un Redactor de Contenido de LinkedIn de clase mundial para la empresa "{company_profile['name']}". Eres un experto en crear posts atractivos, factuales y, sobre todo, relevantes para la marca. Tu mision es tomar el contexto proporcionado y redactar una publicacion final y pulida.

**Reglas de Comportamiento Estrictas:**
- **REGLA DE ORO DE RELEVANCIA:** Siempre debes conectar el tema de la publicacion con el rol, la mision o los servicios de la empresa. El post debe sentirse como si viniera directamente de "{company_profile['name']}", no de un generador de contenido generico. Usa frases como "En {company_profile['name']}, creemos que...", "Nuestra plataforma te ayuda a...", etc.
- **REGLA DE FACTUALIDAD:** Si mencionas cualquier dato o estadistica, DEBES usar la herramienta `web_search` para encontrar informacion real y verificable.
- **PROHIBIDO:** No inventes estadisticas ni uses placeholders como "[Fuente de datos]" o "[X]%" o "[enlace ]". Debes generar un post final y completo.
- Adherete estrictamente al Perfil de Marca proporcionado en el contexto.
- Incluye 3-5 hashtags relevantes.
- Termina con una llamada a la accion (CTA) clara. Usa un formato de post de LinkedIn. Si vas a incluir un enlace en el CTA no uses placeholders, usa este: {cta_link}
{engagement_context}"""

    llm = ChatGoogleGenerativeAI(model=SMART_LLM, google_api_key=GENAI_API_KEY, temperature=0.5)

    agent = create_react_agent(
        model=llm,
        tools=[web_search],
        prompt=system_message,
    )

    # Construir el mensaje humano con todo el contexto
    # Si user_feedback esta presente, esto es un pase de revision — incluirlo.
    user_feedback = state.get("user_feedback")

    input_context = f"""**Contexto para la Redaccion:**

**1. Perfil de la Empresa (Para Relevancia):**
{json.dumps(company_profile, indent=2, ensure_ascii=False)}

**2. Perfil de Marca (Para Tono y Estilo):**
{json.dumps(persona, indent=2, ensure_ascii=False)}

**3. Idea de Contenido Aprobada:**
{json.dumps(idea, indent=2, ensure_ascii=False)}

Ahora, por favor, redacta la publicacion final de LinkedIn. Recuerda la REGLA DE ORO DE RELEVANCIA."""

    if user_feedback:
        logger.info(f"Revisión iterativa generada (HITL). Feedback: {user_feedback[:80]}...")
        input_context += f"""

**⚠️ REVISION REQUERIDA POR EL USUARIO:**
El usuario ha revisado un borrador anterior y ha solicitado los siguientes cambios:
---
{user_feedback}
---
Aplica EXACTAMENTE los cambios solicitados al contenido. Mantén el resto del post sin cambios a menos que el feedback indique lo contrario."""

    result = agent.invoke(
        {"messages": [("human", input_context)]},
        config={"recursion_limit": 10},
    )

    raw_post_text = result["messages"][-1].content
    if isinstance(raw_post_text, list):
        raw_post_text = "\n".join(
            part if isinstance(part, str) else part.get("text", str(part))
            for part in raw_post_text
        )

    final_llm = ChatGoogleGenerativeAI(model=FAST_LLM, google_api_key=GENAI_API_KEY, temperature=0.1)

    structuring_prompt = ChatPromptTemplate.from_template(
        "Toma el siguiente texto de una publicacion de LinkedIn y devuelvelo "
        "EXCLUSIVAMENTE como un objeto JSON (sin bloques de codigo, sin ```json, "
        "solo el JSON puro) con estas tres claves:\n"
        '  "content": (string) el texto completo del post tal cual,\n'
        '  "hashtags": (array de strings) los hashtags usados,\n'
        '  "call_to_action": (string) la llamada a la accion.\n\n'
        "Debes copiar el contenido completo. NO elimines los hashtags ni "
        "el CTA del campo content.\n\n"
        "Texto:\n---\n{post_text}\n---"
    )

    final_chain = structuring_prompt | final_llm
    structuring_result = final_chain.invoke({"post_text": raw_post_text})

    # Parsear el JSON de la respuesta del LLM.
    # .content puede ser un str o una lista de partes de contenido (respuestas multi-parte de Gemini).
    raw_json = structuring_result.content if hasattr(structuring_result, "content") else str(structuring_result)
    if isinstance(raw_json, list):
        # Unir partes de texto; ignorar entradas que no sean texto (ej. partes de function_call)
        raw_json = "\n".join(
            part if isinstance(part, str) else part.get("text", str(part))
            for part in raw_json
        )

    # Eliminar bloques de codigo markdown si el modelo envuelve el JSON en ```json...```
    raw_json = raw_json.strip()
    json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_json, re.DOTALL)
    if json_match:
        raw_json = json_match.group(1)

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        # Fallback: usar el texto crudo del post tal cual
        print("⚠️ No se pudo parsear el JSON estructurado, usando texto raw.")
        parsed = {
            "content": raw_post_text,
            "hashtags": [],
            "call_to_action": "",
        }

    draft: DraftPost = {
        "content": parsed.get("content", raw_post_text),
        "hashtags": parsed.get("hashtags", []),
        "call_to_action": parsed.get("call_to_action", ""),
    }

    # Normalizar saltos de linea escapados de la salida del LLM
    draft["content"] = draft["content"].replace("\\n", "\n")

    print("\u2705 Borrador de publicacion factual generado.")

    # Limpiar user_feedback despues de incorporarlo, para que el proximo
    # ciclo human_review no vuelva a disparar un bucle de regeneracion.
    return {"draft_post": draft, "user_feedback": None}
