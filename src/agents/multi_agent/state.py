from typing import TypedDict, List, Annotated, Optional, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

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
    # Message log para la orquestación
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Initial payload
    linkedin_access_token: str
    user_post_idea: str
    selected_account: Dict[str, Any]
    
    # Artefactos mutables del pipeline
    company_profile: Optional[CompanyProfile]
    brand_persona_json: Optional[Dict[str, Any]]
    fleshed_out_idea: Optional[PostIdea]
    draft_post: Optional[DraftPost]
    
    # Engagement data fields
    engagement_insights: Optional[Dict[str, Any]]           
    top_performing_posts: Optional[List[Dict[str, Any]]]
    engagement_analysis: Optional[Dict[str, Any]]           
    
    # Ruteo dinámico
    next_agent: Optional[str]

    # HITL (Human-In-The-Loop) feedback para re-ruteo
    user_feedback: Optional[str]