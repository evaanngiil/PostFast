"""
Autorización multi-tenant de AIPost.

Fuente de verdad de pertenencia usuario <-> organización, en orden:

1. Tabla `organizations` (user_id UUID <-> org_urn): la puebla el onboarding
   cuando el usuario conecta su cuenta de LinkedIn. Es la fuente primaria.
2. Tabla `user_organizations` (registro de "primer uso legítimo"): se rellena
   en los endpoints donde el usuario opera la organización con su propio token
   OAuth (generate_post, schedule_post, trigger_batch). Cubre sesiones cuyo
   identificador no está en `organizations` (p. ej. modo demo).

Modo de aplicación configurable con AIPOST_ENFORCE_ORG_ACCESS:
- "true" (por defecto): deniega con 403 si no hay vínculo.
- "false": modo auditoría — solo registra el aviso en logs y permite el acceso
  (útil como interruptor de emergencia sin revertir código).
"""
import os
import uuid as _uuid

from fastapi import HTTPException

from src.core.logger import logger
from src.core.constants import DEMO_MODE
from src.services.supabase_client import get_supabase_admin

TABLE = "user_organizations"

ENFORCE = os.getenv("AIPOST_ENFORCE_ORG_ACCESS", "true").lower() in ("1", "true", "yes")


def _session_user_id(session_data: dict) -> str | None:
    """Extrae el identificador estable del usuario desde la sesión validada."""
    return session_data.get("user_provider_id") or (session_data.get("user_info") or {}).get("id")


def _resolve_user_uuid(user_id: str) -> str | None:
    """
    Devuelve el UUID interno del usuario (clave de `organizations.user_id`).

    Las sesiones pueden llevar directamente el UUID de Supabase o un id del
    proveedor (LinkedIn); en el segundo caso se resuelve vía el perfil.
    """
    try:
        _uuid.UUID(str(user_id))
        return str(user_id)
    except (ValueError, AttributeError, TypeError):
        pass
    try:
        from src.supabase_auth import get_user_profile
        profile = get_user_profile(user_id)
        return profile["id"] if profile else None
    except Exception as exc:
        logger.warning("[org_access] No se pudo resolver UUID para %s: %s", user_id, exc)
        return None


def _own_personal_urns(user_id: str, user_uuid: str | None) -> set[str]:
    """
    Pseudo-URNs personales que pertenecen intrínsecamente al usuario.

    Para cuentas personales sin URN de LinkedIn (organizations.org_urn = null),
    el frontend construye 'urn:li:person:<id-de-usuario>': ese identificador es
    del propio usuario por definición y no requiere fila de vinculación.
    """
    urns = {f"urn:li:person:{user_id}"}
    if user_uuid:
        urns.add(f"urn:li:person:{user_uuid}")
        
    try:
        from src.supabase_auth import get_user_profile
        profile = get_user_profile(user_id)
        if profile and profile.get("linkedin_provider_id"):
            urns.add(f"urn:li:person:{profile['linkedin_provider_id']}")
    except Exception as exc:
        logger.warning("[org_access] No se pudo obtener linkedin_provider_id para %s: %s", user_id, exc)
        
    return urns


def get_user_org_urns(session_data: dict) -> list[str]:
    """
    Devuelve todas las organizaciones vinculadas al usuario de la sesión,
    combinando la tabla `organizations` (onboarding), `user_organizations`
    y sus pseudo-URNs personales.
    """
    user_id = _session_user_id(session_data)
    if not user_id:
        return []

    urns: set[str] = set()
    supabase = get_supabase_admin()

    # 0. Pseudo-URNs personales del propio usuario (no requieren vinculación).
    user_uuid = _resolve_user_uuid(user_id)
    urns.update(_own_personal_urns(user_id, user_uuid))

    # 1. Fuente primaria: tabla organizations (onboarding).
    if user_uuid:
        try:
            res = (
                supabase.table("organizations")
                .select("org_urn")
                .eq("user_id", user_uuid)
                .execute()
            )
            urns.update(row["org_urn"] for row in (res.data or []) if row.get("org_urn"))
        except Exception as exc:
            logger.error("[org_access] Error consultando organizations para %s: %s", user_uuid, exc)

    # 2. Fuente secundaria: registros de primer uso legítimo.
    try:
        res = (
            supabase.table(TABLE)
            .select("org_urn")
            .eq("user_provider_id", str(user_id))
            .execute()
        )
        urns.update(row["org_urn"] for row in (res.data or []) if row.get("org_urn"))
    except Exception as exc:
        logger.warning("[org_access] Error consultando %s para %s: %s", TABLE, user_id, exc)

    return sorted(urns)


def register_org_access(session_data: dict, org_urn: str) -> None:
    """
    Registra (upsert idempotente) que el usuario de la sesión opera esta organización.

    :param session_data: Sesión validada por la dependencia de auth.
    :param org_urn: URN de la organización (o account_id de la plataforma).
    """
    user_id = _session_user_id(session_data)
    if not user_id or not org_urn:
        return
    try:
        supabase = get_supabase_admin()
        supabase.table(TABLE).upsert(
            {
                "user_provider_id": str(user_id),
                "provider": session_data.get("provider") or "linkedin",
                "org_urn": org_urn,
            },
            on_conflict="user_provider_id,org_urn",
        ).execute()
    except Exception as exc:
        # No bloquea el flujo funcional: el assert posterior decidirá.
        logger.warning("[org_access] No se pudo registrar acceso %s -> %s: %s", user_id, org_urn, exc)


def assert_org_access(session_data: dict, org_urn: str) -> None:
    """
    Verifica que el usuario de la sesión tiene acceso a la organización.

    :param session_data: Sesión validada por la dependencia de auth.
    :param org_urn: URN/account_id del recurso solicitado.
    :raises HTTPException: 403 si el usuario no está vinculado a la organización
                           (solo con AIPOST_ENFORCE_ORG_ACCESS=true).
    """
    user_id = _session_user_id(session_data)
    if not user_id or not org_urn:
        if ENFORCE:
            raise HTTPException(status_code=403, detail="Acceso a la organización no autorizado.")
        return

    # Modo demo del TFG: el usuario mock no pasa por onboarding real.
    if DEMO_MODE and str(user_id).startswith("mock_"):
        return

    # Fast-path: el pseudo-URN personal del propio usuario siempre es suyo
    # (evita roundtrip a BD y cubre cuentas personales sin URN de LinkedIn).
    if org_urn in _own_personal_urns(str(user_id), _resolve_user_uuid(user_id)):
        return

    try:
        allowed = get_user_org_urns(session_data)
    except Exception as exc:
        # Transitorio: ante fallo de infraestructura no se bloquea la aplicación,
        # pero se deja constancia crítica en logs.
        logger.critical("[org_access] Verificación de tenant NO disponible: %s. Permitiendo temporalmente.", exc)
        return

    if org_urn in allowed:
        return

    if not ENFORCE:
        logger.warning(
            "[org_access] AUDITORÍA (enforcement OFF): usuario %s accedió a %s sin vínculo registrado.",
            user_id, org_urn,
        )
        return

    logger.warning(
        "[org_access] DENEGADO: usuario %s intentó acceder a %s (vinculadas: %s)",
        user_id, org_urn, allowed or "ninguna",
    )
    raise HTTPException(status_code=403, detail="No tienes acceso a esta organización.")
