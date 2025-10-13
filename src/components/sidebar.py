import base64
from io import BytesIO
import streamlit as st
from typing import Dict, Any
from PIL import Image

# Las importaciones de tus módulos de autenticación
from src.core.logger import logger
from src.supabase_auth import logout
try:
    from src.linkedin_auth import display_auth_status, display_account_selector
except ImportError as e:
    st.error(f"Fatal Import Error (auth): {e}")
    st.stop()

def get_user_initials(name: str) -> str:
    """Genera iniciales a partir de un nombre."""
    if not name:
        return "👤"
    parts = name.split()
    if len(parts) > 1:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][0].upper()

def get_base64_image(image_path: str) -> str:
    """Convierte una imagen a una cadena base64."""
    with Image.open(image_path) as img:
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()



def render_sidebar() -> Dict[str, Any] | None:
    """
    Renders the modern, brand-aligned sidebar for AIPost.
    
    Returns:
        The dictionary of the selected account data, or None if no account is selected.
    """
    
    # Inyectamos el CSS para un diseño profesional y alineado con la marca AIPost.
    st.markdown("""
    <style>
        /* Importar la fuente de íconos de Bootstrap */
        @import url("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css");

        /* Variables de color de la marca AIPost */
        :root {
            --brand-teal: #00A99D; /* Teal del logo */
            --brand-charcoal: #00A99D;
            --background-dark: #F0F2F6;
            --text-light: #473E40;
            --text-muted: #495f5e;
            --danger-red: #E53E3E;
        }

        /* Estilo del contenedor principal del sidebar */
        [data-testid="stSidebar"] {
            background-color: var(--background-dark);
            border-right: 1px solid var(--brand-charcoal);
        }

        .st-emotion-cache-kgpedg {
            display: none;
        }

        
        /* Títulos de las secciones */
        .nav-title {
            color: var(--text-muted);
            font-weight: 500;
            font-size: 0.9rem;
            margin: 2rem 0 0.75rem 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }
        
        /* Sección de usuario */
        .user-section {
            display: flex;
            align-items: center;
            gap: 12px;
            background: var(--brand-charcoal);
            border-radius: 10px;
            padding: 0.75rem;
            margin: 1rem 0;
        }
        .user-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: var(--text-light);
            color: var(--background-dark);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
            font-weight: 600;
            flex-shrink: 0;
        }
        .user-info .user-name {
            color: var(--background-dark);
            font-weight: 600;
            margin: 0;
            line-height: 1.2;
        }
        .user-info .user-email {
            color: var(--text-muted);
            font-size: 0.8rem;
            margin: 0;
        }
        
       .nav-link {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-light);
            padding: 0.75rem 1rem;
            border-radius: 8px;
            margin-bottom: 0.5rem;
            transition: all 0.2s ease-in-out;
            text-decoration: none !important; 
        }

        .nav-link:hover {
            background-color: var(--brand-charcoal);
            color: var(--text-light);
            text-decoration: none !important;
        }

        .nav-link:visited,
        .nav-link:active,
        .nav-link:focus {
            color: var(--text-light);
            text-decoration: none !important;
        }

        /* Asegurar que no haya subrayado en ningún estado del enlace */
        .nav-link:link,
        .nav-link:visited,
        .nav-link:hover,
        .nav-link:active,
        .nav-link:focus {
            text-decoration: none !important;
            border-bottom: none !important;
        }

        .nav-link i {
            font-size: 1.2rem;
            color: var(--brand-teal);
        }

        .nav-link:hover i {
            color: white !important;
        }
        /* Botón de cerrar sesión */
        .stButton button {
            background: transparent !important;
            color: var(--danger-red) !important;
            border: 1px solid var(--danger-red) !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            transition: all 0.2s ease-in-out !important;
            width: 100% !important;
        }
        .stButton button:hover {
            background: var(--danger-red) !important;
            color: white !important;
        }
        .stButton button::before {
            font-family: "bootstrap-icons";
            content: "\\F343";
            margin-right: 0.5rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        try:
            logo_base64 = get_base64_image("./src/assets/AIPOST.png")
            st.markdown(
                f"<div style='text-align:center; margin: 25px 0 0.25rem 0;'>"
                f"<img src='data:image/png;base64,{logo_base64}' width='150'/>"
                f"</div>", unsafe_allow_html=True
            )
        except Exception:
            st.markdown("<h3 style='text-align:center;'>AIPOST</h3>", unsafe_allow_html=True)

        # --- SECCIÓN DE USUARIO ---
        user = st.session_state.get('user')
        if user:
            logger.info(f"AQUI ESTA EL USER {user}")
            user_name = getattr(user, 'name', 'Usuario Anónimo')
            user_email = getattr(user, 'email', 'Sin email')
            user_initials = get_user_initials(user_name)
            
            st.markdown(f"""
            <div class="user-section">
                <div class="user-avatar">{user_initials}</div>
                <div class="user-info">
                    <p class="user-name">{user_name}</p>
                    <p class="user-email">{user_email}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # --- NAVEGACIÓN PRINCIPAL ---
        st.markdown('<div class="nav-title">Herramientas</div>', unsafe_allow_html=True)
        st.markdown("<a href='Dashboard' target='_self' class='nav-link'><i class='bi bi-grid-fill'></i> Dashboard</a>", unsafe_allow_html=True)
        st.markdown("<a href='Content_Generation' target='_self' class='nav-link'><i class='bi bi-magic'></i> Generar Contenido</a>", unsafe_allow_html=True)
        st.markdown("<a href='Posts_Management' target='_self' class='nav-link'><i class='bi bi-archive-fill'></i> Gestionar Posts</a>", unsafe_allow_html=True)
        
        # --- CONEXIONES SOCIALES ---
        st.markdown('<div class="nav-title">Conexiones</div>', unsafe_allow_html=True)
        with st.container(border=True):
            display_auth_status(sidebar=True)
            selected_account_data = display_account_selector(sidebar=True)

        # --- ACCIÓN DE CIERRE DE SESIÓN ---
        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            logout()
            st.success("¡Sesión cerrada correctamente!")
            st.rerun()

        # Retornamos solo los datos necesarios
        return selected_account_data