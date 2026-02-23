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
    # Datos del selected_account, verificados y enriquecidos
    name: str
    urn: str
    vanity_name: str
    
    # Datos extraídos de la página pública de LinkedIn
    followers: Optional[str]
    industry: Optional[str]
    company_size: Optional[str]
    headquarters: Optional[str]
    company_type: Optional[str]
    founded: Optional[str]
    specialties: Optional[List[str]]
    
    # Contenido limpio para el análisis de persona
    about_us_content: Optional[str]

class AgentState(TypedDict):
    # Entradas iniciales del frontend
    linkedin_access_token: str
    user_post_idea: str
    selected_account: Dict[str, Any]
    
    # Artefactos generados
    company_profile: Optional[CompanyProfile]
    brand_persona_json: Optional[Dict[str, Any]]
    fleshed_out_idea: Optional[PostIdea]
    draft_post: Optional[DraftPost]
    
    # Control de flujo
    next_agent: Optional[str]