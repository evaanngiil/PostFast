import streamlit as st
from src.linkedin_auth import ensure_auth
from src.components.ui_helpers import set_page_config
from src.supabase_auth import (
    get_user_profile,
    get_user_organizations,
    complete_onboarding_for_all_orgs,
)
from src.core.logger import logger

set_page_config("AIPost - Completa tu perfil")
ensure_auth(protect_route=True)

# Ocultar la navegación lateral en el flujo de onboarding.
st.set_option('client.showSidebarNavigation', False)
st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none;}
    [data-testid="stHeader"] {display: none;}
    .block-container {padding-top: 0 !important; max-width: 700px;}

    /* Cabecera hero con gradiente */
    .onboarding-hero {
        background: linear-gradient(135deg, #00A99D 0%, #007A70 100%);
        border-radius: 0 0 24px 24px;
        padding: 2.5rem 2rem 2rem 2rem;
        text-align: center;
        margin: -1rem -1rem 2rem -1rem;
    }
    .onboarding-hero h1 {
        color: white;
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }
    .onboarding-hero p {
        color: rgba(255,255,255,0.88);
        font-size: 1rem;
        margin-bottom: 0;
    }

    /* Contenedor del formulario */
    .form-card {
        background: white;
        border-radius: 16px;
        border: 1px solid #e8e8e8;
        padding: 2rem;
        box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    }
    .form-card h3 {
        color: #1a1a2e;
        font-size: 1.2rem;
        margin-bottom: 0.25rem;
    }
    .form-card .form-desc {
        color: #6c757d;
        font-size: 0.9rem;
        margin-bottom: 1.5rem;
    }

    /* Personalización de inputs */
    .stTextInput > div > div > input {
        border-radius: 10px !important;
        border: 1.5px solid #e0e0e0 !important;
        padding: 0.6rem 1rem !important;
        font-size: 0.95rem !important;
        transition: border-color 0.2s ease;
    }
    .stTextInput > div > div > input:focus {
        border-color: #00A99D !important;
        box-shadow: 0 0 0 3px rgba(0,169,157,0.12) !important;
    }
    .stMultiSelect > div {
        border-radius: 10px !important;
    }

    /* Botón de submit primario */
    .stFormSubmitButton > button {
        background: linear-gradient(135deg, #00A99D 0%, #007A70 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.7rem 1.5rem !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        transition: all 0.25s ease !important;
    }
    .stFormSubmitButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(0,169,157,0.3) !important;
    }

    /* Animación para mensaje de éxito */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(16px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .success-msg {
        animation: fadeInUp 0.5s ease;
        background: #d4edda;
        color: #155724;
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
        font-weight: 600;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

user = st.session_state.get('user')
if not user:
    st.error("Sesion no valida.")
    st.stop()

profile = get_user_profile(user.id)
welcome_name = (profile or {}).get('first_name') or getattr(user, 'name', None) or 'usuario'

logger.info(f"Iniciando Onboarding para usuario {user.id}")

# Redirigir al Dashboard si el usuario ya completó el onboarding.
# La tabla de organizaciones actúa como fuente de la verdad para este estado.
orgs = get_user_organizations(user.id)
completed_orgs = [o for o in orgs if o.get("has_completed_onboarding")]
if completed_orgs:
    logger.info(f"Usuario {user.id} ya tiene orgs completadas. Redirigiendo a Dashboard.")
    st.switch_page("pages/Dashboard.py")

try:
    st.markdown("<div style='text-align:center; padding-top:1.5rem;'>", unsafe_allow_html=True)
    st.image("./src/assets/AIPOST.png", width=120)
    st.markdown("</div>", unsafe_allow_html=True)
except Exception:
    pass

hero_title = f"Bienvenido, {welcome_name}!"
hero_subtitle = "Configura tu perfil para personalizar tu experiencia con IA"
submit_label = "Empezar a usar AIPost"

st.markdown(f"""
<div class="onboarding-hero">
    <h1>{hero_title}</h1>
    <p>{hero_subtitle}</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="form-card">
    <h3>Sobre ti</h3>
    <div class="form-desc">Solo necesitamos unos datos para calibrar tu asistente de contenido.</div>
</div>
""", unsafe_allow_html=True)

with st.form("onboarding_form", clear_on_submit=False):
    role = st.text_input(
        "Tu rol en la organizacion",
        placeholder="Ej: Fundador, Marketing Manager, Community Manager",
    )

    goals_options = [
        "Generar leads",
        "Aumentar engagement",
        "Educar a la audiencia",
        "Construir marca personal",
        "Ahorrar tiempo en contenido",
    ]
    goals = st.multiselect(
        "Objetivos principales con la plataforma (max. 3)",
        goals_options,
        max_selections=3,
    )

    submitted = st.form_submit_button(
        submit_label, use_container_width=True, type="primary"
    )

    if submitted:
        if not role:
            st.warning("Indica tu rol para continuar.")
        elif not goals:
            st.warning("Selecciona al menos un objetivo.")
        else:
            # Onboarding por defecto: crea la organización personal.
            # Si el token de LinkedIn está presente, sincroniza automáticamente todas las orgs gestionadas
            # aplicando el mismo rol y objetivos a cada una de ellas.
            ok = complete_onboarding_for_all_orgs(user.id, role, goals)

            if ok:
                logger.info(f"Onboarding completado para user {user.id}")
                st.session_state.pop("profile_data", None)
                st.session_state.pop("onboarding_just_completed", None)
                st.session_state.pop("onboarding_step", None)
                st.markdown(
                    '<div class="success-msg">Perfil configurado correctamente! Redirigiendo...</div>',
                    unsafe_allow_html=True,
                )
                st.switch_page("pages/Dashboard.py")
            else:
                st.error("Error al guardar. Intentalo de nuevo.")
