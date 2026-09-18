from typing import TypedDict, List, Optional, Dict, Any

class PostIdea(TypedDict):
    topic: str
    suggested_format: str
    strategic_goal: str

class DraftPost(TypedDict):
    content: str 
    hashtags: List[str]
    call_to_action: str

class CompanyProfile(TypedDict):
    """Estructura de metadata consolidada para el tenant corporativo."""
    # Base identity claims extraídos del auth token
    name: str
    urn: str
    vanity_name: str
    
    # Atributos extraídos vía scraping/API
    followers: Optional[str]
    industry: Optional[str]
    company_size: Optional[str]
    headquarters: Optional[str]
    company_type: Optional[str]
    founded: Optional[str]
    specialties: Optional[List[str]]
    
    # Copywriting crudo para el nodo de brand_persona
    about_us_content: Optional[str]

class AgentState(TypedDict):
    """Definición del DAG state para el grafo multi-agente."""
    # Initial payload
    linkedin_access_token: str
    user_post_idea: str
    selected_account: Dict[str, Any]
    link_url: Optional[str]
    
    # Artefactos mutables del pipeline
    company_profile: Optional[CompanyProfile]
    brand_persona_json: Optional[Dict[str, Any]]
    fleshed_out_idea: Optional[PostIdea]
    draft_post: Optional[DraftPost]
    last_draft_content: Optional[str]  # Mantiene el texto exacto para referencia en feedback

    
    # Engagement data fields
    engagement_insights: Optional[Dict[str, Any]]           
    top_performing_posts: Optional[List[Dict[str, Any]]]
    engagement_analysis: Optional[Dict[str, Any]]           
    
    # HITL (Human-In-The-Loop) feedback para re-ruteo
    user_feedback: Optional[str]

    # NUEVOS — Knowledge & RAG
    knowledge_indexed: Optional[bool]              # Flag de indexación completada
    task_id: Optional[str]                          # ID de la tarea Celery para Realtime Broadcast

    # NUEVOS — Detección de vacío de conocimiento
    # Avisa al usuario cuando su petición exige información específica/verificada
    # (una relación, un dato, una alianza, un caso) que NO existe en la base de
    # conocimiento, evitando que se publique un post genérico sin que lo sepa.
    knowledge_gap: Optional[Dict[str, Any]]         # {has_gap, missing_info, user_message}
    
    # NUEVOS — Duplicate Detection
    existing_posts_on_topic: Optional[List[Dict[str, Any]]]  # Posts similares encontrados
    duplicate_context: Optional[str]               # Contexto formateado para el writer
    
    # NUEVOS — Trend Research
    industry_trends: Optional[str]                 # Tendencias actuales del sector
    
    # NUEVOS — Fact Checking
    fact_check_report: Optional[Dict[str, Any]]    # Reporte de verificación
    
    # NUEVOS — Safety
    safety_report: Optional[Dict[str, Any]]        # Reporte de seguridad/compliance
    
    # NUEVOS — Skills
    selected_skill: Optional[Dict[str, Any]]       # Habilidad seleccionada para redacción
    selected_skills: Optional[List[Dict[str, Any]]] # Lista de habilidades seleccionadas
    
    # NUEVOS — Control de Bucles Infinitos
    correction_loops: Optional[int]                # Contador de reintentos por seguridad o factualidad
    
    # NUEVOS — Modo Edición Rápida (protocolo estructurado)
    edit_mode: Optional[bool]                      # Flag para indicar si es una edición rápida de post
    original_post: Optional[str]                   # Texto original del post a editar (modo edición)
    edit_instructions: Optional[str]               # Instrucciones de mejora del usuario (modo edición)

    # NUEVOS — Evaluación / Ablación
    # Nombres de capacidades desactivadas para estudios de ablación del TFG:
    # 'trend_researcher', 'duplicate_detector', 'fact_checker', 'safety_guard',
    # 'engagement_analyzer', 'persona_analyst', 'research_loop'.
    ablation_disabled: Optional[List[str]]