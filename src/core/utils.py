import os
import yaml
import logging
from pathlib import Path

from src.core.logger import logger

def load_yaml_files(path: Path) -> dict:
    """
    Load every YAML file in the given path and return a dictionary with the content of each file.

    :param path: Path to the directory containing the YAML files.
    :return: Dictionary containing the content of each YAML file.
    """
    data = {}
    path = Path(path)

    if not path.exists():
        logger.error(f"Path {path} does not exist")
        raise FileNotFoundError(f"Path {path} does not exist")

    files = list(path.glob("*.yml")) + list(path.glob("*.yaml"))
    if not files:
        logger.warning(f"No YAML files found in {path}")
        raise FileNotFoundError(f"No YAML files found in {path}")

    for file in files:
        try:
            with file.open('r', encoding="utf-8") as f:
                data[file.stem] = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.exception(f"Error parsing YAML file {file}: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error reading YAML file {file}: {e}")
            raise

    return data  