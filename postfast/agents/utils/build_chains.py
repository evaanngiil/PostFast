from postfast.core.config import get_config
from postfast.core.logger import logger
from postfast.agents.utils.chain_factory import ChainOutputWithoutParser

try:
    sample_chain = ChainOutputWithoutParser(
        chain_config=get_config().get("chains")['sample']['sample_chain']
    ).build()
    logger.info("Chain [sample_chain] build successfully")
except KeyError as e:
    logger.error(f"Error on config: missing key - {e}")
    raise e
except Exception as e:
    logger.error(f"Error building chain [sample_chain]: {e}")
    raise e
