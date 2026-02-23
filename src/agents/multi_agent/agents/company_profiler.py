from typing import Dict, Any, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from state import AgentState, CompanyProfile
from tools.profiler_tools import scrape_website
from src.core.constants import SMART_LLM, GENAI_API_KEY

# Pydantic model para la extracción de datos estructurados
class ExtractedLinkedInData(BaseModel):
    followers: Optional[str] = Field(description="El número de seguidores de la empresa.")
    about_us: Optional[str] = Field(description="El texto completo de la sección 'About us'.")
    industry: Optional[str] = Field(description="El sector o industria de la empresa.")
    company_size: Optional[str] = Field(description="El tamaño de la empresa (ej. '1 employee', '11-50 employees').")
    headquarters: Optional[str] = Field(description="La ciudad y región de la sede principal.")
    company_type: Optional[str] = Field(description="El tipo de empresa (ej. 'Self-Employed', 'Privately Held').")
    founded: Optional[str] = Field(description="El año de fundación de la empresa.")
    specialties: Optional[List[str]] = Field(description="Una lista de las especialidades de la empresa.")

EXTRACTION_PROMPT = """
Eres un sistema de extracción de datos de alta precisión. Tu tarea es analizar el siguiente texto desordenado, que ha sido extraído de una página de empresa de LinkedIn, y extraer la información clave en un formato JSON estructurado.

**Instrucciones:**
1.  Lee todo el texto para identificar las secciones relevantes.
2.  Extrae los valores para los campos solicitados: followers, about_us, industry, company_size, headquarters, company_type, founded, specialties.
3.  Ignora completamente el texto irrelevante como banners de cookies, políticas de privacidad, menús de navegación, pies de página y anuncios.
4.  Si un campo no se encuentra en el texto, déjalo como nulo.

**Texto Desordenado para Analizar:**
---
{scraped_content}
---
"""

def run_company_profiler_node(state: AgentState) -> Dict[str, Any]:
    print("--- 🕵️ EJECUTANDO EXTRACTOR Y SINTETIZADOR DE CONTEXTO ---")
    
    selected_account = state.get("selected_account")
    if not selected_account:
        raise ValueError("El objeto `selected_account` es necesario.")

    vanity_name = selected_account.get("vanityName")
    if not vanity_name:
        raise ValueError("El 'vanityName' es necesario para construir la URL de LinkedIn.")
    
    linkedin_url = f"https://www.linkedin.com/company/{vanity_name}"
    
    # 1. Scrapear el contenido
    print(f"Extrayendo contenido de la fuente de verdad: {linkedin_url}")
    scraped_content = scrape_website.invoke({"url": linkedin_url})
    if "Error" in scraped_content or not scraped_content.strip():
        raise ConnectionError(f"No se pudo obtener contenido de {linkedin_url} para el análisis.")
    
    print(f"SCRAPING: {scraped_content}")

    # 2. Usar un LLM para extraer la información estructurada
    llm = ChatGoogleGenerativeAI(model=SMART_LLM, google_api_key=GENAI_API_KEY, temperature=0.0)
    structured_llm = llm.with_structured_output(ExtractedLinkedInData)
    chain = ChatPromptTemplate.from_template(EXTRACTION_PROMPT) | structured_llm
    
    print("Interpretando el contenido extraído para extraer datos clave...")
    extracted_data = chain.invoke({"scraped_content": scraped_content})

    # 3. Consolidar y enriquecer el perfil final
    # Los datos extraídos de la página pública tienen prioridad sobre los datos de la sesión.
    profile = CompanyProfile(
        name=selected_account.get("name", "Nombre Desconocido"),
        urn=selected_account.get("urn"),
        vanity_name=vanity_name,
        followers=extracted_data.followers,
        industry=extracted_data.industry,
        company_size=extracted_data.company_size,
        headquarters=extracted_data.headquarters,
        company_type=extracted_data.company_type,
        founded=extracted_data.founded,
        specialties=extracted_data.specialties,
        about_us_content=extracted_data.about_us
    )
    
    print(f"✅ Contexto de empresa enriquecido y finalizado para '{profile['name']}'.")
    return {"company_profile": profile}