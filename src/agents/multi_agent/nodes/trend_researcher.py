"""
Nodo Trend Researcher para PostFast.
Busca tendencias actuales de la industria, noticias recientes y estadísticas
del sector para enriquecer el post con actualidad y relevancia.
"""
from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agents.multi_agent.state import AgentState
from src.agents.multi_agent.tools.profiler_tools import web_search
from src.core.constants import MEDIUM_LLM, GENAI_API_KEY
from src.core.logger import logger

class IndustryTrends(BaseModel):
    current_trends: List[str] = Field(
        description="3-5 tendencias actuales del sector relevantes para el post."
    )
    trending_topics: List[str] = Field(
        description="3-5 temas trending en LinkedIn/redes para esta industria."
    )
    data_points: List[str] = Field(
        description="2-3 datos o estadísticas recientes verificables del sector."
    )
    content_angles: List[str] = Field(
        description="2-3 ángulos de contenido sugeridos basados en las tendencias."
    )

PROMPT_TEMPLATE = """
Eres un Investigador de Tendencias de LinkedIn experto. Tu misión es analizar la información recopilada de la web y destilar tendencias actuales y datos relevantes de la industria para enriquecer el post de LinkedIn del usuario.

**Perfil de la Empresa:**
Nombre: {company_name}
Industria: {industry}
Especialidades: {specialties}

**Idea Propuesta por el Usuario:**
"{user_idea}"

**Resultados de Búsqueda de Internet (Tendencias del Sector):**
{search_results}

Analiza e identifica tendencias relevantes, temas de conversación clave y estadísticas fiables en el formato JSON estructurado solicitado.
"""

def run_trend_researcher_node(state: AgentState) -> Dict[str, Any]:
    print("--- 📈 EJECUTANDO INVESTIGADOR DE TENDENCIAS ---")
    logger.info("=== TREND RESEARCHER: start ===")
    
    company_profile = state.get("company_profile", {})
    user_idea = state.get("user_post_idea", "")
    industry = company_profile.get("industry", "Tecnología")
    specialties = company_profile.get("specialties", [])
    company_name = company_profile.get("name", "Empresa")
    
    specs_str = ", ".join(specialties) if specialties else "No especificadas"
    
    # Realizar búsquedas sobre el sector y la temática (año dinámico)
    from datetime import date
    search_query = f"trends {date.today().year} {industry} {user_idea}"
    logger.info(f"Buscando tendencias en internet con la consulta: '{search_query}'")
    
    try:
        search_results = web_search.invoke(search_query)
    except Exception as e:
        logger.warning(f"Error al ejecutar web_search: {e}. Se procederá usando conocimiento interno del LLM.")
        search_results = "No se pudieron obtener resultados en tiempo real por fallo de red o API."
        
    llm = ChatGoogleGenerativeAI(
        model=MEDIUM_LLM,
        google_api_key=GENAI_API_KEY,
        temperature=0.4,
    )
    structured_llm = llm.with_structured_output(IndustryTrends)
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    chain = prompt | structured_llm
    
    try:
        trends_output = chain.invoke({
            "company_name": company_name,
            "industry": industry,
            "specialties": specs_str,
            "user_idea": user_idea,
            "search_results": search_results
        })
        
        # Pydantic to dict conversion
        if hasattr(trends_output, "model_dump"):
            trends_dict = trends_output.model_dump()
        elif hasattr(trends_output, "dict"):
            trends_dict = trends_output.dict()
        else:
            trends_dict = dict(trends_output)
            
        # Formatear a texto legible para el writer
        formatted_trends = []
        formatted_trends.append("### 📈 TENDENCIAS Y CONTEXTO DEL SECTOR:")
        formatted_trends.append("**Tendencias Actuales:**")
        for t in trends_dict.get("current_trends", []):
            formatted_trends.append(f"- {t}")
            
        formatted_trends.append("\n**Temas de Conversación en LinkedIn:**")
        for topic in trends_dict.get("trending_topics", []):
            formatted_trends.append(f"- {topic}")
            
        formatted_trends.append("\n**Datos y Estadísticas Recientes:**")
        for dp in trends_dict.get("data_points", []):
            formatted_trends.append(f"- {dp}")
            
        formatted_trends.append("\n**Ángulos Recomendados:**")
        for angle in trends_dict.get("content_angles", []):
            formatted_trends.append(f"- {angle}")
            
        trends_text = "\n".join(formatted_trends)
        
        print("✅ Tendencias de la industria obtenidas y estructuradas.")
        logger.info("=== TREND RESEARCHER: completed ===")
        return {"industry_trends": trends_text}
        
    except Exception as e:
        logger.error(f"Fallo en el formateo de tendencias: {e}")
        fallback_text = f"### 📈 TENDENCIAS DEL SECTOR:\n- Tendencia emergente en {industry} relacionada con {user_idea}.\n- Mayor relevancia de automatización y optimización en {specs_str}."
        return {"industry_trends": fallback_text}
