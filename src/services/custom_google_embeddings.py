import os
import time
from typing import List

import requests
from langchain_core.embeddings import Embeddings


class CustomGoogleRestEmbeddings(Embeddings):
    """
    Cliente REST personalizado para Google Generative AI Embeddings.
    Permite especificar el 'outputDimensionality' que langchain_google_genai no soporta
    de forma nativa de momento en la versión instalada.

    - La API key viaja en la cabecera `x-goog-api-key` (nunca en la URL, que
      acaba filtrada en logs y trazas de error).
    - Reintenta con backoff ante 429/5xx: el pipeline multi-agente encadena
      varias búsquedas vectoriales en pocos segundos y el free tier limita
      las peticiones por minuto.
    """

    MAX_RETRIES = 3
    BACKOFF_SECONDS = (2, 5, 10)

    def __init__(self, model: str = "models/gemini-embedding-001", api_key: str = None, dimensionality: int = 768):
        self.model = model
        self.api_key = api_key or os.environ.get("GENAI_API_KEY")
        if not self.api_key:
            raise ValueError("API Key is required for CustomGoogleRestEmbeddings")
        self.dimensionality = dimensionality
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/{self.model}:embedContent"
        self.batch_url = f"https://generativelanguage.googleapis.com/v1beta/{self.model}:batchEmbedContents"

    def _post(self, url: str, payload: dict) -> dict:
        headers = {"x-goog-api-key": self.api_key}
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 429 or response.status_code >= 500:
                last_error = requests.HTTPError(
                    f"{response.status_code} en la API de embeddings (intento {attempt + 1}/{self.MAX_RETRIES})"
                )
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.BACKOFF_SECONDS[attempt])
                    continue
                raise last_error
            response.raise_for_status()
            return response.json()
        raise last_error  # inalcanzable en la práctica; defensivo

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # La API de batchEmbedContents admite solicitudes en lote.
        requests_payload = []
        for text in texts:
            requests_payload.append({
                "model": self.model,
                "content": {
                    "parts": [{"text": text}]
                },
                "outputDimensionality": self.dimensionality
            })

        data = self._post(self.batch_url, {"requests": requests_payload})

        embeddings = []
        for item in data.get("embeddings", []):
            embeddings.append(item.get("values", []))

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        payload = {
            "model": self.model,
            "content": {
                "parts": [{"text": text}]
            },
            "outputDimensionality": self.dimensionality
        }
        data = self._post(self.base_url, payload)
        return data.get("embedding", {}).get("values", [])
