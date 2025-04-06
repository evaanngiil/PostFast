# social_apis.py
import requests
from src.core.logger import logger
from src.core.constants import FB_GRAPH_URL, LI_API_URL
import time
from urllib.parse import quote # Necesario para URNs

# Helper fetch_with_retry_log
def fetch_with_retry_log(api_call_func, func_name, max_retries=3, delay=5):
    for attempt in range(max_retries):
        try:
            response = api_call_func()
            response.raise_for_status()
            logger.debug(f"API call {func_name} successful (attempt {attempt + 1}). Status: {response.status_code}")
            try:
                # Devolver JSON si es posible, si no, texto
                return response.json()
            except requests.exceptions.JSONDecodeError:
                logger.warning(f"API call {func_name} returned non-JSON response: {response.text[:100]}...") # Loguear inicio del texto
                return None # Devolver None si no es JSON válido, ya que esperamos dicts
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTPError en {func_name} (attempt {attempt + 1}/{max_retries}): {e.response.status_code} - {e.response.text[:200]}...") # Loguear inicio del error
            if e.response.status_code >= 500 or e.response.status_code == 429:
                if attempt + 1 == max_retries: logger.error(f"API call {func_name} failed after {max_retries} retries."); raise
                logger.info(f"Retrying {func_name} in {delay} seconds..."); time.sleep(delay)
            else: logger.error(f"API call {func_name} failed with client error: {e.response.status_code}. No retrying."); raise e
        except requests.exceptions.RequestException as e:
            logger.error(f"RequestException en {func_name} (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt + 1 == max_retries: logger.error(f"API call {func_name} failed after {max_retries} retries."); raise
            logger.info(f"Retrying {func_name} in {delay} seconds..."); time.sleep(delay)
        except Exception as e:
             logger.exception(f"Unexpected error in {func_name} (attempt {attempt + 1}/{max_retries}): {e}")
             raise
    return None # Devolver None si todas las retries fallan por RequestException

# --- Funciones de Instagram (Mantenidas para futuro, pero no usadas ahora) ---
def get_instagram_insights(ig_user_id, page_access_token, start_date_str, end_date_str):
     """Placeholder: Extract insights from an Instagram account."""
     logger.warning("get_instagram_insights is a placeholder and not fully implemented/used.")
     return None

def post_to_instagram(ig_user_id, page_access_token, image_url=None, video_url=None, caption=""):
     """Placeholder: Publish an image or video on Instagram Business/Creator."""
     logger.warning("post_to_instagram is a placeholder and not fully implemented/used.")
     return None 


# === LinkedIn ===
def get_linkedin_user_info(access_token):
    """
    Get user info from LinkedIn using the OpenID Connect /userinfo endpoint.
    Requires 'openid', 'profile', 'email' scopes.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    # Usar el endpoint estándar /userinfo para OpenID Connect
    userinfo_url = f"{LI_API_URL}/userinfo"
    logger.debug(f"Calling LinkedIn UserInfo endpoint: {userinfo_url}")

    def api_call():
        return requests.get(userinfo_url, headers=headers)

    user_info_data = fetch_with_retry_log(api_call, "get_linkedin_user_info (/userinfo)")

    # Es crucial que user_info_data sea un diccionario y contenga 'sub'
    if isinstance(user_info_data, dict) and 'sub' in user_info_data:
        logger.info(f"Successfully fetched LinkedIn user info. User sub: {user_info_data.get('sub')}")
        # Aseguramos que el campo 'id' exista mapeado desde 'sub' para consistencia interna si se usa en otro lado
        user_info_data['id'] = user_info_data.get('sub')
        return user_info_data
    elif isinstance(user_info_data, dict):
         logger.error(f"LinkedIn /userinfo response received, but 'sub' field is missing. Response keys: {user_info_data.keys()}")
         return None
    else:
        logger.error(f"Failed to fetch or parse LinkedIn user info from /userinfo. Received: {user_info_data}")
        return None


def get_linkedin_organizations(access_token):
    """
    Get LinkedIn organizations where the user has an ADMINISTRATOR role.
    Requires 'r_organization_admin' scope.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202311", # Mantener versión reciente
        "X-Restli-Protocol-Version": "2.0.0" # Necesario para algunas APIs V2
    }
    # Parámetros para buscar membresías de administrador
    params = {
        "q": "roleAssignee",
        "role": "ADMINISTRATOR",
        "state": "APPROVED", # Asegurar que el rol está activo
        "count": 50 # Pedir un número razonable de organizaciones
    }
    logger.debug("Fetching LinkedIn organizations with ADMIN role...")

    def api_call():
        return requests.get(f"{LI_API_URL}/organizationAcls", headers=headers, params=params)

    acl_data = fetch_with_retry_log(api_call, "get_linkedin_organizations (ACLs)")
    organizations = []

    if acl_data and isinstance(acl_data, dict) and 'elements' in acl_data:
        logger.info(f"Found {len(acl_data['elements'])} potential organization ACLs.")
        for element in acl_data['elements']:
            org_urn = element.get('organizationalTarget')
            # Extraer también el rol para asegurar que es el correcto (aunque filtramos por API)
            role_in_acl = element.get('role')
            state_in_acl = element.get('state')

            if org_urn and role_in_acl == "ADMINISTRATOR" and state_in_acl == "APPROVED":
                logger.debug(f"Fetching details for Organization URN: {org_urn}")
                # Obtener detalles (nombre) para esta organización
                org_info = get_linkedin_organization_details(org_urn, access_token)
                if org_info and isinstance(org_info, dict):
                    organizations.append({
                        "urn": org_urn, # Guardar el URN como ID principal
                        "id": org_urn, # Duplicar en 'id' para posible compatibilidad
                        "name": org_info.get("localizedName", org_urn.split(':')[-1]), # Nombre localizado o extraer ID numérico del URN
                        # Se pueden añadir más detalles aquí si se necesitan: logo, etc.
                        "logo": org_info.get("logoV2", {}), # Ejemplo: estructura del logo
                        "platform": "LinkedIn" # Añadir plataforma
                    })
                else:
                     logger.warning(f"Could not get details for org URN: {org_urn}. Skipping.")
            else:
                logger.debug(f"Skipping ACL element, criteria not met: {element}")
    elif isinstance(acl_data, dict):
         logger.warning(f"LinkedIn organization ACL response structure unexpected or empty: {acl_data.keys()}")
    else:
         logger.error(f"Failed to get valid data structure from LinkedIn organization ACLs endpoint. Received: {acl_data}")


    logger.info(f"Processed LinkedIn organizations. Found {len(organizations)} admin roles.")
    return organizations


def get_linkedin_organization_details(org_urn, access_token):
    """Get details (like name, logo) of an organization by its URN."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202311" # Especificar versión
        # "X-Restli-Protocol-Version": "2.0.0" - No suele ser necesario para este GET simple
    }
    # El URN debe estar URL-encoded para usar en la ruta
    encoded_urn = quote(org_urn)
    details_url = f"{LI_API_URL}/organizations/{encoded_urn}"
    logger.debug(f"Calling LinkedIn Organization Details endpoint: {details_url}")

    params = {"fields": "id,localizedName,logoV2(original~:playableStreams)"}

    def api_call():
        return requests.get(details_url, headers=headers, params=params)

    try:
        details = fetch_with_retry_log(api_call, f"get_linkedin_organization_details (URN: {org_urn})")
        if isinstance(details, dict):
             logger.debug(f"Details received for {org_urn}: {details.keys()}")
             return details
        else:
             logger.error(f"Invalid data type received for org details {org_urn}: {type(details)}")
             return None
    except Exception as e:
         # fetch_with_retry_log ya loguea el error, sólo logueamos el fallo final aquí
         logger.error(f"Final error fetching details for LinkedIn org {org_urn}.")
         return None


def get_linkedin_page_insights(org_urn, access_token, start_ts_ms, end_ts_ms):
    """Extract insights from a LinkedIn organization page."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202311",
        "X-Restli-Protocol-Version": "2.0.0" # Necesario para estos endpoints de estadísticas
    }
    results = {'followers': None, 'views': None}
    logger.debug(f"Fetching LinkedIn insights for {org_urn} from {start_ts_ms} to {end_ts_ms}")

    # Followers Statistics
    params_followers = {
        "q": "organizationalEntity",
        "organizationalEntity": org_urn,
        "timeIntervals.timeGranularityType": "DAY",
        "timeIntervals.timeRange.start": start_ts_ms,
        "timeIntervals.timeRange.end": end_ts_ms
    }
    follower_stats_url = f"{LI_API_URL}/organizationalEntityFollowerStatistics"
    def call_followers():
        return requests.get(follower_stats_url, headers=headers, params=params_followers)
    try:
        results['followers'] = fetch_with_retry_log(call_followers, f"get_linkedin_followers (URN: {org_urn})")
        logger.debug(f"Follower stats raw response keys: {results['followers'].keys() if isinstance(results['followers'], dict) else 'N/A'}")
    except Exception as e:
        logger.error(f"Failed to get LinkedIn followers stats for {org_urn}.") # Error ya logueado en fetcher

    # Page Statistics (Views, Clicks, etc.)
    params_views = {
        "q": "organization", # Diferente 'q' aquí
        "organization": org_urn,
        "timeIntervals.timeGranularityType": "DAY",
        "timeIntervals.timeRange.start": start_ts_ms,
        "timeIntervals.timeRange.end": end_ts_ms,
        # Especificar campos deseados (ajustar según necesidad)
        "fields": "totalPageStatistics(views),totalShareStatistics(engagement,impressionCount,likeCount,commentCount,shareCount,clickCount)"
    }
    page_stats_url = f"{LI_API_URL}/organizationPageStatistics"
    def call_views():
        return requests.get(page_stats_url, headers=headers, params=params_views)
    try:
        results['views'] = fetch_with_retry_log(call_views, f"get_linkedin_page_views (URN: {org_urn})")
        logger.debug(f"Page stats raw response keys: {results['views'].keys() if isinstance(results['views'], dict) else 'N/A'}")
    except Exception as e:
        logger.error(f"Failed to get LinkedIn page stats for {org_urn}.")

    return results


def post_to_linkedin_organization(target_entity_urn, access_token, text_content, link_url=None, link_title=None, link_thumbnail_url=None):
    """
    Publish content (text, optional link) to a LinkedIn entity (Profile or Organization).
    Requires 'w_member_social' scope.
    """
    # 1. Obtener el URN del autor (persona que publica)
    user_info = get_linkedin_user_info(access_token)
    if not user_info or not user_info.get('sub'):
        logger.error("Could not get LinkedIn user URN (sub) needed for posting.")
        raise Exception("Could not get LinkedIn user URN (sub) needed for posting.")
    author_urn = f"urn:li:person:{user_info['sub']}"
    logger.debug(f"Posting to LinkedIn as author: {author_urn}")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202311",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json"
    }

    # 2. Construir el cuerpo del post (ShareContent)
    share_content = {
        "shareCommentary": {"text": text_content},
        "shareMediaCategory": "NONE"
    }
    if link_url:
        share_content["shareMediaCategory"] = "ARTICLE"
        article_content = {"originalUrl": link_url}
        if link_title: article_content["title"] = {"text": link_title} # El título va dentro de un objeto 'text'
        if link_thumbnail_url: article_content["thumbnails"] = [{"url": link_thumbnail_url}] # Miniaturas como lista
        share_content["media"] = [{"status": "READY", **article_content}] # Desempaquetar dict


    # 3. Construir cuerpo completo de la petición UGC Post
    post_body = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": share_content
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC" # O 'CONNECTIONS'
        }
        # "containerEntity" se añade condicionalmente abajo
    }

    # Determinar si target_entity_urn es una organización o un perfil
    # Los URN de organización empiezan por "urn:li:organization:"
    # Los URN de persona empiezan por "urn:li:person:"
    is_organization_post = False
    if target_entity_urn and isinstance(target_entity_urn, str) and target_entity_urn.startswith("urn:li:organization:"):
        is_organization_post = True
        post_body["containerEntity"] = target_entity_urn # Añadir sólo para organizaciones
        logger.info(f"Posting to LinkedIn Organization: {target_entity_urn}")
    elif target_entity_urn and isinstance(target_entity_urn, str) and target_entity_urn.startswith("urn:li:person:"):
         # Verificar si el target URN es el mismo que el autor URN
         if target_entity_urn == author_urn:
              logger.info("Posting to LinkedIn User's own profile.")
              # No se añade containerEntity para posts al perfil propio
         else:
              # Postear al perfil de OTRA persona no suele estar permitido vía API
              logger.error(f"Attempting to post to another person's profile ({target_entity_urn}) which is likely not supported.")
              raise ValueError("Posting to another user's profile is not supported via API.")
    else:
         logger.error(f"Invalid or missing target_entity_urn for LinkedIn post: {target_entity_urn}")
         raise ValueError("Invalid target URN for LinkedIn post.")


    logger.debug(f"LinkedIn post body: {json.dumps(post_body, indent=2)}") # Log formateado
    post_url = f"{LI_API_URL}/ugcPosts"

    def api_call():
        return requests.post(post_url, headers=headers, json=post_body)

    # Llamada API y manejo de respuesta (sin cambios)
    try:
        # Usar la response directamente, no el resultado de .json() que podría fallar en 201
        response_obj = fetch_with_retry_log(api_call, f"post_to_linkedin ({'Org' if is_organization_post else 'Profile'}) (Target: {target_entity_urn})")

        # Verificar si fetch_with_retry_log devolvió una respuesta válida de requests
        if isinstance(response_obj, requests.Response):
             post_id_urn = response_obj.headers.get('x-restli-id') or response_obj.headers.get('X-RestLi-Id')
             if response_obj.status_code == 201 and post_id_urn:
                 logger.info(f"Successfully posted to LinkedIn. Post URN: {post_id_urn}")
                 return {"id": post_id_urn}
             else:
                 # Error incluso si fetch_with_retry_log no lanzó excepción (ej. status 200 OK pero sin ID)
                 logger.error(f"LinkedIn post attempt returned status {response_obj.status_code} or missing ID header. Expected 201 with ID. Response: {response_obj.text[:200]}")
                 raise Exception(f"LinkedIn post failed with status {response_obj.status_code} or missing ID.")
        else:
             # Si fetch_with_retry_log devolvió None o texto
             logger.error(f"LinkedIn post failed. Fetcher did not return a valid Response object. Got: {type(response_obj)}")
             raise Exception("LinkedIn post failed (invalid response from API call handler).")

    except Exception as e:
         logger.exception(f"Exception during LinkedIn post to {target_entity_urn}")
         raise e # Re-lanzar