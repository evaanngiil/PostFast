import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from src.core.constants import TAVILY_API_KEY
from langchain_community.tools.tavily_search import TavilySearchResults


@tool
def scrape_website(url: str) -> str:
    """Extrae el contenido de texto principal de una URL dada."""
    print(f"--- 🛠️ Herramienta Scraper: Extrayendo contenido de '{url}' ---")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for script_or_style in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            script_or_style.decompose()
        text = soup.get_text(separator=' ', strip=True)
        return ' '.join(text.split())[:8000] # Limita la longitud
    except requests.RequestException as e:
        return f"Error al acceder a la URL {url}: {e}"
    except Exception as e:
        return f"Error inesperado al procesar la URL {url}: {e}"
    
@tool
def web_search(query: str) -> str:
    """
    Realiza una búsqueda web para encontrar información factual, estadísticas o estudios recientes.
    Usa esto para encontrar datos que respalden las afirmaciones en una publicación.
    """
    print(f"--- 🛠️ Herramienta de Búsqueda: Buscando '{query}' ---")
    if not TAVILY_API_KEY:
        return "La clave API de Tavily no está configurada."
    tavily_tool = TavilySearchResults(max_results=3, api_key=TAVILY_API_KEY)
    results = tavily_tool.invoke(query)
    return "\n".join([f"Fuente: {res['url']}\nContenido: {res['content']}" for res in results])