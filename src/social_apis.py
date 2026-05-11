"""
Módulo principal para la integración con APIs de redes sociales.
Contiene las funciones encargadas de interactuar con plataformas como LinkedIn (y futuramente Instagram),
gestionando la obtención de datos de usuario, organizaciones, métricas de engagement y la publicación de posts.
Implementa una capa de retries para garantizar robustez en las peticiones de red.
"""
import requests
from src.core.logger import logger
from src.core.constants import  LI_API_URL, LI_API_URL_REST
import time
import json
from urllib.parse import quote # Necesario para URNs

def fetch_with_retry_log(api_call_func, func_name, max_retries=3, delay=5):
    """
    Ejecuta una llamada a una API con lógica de reintentos y registro de logs.

    :param api_call_func: Función que realiza la llamada a la API (debe devolver un objeto Response de requests).
    :param func_name: Nombre de la función o endpoint para propósitos de logging.
    :param max_retries: Número máximo de intentos antes de fallar (por defecto 3).
    :param delay: Segundos de espera entre cada reintento (por defecto 5).
    :return: Los datos en formato JSON (dict) si la llamada es exitosa, o None en caso de fallo.
    :raises HTTPError: Si se recibe un error 429 (Rate Limit) u otros errores no recuperables.
    """
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
     """
     Obtiene las estadísticas (insights) de una cuenta de Instagram.
     (Función no implementada completamente, mantenida para uso futuro).

     :param ig_user_id: ID del usuario de Instagram.
     :param page_access_token: Token de acceso de la página.
     :param start_date_str: Fecha de inicio para las estadísticas (str).
     :param end_date_str: Fecha de fin para las estadísticas (str).
     :return: None.
     """
     logger.warning("get_instagram_insights is a placeholder and not fully implemented/used.")
     return None

def post_to_instagram(ig_user_id, page_access_token, image_url=None, video_url=None, caption=""):
     """
     Publica una imagen o video en una cuenta de Instagram Business/Creator.
     (Función no implementada completamente, mantenida para uso futuro).

     :param ig_user_id: ID del usuario de Instagram.
     :param page_access_token: Token de acceso de la página.
     :param image_url: URL de la imagen a publicar (opcional).
     :param video_url: URL del video a publicar (opcional).
     :param caption: Texto de la publicación (por defecto vacío).
     :return: None.
     """
     logger.warning("post_to_instagram is a placeholder and not fully implemented/used.")
     return None 
    
def get_linkedin_user_info(access_token):
    """
    Obtiene la información del usuario de LinkedIn usando los endpoints /me y /userinfo.

    El endpoint /me devuelve id, nombre y foto de perfil pero no el email.
    El endpoint /userinfo (requiere scopes 'openid' + 'email') devuelve sub, name, email, etc.
    Llamamos a /me primero para la foto en alta resolución, y luego a /userinfo para el email.

    :param access_token: Token OAuth de LinkedIn del usuario.
    :return: Diccionario con la información formateada del usuario (id, nombre, email, foto, etc.) o None si falla.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    # --- 1. Llamar a /me para datos de perfil y foto ---
    params = {
        "projection": "(id,localizedFirstName,localizedLastName,profilePicture(displayImage~:playableStreams))"
    }
    me_url = f"{LI_API_URL}/me"
    logger.debug(f"Calling LinkedIn /me endpoint: {me_url}")

    def api_call_me():
        return requests.get(me_url, headers=headers, params=params)

    user_info_data = fetch_with_retry_log(api_call_me, "get_linkedin_user_info (/me)")

    if not isinstance(user_info_data, dict) or 'id' not in user_info_data:
        logger.error(f"Failed to fetch LinkedIn user info from /me. Received: {user_info_data}")
        return None

    logger.info(f"Successfully fetched LinkedIn user info. User id: {user_info_data.get('id')}")

    first_name = user_info_data.get("localizedFirstName", "")
    last_name = user_info_data.get("localizedLastName", "")
    picture_url = None

    profile_picture_data = user_info_data.get("profilePicture", {}).get("displayImage~", {})
    if profile_picture_data and "elements" in profile_picture_data and profile_picture_data["elements"]:
        try:
            picture_url = profile_picture_data["elements"][-1]["identifiers"][0]["identifier"]
        except (KeyError, IndexError):
            logger.warning("Could not extract profile picture URL from the new structure.")

    formatted_user_info = {
        "id": user_info_data.get("id"),
        "sub": user_info_data.get("id"),
        "firstName": first_name,
        "lastName": last_name,
        "name": f"{first_name} {last_name}".strip(),
        "picture": picture_url,
    }

    # --- 2. Llamar a /userinfo para el email (OpenID Connect) ---
    try:
        userinfo_url = f"{LI_API_URL}/userinfo"
        logger.debug(f"Calling LinkedIn /userinfo endpoint for email: {userinfo_url}")

        def api_call_userinfo():
            return requests.get(userinfo_url, headers=headers)

        oidc_data = fetch_with_retry_log(api_call_userinfo, "get_linkedin_user_info (/userinfo)")
        if isinstance(oidc_data, dict):
            email = oidc_data.get("email")
            if email:
                formatted_user_info["email"] = email
                logger.info(f"Email retrieved from /userinfo: {email}")
            # También obtener foto de /userinfo como respaldo
            if not picture_url and oidc_data.get("picture"):
                formatted_user_info["picture"] = oidc_data["picture"]
            # Guardar given_name y family_name para su uso posterior
            if oidc_data.get("given_name"):
                formatted_user_info["given_name"] = oidc_data["given_name"]
            if oidc_data.get("family_name"):
                formatted_user_info["family_name"] = oidc_data["family_name"]
    except Exception as e:
        logger.warning(f"Failed to fetch email from /userinfo (non-fatal): {e}")

    return formatted_user_info



def get_linkedin_organizations(access_token):
    """
    Obtiene las organizaciones de LinkedIn donde el usuario tiene un rol de ADMINISTRATOR o ANALYTICS.
    Requiere el scope 'r_organization_admin'.

    :param access_token: Token OAuth de LinkedIn del usuario.
    :return: Lista de diccionarios con la información de las organizaciones, o lista vacía si no se encuentran.
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
    Recupera información sobre una industria de LinkedIn utilizando su ID.
    Referencia: https://docs.microsoft.com/en-us/linkedin/shared/references/v2/industry/industry?context=linkedin/share/v2/industry/industry

    :param industry_id: ID de la industria en LinkedIn (ej. 'urn:li:industry:47').
    :param access_token: Token OAuth de LinkedIn.
    :return: Nombre localizado de la industria (str) o None si no se encuentra.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202311"
    }
  
    
    params = {}
    
    industry_id = int(industry_id.split(":")[-1])
    industry_url_endpoint = f"https://api.linkedin.com/v2/industries/{industry_id}"
    
    logger.debug(f"Calling LinkedIn Industry endpoint: {industry_url_endpoint} with params: {params}")

    def api_call():
        return requests.get(industry_url_endpoint, headers=headers, params=params)

    industry_info_data = fetch_with_retry_log(api_call, f"get_industry_info (ID: {industry_id})")

    if isinstance(industry_info_data, dict):
        logger.info(f"Successfully fetched industry info for ID {industry_id}.")
        # Extraemos el nombre de forma segura porque el field "name" podría ser None
        name_data = industry_info_data.get("name")
        if isinstance(name_data, dict):
            return name_data.get("localized", {}).get("en_US")
        return None
    elif isinstance(industry_info_data, requests.Response):
        logger.error(f"Failed to get industry info for ID {industry_id}. Status: {industry_info_data.status_code}, Body: {industry_info_data.text[:200]}")
    else:
        logger.warning(f"LinkedIn industry info response structure unexpected or empty: {industry_info_data.keys() if isinstance(industry_info_data, dict) else None}")
        
        
def get_linkedin_asset_url(asset_urn, access_token):
    """
    Recupera la URL pública de descarga para un URN de un asset digital de medios en LinkedIn.
    Referencia: https://learn.microsoft.com/en-us/linkedin/marketing/integrations/community-management/shares/vector-images-api#retrieve-a-vector-image
    (Aunque la doc es para Vector, el endpoint /digitalmediaAssets/{urn} suele funcionar para otros assets)

    :param asset_urn: URN del asset digital (ej. 'urn:li:digitalmediaAsset:...').
    :param access_token: Token OAuth de LinkedIn.
    :return: URL de descarga pública (str) o None si no se puede recuperar.
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
            # Rutas comunes: 'downloadUrl', 'privateDownloadUrl', 'elements'[0]['identifiers'][0]['identifier']
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
    Obtiene los detalles (nombre, logo, etc.) de una organización de LinkedIn a partir de su URN.
    Extrae el ID numérico, llama a la API e intenta resolver el URN del logo a una URL.

    :param org_urn: URN de la organización (ej. 'urn:li:organization:12345').
    :param access_token: Token OAuth de LinkedIn del usuario.
    :return: Diccionario con los detalles de la organización o None si ocurre un error.
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
    
    :param access_token: Token OAuth de LinkedIn del autor.
    :param target_urn: El URN del autor (ej. 'urn:li:person:XXXX' o 'urn:li:organization:YYYY').
    :param count: Número de posts a recuperar (máx. 100).
    :param start: Punto de inicio para la paginación.
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
    

def get_linkedin_company_batch_data(access_token: str, org_urn: str, posts_count: int = 20, start: int = 0) -> dict:
    """
    Extrae en batch toda la informacion relevante de una empresa de LinkedIn:
      - Detalles de la organizacion (nombre, sector, descripcion, etc.)
      - Posts recientes publicados por la organizacion
      - Seguidores (si el scope lo permite)

    Se usa en el onboarding, la primera vez que el usuario conecta una empresa,
    para pre-poblar la base de datos con el contexto necesario para el agente.

    :param access_token: Token OAuth de LinkedIn del usuario.
    :param org_urn:      URN de la organizacion (ej. 'urn:li:organization:12345').
    :param posts_count:  Numero de posts recientes a recuperar (default 20).
    :param start:        Offset de paginacion (default 0).
    :return: Dict con claves 'organization', 'posts', 'follower_count'.
             Cada clave puede ser None si la llamada falla.
    """
    logger.info(f"[company_batch] Iniciando extraccion batch para {org_urn}")

    result = {
        "org_urn": org_urn,
        "organization": None,
        "posts": None,
        "follower_count": None,
    }

    # 1. Detalles de la organizacion
    try:
        org_details = get_linkedin_organization_details(org_urn, access_token)
        result["organization"] = org_details
        logger.info(f"[company_batch] Detalles de organizacion recuperados para {org_urn}")
    except Exception as e:
        logger.error(f"[company_batch] Error recuperando detalles de organizacion {org_urn}: {e}")

    # 2. Posts recientes de la organizacion
    try:
        posts = get_linkedin_posts(access_token, target_urn=org_urn, count=posts_count, start=start)
        result["posts"] = posts or []
        logger.info(f"[company_batch] {len(result['posts'])} posts recuperados para {org_urn}")
    except Exception as e:
        logger.error(f"[company_batch] Error recuperando posts para {org_urn}: {e}")
        result["posts"] = []

    # 3. Numero de seguidores (endpoint /networkSizes, scope r_organization_followers)
    try:
        follower_count = get_linkedin_organization_follower_count(org_urn, access_token)
        result["follower_count"] = follower_count
        logger.info(f"[company_batch] Seguidores para {org_urn}: {follower_count}")
    except Exception as e:
        logger.warning(f"[company_batch] No se pudo obtener el conteo de seguidores para {org_urn}: {e}")

    logger.info(f"[company_batch] Extraccion batch completada para {org_urn}")
    return result


def get_linkedin_organization_follower_count(org_urn: str, access_token: str) -> int | None:
    """
    Obtiene el numero de seguidores de una organizacion de LinkedIn.
    Requiere el scope 'r_organization_followers'.

    :param org_urn:      URN de la organizacion (ej. 'urn:li:organization:12345').
    :param access_token: Token OAuth del usuario con acceso admin.
    :return: Numero entero de seguidores o None si falla.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202311",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    # El endpoint networkSizes requiere el URN codificado como parametro
    encoded_urn = quote(org_urn)
    url = f"{LI_API_URL}/networkSizes/{encoded_urn}?edgeType=CompanyFollowedByMember"

    def api_call():
        return requests.get(url, headers=headers)

    try:
        data = fetch_with_retry_log(api_call, f"get_organization_follower_count ({org_urn})")
        if isinstance(data, dict):
            count = data.get("firstDegreeSize")
            logger.debug(f"Follower count for {org_urn}: {count}")
            return count
        logger.warning(f"Respuesta inesperada al obtener seguidores de {org_urn}: {data}")
        return None
    except Exception as e:
        logger.error(f"Error obteniendo seguidores de {org_urn}: {e}")
        return None


def post_to_linkedin_organization(target_entity_urn, access_token, text_content, link_url=None, link_title=None, link_thumbnail_url=None):
    """
    Publica contenido (texto, enlace opcional) en una entidad de LinkedIn (Perfil u Organización).
    Utiliza la API moderna de posts de LinkedIn (/rest/posts).

    :param target_entity_urn: URN de la entidad de destino (perfil u organización).
    :param access_token: Token OAuth de LinkedIn del autor.
    :param text_content: Contenido de texto principal de la publicación.
    :param link_url: URL de un artículo o enlace a adjuntar (opcional).
    :param link_title: Título del enlace adjunto (opcional).
    :param link_thumbnail_url: URL de la miniatura del enlace (opcional).
    :return: Diccionario con el 'id' (URN) de la publicación creada.
    :raises HTTPError: Si la petición a LinkedIn falla.
    """
    is_organization_post = False
    if target_entity_urn and isinstance(target_entity_urn, str) and target_entity_urn.startswith("urn:li:organization:"):
        is_organization_post = True
        # Seteamos el URN directamente como autor si es una publicación de organización
        author_urn = target_entity_urn
        logger.info(f"Preparing post to LinkedIn Organization: {target_entity_urn}")
    elif target_entity_urn and isinstance(target_entity_urn, str) and target_entity_urn.startswith("urn:li:person:"):
        # Para perfiles personales, el URN del target se usa directamente como autor
        author_urn = target_entity_urn
        logger.info(f"Preparing post to LinkedIn User profile: {target_entity_urn}")
    else:
        # Fallback: fetcheamos el user_info si el target URN es ambiguo o falta
        user_info = get_linkedin_user_info(access_token)
        if not user_info or not user_info.get('sub'):
            logger.error("Could not get LinkedIn user URN (sub) needed for posting.")
            raise Exception("Could not get LinkedIn user URN (sub) needed for posting.")
        author_urn = f"urn:li:person:{user_info['sub']}"
        logger.info(f"Posting to LinkedIn as fallback author: {author_urn}")

    logger.debug(f"Posting to LinkedIn as author: {author_urn}")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202601",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json"
    }

    # Construimos el payload con la estructura requerida por la API moderna de posts
    post_body = {
        "author": author_urn,
        "commentary": text_content,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED"
    }

    # Si viene un link_url, lo empaquetamos como un artículo adjunto en el payload
    if link_url:
        article = {"source": link_url}
        if link_title:
            article["title"] = link_title
        if link_thumbnail_url:
            article["thumbnail"] = link_thumbnail_url
        post_body["content"] = {
            "article": article
        }

    logger.debug(f"LinkedIn post body: {json.dumps(post_body, indent=2)}")
    # Hacemos el request al endpoint moderno /rest/posts
    post_url = f"{LI_API_URL_REST}/posts"

    def api_call():
        return requests.post(post_url, headers=headers, json=post_body)

    try:
        response = requests.post(post_url, headers=headers, json=post_body)
        response.raise_for_status()  # Lanza excepción si 4xx/5xx

        # LinkedIn Posts API devuelve 201 con body vacío.
        # El URN del post va en el header 'x-restli-id'.
        post_id_urn = (
            response.headers.get("x-restli-id")
            or response.headers.get("X-RestLi-Id")
        )

        # Intentar parsear body por si acaso hay respuesta JSON
        if not post_id_urn:
            try:
                body = response.json()
                post_id_urn = body.get("id") or body.get("urn")
            except Exception:
                pass  # Body vacío es esperado con 201

        logger.info(f"Successfully posted to LinkedIn. Post URN: {post_id_urn}")
        return {"id": post_id_urn}
        
    except requests.exceptions.HTTPError as e:
        error_str = e.response.text[:300] if e.response else str(e)
        logger.error(f"HTTPError posting to LinkedIn ({target_entity_urn}): {e.response.status_code} - {error_str}")
        raise
    except Exception as e:
        logger.exception(f"Exception during LinkedIn post processing for {target_entity_urn}")
        raise


def get_organization_share_statistics(org_urn, access_token, share_urns=None, start_timestamp=None, end_timestamp=None):
    """
    Recupera las estadísticas de compartición de las publicaciones de una organización.
    Endpoint: GET /organizationalEntityShareStatistics
    Scope: r_organization_social
    
    :param org_urn: URN de la organización (ej. 'urn:li:organization:12345').
    :param access_token: Token OAuth de LinkedIn.
    :param share_urns: Lista opcional de URNs de compartición específicos para filtrar (máx. 20 por lote).
    :param start_timestamp: Marca de tiempo de inicio opcional (ms) para estadísticas limitadas en el tiempo.
    :param end_timestamp: Marca de tiempo de fin opcional (ms) para estadísticas limitadas en el tiempo.
    :return: Lista de diccionarios con estadísticas de compartición (impresiones, clics, likes, comentarios, shares por post).
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202401",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    
    params = {
        "q": "organizationalEntity",
        "organizationalEntity": org_urn
    }
    
    if share_urns:
        for i, urn in enumerate(share_urns[:20]):
            params[f"shares[{i}]"] = urn
    
    if start_timestamp:
        params["timeIntervals.timeGranularityType"] = "DAY"
        params["timeIntervals.timeRange.start"] = start_timestamp
    if end_timestamp:
        params["timeIntervals.timeRange.end"] = end_timestamp
    
    url = f"{LI_API_URL}/organizationalEntityShareStatistics"
    logger.debug(f"Fetching share statistics for {org_urn}: {url}")
    
    def api_call():
        return requests.get(url, headers=headers, params=params)
    
    try:
        data = fetch_with_retry_log(api_call, f"get_org_share_statistics ({org_urn})")
        if isinstance(data, dict):
            elements = data.get("elements", [])
            logger.info(f"Fetched share statistics for {org_urn}: {len(elements)} elements")
            return elements
        else:
            logger.warning(f"Unexpected response type for share statistics: {type(data)}")
            return []
    except Exception as e:
        logger.error(f"Error fetching share statistics for {org_urn}: {e}")
        return []


def get_organization_page_statistics(org_urn, access_token, start_timestamp=None, end_timestamp=None):
    """
    Recupera estadísticas de la página de una organización (vistas, visitantes, datos demográficos).
    Endpoint: GET /organizationPageStatistics
    Scope: r_organization_social
    
    :param org_urn: URN de la organización.
    :param access_token: Token OAuth de LinkedIn.
    :param start_timestamp: Marca de tiempo de inicio opcional (ms).
    :param end_timestamp: Marca de tiempo de fin opcional (ms).
    :return: Lista de diccionarios con vistas de página, visitantes únicos y demografía de visitantes.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202401",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    
    params = {
        "q": "organization",
        "organization": org_urn
    }
    
    if start_timestamp:
        params["timeIntervals.timeGranularityType"] = "DAY"
        params["timeIntervals.timeRange.start"] = start_timestamp
    if end_timestamp:
        params["timeIntervals.timeRange.end"] = end_timestamp
    
    url = f"{LI_API_URL}/organizationPageStatistics"
    logger.debug(f"Fetching page statistics for {org_urn}: {url}")
    
    def api_call():
        return requests.get(url, headers=headers, params=params)
    
    try:
        data = fetch_with_retry_log(api_call, f"get_org_page_statistics ({org_urn})")
        if isinstance(data, dict):
            elements = data.get("elements", [])
            logger.info(f"Fetched page statistics for {org_urn}: {len(elements)} elements")
            return elements
        else:
            logger.warning(f"Unexpected response type for page statistics: {type(data)}")
            return []
    except Exception as e:
        logger.error(f"Error fetching page statistics for {org_urn}: {e}")
        return []


def get_organization_follower_statistics(org_urn, access_token, start_timestamp=None, end_timestamp=None):
    """
    Recupera estadísticas de seguidores de una organización (crecimiento, datos demográficos).
    Endpoint: GET /organizationalEntityFollowerStatistics
    Scope: r_organization_social
    
    :param org_urn: URN de la organización.
    :param access_token: Token OAuth de LinkedIn.
    :param start_timestamp: Marca de tiempo de inicio opcional (ms).
    :param end_timestamp: Marca de tiempo de fin opcional (ms).
    :return: Lista de diccionarios con el conteo de seguidores a lo largo del tiempo y demografía.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202401",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    
    params = {
        "q": "organizationalEntity",
        "organizationalEntity": org_urn
    }
    
    if start_timestamp:
        params["timeIntervals.timeGranularityType"] = "DAY"
        params["timeIntervals.timeRange.start"] = start_timestamp
    if end_timestamp:
        params["timeIntervals.timeRange.end"] = end_timestamp
    
    url = f"{LI_API_URL}/organizationalEntityFollowerStatistics"
    logger.debug(f"Fetching follower statistics for {org_urn}: {url}")
    
    def api_call():
        return requests.get(url, headers=headers, params=params)
    
    try:
        data = fetch_with_retry_log(api_call, f"get_org_follower_statistics ({org_urn})")
        if isinstance(data, dict):
            elements = data.get("elements", [])
            logger.info(f"Fetched follower statistics for {org_urn}: {len(elements)} elements")
            return elements
        else:
            logger.warning(f"Unexpected response type for follower statistics: {type(data)}")
            return []
    except Exception as e:
        logger.error(f"Error fetching follower statistics for {org_urn}: {e}")
        return []