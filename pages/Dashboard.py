import streamlit as st
from supabase import AuthApiError, PostgrestAPIError

from src.components.ui_helpers import set_page_config

set_page_config("AIPost - Dashboard")


from src.linkedin_auth import ensure_auth
from src.components.sidebar import render_sidebar
from src.supabase_auth import get_user_profile, get_user_organizations, get_active_organization, set_active_organization, mark_aipost_logged_out
from src.core.logger import logger
from src.core.constants import FASTAPI_URL
from src.live_insights import (
    _get_access_token,
    get_live_follower_count,
    get_live_engagement_insights,
    get_live_posts_count,
)
import requests


def _render_org_card(org: dict) -> None:
    """
    Renderiza una tarjeta de organización con cabecera y métricas integradas.

    :param org: Diccionario que contiene los datos de la organización.
    :returns: None
    """
    org_name = org.get("company_name") or "Perfil Personal"
    is_personal = org.get("is_personal", False)
    if is_personal:
        org_name = org.get("company_name") or "Perfil Personal"

    badge_class = "badge-personal" if is_personal else "badge-company"
    badge_text = "Personal" if is_personal else "Organizacion"

    # Recuperar estadísticas
    followers = None
    total_impressions_org = None
    avg_engagement_rate = None
    total_likes_org = None
    total_comments_org = None
    post_count = None

    org_urn = org.get("org_urn")
    if org_urn and not is_personal:
        _token = _get_access_token()
        if _token:
            try:
                followers = get_live_follower_count(org_urn, _token)
            except Exception:
                pass
            try:
                ei = get_live_engagement_insights(org_urn, _token)
                if ei:
                    total_impressions_org = ei.get("total_impressions")
                    avg_engagement_rate = ei.get("avg_engagement_rate")
                    total_likes_org = ei.get("total_likes")
                    total_comments_org = ei.get("total_comments")
            except Exception:
                pass
            try:
                post_count = get_live_posts_count(org_urn, _token)
            except Exception:
                pass

    # Encabezado de la tarjeta (HTML para gradiente)
    st.markdown(f"""
    <div class="org-card">
        <div class="org-card-header">
            <h4>{org_name}</h4>
            <span class="org-badge {badge_class}">{badge_text}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Funciones de formateo auxiliar
    def _fmt_int(val):       
        if val is not None and val > 0:
            return f"{val:,}"
        return "--"

    def _fmt_rate(val):
        if val is not None and val > 0:
            return f"{val:.2f}%"
        return "--"

    if org_urn and not is_personal:
        metric_data = [
            ("Seguidores", _fmt_int(followers)),
            ("Posts", str(post_count) if post_count is not None else "0"),
            ("Impresiones", _fmt_int(total_impressions_org)),
            ("Eng. Rate", _fmt_rate(avg_engagement_rate)),
            ("Reacciones", _fmt_int(total_likes_org)),
            ("Comentarios", _fmt_int(total_comments_org)),
        ]

        mcols = st.columns(len(metric_data))
        for i, (label, value) in enumerate(metric_data):
            mcols[i].metric(label, value)
    else:
        st.caption(" ")


ensure_auth(protect_route=True)

user = st.session_state.get('user')

if not user:
    logger.error("Usuario no encontrado en session_state, redirigiendo a login.")
    mark_aipost_logged_out()
    st.switch_page("app.py")

profile = get_user_profile(user.id)

# Redirigir automáticamente al flujo de onboarding si no existen organizaciones configuradas.
# Este paso es obligatorio para asegurar que el modelo de IA tenga contexto del rol y objetivos.
orgs = get_user_organizations(user.id)
completed_orgs = [o for o in orgs if o.get("has_completed_onboarding")]

if profile is None:
    logger.info(f"Perfil no encontrado para {user.id}. Redirigiendo a Onboarding.")
    st.switch_page("pages/Onboarding.py")

if not completed_orgs:
    logger.info(f"Usuario {user.id} sin organizaciones configuradas. Redirigiendo a Onboarding.")
    st.switch_page("pages/Onboarding.py")

li_connected = st.session_state.get("li_connected", False)

active_org = get_active_organization(user.id)
if not active_org and completed_orgs:
    active_org = completed_orgs[0]
if active_org:
    st.session_state["active_org"] = active_org

logger.debug(f"Usuario {user.id} verificado. Org activa: {(active_org or {}).get('company_name', 'Personal')}. Mostrando Dashboard.")

selected_account = render_sidebar(user)

st.markdown("""
<style>
    .clickable-card {
        display: block;
        text-decoration: none !important;
        height: 100%;
    }


    /* Tarjeta CTA de LinkedIn */
    .li-cta-card {
        background: linear-gradient(135deg, #0077B5 0%, #005885 100%);
        padding: 2rem;
        border-radius: 14px;
        color: white;
        margin: 1.5rem 0;
        box-shadow: 0 4px 16px rgba(0, 119, 181, 0.25);
    }
    .li-cta-card h3 {
        color: white;
        margin: 0 0 0.5rem 0;
        font-size: 1.4rem;
    }
    .li-cta-card p {
        color: rgba(255,255,255,0.9);
        font-size: 1rem;
        margin: 0 0 1.25rem 0;
        line-height: 1.5;
    }
    .li-cta-card ul {
        color: rgba(255,255,255,0.9);
        margin: 0 0 1.25rem 0;
        padding-left: 1.25rem;
    }
    .li-cta-card li {
        margin-bottom: 0.3rem;
    }
    .li-cta-btn {
        display: inline-block;
        background-color: white;
        color: #0077B5;
        padding: 0.6rem 1.5rem;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 700;
        font-size: 1rem;
        transition: 0.2s ease;
    }
    .li-cta-btn:hover {
        background-color: #f0f0f0;
        text-decoration: none;
        color: #005885;
    }

    /* Estado vacío */
    .empty-state {
        text-align: center;
        padding: 3rem 1rem;
        color: #495f5e;
    }
    .empty-state h3 {
        color: #473E40;
        margin-bottom: 0.5rem;
    }

        /* General */
    .dashboard-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0;
    }
    .dashboard-email {
        font-size: 0.95rem;
        color: #6c757d;
        margin-bottom: 0.15rem;
    }
    .dashboard-subtitle {
        font-size: 1.05rem;
        color: #495f5e;
        margin-bottom: 1.5rem;
    }

    /* Píldora de estado de onboarding */
    .onboarding-pill {
        display: inline-block;
        padding: 0.3rem 1rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 1.5rem;
    }
    .pill-completed {
        background: #d4edda;
        color: #155724;
    }
    .pill-pending {
        background: #fff3cd;
        color: #856404;
    }

    /* Métricas agregadas */
    .metrics-banner {
        background: linear-gradient(135deg, #00A99D 0%, #007A70 100%);
        border-radius: 14px;
        padding: 1.5rem 2rem;
        margin-bottom: 2rem;
        color: white;
    }
    .metrics-banner h4 {
        color: white;
        margin: 0 0 1rem 0;
        font-size: 1rem;
        font-weight: 600;
        opacity: 0.9;
    }
    .metric-item {
        text-align: center;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: white;
        line-height: 1.2;
    }
    .metric-label {
        font-size: 0.8rem;
        color: rgba(255,255,255,0.85);
        margin-top: 0.2rem;
    }

    /* Tarjetas de organización */
    .org-card {
        background: white;
        border-radius: 14px;
        border: 1px solid #e8e8e8;
        overflow: hidden;
        transition: all 0.25s ease;
        margin-bottom: 1rem;
    }
    .org-card:hover {
        border-color: #00A99D;
        box-shadow: 0 6px 20px rgba(0,169,157,0.12);
        transform: translateY(-2px);
    }
    .org-card-header {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1rem 1.25rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #e8e8e8;
    }
    .org-card-header h4 {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 600;
        color: #1a1a2e;
    }
    .org-badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-personal {
        background: #e0f7f5;
        color: #007A70;
    }
    .badge-company {
        background: #e8eaf6;
        color: #3949ab;
    }
    .org-card-body {
        padding: 1.25rem;
    }

    /* Tarjetas de acción */
    .clickable-card {
        display: block;
        text-decoration: none !important;
        height: 100%;
    }
    .action-card {
        background: white;
        padding: 1.5rem;
        border-radius: 14px;
        border: 1px solid #e8e8e8;
        transition: all 0.25s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 180px;
    }
    .action-card:hover {
        border-color: #00A99D;
        box-shadow: 0 6px 20px rgba(0,169,157,0.12);
        transform: translateY(-2px);
    }
    .action-card h3 {
        color: #1a1a2e;
        margin-top: 0;
        margin-bottom: 0.5rem;
        font-size: 1.2rem;
    }
    .action-card p {
        color: #6c757d;
        margin-bottom: 0;
        font-size: 0.95rem;
        flex-grow: 1;
    }
    .action-card .cta {
        margin-top: 1rem;
        font-weight: 600;
        color: #00A99D;
        font-size: 0.9rem;
    }

    /* Caja de conexión */
    .connection-box {
        background: #f8f9fa;
        border-left: 4px solid #00A99D;
        padding: 1rem 1.25rem;
        border-radius: 8px;
        color: #495f5e;
        margin-top: 1.5rem;
        font-size: 0.95rem;
</style>
""", unsafe_allow_html=True)

content_gen_url = "/Content_Generation"
posts_mgmt_url = "/Posts_Management"

welcome_name = profile.get('first_name', user.email) if profile else getattr(user, 'name', None) or getattr(user, 'email', 'Usuario')

st.markdown(f"<div class='dashboard-header'>¡Bienvenido de nuevo, {welcome_name}!</div>", unsafe_allow_html=True)
st.markdown("<div class='dashboard-subtitle'>Accede rapidamente a tus herramientas para crear, gestionar y analizar contenido.</div>", unsafe_allow_html=True)


# Vista de cuenta sin vinculación a LinkedIn.
if not li_connected:

    li_login_url = f"{FASTAPI_URL}/auth/login/linkedin"
    st.markdown(f"""
    <div class="li-cta-card">
        <h3>Conecta tu cuenta de LinkedIn</h3>
        <p>Desbloquea todo el potencial de AIPost conectando tu perfil profesional:</p>
        <ul>
            <li>Analiza el rendimiento de tus publicaciones con metricas reales</li>
            <li>Genera contenido optimizado para tu audiencia</li>
            <li>Programa y publica directamente desde la plataforma</li>
            <li>Accede a insights de engagement, impresiones y seguidores</li>
        </ul>
        <a href="{li_login_url}" class="li-cta-btn">Conectar LinkedIn</a>
    </div>
    """, unsafe_allow_html=True)

    # Tarjetas de acciones principales.
    st.subheader("Acciones principales")

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown(f"""
        <a href="{content_gen_url}" target="_self" class="clickable-card">
            <div class="action-card">
                <div>
                    <h3>Generacion de Contenido</h3>
                    <p>Crea publicaciones optimizadas y originales utilizando inteligencia artificial. Define tu estilo y deja que la magia suceda.</p>
                </div>
                <div class="cta">Ir &rarr;</div>
            </div>
        </a>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <a href="{posts_mgmt_url}" target="_self" class="clickable-card">
            <div class="action-card">
                <div>
                    <h3>Gestion de Posts</h3>
                    <p>Revisa, organiza y programa tus publicaciones. Visualiza tu calendario editorial y manten el control de tu contenido.</p>
                </div>
                <div class="cta">Ir &rarr;</div>
            </div>
        </a>
        """, unsafe_allow_html=True)

    st.subheader("Tus Organizaciones")

    if not orgs:
        st.markdown("""
        <div class="empty-state">
            <h3>No hay organizaciones</h3>
            <p>Conecta LinkedIn para importar automaticamente tus organizaciones.</p>
        </div>
        """, unsafe_allow_html=True)


# Vista completa con integración a LinkedIn (métricas activas).
else:

    st.subheader("Acciones principales")

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown(f"""
        <a href="{content_gen_url}" target="_self" class="clickable-card">
            <div class="action-card">
                <div>
                    <h3>Generacion de Contenido</h3>
                    <p>Crea publicaciones optimizadas y originales utilizando inteligencia artificial. Define tu estilo y deja que la magia suceda.</p>
                </div>
                <div class="cta">Ir &rarr;</div>
            </div>
        </a>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <a href="{posts_mgmt_url}" target="_self" class="clickable-card">
            <div class="action-card">
                <div>
                    <h3>Gestion de Posts</h3>
                    <p>Revisa, organiza y programa tus publicaciones. Visualiza tu calendario editorial y manten el control de tu contenido.</p>
                </div>
                <div class="cta">Ir &rarr;</div>
            </div>
        </a>
        """, unsafe_allow_html=True)

    st.subheader("Metricas Generales")

    # Agregación de KPIs para todas las organizaciones vinculadas al usuario.
    total_followers = 0
    total_impressions = 0
    total_likes = 0
    total_comments = 0
    total_posts = 0
    weighted_eng_sum = 0
    weighted_eng_imp = 0

    _token = _get_access_token()
    for org in orgs:
        org_urn = org.get("org_urn")
        if org_urn and _token:
            try:
                fc = get_live_follower_count(org_urn, _token)
                if fc:
                    total_followers += fc
            except Exception:
                pass
            try:
                ei = get_live_engagement_insights(org_urn, _token)
                if ei:
                    total_impressions += ei.get("total_impressions") or 0
                    total_likes += ei.get("total_likes") or 0
                    total_comments += ei.get("total_comments") or 0
                    imp = ei.get("total_impressions") or 0
                    eng = ei.get("total_engagements") or 0
                    weighted_eng_sum += eng
                    weighted_eng_imp += imp
            except Exception:
                pass
            try:
                total_posts += get_live_posts_count(org_urn, _token)
            except Exception:
                pass

    avg_eng_rate = round(weighted_eng_sum / weighted_eng_imp * 100, 2) if weighted_eng_imp > 0 else 0.0

    st.markdown(f"""
    <div class="metrics-banner">
        <div style="display:flex; gap:2rem; flex-wrap:wrap;">
            <div class="metric-item">
                <div class="metric-value">{total_followers:,}</div>
                <div class="metric-label">Seguidores totales</div>
            </div>
            <div class="metric-item">
                <div class="metric-value">{total_impressions:,}</div>
                <div class="metric-label">Impresiones</div>
            </div>
            <div class="metric-item">
                <div class="metric-value">{avg_eng_rate}%</div>
                <div class="metric-label">Engagement Rate</div>
            </div>
            <div class="metric-item">
                <div class="metric-value">{total_likes:,}</div>
                <div class="metric-label">Reacciones</div>
            </div>
            <div class="metric-item">
                <div class="metric-value">{total_comments:,}</div>
                <div class="metric-label">Comentarios</div>
            </div>
            <div class="metric-item">
                <div class="metric-value">{total_posts}</div>
                <div class="metric-label">Total Posts</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


    st.subheader("Tus Organizaciones")

    for org in orgs:
        _render_org_card(org=org)

    logger.warning(f"Orgs: {orgs}")
        
    if not orgs:
        st.info("No tienes organizaciones registradas. Conecta LinkedIn para descubrir tus organizaciones.")


st.markdown("<div style='margin:2rem 0 0.5rem 0;'></div>", unsafe_allow_html=True)
st.subheader("Estado de Conexion")

if st.session_state.get("li_connected"):
    user_info = st.session_state.get("li_user_info", {})
    li_name = user_info.get("name", "Usuario de LinkedIn")
    st.markdown(f"""
    <div class="connection-box">
        Conectado a LinkedIn como <strong>{li_name}</strong>.
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="connection-box" style="border-left-color: #E8B200;">
        No has conectado tu cuenta de LinkedIn. Ve a la barra lateral para autorizar el acceso.
    </div>
    """, unsafe_allow_html=True)