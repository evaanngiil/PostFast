from abc import ABC, abstractmethod
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import PromptTemplate

from src.core.logger import logger
from src.agents.utils.llm_factory import LLMFactory

class BaseChain(ABC):
    def __init__(self, chain_config: dict, tools: list = None):
        try:
            self._provider, self._llm_name = chain_config["llm"].split(":")
            self._llm_params = chain_config["llm_params"]
            self.tools = tools
            self.model = LLMFactory.create(
                provider=self._provider,
                llm_name=self._llm_name,
                llm_params=self._llm_params,
                tools=self.tools
            )
            self.prompt = PromptTemplate(
                input_variables=["question"],
                template=chain_config["prompt"]
            )
        except KeyError as e:
            logger.error(f"Missing key in chain config: {e}")
        except Exception as e:
            logger.error(f"Error building chain: {e}")
            raise
            
    @property
    @abstractmethod
    def parser(self):
        raise NotImplementedError()
    
    def build(self):
        try:
            chain = self.prompt | self.model
            return chain if not self.parser else chain | self.parser
        except Exception as e:
            logger.error(f"Error building chain: {e}")
            raise
        
class ChainOutputWithoutParser(BaseChain):
    @property
    def parser(self):
        return None
    
class ChainStringOutput(BaseChain):
    @property
    def parser(self):
        return StrOutputParser()
    
class ChainStructuredOutput(BaseChain):
    def __init__(self, chain_config: dict, pydantic_object, tools: list = None):
        super().__init__(chain_config=chain_config, tools=tools)
        self._pydantic_object = pydantic_object

    @property
    def parser(self):
        raise NotImplementedError()
    
    def build(self):
        try:
            return  self.prompt | self.model.with_structured_output(self._pydantic_object)
        except Exception as e:
            logger.error(f"Error building ChainStructuredOutput: {e}")
            raise
