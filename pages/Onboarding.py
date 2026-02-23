import streamlit as st
from src.linkedin_auth import ensure_auth
from src.components.ui_helpers import set_page_config
from src.services.supabase_client import get_supabase
from src.supabase_auth import get_user_profile
from src.core.logger import logger
from supabase import PostgrestAPIError

# --- Autenticación y Configuración ---
set_page_config("AIPost - Completa tu perfil")
ensure_auth(protect_route=True)

# Ocultar la barra lateral en esta página específica
st.set_option('client.showSidebarNavigation', False)
st.markdown("""
    <style>
        [data-testid="stSidebar"] {display: none;}
        [data-testid="stHeader"] {display: none;}
        .block-container {padding-top: 2rem !important;}
    </style>
""", unsafe_allow_html=True)

# --- Obtener usuario y perfil ---
user = st.session_state.get('user')
if not user:
    st.error("Sesión no válida.")
    st.stop()

# Cargamos el perfil (que Dashboard.py debió crear)
profile = get_user_profile(user.id)
if not profile:
    st.error("Error al cargar tu perfil. Contacta a soporte.")
    logger.error(f"Error en Onboarding: No se pudo cargar el perfil {user.id} que Dashboard debía crear.")
    st.stop()

logger.info(f"Iniciando Onboarding para el usuario {user}.")
sb_db = get_supabase()
welcome_name = profile.get('first_name', 'usuario')

# --- Lógica del Wizard ---

if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = 1

# Contenedor principal centrado
col1, col_main, col3 = st.columns([1, 1.5, 1])
with col_main:
    
    try:
        st.markdown("<div style='text-align: center'></div>", unsafe_allow_html=True)
        st.image("./src/assets/AIPOST.png", width=150)
    except Exception:
        pass # No fallar si no se encuentra el logo

    st.title(f"¡Bienvenido, {welcome_name}! 👋")
    st.caption("Solo necesitamos unos pocos detalles para calibrar tu asistente de IA.")
    
    total_steps = 3
    progress_value = (st.session_state.onboarding_step - 1) / (total_steps - 1)
    st.progress(progress_value)

    profile_data = st.session_state.get("profile_data", {})
    
    # --- PASO 1: Información de la Compañía ---
    if st.session_state.onboarding_step == 1:
        st.subheader("Paso 1: Sobre ti y tu empresa")
        with st.form("step_1_form"):
            company_name = st.text_input("Nombre de tu Empresa (opcional)", 
                                         value=profile_data.get('company_name', ''))
            role_in_company = st.text_input("Tu Rol (opcional)", 
                                            value=  profile_data.get('role_in_company', ''), 
                                            placeholder="Ej: Fundador, Marketer Digital")
            industry = st.text_input("¿A qué industria o sector te dedicas?", 
                                     value=profile_data.get('industry', ''), 
                                     placeholder="Ej: Software como Servicio (SaaS)")
            
            next_step = st.form_submit_button("Siguiente", use_container_width=True, type="primary")
            
            if next_step:
                if not industry:
                    st.warning("Por favor, indícanos tu industria.")
                else:
                    st.session_state.profile_data = {
                        "company_name": company_name,
                        "role_in_company": role_in_company,
                        "industry": industry
                    }
                    st.session_state.onboarding_step = 2
                    st.rerun()

    # --- PASO 2: Configuración del MAS (Audiencia y Tono) ---
    elif st.session_state.onboarding_step == 2:
        st.subheader("Paso 2: Define tu Voz y Audiencia")
        with st.form("step_2_form"):
            metas_disponibles = ["Generar leads", "Aumentar engagement", "Educar a la audiencia", "Construir marca", "Ahorrar tiempo"]
            user_goals = st.multiselect(
                "¿Cuáles son tus objetivos principales?",
                metas_disponibles,
                default=profile.get('user_goals', []),
                max_selections=2
            )
            
            col_back, col_next = st.columns(2)
            with col_back:
                if st.form_submit_button("Volver", use_container_width=True):
                    st.session_state.onboarding_step = 1
                    st.rerun()
            with col_next:
                if st.form_submit_button("Finalizar", use_container_width=True, type="primary"):
                    if not user_goals:
                        st.warning("Por favor, completa todos los campos para continuar.")
                    else:
                        st.session_state.profile_data.update({
                            "user_goals": user_goals,
                            "has_completed_onboarding": True
                        })
                        
                        # --- Guardar en Supabase ---
                        try:
                            # Usamos la política RLS "Allow individual update"
                            sb_db.table("user_profiles").update(st.session_state.profile_data).eq("id", user.id).execute()
                            
                            get_user_profile.clear() # Limpiar caché para Dashboard
                            
                            del st.session_state.onboarding_step
                            del st.session_state.profile_data
                            
                            st.session_state.onboarding_step = 3
                            st.rerun()
                            
                        except PostgrestAPIError as e:
                            logger.error(f"Error al ACTUALIZAR perfil {user.id}: {e}")
                            st.error(f"Error al guardar tu perfil: {e.message}")
                        except Exception as e:
                            logger.error(f"Error inesperado al ACTUALIZAR perfil {user.id}: {e}")
                            st.error(f"Ocurrió un error inesperado: {e}")

    # --- PASO 3: Finalización ---
    elif st.session_state.onboarding_step == 3:
        st.success("¡Tu perfil está completo! Tu asistente IA ha sido calibrado.")
        st.balloons()
        st.markdown("---")
        if st.button("Ir al Dashboard ✨", use_container_width=True, type="primary"):
            st.switch_page("pages/Dashboard.py")