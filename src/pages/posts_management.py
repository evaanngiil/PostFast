import streamlit as st
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List
import pandas as pd

from src.services import api_client
from src.core.logger import logger

def get_posts_from_api(status: str = None) -> List[Dict[str, Any]]:
    """Obtiene posts desde la API."""
    token = api_client._get_current_token()
    if not token:
        st.error("No hay token de autenticación. Por favor, inicia sesión.")
        return []
    try:
        response = requests.get(
            f"{api_client.FASTAPI_URL}/content/posts",
            params={"status": status} if status else {},
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching posts: {e}")
        st.error(f"Error al obtener posts: {e}")
        return []

def delete_post_from_api(post_id: str) -> bool:
    """Elimina un post desde la API."""
    token = api_client._get_current_token()
    if not token:
        st.error("No hay token de autenticación. Por favor, inicia sesión.")
        return False
    try:
        response = requests.delete(
            f"{api_client.FASTAPI_URL}/content/posts/{post_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {e}")
        st.error(f"Error al eliminar post: {e}")
        return False

def update_post_from_api(post_id: str, updates: Dict[str, Any]) -> bool:
    """Actualiza un post desde la API."""
    token = api_client._get_current_token()
    if not token:
        st.error("No hay token de autenticación. Por favor, inicia sesión.")
        return False
    try:
        response = requests.put(
            f"{api_client.FASTAPI_URL}/content/posts/{post_id}",
            json=updates,
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error updating post {post_id}: {e}")
        st.error(f"Error al actualizar post: {e}")
        return False

def publish_post_from_api(post_id: str, platform: str, account_id: str) -> bool:
    """Publica un post guardado o programado."""
    token = api_client._get_current_token()
    if not token:
        st.error("No hay token de autenticación. Por favor, inicia sesión.")
        return False
    try:
        # Obtener el contenido del post
        response = requests.get(
            f"{api_client.FASTAPI_URL}/content/posts/{post_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        post_data = response.json()
        
        # Publicar usando el endpoint de schedule_post
        publish_response = requests.post(
            f"{api_client.FASTAPI_URL}/content/schedule_post",
            json={
                "platform": platform,
                "account_id": account_id,
                "content": post_data["content"],
                "link_url": post_data.get("link_url")
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        publish_response.raise_for_status()
        
        # Actualizar el estado del post a "published"
        update_post_from_api(post_id, {"status": "published", "published_time": datetime.now(timezone.utc).isoformat()})
        return True
    except Exception as e:
        logger.error(f"Error publishing post {post_id}: {e}")
        st.error(f"Error al publicar post: {e}")
        return False

def render_post_card(post: Dict[str, Any], context: Dict[str, Any]):
    """Renderiza una tarjeta individual de post."""
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write(f"**{post.get('title', 'Sin título')}**")
            st.caption(f"Plataforma: {post['platform']} | Estado: {post['status']}")
            st.caption(f"Creado: {post['created_at'][:19] if post.get('created_at') else 'N/A'}")
            
            if post.get('scheduled_time'):
                st.caption(f"Programado: {post['scheduled_time'][:19]}")
            if post.get('published_time'):
                st.caption(f"Publicado: {post['published_time'][:19]}")
            
            # Mostrar contenido (truncado)
            content = post.get('content', '')
            if len(content) > 200:
                st.write(f"{content[:200]}...")
                with st.expander("Ver contenido completo"):
                    st.write(content)
            else:
                st.write(content)
        
        with col2:
            # Botones de acción según el estado
            if post['status'] == 'saved_for_later':
                if st.button("📤 Publicar", key=f"publish_{post['id']}", use_container_width=True):
                    if publish_post_from_api(post['id'], post['platform'], post['account_id']):
                        st.success("Post publicado!")
                        st.rerun()
                
                if st.button("✏️ Editar", key=f"edit_{post['id']}", use_container_width=True):
                    st.session_state['editing_post'] = post
                    st.rerun()
            
            elif post['status'] == 'scheduled':
                if st.button("🕐 Reprogramar", key=f"reschedule_{post['id']}", use_container_width=True):
                    st.session_state['rescheduling_post'] = post
                    st.rerun()
            
            if st.button("🗑️ Eliminar", key=f"delete_{post['id']}", use_container_width=True):
                if delete_post_from_api(post['id']):
                    st.success("Post eliminado!")
                    st.rerun()

def render_edit_form(post: Dict[str, Any]):
    """Renderiza el formulario de edición de post."""
    with st.container(border=True):
        st.subheader("✏️ Editar Post")
        
        with st.form(f"edit_form_{post['id']}"):
            title = st.text_input("Título", value=post.get('title', ''))
            content = st.text_area("Contenido", value=post.get('content', ''), height=200)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 Guardar cambios"):
                    updates = {
                        "title": title,
                        "content": content
                    }
                    if update_post_from_api(post['id'], updates):
                        st.success("Post actualizado!")
                        del st.session_state['editing_post']
                        st.rerun()
            
            with col2:
                if st.form_submit_button("❌ Cancelar"):
                    del st.session_state['editing_post']
                    st.rerun()

def render_reschedule_form(post: Dict[str, Any]):
    """Renderiza el formulario de reprogramación."""
    with st.container(border=True):
        st.subheader("🕐 Reprogramar Post")
        
        with st.form(f"reschedule_form_{post['id']}"):
            new_time = st.datetime_input(
                "Nueva fecha y hora",
                value=datetime.fromisoformat(post['scheduled_time'].replace('Z', '+00:00')) if post.get('scheduled_time') else datetime.now(timezone.utc),
                min_value=datetime.now(timezone.utc)
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("🕐 Reprogramar"):
                    updates = {"scheduled_time": new_time.isoformat()}
                    if update_post_from_api(post['id'], updates):
                        st.success("Post reprogramado!")
                        del st.session_state['rescheduling_post']
                        st.rerun()
            
            with col2:
                if st.form_submit_button("❌ Cancelar"):
                    del st.session_state['rescheduling_post']
                    st.rerun()

def render_page(context: Dict[str, Any]):
    """Renderiza la página de gestión de posts."""
    st.title("📝 Gestión de Posts")
    
    if not context.get('data'):
        st.info("Por favor selecciona una cuenta en la barra lateral para ver los posts.")
        return
    
    # Filtros
    col1, col2 = st.columns([2, 1])
    with col1:
        status_filter = st.selectbox(
            "Filtrar por estado",
            ["Todos", "Guardados para más tarde", "Programados", "Publicados"],
            index=0
        )
    
    with col2:
        if st.button("🔄 Actualizar", use_container_width=True):
            st.rerun()
    
    # Formularios de edición/reprogramación
    if 'editing_post' in st.session_state:
        render_edit_form(st.session_state['editing_post'])
        return
    
    if 'rescheduling_post' in st.session_state:
        render_reschedule_form(st.session_state['rescheduling_post'])
        return
    
    # Obtener posts
    status_mapping = {
        "Todos": None,
        "Guardados para más tarde": "saved_for_later",
        "Programados": "scheduled", 
        "Publicados": "published"
    }
    status_param = status_mapping[status_filter]
    posts = get_posts_from_api(status_param)
    
    if not posts:
        st.info(f"No hay posts {status_filter.lower() if status_filter != 'Todos' else ''}")
        return
    
    # Mostrar estadísticas
    st.subheader("📊 Estadísticas")
    stats_cols = st.columns(4)
    status_counts = {}
    for post in posts:
        status = post['status']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Mapeo de estados para mostrar nombres legibles
    status_display_names = {
        "saved_for_later": "Guardados",
        "scheduled": "Programados", 
        "published": "Publicados",
        "draft": "Borradores"
    }
    
    for i, (status, count) in enumerate(status_counts.items()):
        with stats_cols[i]:
            display_name = status_display_names.get(status, status.replace('_', ' ').title())
            # Asegurar que display_name nunca sea None o vacío
            if not display_name or display_name.strip() == "":
                display_name = "Otros"
            st.metric(
                label=display_name,
                value=count
            )
    
    st.divider()
    
    # Lista de posts
    st.subheader(f"📋 Posts ({len(posts)} encontrados)")
    
    # Ordenar por fecha de creación (más recientes primero)
    posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    for post in posts:
        render_post_card(post, context) 