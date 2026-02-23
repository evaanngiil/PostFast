import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_tool_calling_agent, AgentExecutor

from typing import Dict, Any

from state import AgentState, DraftPost
from src.core.constants import SMART_LLM, GENAI_API_KEY
from tools.profiler_tools import web_search


def run_content_writer_node(state: AgentState) -> dict:
    """
    Nodo de agente autónomo que redacta el contenido, usando herramientas de búsqueda
    para asegurar que la información sea factual y completa.
    """
    print("--- ✍️ EJECUTANDO REDACTOR DE CONTENIDO (AUTÓNOMO) ---")
    
    persona = state.get("brand_persona_json")
    idea = state.get("fleshed_out_idea")
    company_profile = state.get("company_profile")
    
    if not all([persona, idea, company_profile]):
        raise ValueError("Faltan datos para redactar el contenido (persona, idea o perfil de empresa).")
    
    website_url = company_profile.get("website_url")
    linkedin_page_url = company_profile.get("linkedin_page_url")
    cta_link = website_url if website_url else linkedin_page_url

    tools = [web_search]
    
    # Este prompt define la "personalidad" y las reglas del agente.
    # Incluye placeholders para 'input' y 'agent_scratchpad' que el agente usará internamente.
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""
            Eres un Redactor de Contenido de LinkedIn de clase mundial para la empresa "{company_profile['name']}". Eres un experto en crear posts atractivos, factuales y, sobre todo, relevantes para la marca. Tu misión es tomar el contexto proporcionado y redactar una publicación final y pulida.

            **Reglas de Comportamiento Estrictas:**
            - **REGLA DE ORO DE RELEVANCIA:** Siempre debes conectar el tema de la publicación con el rol, la misión o los servicios de la empresa. El post debe sentirse como si viniera directamente de "{company_profile['name']}", no de un generador de contenido genérico. Usa frases como "En {company_profile['name']}, creemos que...", "Nuestra plataforma te ayuda a...", etc.
            - **REGLA DE FACTUALIDAD:** Si mencionas cualquier dato o estadística, DEBES usar la herramienta `web_search` para encontrar información real y verificable.
            - **PROHIBIDO:** No inventes estadísticas ni uses placeholders como "[Fuente de datos]" o "[X]%" o "[enlace ]". Debes generar un post final y completo.
            - Adhiérete estrictamente al Perfil de Marca proporcionado en el contexto.
            - Incluye 3-5 hashtags relevantes.
            - Termina con una llamada a la acción (CTA) clara. Usa un formato de post de LinkedIn. Si vas a incluir un enlace en el CTA no uses placeholders, usa este: {cta_link}"""
        ),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    llm = ChatGoogleGenerativeAI(model=SMART_LLM, google_api_key=GENAI_API_KEY, temperature=0.5)
    
    # 3. USAR LA FUNCIÓN CORRECTA PARA CREAR EL AGENTE
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    # Esto alinea cómo pasamos la información con lo que el agente espera.
    input_context = f"""
    **Contexto para la Redacción:**

    **1. Perfil de la Empresa (Para Relevancia):**
    {json.dumps(company_profile, indent=2, ensure_ascii=False)}

    **2. Perfil de Marca (Para Tono y Estilo):**
    {json.dumps(persona, indent=2, ensure_ascii=False)}

    **3. Idea de Contenido Aprobada:**
    {json.dumps(idea, indent=2, ensure_ascii=False)}

    Ahora, por favor, redacta la publicación final de LinkedIn. Recuerda la REGLA DE ORO DE RELEVANCIA.
    """
    
    # Invocamos al agente con el contexto combinado
    result = agent_executor.invoke({"input": input_context})
    
    # El resultado final del agente es texto. Usamos un LLM para garantizar una salida JSON limpia.
    final_llm = ChatGoogleGenerativeAI(model=SMART_LLM, google_api_key=GENAI_API_KEY, temperature=0.1)
    structured_llm = final_llm.with_structured_output(DraftPost)
    
    structuring_prompt = ChatPromptTemplate.from_template(
        "Toma el siguiente texto de una publicación de LinkedIn y formatéalo en un objeto JSON `DraftPost` con `content`, `hashtags` y `call_to_action`. Debes copiar el contenido de hashtags y call_to_action para formaterlos. NO los elimines del texto original.\n\nTexto:\n---\n{post_text}\n---"
    )
    
    final_chain = structuring_prompt | structured_llm
    draft = final_chain.invoke({"post_text": result['output']})

    print("✅ Borrador de publicación factual generado.")

    return {"draft_post": draft}
