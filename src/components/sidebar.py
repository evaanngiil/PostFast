import base64
from io import BytesIO
import streamlit as st
from typing import Dict, Any, Optional
from PIL import Image

from src.core.logger import logger
from src.supabase_auth import logout, get_user_profile, get_user_organizations, set_active_organization, update_profile_email, get_active_organization, update_org_urn

try:
    from src.linkedin_auth import display_auth_status
except ImportError as e:
    st.error(f"Fatal Import Error (auth): {e}")
    st.stop()

def get_user_initials(name: str) -> str:
    """
    Extrae y genera iniciales a partir de un nombre completo.

    :param name: Nombre del usuario en formato texto.
    :returns: String con las iniciales (máximo 2 caracteres) o un emoji por defecto.
    """
    if not name:
        return "👤"
    parts = name.split()
    if len(parts) > 1:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][0].upper()

def get_base64_image(image_path: str) -> str:
    """
    Lee un asset del disco y lo codifica en base64 para inyección inline.

    :param image_path: Ruta del sistema al archivo de imagen.
    :returns: String codificado en base64 listo para usar en HTML.
    """
    with Image.open(image_path) as img:
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()



def render_sidebar(user) -> Dict[str, Any] | None:
    """
    Renderiza la barra lateral principal de navegación y selección de contexto.

    :param user: Objeto de usuario autenticado de Supabase.
    :returns: Un diccionario con el estado de la cuenta seleccionada o None si es inválido.
    """
    
    # Validamos el usuario de Supabase que nos ha pasado Dashboard.py
    if not user or not hasattr(user, 'id'):
        logger.error(f"render_sidebar fue llamado sin un usuario de Supabase válido. User: {user}")
        st.warning("Error de sesión. Por favor, inicia sesión de nuevo.")
    # Fallback de seguridad en caso de que el payload del usuario esté corrupto.
        st.switch_page("app.py")
        return None
    
    
    st.markdown("""
    <style>
        /* Importación de tipografía de íconos. */
        @import url("https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css");

        /* Sistema de tokens de color. */
        :root {
            --brand-teal: #00A99D; /* Teal del logo */
            --brand-charcoal: #00A99D;
            --background-dark: #F0F2F6;
            --text-light: #473E40;
            --text-muted: #495f5e;
            --danger-red: #E53E3E;
        }

        /* Contenedor principal. */
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
            padding: 0.75rem 1rem;
            border-radius: 8px;
            margin-bottom: 0.5rem;
            transition: all 0.2s ease-in-out;
            text-decoration: none !important; 
        }

        /* Forzar el mismo color para enlaces nuevos y visitados */
        .nav-link:link,
        .nav-link:visited {
            color: var(--text-light) !important;
            text-decoration: none !important;
        }

        .nav-link:hover,
        .nav-link:active,
        .nav-link:focus {
            background-color: var(--brand-charcoal);
            color: white !important;
            text-decoration: none !important;
        }

        .nav-link i {
            font-size: 1.2rem;
            color: var(--brand-teal);
        }

        .nav-link:hover i {
            color: white !important;
        }

        /* Botón de logout. */
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

        if user:
            logger.info(f"Sidebar renderizando para user.id: {user.id}")
            
            profile = get_user_profile(user.id)
            user_name = "Usuario"
            user_surname = "Anónimo"
            
            if profile:
                user_name = profile.get('first_name', 'Usuario')
                user_surname = profile.get('last_name', '') # Apellido puede estar vacío
            else:
                # Resolución de atributos mediante metadata en caso de que el registro de perfil falle.
                logger.warning(f"Sidebar no pudo encontrar el perfil para {user.id}, usando metadata.")
                user_name = user.user_metadata.get('first_name', 'Usuario')
                user_surname = user.user_metadata.get('last_name', 'Anónimo')

            # Estrategia de resolución de email priorizando fuentes verificadas.
            def _is_real_email(e):
                return bool(e) and '@linkedin.placeholder' not in e

            raw_email = getattr(user, 'email', None)
            profile_email = profile.get('email', '') if profile else ''
            li_user = True if st.session_state.get('li_user_info', {}) else False
            li_email = st.session_state.get('li_user_info', {'email': 'NO EMAIL'}).get('email', '') if li_user else 'No email'

            if _is_real_email(raw_email):
                user_email = raw_email
            elif _is_real_email(profile_email):
                user_email = profile_email
            elif _is_real_email(li_email):
                user_email = li_email
                # Migración asíncrona del email para usuarios legacy.
                update_profile_email(user.id, li_email)
            else:
                user_email = 'Sin email'
            full_name = f"{user_name} {user_surname}".strip()
            user_initials = get_user_initials(full_name)
            
            st.markdown(f"""
            <div class="user-section">
                <div class="user-avatar">{user_initials}</div>
                <div class="user-info">
                    <p class="user-name">{full_name}</p>
                    <p class="user-email">{user_email}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Selector unificado: sincroniza el state de la API de LinkedIn con la persistencia en DB para mitigar desincronizaciones del contexto global.
            linkedin_accounts = st.session_state.get("user_accounts") or []
            db_orgs = get_user_organizations(user.id)

            # Índices de acceso en tiempo constante (O(1)) por URN y nombre de empresa.
            urn_to_db_org: Dict[str, dict] = {}
            name_to_db_org: Dict[str, dict] = {}
            personal_db_org: Optional[dict] = None
            for db_o in db_orgs:
                if db_o.get("is_personal"):
                    personal_db_org = db_o
                org_urn = db_o.get("org_urn")
                if org_urn:
                    urn_to_db_org[org_urn] = db_o
                cname = (db_o.get("company_name") or "").strip().lower()
                if cname:
                    name_to_db_org[cname] = db_o

            if linkedin_accounts and st.session_state.get("li_connected"):
                st.markdown('<div class="nav-title">Organizacion</div>', unsafe_allow_html=True)

                def _format_li_account(acc):
                    label = acc.get("name", "N/A")
                    acc_type = acc.get("type", "profile")
                    if acc_type == "organization":
                        return f"{label} (Empresa)"
                    return f"{label} (Personal)"

                # Recuperar el índice activo evaluando la base de datos, ignorando
                # el estado volátil del session_state para prevenir reseteos en soft reloads.
                active_org_from_db = get_active_organization(user.id)
                active_urn_from_db = (active_org_from_db or {}).get("org_urn")
                active_name_from_db = ((active_org_from_db or {}).get("company_name") or "").strip().lower()
                active_is_personal = (active_org_from_db or {}).get("is_personal", False)

                current_idx = 0  # default: first account (personal)
                for i, acc in enumerate(linkedin_accounts):
                    acc_urn = acc.get("urn", "")
                    acc_name = (acc.get("name") or "").strip().lower()
                    acc_type = acc.get("type", "profile")

                    # Búsqueda estricta por URN (identificador determinista).
                    if active_urn_from_db and acc_urn == active_urn_from_db:
                        current_idx = i
                        break
                    # Fallback de inferencia heurística por string matching.
                    if active_name_from_db and acc_name == active_name_from_db:
                        current_idx = i
                        break
                    # Fallback a cuenta de origen (perfil de usuario básico).
                    if active_is_personal and acc_type == "profile":
                        current_idx = i
                        break

                selected_index = st.selectbox(
                    "Cuenta activa",
                    options=range(len(linkedin_accounts)),
                    format_func=lambda i: _format_li_account(linkedin_accounts[i]),
                    index=current_idx,
                    label_visibility="collapsed",
                    key="unified_account_selector",
                )

                newly_selected = linkedin_accounts[selected_index]

                def _find_db_org(li_acc: dict) -> Optional[dict]:
                    """
                    Empareja un payload abstracto de cuenta de LinkedIn con su entidad equivalente en DB.

                    :param li_acc: Diccionario de la API de la red social.
                    :returns: Registro de la organización o None si el binding falla.
                    """
                    urn = li_acc.get("urn", "")
                    # Match prioritario por URN de LinkedIn.
                    if urn and urn in urn_to_db_org:
                        return urn_to_db_org[urn]
                    # Match secundario normalizando el nombre empresarial.
                    cname = (li_acc.get("name") or "").strip().lower()
                    if cname and cname in name_to_db_org:
                        return name_to_db_org[cname]
                    # Handleo de perfil del usuario.
                    if li_acc.get("type") == "profile" and personal_db_org:
                        return personal_db_org
                    return None

                # Detección de drift entre la UI y el estado persistente.
                newly_selected_urn = newly_selected.get("urn", "")

                if active_org_from_db is None:
                    # Cold start: inicialización forzosa en BD sin disparar ciclos infinitos de re-renderizado.
                    matched_db = _find_db_org(newly_selected)
                    if matched_db:
                        set_active_organization(user.id, matched_db["id"])
                        st.session_state["active_org"] = matched_db
                        if newly_selected_urn and not matched_db.get("org_urn"):
                            update_org_urn(matched_db["id"], newly_selected_urn)
                    st.session_state.selected_account = newly_selected
                else:
                    db_already_matches = (
                        (active_urn_from_db and newly_selected_urn == active_urn_from_db)
                        or (
                            not active_urn_from_db
                            and active_name_from_db
                            and (newly_selected.get("name") or "").strip().lower() == active_name_from_db
                        )
                        or (
                            active_is_personal
                            and newly_selected.get("type") == "profile"
                        )
                    )

                    if not db_already_matches:
                        # El usuario alteró explícitamente el select dropdown: sincronizar payload a la BD.
                        matched_db = _find_db_org(newly_selected)
                        if matched_db:
                            set_active_organization(user.id, matched_db["id"])
                            st.session_state["active_org"] = matched_db
                            if newly_selected_urn and not matched_db.get("org_urn"):
                                update_org_urn(matched_db["id"], newly_selected_urn)
                            st.session_state.selected_account = newly_selected
                            st.rerun()
                        else:
                            # Descarte temporal en sesión para evitar reruns innecesarios ante orfandad en BD.
                            st.session_state.selected_account = newly_selected
                    else:
                        # El state de BD concuerda con la UI; forzar actualización en sesión local para purgar leaks.
                        st.session_state.selected_account = newly_selected
                        # Parche reactivo: inyectar el URN omitido en el tuple persistente existente.
                        matched_db = _find_db_org(newly_selected)
                        if matched_db and newly_selected_urn and not matched_db.get("org_urn"):
                            update_org_urn(matched_db["id"], newly_selected_urn)
                        # Propagar alias de estado a la llave legacy.
                        if matched_db:
                            st.session_state["active_org"] = matched_db

        st.markdown('<div class="nav-title">Herramientas</div>', unsafe_allow_html=True)
        st.markdown(f"<a href='/Dashboard' target='_self' class='nav-link'><i class='bi bi-grid-fill'></i> Dashboard</a>", unsafe_allow_html=True)
        st.markdown(f"<a href='/Content_Generation' target='_self' class='nav-link'><i class='bi bi-magic'></i> Generar Contenido</a>", unsafe_allow_html=True)
        st.markdown(f"<a href='/Posts_Management' target='_self' class='nav-link'><i class='bi bi-archive-fill'></i> Gestionar Posts</a>", unsafe_allow_html=True)

        st.markdown('<div class="nav-title">Conexiones</div>', unsafe_allow_html=True)
        display_auth_status(sidebar=True)

        st.divider()
        if st.button("Cerrar Sesion", use_container_width=True):
            logout()
            st.switch_page("app.py")

        return st.session_state.get("selected_account")