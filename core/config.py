import os
from functools import lru_cache
from pathlib import Path

from logger import logger
from utils import load_yaml_files

class ConfigLoader:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._intinialized = False
        return cls._instance

    def __init__(self):
        if not self._intinialized:
          self._intinialized = True
          self.load_config()

    def load_config(self):
        """Load configuration from yaml files and env variables"""
        try:
          config_path = Path(__file__).parent.parent.parent / "config" 

          if not config_path.exists():
              logger.error("Configuration path {config_path} does not exist")
              raise FileNotFoundError("Config path does not exist")

          self.config = load_yaml_files(path=config_path)
          logger.info("YAML files loaded successfully")
        except KeyError as e:
          logger.error(f"Error loading configuration key: {e}")
          raise
        except Exception as e:
          logger.error(f"Unexpected error loading configuration: {e}")
          raise

    def get(self, key: str):
        """Get a configuration key by using dot notation"""
        try:
            keys = key.split(".")
            value = self.config
            for key in keys:
                if key in value:
                  value = value[key]
                else:
                    logger.error(f"Key {key} not found in configuration")
                    raise KeyError(f"Key {key} not found in configuration")
            return value
        except Exception as e:
            logger.error(f"Error getting configuration key '{key}': {e}")                
            raise

@lru_cache()
def get_config() -> ConfigLoader:
    """Return a ConfigLoader instance with cache to avoid multiple loads""" 
    return ConfigLoader()
        