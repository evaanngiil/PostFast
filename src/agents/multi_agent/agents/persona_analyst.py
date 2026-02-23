from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from state import AgentState
from src.core.constants import SMART_LLM, GENAI_API_KEY
from tools.profiler_tools import scrape_website

class BrandPersona(BaseModel):
    core_topics: List[str] = Field(description="Lista de 3-5 temas o conceptos centrales que la marca discute con frecuencia.")
    emotional_tone: List[str] = Field(description="Lista de 3-5 adjetivos que describen el tono emocional principal (ej. 'inspirador', 'técnico', 'formal', 'cercano').")
    style_rules: List[str] = Field(description="Lista de 2-3 reglas de estilo concretas y accionables observadas en el texto (ej. 'Usa datos para respaldar afirmaciones', 'Hace preguntas directas a la audiencia', 'Estructura el contenido en listas cortas').")
    # vocabulary_tier: str = Field(description="Nivel de vocabulario (ej. 'Común', 'De Negocios', 'Técnico').")

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
        dossier_entries.append(f"\nDescripción Principal ('About Us'):\n{about_us.strip()}")
    
    if not company_profile.get("about_us_content") and not company_profile.get("specialties"):
        raise ValueError("No hay contenido de perfil (ni 'about_us' ni 'specialties') disponible para analizar la persona.")

    company_dossier = "\n".join(dossier_entries)

    llm = ChatGoogleGenerativeAI(model=SMART_LLM, google_api_key=GENAI_API_KEY, temperature=0.2)
    structured_llm = llm.with_structured_output(BrandPersona)
    
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    chain = prompt | structured_llm
    
    print("Sintetizando el Perfil de Marca con Gemini...")
    persona_profile = chain.invoke({"scraped_content": company_dossier})
    
    print("✅ Perfil de Marca generado.")
    print(persona_profile)

    return {"brand_persona_json": persona_profile.dict()}
