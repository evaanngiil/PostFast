"""Nodo de analisis predictivo sobre los datos de engagement estructurados.

Nodo de LangGraph que usa un LLM para analizar patrones de engagement a partir de
las metricas crudas extraidas por engagement_extractor.

Ubicado en el pipeline DESPUES de engagement_extractor, ANTES de persona_analyst.
Lee: engagement_insights, top_performing_posts, company_profile
Escribe: engagement_analysis
"""

import json
from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agents.multi_agent.state import AgentState
from src.core.constants import MEDIUM_LLM, GENAI_API_KEY
from src.core.logger import logger


class EngagementAnalysis(BaseModel):
    """Salida estructurada para el analisis de patrones de engagement."""
    content_patterns: str = Field(
        description="Resumen de los patrones de contenido que generan mas engagement (temas, formatos, longitud)."
    )
    best_posting_times: str = Field(
        description="Mejores horarios y dias de la semana para publicar basado en los datos."
    )
    top_formats: List[str] = Field(
        description="Lista de los 3-5 formatos de contenido con mayor engagement (ej. 'carrusel', 'texto largo', 'imagen con estadistica')."
    )
    top_topics: List[str] = Field(
        description="Lista de los 3-5 temas que generan mas interaccion con la audiencia."
    )
    audience_insights: str = Field(
        description="Observaciones sobre la audiencia basadas en las demograficas de seguidores y visitantes."
    )
    recommendations: List[str] = Field(
        description="Lista de 3-5 recomendaciones accionables para mejorar el engagement."
    )
    avg_engagement_rate_assessment: str = Field(
        description="Evaluacion del engagement rate promedio comparado con benchmarks tipicos de LinkedIn (bueno/medio/bajo y por que)."
    )


PROMPT_TEMPLATE = """Eres un Analista de Engagement de LinkedIn experto. Tu tarea es analizar las metricas de engagement de una organizacion y generar insights accionables.

**Empresa:** {company_name} ({industry})

**Metricas Agregadas:**
{aggregate_metrics}

**Top 10 Posts por Engagement Rate:**
{top_posts}

**Estadisticas de Pagina (vistas y visitantes):**
{page_stats}

**Estadisticas de Seguidores (crecimiento y demografia):**
{follower_stats}

Basandote en estos datos, analiza los patrones de engagement y genera recomendaciones estrategicas para mejorar el rendimiento del contenido de esta organizacion en LinkedIn.

Responde en formato JSON estructurado (EngagementAnalysis).
"""


def run_engagement_analyzer_node(state: AgentState) -> Dict[str, Any]:
    """Nodo de LangGraph: analiza patrones de engagement usando LLM.
    
    Toma engagement_insights y top_performing_posts en crudo del
    nodo extractor y produce analisis estrategico y recomendaciones.
    """
    logger.info("Iniciando análisis algorítmico de engagement.")

    engagement_insights = state.get("engagement_insights")
    top_posts = state.get("top_performing_posts", [])
    company_profile = state.get("company_profile", {})

    if not engagement_insights or engagement_insights.get("error"):
        logger.warning("Analizador de engagement: no hay engagement_insights validos. Generando analisis fallback.")
        return {
            "engagement_analysis": {
                "content_patterns": "Sin datos suficientes para analizar patrones.",
                "best_posting_times": "Sin datos disponibles.",
                "top_formats": [],
                "top_topics": [],
                "audience_insights": "Sin datos demograficos disponibles.",
                "recommendations": [
                    "Publicar contenido regularmente para generar datos de engagement.",
                    "Experimentar con diferentes formatos (texto, imagen, carrusel, video).",
                    "Interactuar con comentarios para aumentar el alcance organico.",
                ],
                "avg_engagement_rate_assessment": "Sin datos para evaluar.",
            }
        }

    company_name = company_profile.get("name", "Desconocida")
    industry = company_profile.get("industry", "No especificada")
    aggregate = engagement_insights.get("aggregate_metrics", {})
    page_stats = engagement_insights.get("page_statistics", [])
    follower_stats = engagement_insights.get("follower_statistics", [])

    llm = ChatGoogleGenerativeAI(
        model=MEDIUM_LLM,
        google_api_key=GENAI_API_KEY,
        temperature=0.3,
    )
    structured_llm = llm.with_structured_output(EngagementAnalysis)

    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    chain = prompt | structured_llm

    try:
        analysis_result = chain.invoke({
            "company_name": company_name,
            "industry": industry,
            "aggregate_metrics": json.dumps(aggregate, indent=2, ensure_ascii=False),
            "top_posts": json.dumps(top_posts[:10], indent=2, ensure_ascii=False),
            "page_stats": json.dumps(page_stats[:5], indent=2, ensure_ascii=False),
            "follower_stats": json.dumps(follower_stats[:5], indent=2, ensure_ascii=False),
        })

        # Convertir Pydantic a dict
        if hasattr(analysis_result, "model_dump"):
            analysis_dict = analysis_result.model_dump()
        elif hasattr(analysis_result, "dict"):
            analysis_dict = analysis_result.dict()
        else:
            analysis_dict = dict(analysis_result)

        print("Analisis de engagement completado.")
        logger.info(f"Analisis de engagement generado para {company_name}: "
                     f"{len(analysis_dict.get('recommendations', []))} recomendaciones")

        return {"engagement_analysis": analysis_dict}

    except Exception as e:
        logger.error(f"Error en la llamada LLM del analizador de engagement: {e}", exc_info=True)
        return {
            "engagement_analysis": {
                "content_patterns": f"Error durante el analisis: {str(e)}",
                "best_posting_times": "Error - usar datos manuales.",
                "top_formats": [],
                "top_topics": [],
                "audience_insights": "Error durante el analisis.",
                "recommendations": ["Reintentar el analisis de engagement."],
                "avg_engagement_rate_assessment": "No disponible debido a error.",
            }
        }
