import os
import json
import sys

# --- Configuración del entorno ---
# Añadimos 'src' al path para que Python encuentre los módulos de tu aplicación
# Esto es necesario para que el script se pueda ejecutar desde la raíz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# Ahora que el mock está listo, podemos importar las funciones
from src.social_apis import get_linkedin_organizations, get_linkedin_posts, get_linkedin_user_info
from src.core.logger import logger

# --- INSTRUCCIONES ---
# 1. Asegúrate de tener un fichero .env en la raíz con tus credenciales.
# 2. Pega aquí un ACCESS_TOKEN válido de LinkedIn para hacer la prueba.
#    Puedes obtener uno temporalmente después de hacer login en tu app.
ACCESS_TOKEN = "AQVOAvF0qpMqbRXeK4EIVDR-H6PvbdhTmaMH_05YzkK9hC0gQgfW2geaHH5A-qSnu8cjGUQBz_UypuOeOizndQGPSffDPj6h3Iufd7WuUmKRamkEAef9wuSl-NINgmUqB5y6LtsJG239en8H83YvzYMXZBijFDFzmqecz1F7HFVW8LII4pdQVEtU1lqvUTcEVOiUzxkoAtsd2Uq_vO-r4-Mes6FFoI1FPgVuxf0SZyXyc_Pz6YaVai7oEq84nbnamjXythaQjjxR4DU2hMQj7bn7ImwTeQS8aS8sdYnaIJaxxg4Hbo3wHHYZssrt9RSS-KrZ_rKxiXHLOIoy43VWd-Hcmk-H6g"

# 3. Pega aquí el URN del perfil o de la organización de la que quieres ver los posts.
#    - Para obtener el URN de tu perfil:
#      a. Primero, obtendremos tu ID de la API.
#    - Para una organización, puedes encontrar el ID numérico en la URL de su página.
TARGET_URN = "" # Lo rellenaremos dinámicamente

def run_test():
    """
    Función principal para ejecutar la prueba.
    """
    if not ACCESS_TOKEN or "PEGA AQUÍ" in ACCESS_TOKEN:
        logger.error("Por favor, edita este script y añade un ACCESS_TOKEN de LinkedIn válido.")
        return

# --- Paso 1: Obtener las organizaciones asociadas al usuario ---
    logger.info("Paso 1: Obteniendo las organizaciones que administras...")
    organizations = get_linkedin_organizations(ACCESS_TOKEN)
    
    if not organizations:
        logger.warning("No se encontraron organizaciones para este usuario o la llamada falló.")
        logger.info("Asegúrate de que tu cuenta de LinkedIn administre al menos una página de empresa.")
        return
    
        
    # Seleccionamos la primera organización de la lista para la prueba
    first_org = organizations[0]
    org_urn = first_org.get("urn")
    org_name = first_org.get("name")
    
    if not org_urn:
        logger.error("La organización encontrada no tiene un URN válido.")
        return
        
    logger.info(f"¡Éxito! Se usará la primera organización encontrada: '{org_name}' (URN: {org_urn})")
    
    # --- Paso 2: Usar el URN de la organización para buscar sus posts ---
    logger.info(f"\nPaso 2: Buscando los últimos 5 posts de la organización '{org_name}'...")

    posts = get_linkedin_posts(access_token=ACCESS_TOKEN, target_urn=org_urn, count=5)

    if posts is not None:
        logger.info(f"¡Éxito! Se han encontrado {len(posts)} posts.")
        print("\n--- RESULTADO DE LOS POSTS DE LA ORGANIZACIÓN ---")
        # Imprimimos el resultado de forma legible
        print(json.dumps(posts, indent=2))
        print("\n--- FIN DEL RESULTADO ---")
    else:
        logger.error("La llamada para obtener los posts de la organización ha fallado. Revisa los logs.")
        

if __name__ == "__main__":
    run_test()