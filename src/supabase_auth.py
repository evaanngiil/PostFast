import uuid as _uuid_mod

from supabase import PostgrestAPIError, create_client, Client
from typing import Optional

from src.core.logger import logger
from src.core.constants import SUPABASE_URL, SUPABASE_KEY
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

def cond_cache_data(ttl=300, show_spinner=False):
    """
    Decorador no-op, legado de la caché de Streamlit (frontend ya retirado).

    Se conserva la firma y el método `.clear()` para no tocar los numerosos
    call-sites que invalidaban aquella caché (`get_user_profile.clear()`).
    """
    def decorator(fn):
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        wrapper.clear = lambda: None
        return wrapper
    return decorator

# Caché estática del perfil para evitar queries repetidas durante el ciclo de vida del router.
@cond_cache_data(ttl=300, show_spinner=False)  # Cache 5 min
def get_user_profile(user_id: str) -> Optional[dict]:
    """
    Consulta public.user_profiles usando privilegios de administrador.

    :param user_id: UUID string correspondiente al usuario o ID de proveedor externo (LinkedIn).
    :returns: Diccionario del perfil, o None si no existe o falla.
    """
    is_uuid = True
    try:
        _uuid_mod.UUID(str(user_id))
    except (ValueError, AttributeError):
        is_uuid = False

    if not is_uuid:
        try:
            sb = get_supabase_admin()
            result = sb.table("user_profiles").select("*").eq("linkedin_provider_id", user_id).maybe_single().execute()
            if result and result.data:
                logger.info(f"get_user_profile: Resolving non-UUID ID {user_id!r} to UUID profile {result.data['id']}")
                return result.data
        except Exception as e:
            logger.error(f"Error buscando perfil por linkedin_provider_id={user_id}: {e}")
        logger.warning(f"get_user_profile recibio un ID no-UUID: {user_id!r} y no se pudo resolver. Retornando None.")
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
    is_uuid = True
    try:
        _uuid_mod.UUID(str(user_id))
    except (ValueError, AttributeError):
        is_uuid = False

    if not is_uuid:
        profile = get_user_profile(user_id)
        if profile:
            user_id = profile["id"]
        else:
            logger.warning(f"get_user_organizations recibio un ID no-UUID y no se pudo resolver a perfil: {user_id!r}")
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
        orgs = resp.data or []
        # Load logos from company_profiles for all organization URNs
        org_urns = [o["org_urn"] for o in orgs if o.get("org_urn")]
        logo_map = {}
        if org_urns:
            try:
                profiles_resp = (
                    sb.table("company_profiles")
                    .select("org_urn, raw_batch_data, company_profile")
                    .in_("org_urn", org_urns)
                    .execute()
                )
                for p in (profiles_resp.data or []):
                    logo = None
                    comp_prof = p.get("company_profile") or {}
                    raw_data = p.get("raw_batch_data") or {}
                    if comp_prof.get("logo_url"):
                        logo = comp_prof["logo_url"]
                    elif raw_data.get("logo_url"):
                        logo = raw_data["logo_url"]
                    elif "organization" in raw_data and raw_data["organization"]:
                        logo = raw_data["organization"].get("logo_url")
                    
                    if logo:
                        logo_map[p["org_urn"]] = logo
            except Exception as pe:
                logger.warning(f"Error loading company profiles logos: {pe}")

        profile = get_user_profile(user_id)
        if profile:
            first_name = profile.get("first_name") or ""
            last_name = profile.get("last_name") or ""
            avatar_url = profile.get("avatar_url")
            linkedin_id = profile.get("linkedin_provider_id")

            # El perfil PERSONAL representa la cuenta de LinkedIn: si está
            # vinculada, muestra el nombre y foto reales de LinkedIn (no los
            # datos de registro de la plataforma).
            li_first, li_last, li_picture = "", "", None
            if linkedin_id:
                try:
                    sess_resp = (
                        sb.table("user_sessions")
                        .select("user_info")
                        .eq("user_provider_id", user_id)
                        .eq("provider", "linkedin")
                        .order("last_accessed_at", desc=True)
                        .limit(1)
                        .execute()
                    )
                    li_info = (sess_resp.data[0].get("user_info") if sess_resp.data else {}) or {}
                    full_name = (li_info.get("name") or "").split(" ", 1)
                    li_first = li_info.get("given_name") or (full_name[0] if full_name else "")
                    li_last = li_info.get("family_name") or (full_name[1] if len(full_name) > 1 else "")
                    li_picture = li_info.get("picture")
                except Exception as li_err:
                    logger.warning(f"No se pudo leer la identidad de LinkedIn para {user_id}: {li_err}")

            for org in orgs:
                org["first_name"] = first_name
                org["last_name"] = last_name
                if org.get("is_personal"):
                    if li_first or li_last:
                        org["first_name"] = li_first or first_name
                        org["last_name"] = li_last or last_name
                    if li_picture or avatar_url:
                        org["logo_url"] = li_picture or avatar_url
                    if linkedin_id:
                        org["org_urn"] = f"urn:li:person:{linkedin_id}"
                else:
                    org["logo_url"] = logo_map.get(org.get("org_urn"))
        else:
            for org in orgs:
                org["logo_url"] = logo_map.get(org.get("org_urn"))
        return orgs
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

    :param user_id: UUID del dueño o ID de proveedor externo.
    :param org_data: Payload con la información del negocio (company_name, etc).
    :returns: Diccionario de la nueva organización insertada, o None si falla.
    """
    try:
        is_uuid = True
        try:
            _uuid_mod.UUID(str(user_id))
        except (ValueError, AttributeError):
            is_uuid = False

        if not is_uuid:
            profile = get_user_profile(user_id)
            if profile:
                user_id = profile["id"]
            else:
                logger.error(f"create_organization recibio un ID no-UUID y no se pudo resolver a perfil: {user_id!r}")
                return None

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
        is_uuid = True
        try:
            _uuid_mod.UUID(str(user_id))
        except (ValueError, AttributeError):
            is_uuid = False

        if not is_uuid:
            profile = get_user_profile(user_id)
            if profile:
                user_id = profile["id"]
            else:
                logger.error(f"set_active_organization recibio un ID no-UUID y no se pudo resolver: {user_id!r}")
                return False

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

    :param user_id: UUID del usuario o ID de proveedor externo.
    :param role: Puesto o rol introducido por el usuario.
    :param goals: Lista de metas de negocio a alcanzar.
    :returns: True si el flujo completo se aplicó, False si algo falló.
    """
    try:
        is_uuid = True
        try:
            _uuid_mod.UUID(str(user_id))
        except (ValueError, AttributeError):
            is_uuid = False

        if not is_uuid:
            profile = get_user_profile(user_id)
            if profile:
                user_id = profile["id"]
            else:
                logger.error(f"complete_onboarding_for_all_orgs recibio un ID no-UUID y no se pudo resolver a perfil: {user_id!r}")
                return False

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

        logger.info(f"Onboarding completado para user {user_id}, org {new_org['id']}")
        return True
    except Exception as e:
        logger.error(f"Error en complete_onboarding_for_all_orgs para {user_id}: {e}")
        return False


def update_profile_email(user_id: str, email: str) -> bool:
    """
    Sobrescribe la dirección email en BD si es válida y real.

    :param user_id: UUID en string o ID de proveedor externo.
    :param email: Nueva dirección a consolidar.
    :returns: True en caso de éxito, False si es placeholder o error.
    """
    if not email or '@linkedin.placeholder' in email:
        return False
    try:
        is_uuid = True
        try:
            _uuid_mod.UUID(str(user_id))
        except (ValueError, AttributeError):
            is_uuid = False

        if not is_uuid:
            profile = get_user_profile(user_id)
            if profile:
                user_id = profile["id"]
            else:
                logger.error(f"update_profile_email recibio un ID no-UUID y no se pudo resolver a perfil: {user_id!r}")
                return False

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

    is_uuid = True
    try:
        _uuid_mod.UUID(str(user_id))
    except (ValueError, AttributeError):
        is_uuid = False

    if not is_uuid:
        profile = get_user_profile(user_id)
        if profile:
            user_id = profile["id"]
        else:
            logger.warning(f"sync_linkedin_orgs_to_db: invalid user_id {user_id!r} and could not resolve to profile")
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
def _migrate_user_assets(sb, from_user_id: str, to_user_id: str) -> None:
    """
    Migra los activos de negocio de un perfil a otro al re-vincular LinkedIn.

    Cuando un provider_id de LinkedIn se desvincula del perfil A para vincularse
    al perfil B, las organizaciones (y sus vínculos de autorización) deben viajar
    con él: de lo contrario el usuario pierde el acceso a sus empresas, RAG,
    skills e histórico (todos cuelgan del org_urn).
    """
    if not from_user_id or not to_user_id or from_user_id == to_user_id:
        return
    try:
        # 1. Organizaciones no personales: transferencia directa de propiedad.
        moved = (
            sb.table("organizations")
            .update({"user_id": to_user_id})
            .eq("user_id", from_user_id)
            .eq("is_personal", False)
            .execute()
        )
        moved_rows = moved.data or []

        # 2. Organización personal: si el destino ya tiene una, fusionar el org_urn
        #    (si le falta) y eliminar la del origen para no duplicar.
        src_personal = (
            sb.table("organizations").select("*")
            .eq("user_id", from_user_id).eq("is_personal", True).execute()
        ).data or []
        dst_personal = (
            sb.table("organizations").select("*")
            .eq("user_id", to_user_id).eq("is_personal", True).execute()
        ).data or []

        for src in src_personal:
            if dst_personal:
                dst = dst_personal[0]
                if src.get("org_urn") and not dst.get("org_urn"):
                    sb.table("organizations").update({"org_urn": src["org_urn"]}).eq("id", dst["id"]).execute()
                # Repuntar active_org_id si alguien referencia la fila que se elimina
                sb.table("user_profiles").update({"active_org_id": dst["id"]}).eq("active_org_id", src["id"]).execute()
                sb.table("organizations").delete().eq("id", src["id"]).execute()
            else:
                sb.table("organizations").update({"user_id": to_user_id}).eq("id", src["id"]).execute()
                moved_rows.append(src)

        # 3. El perfil de origen no debe apuntar a una org que ya no posee.
        owned = (
            sb.table("organizations").select("id").eq("user_id", from_user_id).execute()
        ).data or []
        profile_row = (
            sb.table("user_profiles").select("active_org_id").eq("id", from_user_id).execute()
        ).data or []
        if profile_row and profile_row[0].get("active_org_id") and profile_row[0]["active_org_id"] not in {o["id"] for o in owned}:
            sb.table("user_profiles").update({"active_org_id": None}).eq("id", from_user_id).execute()

        # 4. Vínculos de autorización multi-tenant (user_organizations).
        all_urns = [r.get("org_urn") for r in moved_rows if r.get("org_urn")]
        for urn in all_urns:
            try:
                sb.table("user_organizations").upsert(
                    {"user_provider_id": to_user_id, "provider": "linkedin", "org_urn": urn},
                    on_conflict="user_provider_id,org_urn",
                ).execute()
            except Exception as link_err:
                logger.warning(f"[migrate_assets] No se pudo vincular {urn} a {to_user_id}: {link_err}")

        logger.info(
            "[migrate_assets] %d organizaciones migradas de %s a %s.",
            len(moved_rows), from_user_id, to_user_id,
        )
    except Exception as exc:
        logger.error(f"[migrate_assets] Error migrando activos de {from_user_id} a {to_user_id}: {exc}")


def get_or_create_linkedin_profile(provider_id: str, user_info: dict, existing_user_id: Optional[str] = None) -> Optional[dict]:
    """
    Resuelve heurísticamente la vinculación (o creación) del perfil para usuarios OAuth.

    :param provider_id: Identificador (no UUID) que proviene de LinkedIn.
    :param user_info: Diccionario devuelto por el identity layer.
    :param existing_user_id: UUID del usuario de plataforma actual, si ya está autenticado.
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

    if existing_user_id:
        try:
            # Check if this provider_id is already linked to another profile
            dup_resp = sb.table("user_profiles").select("id").eq("linkedin_provider_id", provider_id).execute()
            if dup_resp and dup_resp.data:
                for row in dup_resp.data:
                    if row["id"] != existing_user_id:
                        sb.table("user_profiles").update({"linkedin_provider_id": None}).eq("id", row["id"]).execute()
                        logger.info(f"Unlinked linkedin_provider_id {provider_id} from profile {row['id']} to link it to {existing_user_id}")
                        # CRÍTICO: las organizaciones (y sus vínculos de acceso)
                        # viajan con la cuenta de LinkedIn al nuevo perfil.
                        _migrate_user_assets(sb, row["id"], existing_user_id)
            
            resp = sb.table("user_profiles").select("*").eq("id", existing_user_id).maybe_single().execute()
            if resp and resp.data:
                profile = resp.data
                updates = {}
                # Update the linkedin_provider_id if needed
                if not profile.get("linkedin_provider_id") or profile.get("linkedin_provider_id") != provider_id:
                    updates["linkedin_provider_id"] = provider_id
                if user_info.get("picture") and profile.get("avatar_url") != user_info["picture"]:
                    updates["avatar_url"] = user_info["picture"]
                if updates:
                    sb.table("user_profiles").update(updates).eq("id", existing_user_id).execute()
                    profile.update(updates)
                    logger.info(f"Updated profile {existing_user_id} with linked LinkedIn provider {provider_id}")
                get_user_profile.clear()
                return profile
        except Exception as e:
            logger.warning(f"Failed to update existing_user_id {existing_user_id}: {e}")

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
                profile = resp.data
                if user_info.get("picture") and profile.get("avatar_url") != user_info["picture"]:
                    try:
                        sb.table("user_profiles").update({"avatar_url": user_info["picture"]}).eq("id", profile["id"]).execute()
                        profile["avatar_url"] = user_info["picture"]
                        logger.info(f"Updated avatar_url for profile {profile['id']}")
                    except Exception as ae:
                        logger.warning(f"Failed to update avatar_url: {ae}")
                return profile
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
                updates = {}
                if has_li_column and not profile.get("linkedin_provider_id"):
                    updates["linkedin_provider_id"] = provider_id
                if user_info.get("picture") and profile.get("avatar_url") != user_info["picture"]:
                    updates["avatar_url"] = user_info["picture"]
                
                if updates:
                    try:
                        sb.table("user_profiles").update(updates).eq("id", profile["id"]).execute()
                        profile.update(updates)
                        logger.info(f"Updated profile {profile['id']} with {updates}")
                    except Exception as e:
                        logger.warning(f"Failed to update profile: {e}")
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
                updates = {}
                if has_li_column and not profile.get("linkedin_provider_id"):
                    updates["linkedin_provider_id"] = provider_id
                if user_info.get("picture") and profile.get("avatar_url") != user_info["picture"]:
                    updates["avatar_url"] = user_info["picture"]
                if updates:
                    try:
                        sb.table("user_profiles").update(updates).eq("id", profile["id"]).execute()
                        profile.update(updates)
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
            "avatar_url": user_info.get("picture")
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
