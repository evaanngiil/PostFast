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
            #  Si el error es 429, no reintentar, ya que es un límite de cuota.
            if e.response.status_code == 429:
                 logger.error(f"API call {func_name} failed due to rate limiting (429). Daily quota likely exceeded. No retrying.")
                 raise e # Re-lanzar la excepción para que sea manejada por la función que llama.
            if e.response.status_code >= 500:
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
# def get_linkedin_user_info(access_token):
#     """
#     Get user info from LinkedIn using the OpenID Connect /userinfo endpoint.
#     Requires 'openid', 'profile', 'email' scopes.
#     """
#     headers = {"Authorization": f"Bearer {access_token}"}
#     # Usar el endpoint estándar /userinfo para OpenID Connect
#     userinfo_url = f"{LI_API_URL}/userinfo"
#     logger.debug(f"Calling LinkedIn UserInfo endpoint: {userinfo_url}")

#     def api_call():
#         return requests.get(userinfo_url, headers=headers)

#     user_info_data = fetch_with_retry_log(api_call, "get_linkedin_user_info (/userinfo)")

#     # Es crucial que user_info_data sea un diccionario y contenga 'sub'
#     if isinstance(user_info_data, dict) and 'sub' in user_info_data:
    
#         logger.info(f"Successfully fetched LinkedIn user info. User sub: {user_info_data.get('sub')}")

#         # Aseguramos que el campo 'id' exista mapeado desde 'sub' para consistencia interna si se usa en otro lado
#         logger.info(f"Formatted user info for frontend: {user_info_data}")
        
#         # Formatear la respuesta para que sea consistente y fácil de usar
#         formatted_info = {
#             "id": user_info_data.get("sub"),
#             'sub': user_info_data.get("sub"),  # Mantener 'sub' para referencia interna
#             "firstName": user_info_data.get("given_name"),
#             "lastName": user_info_data.get("family_name"),
#             "name": user_info_data.get("name"),
#             "email": user_info_data.get("email"), 
#             "picture": user_info_data.get("picture"),
#             "original_response": user_info_data
#         }
#         return formatted_info

#     elif isinstance(user_info_data, dict):
#          logger.error(f"LinkedIn /userinfo response received, but 'sub' field is missing. Response keys: {user_info_data.keys()}")
#          return None
#     else:
#         logger.error(f"Failed to fetch or parse LinkedIn user info from /userinfo. Received: {user_info_data}")
#         return None
    
    
def get_linkedin_user_info(access_token):
    """
    Get user info from LinkedIn using the /me endpoint with specific fields.
    Handles the modern Community Management API structure for profile pictures.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    # Se solicita únicamente la estructura 'displayImage~' que contiene las URLs.
    params = {
        "projection": "(id,localizedFirstName,localizedLastName,profilePicture(displayImage~:playableStreams))"
    }
    userinfo_url = f"{LI_API_URL}/me"
    logger.debug(f"Calling LinkedIn /me endpoint: {userinfo_url} with params: {params}")

    def api_call():
        return requests.get(userinfo_url, headers=headers, params=params)

    user_info_data = fetch_with_retry_log(api_call, "get_linkedin_user_info (/me)")

    if isinstance(user_info_data, dict) and 'id' in user_info_data:
        logger.info(f"Successfully fetched LinkedIn user info. User id: {user_info_data.get('id')}")

        first_name = user_info_data.get("localizedFirstName", "")
        last_name = user_info_data.get("localizedLastName", "")
        picture_url = None

        # La URL de la imagen de perfil está anidada en la nueva estructura
        profile_picture_data = user_info_data.get("profilePicture", {}).get("displayImage~", {})
        if profile_picture_data and "elements" in profile_picture_data and profile_picture_data["elements"]:
            try:
                # Obtener el identificador del último elemento (suele ser la mayor resolución)
                picture_url = profile_picture_data["elements"][-1]["identifiers"][0]["identifier"]
            except (KeyError, IndexError):
                logger.warning("Could not extract profile picture URL from the new structure.")

        # Crear un diccionario consistente para el frontend
        formatted_user_info = {
            "id": user_info_data.get("id"),
            "sub": user_info_data.get("id"),  # Mantener 'sub' mapeado a 'id' para referencia interna
            "firstName": first_name,
            "lastName": last_name,
            "name": f"{first_name} {last_name}".strip(),
            "picture": picture_url,
            # "original_response": user_info_data # Mantener respuesta original para depuración
        }

        return formatted_user_info

    elif isinstance(user_info_data, dict):
         logger.error(f"LinkedIn /me response received, but 'id' field is missing. Response keys: {user_info_data.keys()}")
         return None
    else:
        logger.error(f"Failed to fetch or parse LinkedIn user info from /me. Received: {user_info_data}")
        return None



def get_linkedin_organizations(access_token):
    """
    Get LinkedIn organizations where the user has an ADMINISTRATOR or ANALYTICS role.
    Requires 'r_organization_admin' scope.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202311",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    params = {
        "q": "roleAssignee",
        "state": "APPROVED",
        "count": 50
    }
    logger.debug("Fetching LinkedIn organizations with ADMIN or ANALYTICS role...")

    def api_call():
        return requests.get(f"{LI_API_URL}/organizationAcls", headers=headers, params=params)

    acl_data = fetch_with_retry_log(api_call, "get_linkedin_organizations (ACLs)")
    organizations = []

    if acl_data and isinstance(acl_data, dict) and 'elements' in acl_data:
        logger.info(f"Found {len(acl_data['elements'])} potential organization ACLs.")
        for element in acl_data['elements']:
            org_urn = element.get('organization')
            role_in_acl = element.get('role')
            state_in_acl = element.get('state')

            if org_urn and role_in_acl in ["ADMINISTRATOR", "ANALYST"] and state_in_acl == "APPROVED":
                logger.debug(f"ADMIN/APPROVED role found for URN: {org_urn}. Fetching details...")
                org_info = get_linkedin_organization_details(org_urn, access_token)
                if org_info and isinstance(org_info, dict):
                    org_id_from_details = org_info.get("id", org_urn.split(':')[-1])
                    org_name = org_info.get("localizedName", f"Org {org_id_from_details}")
                    industries = org_info.get("industries", [])

                    organizations.append({
                        "urn": org_urn,
                        "id": org_id_from_details,
                        "name": org_name,
                        "platform": "LinkedIn",
                        "type": "organization",
                        "defaultLocale": org_info.get("defaultLocale"),
                        "vanityName": org_info.get("vanityName"),
                        "localizedSpecialties": org_info.get("localizedSpecialties"),
                        "industries": [get_industry_info(industry_id, access_token) for industry_id in industries],
                        "primaryOrganizationType": org_info.get("primaryOrganizationType"),
                        "versionTag": org_info.get("versionTag")
                    })
    elif isinstance(acl_data, requests.Response): # Chequear si fetch_with_retry_log devolvió un error
         logger.error(f"Failed to get LinkedIn organization ACLs. Status: {acl_data.status_code}, Body: {acl_data.text[:200]}")
    elif isinstance(acl_data, dict):
         logger.warning(f"LinkedIn organization ACL response structure unexpected or empty: {acl_data.keys()}")
    else:
         logger.error(f"Failed to get valid data structure from LinkedIn organization ACLs endpoint. Received type: {type(acl_data)}")


    logger.info(f"Processed LinkedIn organizations. Found {len(organizations)} valid admin roles with details.")
    return organizations

def get_industry_info(industry_id, access_token):
    """
    Retrieves information about a LinkedIn industry by its ID.
    Reference: https://docs.microsoft.com/en-us/linkedin/shared/references/v2/industry/industry?context=linkedin/share/v2/industry/industry
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202311"
    }
    # params = {
    #     "locale.language": "en",
    #     "locale.country": "US"
    # }
    
    params = {}
    
    industry_id = int(industry_id.split(":")[-1])
    industry_url_endpoint = f"https://api.linkedin.com/v2/industries/{industry_id}"
    
    logger.debug(f"Calling LinkedIn Industry endpoint: {industry_url_endpoint} with params: {params}")

    def api_call():
        return requests.get(industry_url_endpoint, headers=headers, params=params)

    industry_info_data = fetch_with_retry_log(api_call, f"get_industry_info (ID: {industry_id})")

    if isinstance(industry_info_data, dict):
        logger.info(f"Successfully fetched industry info for ID {industry_id}.")
        return industry_info_data.get("name", None).get("localized", {}).get("en_US", None) # Devolver el nombre de la industria si existe
    elif isinstance(industry_info_data, requests.Response):
        logger.error(f"Failed to get industry info for ID {industry_id}. Status: {industry_info_data.status_code}, Body: {industry_info_data.text[:200]}")
    else:
        logger.warning(f"LinkedIn industry info response structure unexpected or empty: {industry_info_data.keys() if isinstance(industry_info_data, dict) else None}")
        
        
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
    params = {
        "fields": "vanityName,localizedName,versionTag,defaultLocale,specialties,parentRelationship,localizedSpecialties,industries,name,primaryOrganizationType,id,localizedWebsite"
    }

    logger.debug(f"Calling LinkedIn Organization Details endpoint: {details_url} with params: {params}")

    def api_call():
        return requests.get(details_url, headers=headers, params=params)

    try:
        details = fetch_with_retry_log(api_call, f"get_linkedin_organization_details (URN: {org_urn} / ID: {numeric_org_id})")

        if isinstance(details, dict):
             logger.debug(f"Details received successfully for Org ID {numeric_org_id} (URN: {org_urn}): Keys={details.keys()}")
             details['urn'] = org_urn # Asegurar que el URN original esté presente
            
             return details # Devolver detalles (con o sin 'logo_url')

        elif isinstance(details, requests.Response):
             logger.error(f"Failed to get details for Org ID {numeric_org_id} (URN: {org_urn}). Status: {details.status_code}, Body: {details.text[:200]}")
             return None
        else:
             logger.error(f"Invalid data type ({type(details)}) or no data received for org details ID {numeric_org_id} (URN: {org_urn})")
             return None
    except Exception as e:
         logger.exception(f"Unexpected exception while processing details for Org ID {numeric_org_id} (URN: {org_urn}).")
         return None


def get_linkedin_posts(access_token, target_urn: str, count: int = 10, start: int = 0):
    """
    Recupera los posts (UGC) de un autor específico (usuario u organización).
    Requiere el scope 'r_organization_social' para páginas y 'r_member_social' para perfiles.
    
    :param target_urn: El URN del autor (ej. 'urn:li:person:XXXX' o 'urn:li:organization:YYYY').
    :param count: Número de posts a recuperar (máx. 100).
    :param start: Punto de inicio para la paginación.
    :param kwargs: Contiene el 'access_token' inyectado por el decorador.
    :return: Una lista de posts o None si hay un error.
    """
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    
    params = {
        "author": target_urn,
        "q": "author",
        "count": count,
        "start": start
    }
    
    posts_url = f"{LI_API_URL}/posts"
    logger.debug(f"Calling LinkedIn /posts endpoint: {posts_url} with params: {params}")

    def api_call():
        return requests.get(posts_url, headers=headers, params=params)

    posts_data = fetch_with_retry_log(api_call, f"get_linkedin_posts (URN: {target_urn})")

    if isinstance(posts_data, dict) and 'elements' in posts_data:
        posts = posts_data['elements']
        logger.info(f"Se recuperaron {len(posts)} posts para el URN {target_urn}.")
        return posts
    else:
        logger.error(f"No se pudieron recuperar los posts o la respuesta no tuvo el formato esperado para {target_urn}.")
        return None
    

def post_to_linkedin_organization(target_entity_urn, access_token, text_content, link_url=None, link_title=None, link_thumbnail_url=None):
    """
    Publish content (text, optional link) to a LinkedIn entity (Profile or Organization).
    Requires 'w_member_social' scope.
    """
    user_info = get_linkedin_user_info(access_token)
    if not user_info or not user_info.get('sub'):    
        logger.error("Could not get LinkedIn user URN (sub) needed for posting.") # Ya logueado en get_linkedin_user_info
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