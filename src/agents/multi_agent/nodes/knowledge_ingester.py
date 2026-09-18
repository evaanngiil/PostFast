"""
Nodo Knowledge Ingester (RAG Indexer) para PostFast.
Se encarga de estructurar, embeddear e indexar toda la información de la empresa
en la base de conocimientos vectorial pgvector, incluyendo simulaciones de documentos
internos (Brand Book y Catálogo de Productos) si no existen, para cumplir con el TFG.
"""
from typing import Dict, Any
import json
from src.agents.multi_agent.state import AgentState
from src.services.rag_service import index_document, index_post, search_knowledge
from src.core.constants import MEDIUM_LLM, GENAI_API_KEY
from src.core.logger import logger
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

SIMULATION_PROMPT = """
Eres un Consultor Estratégico de Negocios y Brand Manager. Dado el perfil de esta empresa, debes generar dos documentos estratégicos simulados realistas para enriquecer su base de conocimientos RAG:

**Perfil de la Empresa:**
Nombre: {company_name}
Industria: {industry}
Especialidades: {specialties}
Sobre nosotros: {about_us}

Genera un JSON con exactamente estas dos claves:
1. "brand_book": Una guía de Do's & Don'ts de comunicación para LinkedIn en formato Markdown. Debe detallar estrictamente:
   - "Qué hacer" (Do's) al escribir en LinkedIn (en formato de lista, con pautas claras de estructura, hooks y formato).
   - "Qué NO hacer" (Don'ts) al escribir en LinkedIn (en formato de lista, indicando qué palabras, temas o formatos evitar).
   - Emojis recomendados y hashtags de la marca.
   (Nota: NO incluyas secciones de pautas de tono o valores de marca aquí).
2. "product_catalog": Un catálogo detallado de productos o servicios que ofrece la empresa en formato Markdown. Debe incluir:
   - Nombre de 2-3 productos/servicios estrella.
   - Descripción, beneficios clave, público objetivo y problemas que resuelven.
   - Puntos de diferenciación frente a competidores.

Devuelve EXCLUSIVAMENTE el JSON solicitado, sin texto introductorio ni explicaciones.
"""

PERSONAL_SIMULATION_PROMPT = """
Eres un Consultor Estratégico de Marca Personal y Posicionamiento. Dado el perfil de este profesional, debes generar dos documentos estratégicos simulados realistas para enriquecer su base de conocimientos RAG:

**Perfil Profesional:**
Nombre: {company_name}
Sector/Área de Especialización: {industry}
Especialidades: {specialties}
Sobre mí: {about_us}

Genera un JSON con exactamente estas dos claves:
1. "brand_book": Una guía de Do's & Don'ts de comunicación personal en LinkedIn en formato Markdown. Debe detallar estrictamente:
   - "Qué hacer" (Do's) al escribir en LinkedIn (en formato de lista, pautas claras de gancho, espaciado y estructura).
   - "Qué NO hacer" (Don'ts) al escribir en LinkedIn (en formato de lista, temas, palabras o malas prácticas a evitar).
   - Emojis recomendados y hashtags de la marca personal.
   (Nota: NO incluyas secciones de pautas de tono o valores de marca aquí).
2. "product_catalog": Un catálogo detallado de servicios o áreas de especialización que ofrece el profesional en formato Markdown. Debe incluir:
   - Nombre de 2-3 servicios o soluciones clave que ofrece.
   - Descripción, beneficios clave, público objetivo y problemas que resuelve.
   - Puntos de diferenciación frente a otros profesionales.

Devuelve EXCLUSIVAMENTE el JSON solicitado, sin texto introductorio ni explicaciones.
"""

def run_knowledge_ingester_node(state: AgentState) -> Dict[str, Any]:
    print("--- 📥 EJECUTANDO INGESTOR DE CONOCIMIENTO (RAG INDEXER) ---")
    logger.info("=== KNOWLEDGE INGESTER: start ===")
    
    company_profile = state.get("company_profile", {})
    org_urn = company_profile.get("urn", "")
    company_name = company_profile.get("name", "Empresa")
    industry = company_profile.get("industry") or "Tecnología"
    specialties = company_profile.get("specialties", [])
    about_us = company_profile.get("about_us_content", "")
    
    if not org_urn:
        logger.warning("Knowledge Ingester: no se encuentra org_urn. Continuando...")
        return {"knowledge_indexed": False}
        
    specs_str = ", ".join(specialties) if specialties else "No especificadas"
    is_personal_profile = org_urn.startswith("urn:li:person:")
    
    # 1. Indexar "Sobre Nosotros" / "Sobre Mí"
    if about_us:
        logger.info("Indexando About Us...")
        index_document(
            org_urn=org_urn,
            source_type="about_us",
            source_id="linkedin_about_us",
            content=f"Sobre el perfil profesional de {company_name}:\n{about_us}" if is_personal_profile else f"Sobre la empresa {company_name}:\n{about_us}",
            metadata={"company_name": company_name, "industry": industry}
        )
        
    # 2. Indexar Especialidades
    if specialties:
        logger.info("Indexando especialidades...")
        specialties_content = (
            f"El profesional {company_name} está especializado en las siguientes áreas de expertise: {specs_str}."
            if is_personal_profile else
            f"La empresa {company_name} está especializada en las siguientes áreas de negocio y expertise tecnológico: {specs_str}."
        )
        index_document(
            org_urn=org_urn,
            source_type="specialties",
            source_id="linkedin_specialties",
            content=specialties_content,
            metadata={"company_name": company_name}
        )

    # 3. Indexar posts históricos (top_performing_posts) si están disponibles en el estado
    top_posts = state.get("top_performing_posts", [])
    if top_posts:
        logger.info(f"Indexando {len(top_posts)} posts históricos de la organización...")
        
        # Evaluar calidad de cada post
        from src.services.rag_service import evaluate_post_quality
        evaluated_posts = []
        for i, post in enumerate(top_posts):
            content = post.get("content") or post.get("text") or ""
            if not content:
                continue
            score = evaluate_post_quality(content)
            evaluated_posts.append({
                "post": post,
                "content": content,
                "score": score,
                "index": i
            })
            
        # Ordenar por score descendente
        evaluated_posts.sort(key=lambda x: x["score"], reverse=True)
        
        for idx, item in enumerate(evaluated_posts):
            post = item["post"]
            content = item["content"]
            score = item["score"]
            i = item["index"]
            
            post_urn = post.get("urn") or post.get("id") or f"historic_post_{i}"
            engagement_rate = post.get("engagement_rate", 0.0)
            published_at = post.get("published_at") or post.get("created_at")
            
            # Indexar en post_embeddings (para duplicados)
            index_post(
                org_urn=org_urn,
                post_urn=post_urn,
                content=content,
                summary=post.get("summary", ""),
                dominant_topic=post.get("dominant_topic", ""),
                tone=post.get("tone", ""),
                engagement_rate=engagement_rate,
                published_at=published_at
            )
            
            # Los 5 mejores serán referencia (is_reference=True)
            is_reference = (idx < 5)
            
            # Indexar en general company_knowledge (como posts de referencia/históricos)
            index_document(
                org_urn=org_urn,
                source_type="linkedin_post",
                source_id=post_urn,
                content=f"Post publicado anteriormente con alto engagement:\n{content}",
                metadata={
                    "engagement_rate": engagement_rate, 
                    "published_at": published_at,
                    "score": score,
                    "is_reference": is_reference
                }
            )

    # 4. Simular/Generar Brand Book y Catálogo de Productos si no existen en el RAG
    # Validamos si ya existen registros de tipo brand_book para esta org_urn
    existing_brand_docs = search_knowledge(
        query="valores core y tono de comunicación",
        org_urn=org_urn,
        source_type="brand_book",
        threshold=0.3,
        limit=1
    )
    
    if not existing_brand_docs:
        if is_personal_profile:
            logger.info("No se encontraron documentos de marca previos. Generando simulación de marca personal con Gemini...")
            prompt_str = PERSONAL_SIMULATION_PROMPT
            if industry == "Tecnología":
                industry = "Tecnología / Consultoría Profesional"
        else:
            logger.info("No se encontraron documentos de marca previos. Generando simulación corporativa con Gemini...")
            prompt_str = SIMULATION_PROMPT

        try:
            llm = ChatGoogleGenerativeAI(
                model=MEDIUM_LLM,
                google_api_key=GENAI_API_KEY,
                temperature=0.7
            )
            prompt = ChatPromptTemplate.from_template(prompt_str)
            chain = prompt | llm
            
            response = chain.invoke({
                "company_name": company_name,
                "industry": industry,
                "specialties": specs_str,
                "about_us": about_us or "Sin descripción"
            })
            
            raw_content = response.content
            if isinstance(raw_content, list):
                raw_content = "\n".join(
                    part if isinstance(part, str) else part.get("text", str(part))
                    for part in raw_content
                )
            
            # Limpiar markdown JSON markers si los hay
            raw_content = raw_content.strip()
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            raw_content = raw_content.strip()
            
            doc_data = json.loads(raw_content)
            brand_book_md = doc_data.get("brand_book", "")
            catalog_md = doc_data.get("product_catalog", "")
            
            if brand_book_md:
                logger.info("Indexando Brand Book simulado...")
                index_document(
                    org_urn=org_urn,
                    source_type="brand_book",
                    source_id="simulated_brand_book",
                    content=brand_book_md,
                    metadata={"company_name": company_name, "simulated": True}
                )
                
            if catalog_md:
                logger.info("Indexando Catálogo de Productos/Servicios simulado...")
                index_document(
                    org_urn=org_urn,
                    source_type="product_catalog",
                    source_id="simulated_product_catalog",
                    content=catalog_md,
                    metadata={"company_name": company_name, "simulated": True}
                )
                
            # Agregar simulación de competidores/referentes
            if is_personal_profile:
                logger.info("Generando análisis de referentes e inspiración profesional...")
                competitor_analysis = f"""
### Análisis de Referentes y Posicionamiento Profesional para {company_name} (Simulado)

En el sector de {industry}, otros profesionales suelen publicar contenido puramente promocional o técnico.
Nuestra oportunidad de diferenciación y marca personal en LinkedIn consiste en:
1. Contar historias y anécdotas de proyectos reales (storytelling profesional).
2. Compartir lecciones aprendidas y errores cometidos en el camino (vulnerabilidad y aprendizaje).
3. Publicar reflexiones de liderazgo de opinión sobre el futuro de {specs_str}.
4. Simplificar conceptos complejos mediante hilos y guías educativas muy prácticas.

Ángulos exitosos detectados:
- Contenido de Inspiración: 'Lo que he aprendido tras años trabajando en {specs_str}'.
- Contenido de Valor Técnico: 'Cómo resolví un problema crítico de arquitectura/negocio en 3 pasos'.
- Contenido de Aprendizaje: 'El mayor error de mi carrera en {specs_str} y qué me enseñó'.
"""
            else:
                logger.info("Generando análisis de competidores e inspiración...")
                competitor_analysis = f"""
### Análisis de Competidores y Referentes de la Industria de {company_name} (Simulado)

En el sector de {industry}, los competidores clave suelen enfocarse en mensajes puramente técnicos. 
Nuestra oportunidad de diferenciación narrativa en LinkedIn consiste en:
1. Humanizar la marca contando el 'detrás de escena' (storytelling de proyectos reales).
2. Simplificar conceptos complejos mediante analogías cotidianas y visuales.
3. Publicar posts de opinión liderada (thought leadership) del equipo fundador sobre tendencias del sector.
4. Utilizar carruseles educativos que inviten a guardar el post.

Ángulos exitosos detectados:
- Contenido de Inspiración: 'Lo que nadie te cuenta de trabajar en {specs_str}'.
- Contenido Técnico Educativo: '3 errores comunes en proyectos de {specs_str} y cómo solucionarlos'.
- Contenido Comercial Sutil: 'Cómo ayudamos a un cliente a optimizar sus procesos usando nuestro enfoque'.
"""
            
            index_document(
                org_urn=org_urn,
                source_type="competitor_analysis",
                source_id="simulated_competitors",
                content=competitor_analysis.strip(),
                metadata={"company_name": company_name, "simulated": True}
            )
            
            logger.info("Documentos simulados indexados con éxito.")
            
        except Exception as e:
            logger.error(f"Error generando o indexando documentos de simulación: {e}")
    else:
        logger.info("Base de conocimientos ya enriquecida previamente con documentos corporativos/personales.")

    print("✅ Indexación de conocimiento completada.")
    logger.info("=== KNOWLEDGE INGESTER: completed ===")
    return {"knowledge_indexed": True}
