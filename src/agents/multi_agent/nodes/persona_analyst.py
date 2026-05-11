from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from src.agents.multi_agent.state import AgentState
from src.core.constants import MEDIUM_LLM, GENAI_API_KEY
from src.agents.multi_agent.tools.profiler_tools import scrape_website

class BrandPersona(BaseModel):
    core_topics: List[str] = Field(description="Lista de 3-5 temas o conceptos centrales que la marca discute con frecuencia.")
    emotional_tone: List[str] = Field(description="Lista de 3-5 adjetivos que describen el tono emocional principal (ej. 'inspirador', 'técnico', 'formal', 'cercano').")
    style_rules: List[str] = Field(description="Lista de 2-3 reglas de estilo concretas y accionables observadas en el texto (ej. 'Usa datos para respaldar afirmaciones', 'Hace preguntas directas a la audiencia', 'Estructura el contenido en listas cortas').")

PROMPT_TEMPLATE = """
Tu rol es Analista de Persona, un experto en destilar la esencia de una marca a partir de su contenido web.
Tu tarea es analizar el siguiente **Dossier de Empresa** y sintetizar su voz, tono y estilo en un Perfil de Marca JSON estructurado (`BrandPersona`).

Analiza el siguiente dossier de empresa, extraído de la página de LinkedIn de una marca:
---
{scraped_content}
---

Basándote estrictamente en el JSON anterior, genera un Perfil de Marca que capture la voz, el tono y el estilo de la marca.
"""

def run_persona_analyst_node(state: AgentState) -> Dict[str, Any]:
    """
    Nodo que analiza el contenido de la página de LinkedIn (pre-extraído) para definir la voz de la marca.
    """
    print("--- 🧠 EJECUTANDO ANALISTA DE PERSONA ---")
    
    company_profile = state.get("company_profile")
    if not company_profile:
        raise ValueError("El perfil de la empresa no está disponible.")
        
    dossier_entries = []
    
    if name := company_profile.get("name"):
        dossier_entries.append(f"Nombre de la Empresa: {name}")
        
    if industry := company_profile.get("industry"):
        dossier_entries.append(f"Industria: {industry}")

    if company_size := company_profile.get("company_size"):
        dossier_entries.append(f"Tamaño de la Empresa: {company_size}")
        
    if company_type := company_profile.get("company_type"):
        dossier_entries.append(f"Tipo de Empresa: {company_type}")

    if specialties := company_profile.get("specialties"):
        if isinstance(specialties, list) and specialties:
            dossier_entries.append(f"Especialidades Clave: {', '.join(specialties)}")

    # El 'About Us' es la fuente principal de tono.
    if about_us := company_profile.get("about_us_content"):
        dossier_entries.append(f"\nDescripcion Principal ('About Us'):\n{about_us.strip()}")

    # Inyección prioritaria de análisis de publicaciones recientes para contexto del LLM
    if recent_posts := company_profile.get("recent_posts_analysis"):
        if isinstance(recent_posts, list) and recent_posts:
            dossier_entries.append("\n--- Analisis de Posts Recientes ---")
            for i, post in enumerate(recent_posts[:10], 1):
                post_entry = f"\nPost {i}:"
                if isinstance(post, dict):
                    if summary := post.get("summary"):
                        post_entry += f"\n  Resumen: {summary}"
                    if tone := post.get("tone"):
                        post_entry += f"\n  Tono: {tone}"
                    if topics := post.get("topics"):
                        if isinstance(topics, list):
                            post_entry += f"\n  Temas: {', '.join(str(t) for t in topics)}"
                        else:
                            post_entry += f"\n  Temas: {topics}"
                    if engagement := post.get("engagement"):
                        post_entry += f"\n  Engagement: {engagement}"
                else:
                    post_entry += f"\n  {post}"
                dossier_entries.append(post_entry)

    # Inclusión de métricas de engagement si están expuestas en el state
    engagement_analysis = state.get("engagement_analysis")
    if engagement_analysis and isinstance(engagement_analysis, dict):
        dossier_entries.append("\n--- Analisis de Engagement ---")
        if patterns := engagement_analysis.get("content_patterns"):
            dossier_entries.append(f"Patrones de contenido exitoso: {patterns}")
        if best_times := engagement_analysis.get("best_posting_times"):
            dossier_entries.append(f"Mejores horarios de publicacion: {best_times}")
        if top_formats := engagement_analysis.get("top_formats"):
            dossier_entries.append(f"Formatos con mas engagement: {top_formats}")
        if top_topics := engagement_analysis.get("top_topics"):
            dossier_entries.append(f"Temas con mas engagement: {top_topics}")

    has_about = bool(company_profile.get("about_us_content"))
    has_specialties = bool(company_profile.get("specialties"))
    has_posts = bool(company_profile.get("recent_posts_analysis"))
    has_engagement = bool(engagement_analysis)

    if not has_about and not has_specialties and not has_posts and not has_engagement:
        raise ValueError(
            "No hay contenido de perfil (ni 'about_us', ni 'specialties', "
            "ni 'recent_posts_analysis', ni engagement_analysis) disponible "
            "para analizar la persona."
        )

    company_dossier = "\n".join(dossier_entries)

    llm = ChatGoogleGenerativeAI(model=MEDIUM_LLM, google_api_key=GENAI_API_KEY, temperature=0.2)
    structured_llm = llm.with_structured_output(BrandPersona)
    
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    chain = prompt | structured_llm
    
    print("Sintetizando el Perfil de Marca con Gemini...")
    persona_profile = chain.invoke({"scraped_content": company_dossier})
    
    print("✅ Perfil de Marca generado.")
    print(persona_profile)

    return {"brand_persona_json": persona_profile.dict()}
