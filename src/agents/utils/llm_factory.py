from typing import Dict, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.llms import llamacpp
from langchain_core.language_models import BaseLanguageModel
from langchain_openai import OpenAI

from src.core.constants import GENAI_API_KEY
from src.core.logger import logger

class LLMFactory:
    _providers = {
        "gemini": "_build_gemini_llm"
    }

    _default_params = {
        "temperature": 0.3,
        "max_tokens": 256,
        "top_p": 0.85,
        "streaming": True,
        "verbose": False
    }

    @classmethod
    def create(cls, provider: str, llm_name: str, llm_params: Dict = None, tools: List = None) -> BaseLanguageModel:
            if provider not in cls._providers:
                  logger.error(f"Provider '{provider}' not supported")
                  raise KeyError(f"Provider '{provider}' not supported")
            
            try:
                  method = getattr(cls, cls._providers[provider])
                  model = method(llm_name, llm_params or {}, tools)
                  logger.info(f"LLM loader correctly: {llm_name} ({provider})")
                  return model
            except Exception as e:
                  logger.exception(f"Error initializing LLM {llm_name}: {e}")
                  raise
            
    @staticmethod
    def _build_gemini_llm(llm_name: str, llm_params: Dict, tools: List = None) -> BaseLanguageModel:
          return ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                api_key=GENAI_API_KEY,
                **{**LLMFactory._default_params, **llm_params}
          )
                

