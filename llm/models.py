# llm/models.py - Ollama Direct Client
#
# Role: Low-level direct calls to Ollama API
# Used by: llm/__init__.py wrapper, not for external use
from models.settings import settings
from views.logger import get_logger
import requests

OLLAMA_URL = f"{settings.ollama_url}/api/generate"
LEMONADE_URL = f"{settings.lemonade_url}/api/v1/chat/completions"

MODELS = {
    "fast": settings.model_fast,
    "reasoning": settings.model_reasoning
}

logger = get_logger(__name__)

def call(model, prompt):
    try:
        logger.debug(f"Calling Ollama with model={model}, prompt_len={len(prompt)}")
        res = requests.post(
            OLLAMA_URL, 
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "timeout": 30  # T-4: Timeout de 30s
            },
            timeout=40  # timeout API request
        )
        res.raise_for_status()
        data = res.json()
        logger.debug(f"Ollama response len={len(data.get('response', ''))}")
        return data["response"]
    except requests.exceptions.Timeout:
        logger.error("LLM request timed out after 30s")
        return ""
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP error from Ollama: {e.response.status_code} - {e.response.text[:200]}")
        return ""
    except requests.exceptions.RequestException:
        logger.error("Failed to reach Ollama service")
        return ""

def smart_call(prompt):
    keywords = ["error", "debug", "optimize", "architecture", "complex"]
    
    if any(k in prompt.lower() for k in keywords):
        logger.debug("Prompt keywords detected, using reasoning model")
        return call(MODELS["reasoning"], prompt)
    
    logger.debug("Using fast model for prompt")
    return call(MODELS["fast"], prompt)

def research_and_call(query):
    from web import search_web, scrape_page
    from logger import get_logger
    
    logger.debug(f"Researching query: {query[:50]}...")
    results = search_web(query)
    
    context = ""
    for r in results[:3]:
        context += scrape_page(r["link"])
    
    prompt = f"""
    Use this context to answer:

    {context}

    Question:
    {query}
    """
    
    return call(MODELS["reasoning"], prompt)
