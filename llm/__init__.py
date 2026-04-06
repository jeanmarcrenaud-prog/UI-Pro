# LLM package - Agents, Client, Router, Models
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.models import call, smart_call, research_and_call, OLLAMA_URL, MODELS

MODELS = MODELS or {
    "fast": "qwen2.5-coder:32b",
    "reasoning": "qwen-opus"
}

def planner(task):
    return call(MODELS.get("reasoning", "qwen-opus"), f"Plan task:\n{task}")

def architect(task):
    return call(MODELS.get("reasoning", "qwen-opus"), f"Design architecture:\n{task}")

def coder(task):
    return call(MODELS.get("fast", "qwen2.5-coder:32b"), f"Write clean Python project:\n{task}")

def reviewer(code):
    return call(MODELS.get("reasoning", "qwen-opus"), f"Review and improve code:\n{code}")

def tester(code):
    return call(MODELS.get("reasoning", "qwen-opus"), f"Write pytest tests:\n{code}")

def debugger(code, error):
    return call(MODELS.get("reasoning", "qwen-opus"), f"Fix error:\n{error}\nCode:\n{code}")

def devops(code):
    return call(MODELS.get("reasoning", "qwen-opus"), f"Create Dockerfile + deployment:\n{code}")

def research(task):
    print("Researching...")
    return research_and_call(task)