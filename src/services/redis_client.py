from typing import Optional
import redis
from src.core.logger import logger
from src.core.constants import REDIS_HOST, REDIS_PORT

class RedisClient:
    """
    Cliente de Redis para gestionar el almacenamiento de tokens de sesión.
    Utiliza un patrón Singleton para asegurar una única conexión.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            try:
                cls._instance.client = redis.StrictRedis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    decode_responses=True # Decodificar respuestas a UTF-8
                )
                # Comprobar la conexión
                cls._instance.client.ping()
                logger.info(f"✅ Conectado a Redis en {REDIS_HOST}:{REDIS_PORT}")
            except redis.exceptions.ConnectionError as e:
                logger.error(f"❌ No se pudo conectar a Redis: {e}")
                cls._instance.client = None
        return cls._instance

    def save_linkedin_token_to_redis(self, user_id: str, token: str, ttl_seconds: int = 3600 * 24 * 30):
        """Guarda un token en Redis asociado a un user_id con un tiempo de vida (TTL)."""
        if self.client:
            try:
                key = f"linkedin_token:{user_id}"
                self.client.setex(key, ttl_seconds, token)
                logger.info(f"Token para el usuario {user_id} guardado en Redis.")
            except Exception as e:
                logger.error(f"Error al guardar el token en Redis para el usuario {user_id}: {e}")

    def get_linkedin_token_from_redis(self, user_id: str) -> Optional[str]:
        """Obtiene el token de LinkedIn de un usuario desde Redis."""
        if self.client and user_id:
            try:
                token = self.client.get(f"linkedin_token:{user_id}")
                if token:
                    logger.info(f"Token de LinkedIn para el usuario {user_id} recuperado desde Redis.")
                return token
            except Exception as e:
                logger.error(f"Error al obtener el token de LinkedIn de Redis: {e}")
                return None
        return None

    def delete_token(self, user_id: str):
        """Elimina un token de Redis."""
        if self.client:
            try:
                key = f"linkedin_token:{user_id}"
                self.client.delete(key)
                logger.info(f"Token para el usuario {user_id} eliminado de Redis.")
            except Exception as e:
                logger.error(f"Error al eliminar el token de Redis para el usuario {user_id}: {e}")


# Instancia global que se importará en otros módulos
redis_client = RedisClient()