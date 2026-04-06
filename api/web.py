import requests
import logging

# Structured logger for web module
logger = logging.getLogger(__name__)
if not logger.handlers:
    fh = logging.FileHandler("app.log", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)
from bs4 import BeautifulSoup

def search_web(query):
    try:
        url = f"https://duckduckgo.com/html/?q={query}"
        res = requests.get(url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        logger.warning("Web search failed for query=%r: %s", query, e)
        return []

    results = []
    for a in soup.select(".result__a")[:5]:
        results.append({
            "title": a.text,
            "link": a["href"]
        })

    return results

def scrape_page(url):
    try:
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        return soup.get_text()[:3000]  # limite contexte
    except Exception as e:
        logger.warning("Failed to scrape page %s: %s", url, e)
        return ""
