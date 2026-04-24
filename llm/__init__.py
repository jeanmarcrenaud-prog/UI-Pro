# LLM package - Agents, Client, Router, Models
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.models import call, smart_call, research_and_call, OLLAMA_URL, MODELS
from models.settings import settings

MODELS = {
    "fast": settings.model_fast,
    "reasoning": settings.model_reasoning
}

def planner(task):
    return call(MODELS.get("reasoning", settings.model_reasoning), f"Plan task:\n{task}")

def architect(task):
    return call(MODELS.get("reasoning", settings.model_reasoning), f"Design architecture:\n{task}")

def coder(task):
    return call(MODELS.get("fast", settings.model_fast), f"Write clean Python project:\n{task}")

def reviewer(code):
    return call(MODELS.get("reasoning", settings.model_reasoning), f"Review and improve code:\n{code}")

def tester(code):
    return call(MODELS.get("reasoning", settings.model_reasoning), f"Write pytest tests:\n{code}")

def debugger(code, error):
    return call(MODELS.get("reasoning", settings.model_reasoning), f"Fix error:\n{error}\nCode:\n{code}")

def devops(code):
    return call(MODELS.get("reasoning", settings.model_reasoning), f"Create Dockerfile + deployment:\n{code}")

def research(task):
    print("Researching...")
    return research_and_call(task)