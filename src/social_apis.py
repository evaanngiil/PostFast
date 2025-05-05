# social_apis.py
import requests
from src.core.logger import logger
from src.core.constants import  LI_API_URL
import time
import json
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
                if attempt + 1 == max_retries: 
                    logger.error(f"API call {func_name} failed after {max_retries} retries.") 
                    raise
                logger.info(f"Retrying {func_name} in {delay} seconds..."); time.sleep(delay)
            else: 
                logger.error(f"API call {func_name} failed with client error: {e.response.status_code}. No retrying.") 
                raise e
        except requests.exceptions.RequestException as e:
            logger.error(f"RequestException en {func_name} (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt + 1 == max_retries: 
                logger.error(f"API call {func_name} failed after {max_retries} retries.")
                raise
            logger.info(f"Retrying {func_name} in {delay} seconds...")
            time.sleep(delay)
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
        "LinkedIn-Version": "202311",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    params = {
        "q": "roleAssignee",
        "role": "ADMINISTRATOR",
        "state": "APPROVED",
        "count": 50
    }
    logger.debug("Fetching LinkedIn organizations with ADMIN role...")

    def api_call():
        return requests.get(f"{LI_API_URL}/organizationAcls", headers=headers, params=params)

    acl_data = fetch_with_retry_log(api_call, "get_linkedin_organizations (ACLs)")
    organizations = []

    if acl_data and isinstance(acl_data, dict) and 'elements' in acl_data:
        logger.info(f"Found {len(acl_data['elements'])} potential organization ACLs.")
        for element in acl_data['elements']:
            org_urn = element.get('organization')
            logger.debug(f"Processing potential Organization ACL for URN: {org_urn}")
            role_in_acl = element.get('role')
            state_in_acl = element.get('state')

            if org_urn and role_in_acl == "ADMINISTRATOR" and state_in_acl == "APPROVED":
                logger.debug(f"ADMIN/APPROVED role found for URN: {org_urn}. Fetching details...")
                org_info = get_linkedin_organization_details(org_urn, access_token)
                if org_info and isinstance(org_info, dict):
                    org_id_from_details = org_info.get("id", org_urn.split(':')[-1]) # Usar ID numérico o extraer del URN
                    org_name = org_info.get("localizedName", f"Org {org_id_from_details}") # Nombre o fallback
                    logo_data = org_info.get("logoV2", {}) # Puede ser complejo, pasarlo tal cual

                    # *** Asegurar estructura consistente para el frontend ***
                    organizations.append({
                        "urn": org_urn,
                        "id": org_id_from_details, # ID numérico o extraído
                        "name": org_name,
                        "logo": logo_data, # Pasar datos del logo si existen
                        "platform": "LinkedIn",
                        "type": "organization" # <<< AÑADIR TIPO
                    })
                    logger.info(f"Successfully added organization: {org_name} (URN: {org_urn})")
                else:
                     logger.warning(f"Could not get details for org URN: {org_urn}. Skipping.")
            else:
                logger.debug(f"Skipping ACL element (not ADMIN/APPROVED or missing URN): {element}")
    elif isinstance(acl_data, requests.Response): # Chequear si fetch_with_retry_log devolvió un error
         logger.error(f"Failed to get LinkedIn organization ACLs. Status: {acl_data.status_code}, Body: {acl_data.text[:200]}")
    elif isinstance(acl_data, dict):
         logger.warning(f"LinkedIn organization ACL response structure unexpected or empty: {acl_data.keys()}")
    else:
         logger.error(f"Failed to get valid data structure from LinkedIn organization ACLs endpoint. Received type: {type(acl_data)}")


    logger.info(f"Processed LinkedIn organizations. Found {len(organizations)} valid admin roles with details.")
    return organizations



def get_linkedin_asset_url(asset_urn, access_token):
    """
    Retrieves the public download URL for a LinkedIn digital media asset URN.
    Reference: https://learn.microsoft.com/en-us/linkedin/marketing/integrations/community-management/shares/vector-images-api#retrieve-a-vector-image
    (Aunque la doc es para Vector, el endpoint /digitalmediaAssets/{urn} suele funcionar para otros assets)
    """
    if not asset_urn or not asset_urn.startswith("urn:li:digitalmediaAsset:"):
        logger.warning(f"Invalid asset URN provided to get_linkedin_asset_url: {asset_urn}")
        return None

    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202311" # Usar la misma versión
    }
    # El URN del asset también debe ir codificado en la URL
    encoded_asset_urn = quote(asset_urn)
    asset_url_endpoint = f"{LI_API_URL}/digitalmediaAssets/{encoded_asset_urn}"

    logger.debug(f"Calling LinkedIn Digital Media Asset endpoint: {asset_url_endpoint}")

    def api_call():
        return requests.get(asset_url_endpoint, headers=headers)

    try:
        asset_data = fetch_with_retry_log(api_call, f"get_linkedin_asset_details (URN: {asset_urn})")

        if isinstance(asset_data, dict):
            # Buscar la URL de descarga. La estructura puede variar.
            # Common paths: 'downloadUrl', 'privateDownloadUrl', 'elements'[0]['identifiers'][0]['identifier']
            # Vamos a buscar en los lugares más probables
            download_url = None
            if 'downloadUrl' in asset_data:
                 download_url = asset_data['downloadUrl']
            elif 'privateDownloadUrl' in asset_data: # A veces es esta
                 download_url = asset_data['privateDownloadUrl']
            elif 'elements' in asset_data and isinstance(asset_data['elements'], list) and asset_data['elements']:
                 # Intentar obtener la URL desde la estructura de 'elements' (común en imágenes vectoriales/logos)
                 try:
                     # Buscar el identificador con tipo 'DOWNLOAD_URL' o similar
                     identifiers = asset_data['elements'][0].get('identifiers', [])
                     url_identifier = next((ident for ident in identifiers if ident.get('identifierType') == 'DOWNLOAD_URL'), None)
                     if url_identifier:
                         download_url = url_identifier.get('identifier')
                     else: # Fallback: tomar la primera URL que se encuentre
                         url_identifier = next((ident for ident in identifiers if 'identifier' in ident), None)
                         if url_identifier: download_url = url_identifier.get('identifier')

                 except (IndexError, KeyError, TypeError) as e:
                     logger.warning(f"Could not extract download URL from 'elements' structure for {asset_urn}: {e}")

            if download_url:
                logger.debug(f"Found download URL for asset {asset_urn}: {download_url}")
                return download_url
            else:
                logger.warning(f"Could not find a downloadable URL within the asset data for {asset_urn}. Data keys: {asset_data.keys()}")
                return None

        elif isinstance(asset_data, requests.Response):
             logger.error(f"Failed to get asset details for {asset_urn}. Status: {asset_data.status_code}, Body: {asset_data.text[:200]}")
             return None
        else:
             logger.error(f"Invalid data type ({type(asset_data)}) or no data received for asset details {asset_urn}")
             return None

    except Exception as e:
         logger.exception(f"Unexpected error retrieving asset URL for {asset_urn}")
         return None



def get_linkedin_organization_details(org_urn, access_token):
    """
    Get details (like name, logo URL) of an organization by its URN.
    Extracts numeric ID, calls API, and attempts to resolve logo asset URN to a URL.
    """
    # ... (código existente para extraer numeric_org_id y llamar a /organizations/{id}) ...
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202311"
    }
    numeric_org_id = None
    if isinstance(org_urn, str) and org_urn.startswith("urn:li:organization:"):
        try:
            numeric_org_id = org_urn.split(':')[-1]
            if not numeric_org_id.isdigit():
                 logger.error(f"Extracted ID '{numeric_org_id}' from URN '{org_urn}' is not numeric.")
                 return None
        except IndexError:
            logger.error(f"Could not extract numeric ID from potentially malformed URN: {org_urn}")
            return None
    else:
        logger.error(f"Invalid or non-organization URN provided: {org_urn}")
        return None

    details_url = f"{LI_API_URL}/organizations/{numeric_org_id}"
    params = {"fields": "id,localizedName,logoV2"} # Pedir el logoV2 que contiene el asset URN

    logger.debug(f"Calling LinkedIn Organization Details endpoint: {details_url} with params: {params}")

    def api_call():
        return requests.get(details_url, headers=headers, params=params)

    try:
        details = fetch_with_retry_log(api_call, f"get_linkedin_organization_details (URN: {org_urn} / ID: {numeric_org_id})")

        if isinstance(details, dict):
             logger.debug(f"Details received successfully for Org ID {numeric_org_id} (URN: {org_urn}): Keys={details.keys()}")
             details['urn'] = org_urn # Asegurar que el URN original esté presente

             # --- NUEVO: Intentar obtener URL del logo ---
             logo_url = None
             if 'logoV2' in details and isinstance(details['logoV2'], dict):
                 # Intentar obtener el URN del asset (priorizar 'original' si existe)
                 asset_urn_to_fetch = details['logoV2'].get('original') or details['logoV2'].get('cropped')
                 if asset_urn_to_fetch and isinstance(asset_urn_to_fetch, str):
                     logger.info(f"Attempting to resolve logo asset URN {asset_urn_to_fetch} to URL...")
                     logo_url = get_linkedin_asset_url(asset_urn_to_fetch, access_token)
                     if logo_url:
                         details['logo_url'] = logo_url # <<< Añadir la URL al diccionario de detalles
                         logger.info(f"Successfully resolved logo URL for {org_urn}")
                     else:
                         logger.warning(f"Could not resolve asset URN {asset_urn_to_fetch} to a public URL.")
                 else:
                     logger.warning(f"Could not find a valid asset URN inside logoV2 field for {org_urn}. logoV2 data: {details['logoV2']}")
             else:
                 logger.warning(f"logoV2 field missing or not a dict in details for {org_urn}.")
             # --- FIN NUEVO ---

             return details # Devolver detalles (con o sin 'logo_url')

        # ... (resto del manejo de errores sin cambios) ...
        elif isinstance(details, requests.Response):
             logger.error(f"Failed to get details for Org ID {numeric_org_id} (URN: {org_urn}). Status: {details.status_code}, Body: {details.text[:200]}")
             return None
        else:
             logger.error(f"Invalid data type ({type(details)}) or no data received for org details ID {numeric_org_id} (URN: {org_urn})")
             return None
    except Exception as e:
         logger.exception(f"Unexpected exception while processing details for Org ID {numeric_org_id} (URN: {org_urn}).")
         return None



def get_linkedin_page_insights(org_urn, access_token, start_ts_ms, end_ts_ms):
    """
    Extract insights from a LinkedIn organization page.
    NOTE: Attempts simplified calls if standard ones fail due to permissions.
    """
    if not org_urn or not isinstance(org_urn, str) or not org_urn.startswith("urn:li:organization:"):
        logger.error(f"Invalid URN provided to get_linkedin_page_insights. Expected 'urn:li:organization:...', got: {org_urn}")
        return None

    logger.info(f"Fetching LinkedIn page insights for valid organization URN: {org_urn}")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202311",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    results = {'followers': None, 'views': None}
    logger.debug(f"Fetching LinkedIn ORG insights for {org_urn} from {start_ts_ms} to {end_ts_ms}")

    # --- Followers Statistics ---
    # Original parameters that caused 403
    # params_followers_orig = {
    #     "q": "organizationalEntity",
    #     "organizationalEntity": org_urn,
    #     "timeIntervals.timeGranularityType": "DAY",
    #     "timeIntervals.timeRange.start": start_ts_ms,
    #     "timeIntervals.timeRange.end": end_ts_ms
    # }
    # *** SIMPLIFIED Call Attempt ***
    # Try without timeIntervals first, as the error mentioned them
    params_followers_simple = {
        "q": "organizationalEntity",
        "organizationalEntity": org_urn,
        # Removed timeIntervals
    }
    follower_stats_url = f"{LI_API_URL}/organizationalEntityFollowerStatistics"

    def call_followers_simple():
        logger.debug(f"Calling follower stats (SIMPLE): URL={follower_stats_url}, Params={params_followers_simple}")
        return requests.get(follower_stats_url, headers=headers, params=params_followers_simple)

    try:
        follower_data = fetch_with_retry_log(call_followers_simple, f"get_linkedin_followers (SIMPLE) (URN: {org_urn})")
        if isinstance(follower_data, dict):
            logger.warning(f"Follower stats (SIMPLE) received successfully, but may not contain all expected data. Check keys: {follower_data.keys()}")
            logger.warning(f"FOLLOWER_DATA: {follower_data}")
            results['followers'] = follower_data
            logger.info(f"Follower stats (SIMPLE) received successfully.")
            
        # Check specific error code - if it's 403, log permission issue
        elif isinstance(follower_data, requests.Response) and follower_data.status_code == 403:
             logger.error(f"Permission error (403) getting follower stats (SIMPLE) for {org_urn}. Check OAuth scopes/App Products. Body: {follower_data.text[:200]}")
        elif isinstance(follower_data, requests.Response): # Log other HTTP errors
             logger.error(f"Failed to get follower stats (SIMPLE) for {org_urn}. Status: {follower_data.status_code}, Body: {follower_data.text[:200]}")
        else: # None u otro tipo
             logger.warning(f"No valid follower stats data received (SIMPLE) for {org_urn}. Received type: {type(follower_data)}")
    except Exception as e: # Catch potential exceptions from fetch_with_retry_log itself if it raises
        logger.exception(f"Unexpected error fetching LinkedIn followers stats (SIMPLE) for {org_urn}")
        results['followers'] = None

    # --- Page Statistics ---
    # Original fields that caused 403
    # fields_orig = "totalPageStatistics(views(allDesktopPageViews,allMobilePageViews)),totalShareStatistics(engagement,impressionCount,likeCount,commentCount,shareCount,clickCount)"
    # *** SIMPLIFIED Call Attempt ***
    # Try requesting only very basic fields, one by one if necessary
    fields_simple = "allDesktopPageViews,allMobilePageViews" # Start with the most basic engagement metrics

    params_views_simple = {
        "q": "organization",
        "organization": org_urn,
        # "timeIntervals.timeGranularityType": "DAY", # Keep time intervals here for now
        # "timeIntervals.timeRange.start": start_ts_ms,
        # "timeIntervals.timeRange.end": end_ts_ms,
    }
    page_stats_url = f"{LI_API_URL}/organizationPageStatistics"

    def call_views_simple():
        logger.debug(f"Calling page stats (SIMPLE): URL={page_stats_url}, Params={params_views_simple}")
        return requests.get(page_stats_url, headers=headers, params=params_views_simple)

    try:
        views_data = fetch_with_retry_log(call_views_simple, f"get_linkedin_page_views (SIMPLE) (URN: {org_urn})")
        if isinstance(views_data, dict):
            results['views'] = views_data
            logger.info(f"Page stats (SIMPLE) received successfully.")
            logger.debug(f"Page stats raw response keys: {results['views'].keys()}")
        elif isinstance(views_data, requests.Response) and views_data.status_code == 403:
            logger.error(f"Permission error (403) getting page stats (SIMPLE - fields: {fields_simple}) for {org_urn}. Check OAuth scopes/App Products. Body: {views_data.text[:200]}")
        elif isinstance(views_data, requests.Response):
             logger.error(f"Failed to get page stats (SIMPLE) for {org_urn}. Status: {views_data.status_code}, Body: {views_data.text[:200]}")
        else:
             logger.warning(f"No valid page stats data received (SIMPLE) for {org_urn}. Received type: {type(views_data)}")
    except Exception as e:
        logger.exception(f"Unexpected error fetching LinkedIn page stats (SIMPLE) for {org_urn}.")
        results['views'] = None


    if results['followers'] is None:
        logger.warning(f"Follower stats (SIMPLE) for {org_urn} are None or empty. Check permissions.")
    if results['views'] is None:
        logger.warning(f"Page stats (SIMPLE) for {org_urn} are None or empty. Check permissions.")
    return results


def post_to_linkedin_organization(target_entity_urn, access_token, text_content, link_url=None, link_title=None, link_thumbnail_url=None):
    """
    Publish content (text, optional link) to a LinkedIn entity (Profile or Organization).
    Requires 'w_member_social' scope.
    """
    user_info = get_linkedin_user_info(access_token)
    if not user_info or not user_info.get('sub'):
        # logger.error("Could not get LinkedIn user URN (sub) needed for posting.") # Ya logueado en get_linkedin_user_info
        raise Exception("Could not get LinkedIn user URN (sub) needed for posting.")
    author_urn = f"urn:li:person:{user_info['sub']}"
    logger.debug(f"Posting to LinkedIn as author: {author_urn}")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202311",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json"
    }

    share_content = {
        "shareCommentary": {"text": text_content},
        "shareMediaCategory": "NONE"
    }
    if link_url:
        share_content["shareMediaCategory"] = "ARTICLE"
        article_content = {"originalUrl": link_url}
        if link_title: article_content["title"] = {"text": link_title}
        if link_thumbnail_url: article_content["thumbnails"] = [{"url": link_thumbnail_url}]
        share_content["media"] = [{"status": "READY", **article_content}]

    post_body = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": share_content
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }

    is_organization_post = False
    if target_entity_urn and isinstance(target_entity_urn, str) and target_entity_urn.startswith("urn:li:organization:"):
        is_organization_post = True
        post_body["containerEntity"] = target_entity_urn
        logger.info(f"Preparing post to LinkedIn Organization: {target_entity_urn}")
    elif target_entity_urn and isinstance(target_entity_urn, str) and target_entity_urn.startswith("urn:li:person:"):
         if target_entity_urn == author_urn:
              logger.info("Preparing post to LinkedIn User's own profile.")
         else:
              logger.error(f"Attempting to post to another person's profile ({target_entity_urn}) which is likely not supported.")
              raise ValueError("Posting to another user's profile is not supported via API.")
    else:
         logger.error(f"Invalid or missing target_entity_urn for LinkedIn post: {target_entity_urn}")
         raise ValueError("Invalid target URN for LinkedIn post.")


    logger.debug(f"LinkedIn post body: {json.dumps(post_body, indent=2)}")
    post_url = f"{LI_API_URL}/ugcPosts"

    def api_call():
        return requests.post(post_url, headers=headers, json=post_body)

    try:
        # fetch_with_retry_log devolverá el objeto Response en caso de éxito (201) o fallo HTTP
        response_obj = fetch_with_retry_log(api_call, f"post_to_linkedin ({'Org' if is_organization_post else 'Profile'}) (Target: {target_entity_urn})")

        if isinstance(response_obj, requests.Response):
             post_id_urn = response_obj.headers.get('x-restli-id') or response_obj.headers.get('X-RestLi-Id')
             if response_obj.status_code == 201 and post_id_urn:
                 logger.info(f"Successfully posted to LinkedIn. Post URN: {post_id_urn}")
                 return {"id": post_id_urn}
             else:
                 # Error HTTP (cliente o servidor) o éxito sin ID esperado
                 logger.error(f"LinkedIn post attempt failed or succeeded unexpectedly. Status: {response_obj.status_code}, Headers: {response_obj.headers}, Response: {response_obj.text[:200]}")
                 # Generar una excepción para que la tarea Celery falle o reintente
                 response_obj.raise_for_status() # Esto lanzará HTTPError si status >= 400
                 # Si el status es < 400 pero falta el ID, lanzar un error genérico
                 if not post_id_urn:
                    raise Exception(f"LinkedIn post succeeded (status {response_obj.status_code}) but missing ID header.")
                 # Si llegamos aquí, algo muy raro pasó (e.g., status 200 OK?)
                 raise Exception(f"Unexpected status code {response_obj.status_code} after LinkedIn post.")
        elif response_obj is None:
             # Fallo de conexión o JSON después de reintentos
             logger.error("LinkedIn post failed after retries (connection or parsing error).")
             raise Exception("LinkedIn post failed after retries (connection or parsing error).")
        else:
             # Tipo inesperado devuelto por fetch_with_retry_log
             logger.error(f"LinkedIn post failed. Fetcher returned unexpected type: {type(response_obj)}")
             raise Exception("LinkedIn post failed (unexpected response from API call handler).")

    except Exception as e:
         logger.exception(f"Exception during LinkedIn post processing for {target_entity_urn}")
         raise e # Re-lanzar para que Celery maneje el reintento/fallo