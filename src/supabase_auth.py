import uuid as _uuid_mod

import streamlit as st
from supabase import AuthApiError, PostgrestAPIError, create_client, Client
from typing import Optional
import requests

from src.core.logger import logger
from src.core.constants import FASTAPI_URL, BASE_URL, SUPABASE_URL, SUPABASE_KEY
from src.services.supabase_client import get_supabase_admin

# Cliente dedicado para aislar peticiones Auth y prevenir leaks del JWT en data queries.
_auth_client: Optional[Client] = None


def _get_auth_client() -> Client:
    """
    Inicializa o recupera un cliente Supabase exclusivo para capa de autenticación.

    :returns: Cliente Supabase aislado.
    """
    global _auth_client
    if _auth_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL o SUPABASE_KEY no configurados en el entorno")
        _auth_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase AUTH client created (isolated from data queries)")
    return _auth_client

# Caché estática del perfil para evitar queries repetidas durante el ciclo de vida del router.
@st.cache_data(ttl=300, show_spinner=False)  # Cache 5 min
def get_user_profile(user_id: str) -> Optional[dict]:
    """
    Consulta public.user_profiles usando privilegios de administrador.

    :param user_id: UUID string correspondiente al usuario auth.users.
    :returns: Diccionario del perfil, o None si no existe o falla.
    """
    # Validación preventiva: bloquear IDs de plataformas externas (ej. LinkedIn OAuth IDs cortos)
    # que provoquen excepciones de tipo 'invalid input syntax for type uuid' en PostgreSQL.
    try:
        _uuid_mod.UUID(str(user_id))
    except (ValueError, AttributeError):
        logger.warning(f"get_user_profile recibio un ID no-UUID: {user_id!r}. Retornando None.")
        return None

    try:
        sb = get_supabase_admin()
        result = sb.table("user_profiles").select("*").eq("id", user_id).single().execute()
        return result.data
    except PostgrestAPIError as e:
        if e.code == 'PGRST116':  # "Single row not found"
            logger.warning(f"No se encontro perfil para {user_id}. Es un usuario nuevo.")
            return None
        logger.error(f"Error de Postgrest al obtener perfil: {e}")
        st.error(f"Error al cargar el perfil: {e.message}")
        return None
    except Exception as e:
        logger.error(f"Error inesperado al obtener perfil: {e}")
        return None


# Controladores Multi-tenant (Organizaciones).
def get_user_organizations(user_id: str) -> list:
    """
    Recupera todas las empresas vinculadas al usuario, en orden de creación cronológico.

    :param user_id: Identificador UUID del dueño.
    :returns: Lista de diccionarios con las organizaciones de BD.
    """
    try:
        _uuid_mod.UUID(str(user_id))
    except (ValueError, AttributeError):
        logger.warning(f"get_user_organizations recibio un ID no-UUID: {user_id!r}")
        return []
    try:
        sb = get_supabase_admin()
        resp = (
            sb.table("organizations")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at")
            .execute()
        )
        return resp.data or []
    except Exception as e:
        logger.error(f"Error obteniendo organizaciones para {user_id}: {e}")
        return []


def get_active_organization(user_id: str) -> Optional[dict]:
    """
    Obtiene la organización activa del usuario (basado en el puntero de user_profiles).

    :param user_id: Identificador del usuario.
    :returns: Diccionario de la organización o None.
    """
    profile = get_user_profile(user_id)
    if not profile:
        return None
    active_org_id = profile.get("active_org_id")
    if not active_org_id:
        return None
    try:
        sb = get_supabase_admin()
        resp = (
            sb.table("organizations")
            .select("*")
            .eq("id", active_org_id)
            .maybe_single()
            .execute()
        )
        return resp.data if resp else None
    except Exception as e:
        logger.error(f"Error obteniendo org activa {active_org_id}: {e}")
        return None


def create_organization(user_id: str, org_data: dict) -> Optional[dict]:
    """
    Crea un nuevo tenant y lo configura inmediatamente como activo.

    :param user_id: UUID del dueño.
    :param org_data: Payload con la información del negocio (company_name, etc).
    :returns: Diccionario de la nueva organización insertada, o None si falla.
    """
    try:
        sb = get_supabase_admin()

        existing_profile = get_user_profile(user_id)
        if not existing_profile:

            _email = None
            _first_name = None
            _last_name = None
            try:
                auth_user_resp = sb.auth.admin.get_user_by_id(str(user_id))
                if auth_user_resp and hasattr(auth_user_resp, 'user') and auth_user_resp.user:
                    _email = getattr(auth_user_resp.user, 'email', None)
                    _meta = getattr(auth_user_resp.user, 'user_metadata', {}) or {}
                    _first_name = _meta.get('first_name')
                    _last_name = _meta.get('last_name')
            except Exception as e:
                logger.warning(f"No se pudo obtener auth user para {user_id}: {e}")

            profile_row = {
                "id": str(user_id),
                "email": _email,
                "first_name": _first_name,
                "last_name": _last_name,
                "has_completed_onboarding": False,
            }
            try:
                sb.table("user_profiles").insert(profile_row).execute()
                logger.info(f"Registro en user_profiles completado para el usuario nativo {user_id}")
                get_user_profile.clear()
            except Exception as insert_err:
                logger.warning(f"Insert user_profiles para {user_id} fallo: {insert_err}")
                existing_profile = get_user_profile(user_id)
                if not existing_profile:
                    logger.error(f"No se pudo crear user_profiles para {user_id}. Abortando.")
                    return None

        # Persistencia de la organización en BD.
        row = {
            "user_id": str(user_id),
            "company_name": org_data.get("company_name") or None,
            "role_in_company": org_data.get("role_in_company") or None,
            "industry": org_data.get("industry") or None,
            "user_goals": org_data.get("user_goals") or [],
            "has_completed_onboarding": org_data.get("has_completed_onboarding", False),
            "is_personal": not bool(org_data.get("company_name")),
        }
        resp = sb.table("organizations").insert(row).execute()
        new_org = resp.data[0] if resp.data else None
        if not new_org:
            logger.error(f"Insert en organizations no devolvio datos para user {user_id}")
            return None

        set_active_organization(user_id, new_org["id"])
        logger.info(f"Organizacion creada {new_org['id']} para user {user_id}")
        return new_org
    except Exception as e:
        logger.error(f"Error creando organizacion para {user_id}: {e}")
        return None


def set_active_organization(user_id: str, org_id: str) -> bool:
    """
    Modifica el puntero de organización activa en el perfil del usuario.

    :param user_id: Identificador del usuario.
    :param org_id: Identificador UUID de la nueva organización activa.
    :returns: True si la actualización es exitosa, de lo contrario False.
    """
    try:
        sb = get_supabase_admin()
        sb.table("user_profiles").update(
            {"active_org_id": str(org_id)}
        ).eq("id", str(user_id)).execute()

        get_user_profile.clear()
        logger.info(f"active_org_id actualizado a {org_id} para user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error actualizando active_org_id para {user_id}: {e}")
        return False


def complete_onboarding_for_all_orgs(user_id: str, role: str, goals: list) -> bool:
    """
    Finaliza el proceso de onboarding forzando los estados y flags requeridos.

    :param user_id: UUID del usuario.
    :param role: Puesto o rol introducido por el usuario.
    :param goals: Lista de metas de negocio a alcanzar.
    :returns: True si el flujo completo se aplicó, False si algo falló.
    """
    try:
        org_data = {
            "role_in_company": role,
            "user_goals": goals,
            "has_completed_onboarding": True,
        }
        new_org = create_organization(user_id, org_data)
        if not new_org:
            logger.error(f"complete_onboarding_for_all_orgs: create_organization fallo para {user_id}")
            return False

        # Propagación de parámetros del wizard hacia todos los tenants secundarios.
        # Resuelve estados incompletos de organizaciones cacheadas previamente.
        try:
            sb = get_supabase_admin()
            sb.table("organizations").update({
                "role_in_company": role,
                "user_goals": goals,
                "has_completed_onboarding": True,
            }).eq("user_id", str(user_id)).execute()
            logger.info(
                f"[onboarding] Updated ALL orgs for user {user_id} with "
                f"role='{role}', goals={goals}, has_completed_onboarding=True"
            )
        except Exception as e:
            logger.warning(f"complete_onboarding: failed to update existing orgs: {e}")

        # Sincronización del flag maestro en el perfil de usuario.
        try:
            sb = get_supabase_admin()
            sb.table("user_profiles").update(
                {"has_completed_onboarding": True}
            ).eq("id", str(user_id)).execute()
            get_user_profile.clear()
        except Exception as e:
            logger.warning(f"complete_onboarding: no se pudo actualizar user_profiles.has_completed_onboarding: {e}")

        # Ingesta reactiva de tenants desde memoria hacia DB post-onboarding.
        # Cubre el edge case donde el usuario autoriza LinkedIn antes de completar el profile.
        try:
            import streamlit as _st
            user_accounts = _st.session_state.get("user_accounts") or []
            linkedin_orgs = [
                a for a in user_accounts
                if isinstance(a, dict)
                and a.get("type") != "profile"
                and a.get("urn", "").startswith("urn:li:organization:")
            ]
            if linkedin_orgs:
                sync_linkedin_orgs_to_db(user_id, linkedin_orgs)
                logger.info(
                    f"[onboarding] Synced {len(linkedin_orgs)} LinkedIn orgs "
                    f"with onboarding data for user {user_id}"
                )
        except Exception as e:
            logger.warning(f"complete_onboarding: sync_linkedin_orgs_to_db failed: {e}")

        logger.info(f"Onboarding completado para user {user_id}, org {new_org['id']}")
        return True
    except Exception as e:
        logger.error(f"Error en complete_onboarding_for_all_orgs para {user_id}: {e}")
        return False


def update_profile_email(user_id: str, email: str) -> bool:
    """
    Sobrescribe la dirección email en BD si es válida y real.

    :param user_id: UUID en string.
    :param email: Nueva dirección a consolidar.
    :returns: True en caso de éxito, False si es placeholder o error.
    """
    if not email or '@linkedin.placeholder' in email:
        return False
    try:
        sb = get_supabase_admin()
        sb.table("user_profiles").update(
            {"email": email}
        ).eq("id", str(user_id)).execute()
        get_user_profile.clear()
        logger.info(f"Email actualizado a {email} para user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error actualizando email para {user_id}: {e}")
        return False

def update_org_urn(org_id: str, org_urn: str) -> bool:
    """
    Inyecta URNs en perfiles que entraron incompletos a la BD.

    :param org_id: UUID local de BD.
    :param org_urn: Cadena URN válida oficial.
    :returns: True si se asignó con éxito.
    """
    try:
        sb = get_supabase_admin()
        sb.table("organizations").update({"org_urn": org_urn}).eq("id", org_id).execute()
        return True
    except Exception as e:
        logger.error(f"update_org_urn failed for org {org_id}: {e}")
        return False


# Proceso idempotente de conciliación entre la API de LinkedIn y la persistencia local.
# Disparado periódicamente por load_user_accounts(). Instancia tenants clonando
# la metadata base ('onboarding template') del primer tenant válido.
def sync_linkedin_orgs_to_db(user_id: str, linkedin_orgs: list) -> None:
    """
    Concilia y mapea las páginas de LinkedIn extraídas con la base de datos relacional.

    :param user_id: Identificador del dueño.
    :param linkedin_orgs: Array de páginas recibidas vía REST API.
    :returns: None
    """
    if not linkedin_orgs:
        return

    try:
        _uuid_mod.UUID(str(user_id))
    except (ValueError, AttributeError):
        logger.warning(f"sync_linkedin_orgs_to_db: invalid user_id {user_id!r}")
        return

    try:
        sb = get_supabase_admin()
        existing_orgs = get_user_organizations(user_id)
        existing_urns = {o["org_urn"] for o in existing_orgs if o.get("org_urn")}

        template_org = next(
            (o for o in existing_orgs if o.get("has_completed_onboarding")),
            None,
        )

        for li_org in linkedin_orgs:
            urn = li_org.get("urn")
            name = li_org.get("name")
            if not urn or not urn.startswith("urn:li:organization:"):
                continue

            if urn in existing_urns:
                matching = [o for o in existing_orgs if o.get("org_urn") == urn]
                if matching and not matching[0].get("company_name") and name:
                    try:
                        sb.table("organizations").update(
                            {"company_name": name}
                        ).eq("id", matching[0]["id"]).execute()
                        logger.info(
                            f"[sync_orgs] Backfilled company_name='{name}' "
                            f"for org {matching[0]['id']}"
                        )
                    except Exception as e:
                        logger.warning(f"[sync_orgs] Failed to update company_name: {e}")
                continue

            # Instanciación de nuevo perfil corporativo.
            row = {
                "user_id": str(user_id),
                "org_urn": urn,
                "company_name": name,
                "role_in_company": (
                    template_org.get("role_in_company") if template_org else None
                ),
                "user_goals": (
                    template_org.get("user_goals") if template_org else []
                ),
                "has_completed_onboarding": template_org is not None,
                "is_personal": False,
            }
            try:
                resp = sb.table("organizations").insert(row).execute()
                new_org = resp.data[0] if resp.data else None
                logger.info(
                    f"[sync_orgs] Created org row for '{name}' ({urn}), "
                    f"onboarding={'copied' if template_org else 'pending'}"
                )

                if new_org and not any(
                    o.get("org_urn") for o in existing_orgs
                ):
                    set_active_organization(user_id, new_org["id"])
            except Exception as e:
                logger.warning(
                    f"[sync_orgs] Insert failed for {urn} (may already exist): {e}"
                )

    except Exception as e:
        logger.error(f"sync_linkedin_orgs_to_db failed for user {user_id}: {e}")
        
# Heurísticas de resolución de perfiles OAuth (LinkedIn).
#
# Debido a que el provider OAuth no inserta metadatos completos en auth.users,
# este handler orquesta el upsert local buscando por linkedin_provider_id
# exacto, ejecutando account linking vía email si coincide con un perfil existente,
# o forzando un shadow-user con UUID válido en su defecto.
def get_or_create_linkedin_profile(provider_id: str, user_info: dict) -> Optional[dict]:
    """
    Resuelve heurísticamente la vinculación (o creación) del perfil para usuarios OAuth.

    :param provider_id: Identificador (no UUID) que proviene de LinkedIn.
    :param user_info: Diccionario devuelto por el identity layer.
    :returns: El registro del perfil asociado al usuario actual, o None.
    """
    sb = get_supabase_admin()
    email = user_info.get('email')
    name = user_info.get('name', '')
    # LinkedIn devuelve 'name' completo; intentar separar first/last
    name_parts = name.split(' ', 1) if name else []
    first_name = user_info.get('given_name') or (name_parts[0] if name_parts else '')
    last_name = user_info.get('family_name') or (name_parts[1] if len(name_parts) > 1 else '')

    has_li_column = True

    try:
        # Búsqueda por linkedin_provider_id.
        try:
            resp = (
                sb.table("user_profiles")
                .select("*")
                .eq("linkedin_provider_id", provider_id)
                .maybe_single()
                .execute()
            )
            if resp and resp.data:
                logger.debug(f"Perfil encontrado por linkedin_provider_id={provider_id}")
                return resp.data
        except Exception as e:
            logger.warning(
                f"linkedin_provider_id lookup failed "
                f"(column may not exist yet): {e}"
            )
            has_li_column = False

        # Búsqueda por email para vincular cuenta existente.
        if email:
            resp = (
                sb.table("user_profiles")
                .select("*")
                .eq("email", email)
                .maybe_single()
                .execute()
            )
            if resp and resp.data:
                profile = resp.data
                if has_li_column:
                    try:
                        sb.table("user_profiles").update(
                            {"linkedin_provider_id": provider_id}
                        ).eq("id", profile["id"]).execute()
                        profile["linkedin_provider_id"] = provider_id
                        logger.info(
                            f"Perfil existente {profile['id']} vinculado a "
                            f"LinkedIn provider {provider_id}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"No se pudo vincular linkedin_provider_id "
                            f"al perfil existente: {e}"
                        )
                get_user_profile.clear()
                return profile

        # Creación de perfil nuevo.
        # user_profiles.id tiene FK a auth.users(id), asi que primero
        # necesitamos crear un "shadow user" en auth.users via Admin API.
        effective_email = email or f"{provider_id}@linkedin.placeholder"
        new_id = None

        try:
            admin_resp = sb.auth.admin.create_user({
                "email": effective_email,
                "email_confirm": True,
                "user_metadata": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "provider": "linkedin",
                    "linkedin_provider_id": provider_id,
                },
            })

            new_id = admin_resp.user.id
            logger.info(
                f"Shadow auth.users row creado para LinkedIn user "
                f"{provider_id} -> UUID {new_id}"
            )
        except Exception as admin_err:
            err_msg = str(admin_err).lower()
            if "already" in err_msg or "duplicate" in err_msg or "exists" in err_msg:
                logger.info(
                    f"auth.users ya tiene un usuario con email "
                    f"{effective_email}, buscando su UUID..."
                )
                # Buscar por effective_email Y por email real (si distinto)
                search_emails = {effective_email}

                if email and email != effective_email:
                    search_emails.add(email)
                try:
                    users_resp = sb.auth.admin.list_users()
                    existing = None

                    for u in (users_resp or []):
                        u_email = getattr(u, 'email', None)
                        u_meta = getattr(u, 'user_metadata', {}) or {}
                        if u_email in search_emails:
                            existing = u
                            break

                        if u_meta.get('linkedin_provider_id') == provider_id:
                            existing = u
                            break

                    if existing:
                        new_id = existing.id
                        logger.info(
                            f"Encontrado auth.users UUID existente {new_id} "
                            f"para LinkedIn provider {provider_id}"
                        )
                    else:
                        logger.error(
                            f"auth.users dice duplicado pero no encontramos "
                            f"match para {effective_email} / provider "
                            f"{provider_id}. No se puede crear perfil."
                        )
                        return None
                except Exception as list_err:
                    logger.error(
                        f"No se pudo buscar auth.users: {list_err}"
                    )
                    return None
            else:
                logger.error(
                    f"Error creando shadow auth user para LinkedIn: "
                    f"{admin_err}"
                )
                return None

        if new_id is None:
            return None

        try:
            existing_resp = (
                sb.table("user_profiles")
                .select("*")
                .eq("id", str(new_id))
                .maybe_single()
                .execute()
            )
            if existing_resp and existing_resp.data:
                profile = existing_resp.data

                # Vincular provider_id si falta
                if has_li_column and not profile.get("linkedin_provider_id"):
                    try:
                        sb.table("user_profiles").update(
                            {"linkedin_provider_id": provider_id}
                        ).eq("id", profile["id"]).execute()
                    except Exception:
                        pass
                logger.info(
                    f"user_profiles ya existia para UUID {new_id}, "
                    f"reutilizando."
                )
                get_user_profile.clear()
                return profile
        except Exception:
            pass

        profile_email = effective_email
        try:
            auth_user_resp = sb.auth.admin.get_user_by_id(str(new_id))
            if auth_user_resp and hasattr(auth_user_resp, 'user'):
                real_auth_email = getattr(auth_user_resp.user, 'email', None)
                if real_auth_email and '@linkedin.placeholder' not in real_auth_email:
                    profile_email = real_auth_email
        except Exception:
            pass

        new_profile = {
            "id": str(new_id),
            "email": profile_email,
            "first_name": first_name,
            "last_name": last_name,
            "has_completed_onboarding": False,
        }
        if has_li_column:
            new_profile["linkedin_provider_id"] = provider_id
        sb.table("user_profiles").insert(new_profile).execute()
        logger.info(
            f"Perfil creado para LinkedIn user {provider_id} -> UUID {new_id}"
        )
        get_user_profile.clear()
        return new_profile

    except Exception as e:
        logger.error(f"Error en get_or_create_linkedin_profile({provider_id}): {e}")
        return None


def get_current_user() -> Optional[object]:
    """
    Devuelve el usuario actual de Supabase o None si no hay sesión activa.

    Implementa una estrategia fast-path consultando el session_state cacheado 
    por ensure_auth(), recurriendo al SDK de Auth únicamente en escenarios de 
    login explícito de tipo email/password.

    :returns: Objeto usuario del payload JWT o None.
    """
    # Fast path: recuperación desde state cacheado (inyectado por ensure_auth).
    cached = st.session_state.get('user')
    if cached is not None:
        return cached

    # Slow path: invocación del SDK REST hacia el backend de Supabase Auth.
    try:
        auth_sb = _get_auth_client()
        session = auth_sb.auth.get_session()
        if session and session.user:
            # Guardar para futuros accesos en este script-run
            st.session_state['user'] = session.user
            return session.user
        return None
    except Exception as e:
        st.error(f"Error al obtener el usuario actual: {e}")
        return None


def signup(email: str, password: str, first_name: str, last_name: str) -> bool:
    """
    Registra un nuevo usuario nativo en Supabase.

    Nota: Esta acción no inyecta el token en memoria (no realiza login automático).
    
    :param email: Correo de contacto.
    :param password: Clave segura de acceso.
    :param first_name: Nombre del titular.
    :param last_name: Apellidos del titular.
    :returns: Booleano indicando el éxito del sign_up inicial.
    """
    try:
        auth_sb = _get_auth_client()
        options = {
            "data": {
                "first_name": first_name,
                "last_name": last_name
            },
            "email_redirect_to": BASE_URL
        }

        res = auth_sb.auth.sign_up({
            "email": email,
            "password": password,
            "options": options
        })

        if getattr(res, "user", None):
            user = res.user
            try:
                logger.info(f"Perfil inicial creado para {user.id}.")
            except PostgrestAPIError as e:
                logger.error(f"Error al crear perfil inicial (PostgrestAPIError): {e.message}")
                st.error(f"Error al crear tu perfil: {e.message}")
            except Exception as e:
                logger.error(f"Error inesperado al crear perfil inicial: {e}")
                st.error(f"Ocurrio un error inesperado: {e}")

            get_user_profile.clear()

            st.success("Registro exitoso! Revisa tu email para verificar tu cuenta.")
            return False
        return False
    except AuthApiError as e:
        logger.error(f"Error en el registro (AuthApiError): {e.message}")
        st.error(f"Error en el registro: {e.message}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado en signup: {e}")
        st.error(f"Ocurrio un error inesperado: {e}")
        return False


# Auxiliares de Estado Interno (Session Management).
def mark_aipost_logged_in(user: object) -> None:
    """
    Registra la autorización activa en memoria e inyecta el modelo de usuario.

    :param user: Estructura base del usuario identificado.
    """
    st.session_state['aipost_logged_in'] = True
    st.session_state['user'] = user


def mark_aipost_logged_out() -> None:
    """
    Destruye los tokens y referencias cacheadas del usuario para purgar la sesión de UI.
    """
    st.session_state['aipost_logged_in'] = False
    st.session_state['user'] = None
    # Limpiamos tambien el token unificado
    st.session_state['auth_token_for_url'] = None


def is_aipost_logged_in() -> bool:
    """
    Determina si el flag lógico de autenticación está presente en el contexto UI.

    :returns: True si el usuario ha sido marcado como autenticado.
    """
    return bool(st.session_state.get('aipost_logged_in'))


def get_aipost_user() -> Optional[object]:
    """
    Expone la estructura de usuario validada (MockUser o real) en el ciclo de runtime actual.

    :returns: Instancia del usuario en memoria o None.
    """
    return st.session_state.get('user')


def get_user_from_supabase_token(jwt: str):
    """
    Valida un JWT contra Supabase Auth usando el admin client.

    :param jwt: Token Bearer a validar.
    :returns: Objeto usuario de Supabase si el token está activo, o None si expiró/es falso.
    """
    try:
        auth_sb = _get_auth_client()
        user_response = auth_sb.auth.get_user(jwt)
        return user_response.user
    except Exception:
        return None


def login(email: str, password: str) -> bool:
    """
    Inicia sesión por email/password, obteniendo e inyectando un token unificado en el state local.

    :param email: Correo registrado.
    :param password: Clave validada.
    :returns: True si la sesión fue confirmada y guardada, False en error de credenciales.
    """
    try:
        auth_sb = _get_auth_client()
        response = auth_sb.auth.sign_in_with_password({"email": email, "password": password})
        if response.user and response.session:
            mark_aipost_logged_in(response.user)
            logger.info("Login de Supabase exitoso.")
            get_user_profile.clear()
            return True
        else:
            st.warning("Credenciales incorrectas. Por favor, intentalo de nuevo.")
            return False
    except AuthApiError as e:
        st.error(f"Error de autenticacion: {e.message}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado durante el login: {e}")
        st.error("Ocurrio un error de conexion. Intentalo de nuevo mas tarde.")
        return False


def logout() -> None:
    """
    Fuerza el logout integral: Purga cookies del iframe, la sesión Supabase y memoria.
    """
    # Extracción en runtime del CookieController para prevenir importaciones circulares prematuras.
    try:
        from src.linkedin_auth import get_cookie_controller
        cookies = get_cookie_controller()
        cookies.remove("linkedin_access_token")
    except Exception as e:
        logger.warning(f"No se pudo eliminar la cookie de LinkedIn: {e}")

    # 2. Cerrar sesion en Supabase
    try:
        auth_sb = _get_auth_client()
        auth_sb.auth.sign_out()
    except Exception as e:
        logger.error(f"Error en Supabase sign_out: {e}")

    get_user_profile.clear()

    # 3. Limpiar todo el estado de sesion para asegurar un inicio limpio
    keys_to_clear = list(st.session_state.keys())
    for key in keys_to_clear:
        del st.session_state[key]

    # 4. Limpiar query params
    st.query_params.clear()

    # 5. Llamar al logout del backend (best-effort)
    try:
        requests.get(f"{FASTAPI_URL}/auth/logout", timeout=5)
        logger.info("Llamada al endpoint de logout del backend realizada.")
    except Exception as e:
        logger.warning(f"No se pudo llamar al logout del backend: {e}")

    mark_aipost_logged_out()


def revalidate_aipost_session() -> None:
    """
    Comprueba si hay una sesion de Supabase activa y actualiza st.session_state.
    Se usa como una sincronizacion secundaria, la fuente de verdad principal es el token.

    PERF: Si la sesion ya fue verificada por ensure_auth() (session_verified=True),
    marcamos directamente como revalidado sin llamar a Supabase SDK.
    Esto elimina una llamada de red redundante a get_session() en cada pagina.
    """
    if st.session_state.get('aipost_session_revalidated'):
        return

    # Fast path: ensure_auth ya verifico la sesion completa
    if st.session_state.get('session_verified') and is_aipost_logged_in():
        st.session_state['aipost_session_revalidated'] = True
        return

    try:
        auth_sb = _get_auth_client()
        session = auth_sb.auth.get_session()
        if session and session.user and not is_aipost_logged_in():
            # Si hay sesion de Supabase pero no de AIPost, la marcamos.
            # Esto puede pasar en la primera carga si hay una cookie de Supabase valida.
            mark_aipost_logged_in(session.user)
            logger.debug("Revalidacion de Supabase encontro una sesion activa.")
        elif not session or not session.user:
            _has_li_tok = bool(
                st.session_state.get('auth_token_for_url')
                or st.session_state.get('li_token_data')
            )
            if not _has_li_tok:
                mark_aipost_logged_out()
            else:
                logger.debug(
                    "revalidate: no Supabase SDK session but LinkedIn "
                    "token present -- deferring to token restore"
                )

    except Exception as e:
        logger.warning(f"Error al verificar la sesion de Supabase: {e}")
        _has_li_tok = bool(
            st.session_state.get('auth_token_for_url')
            or st.session_state.get('li_token_data')
        )
        if not _has_li_tok:
            mark_aipost_logged_out()

    st.session_state['aipost_session_revalidated'] = True
