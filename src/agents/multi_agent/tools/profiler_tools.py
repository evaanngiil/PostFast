"""
Herramientas compartidas para content_writer y company_profiler.
Maneja la extracción web y la búsqueda con Tavily.
"""

from langchain_core.tools import tool

try:
    from langchain_tavily import TavilySearch
    _tavily_search = TavilySearch(max_results=5)
except ImportError:
    try:
        from langchain_community.tools.tavily_search import TavilySearchResults
        _tavily_search = TavilySearchResults(max_results=5)
    except ImportError:
        _tavily_search = None


def scrape_website(url: str) -> str:
    """Scrape a website and return its text content."""
    try:
        import requests
        response = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        return response.text[:5000]
    except Exception as e:
        return f"Error scraping {url}: {e}"


@tool
def web_search(query: str) -> str:
    """Search the web for information. Returns relevant search results as text."""
    if _tavily_search is None:
        return "Web search tool is not available (Tavily not configured)."

    try:
        results = _tavily_search.invoke(query)
    except Exception as e:
        return f"Search error: {e}"

    if isinstance(results, str):
        return results if results.strip() else "No results found."

    if isinstance(results, list):
        parts = []
        for res in results:
            if isinstance(res, dict):
                url = res.get("url", "N/A")
                content = res.get("content", "")
                parts.append(f"Fuente: {url}\nContenido: {content}")
            elif isinstance(res, str):
                parts.append(res)
            else:
                parts.append(str(res))
        return "\n\n".join(parts) if parts else "No results found."

    return str(results) if results else "No results found."
