from typing import Optional
from pathlib import Path
import gradio as gr
import asyncio
import logging
import threading
import queue
import json

logger = logging.getLogger(__name__)


# ==================== **1. ORCHESTRATOR STATE** ====================

# Singleton orchestrator
from orchestrator_async import Orchestrator
orchestrator = Orchestrator()

# Task queue (limité)
task_queue: queue.Queue = queue.Queue(maxsize=10)

# Running tasks set
running_tasks: set = set()
task_status: dict = {}  # task_id -> result


# ==================== **2. UTIL FUNCTIONS** ====================

def run_async_task(task: str, max_tokens: Optional[int] = None) -> dict:
    """
    Executer tâche async dans thread.
    
    Args:
        task: Description tâche
        max_tokens: Limite tokens (optionnel)
        
    Returns:
        Dict avec result
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    task_id = task[:4] + "_" + str(id(task))
    task_status[task_id] = {
        "status": "running",
        "progress": 0,
        "error": None
    }
    
    try:
        result = loop.run_until_complete(orchestrator.run(task))
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["result"] = result
        task_status[task_id]["duration_ms"] = result.get("metrics", {}).get("duration_ms", 0)
        
        return {
            "success": True,
            "task": task,
            "result": result,
            "duration_ms": task_status[task_id]["duration_ms"]
        }
        
    except Exception as e:
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["error"] = str(e)
        
        return {
            "success": False,
            "task": task,
            "error": str(e)
        }
    
    finally:
        loop.close()
    
    return {}


def stream_task(task: str, max_tokens: Optional[int] = None) -> tuple:
    """
    Run async avec streaming.
    
    Usage:
      output = stream_task("Task")
      text += output[0]
      progress = output[1]
    """
    task_id = task[:4] + "_" + str(id(task))
    task_status[task_id] = {"status": "running", "progress": 0}
    
    result = run_async_task(task)
    
    if result.get("success"):
        # Chunk streaming (simulé)
        text = result["result"].get("code", "")
        chunks = text.split("```")
        progress = 100 // len(chunks)
    else:
        text = f"[Error: {result.get('error', 'Unknown')}]"
        progress = 100
    
    return (text, progress, result.get("duration_ms", 0))


def clear_history():
    """Clear historique"""
    task_status.clear()
    return "History cleared"


def parse_json(text: str):
    """
    Parse JSON from LLM response.
    """
    try:
        return json.loads(text)
    except:
        return text


# ==================== **3. GRADIO UI** ====================

with gr.Blocks(title="🚀 Copilot Autonome Local", theme=gr.themes.()) as demo:
    gr.Markdown("""
    # 🧠 **Copilot Autonome Local**
    
    ### Pipeline Async avec:
    - ✅ Multi-model routing
    - ✅ Memory contextual
    - ✅ Circuit breaker
    - ✅ State tracking
    """)
    
    # Input
    task_input = gr.Textbox(
        label="📝 Task Description",
        placeholder="Ex: 'Create FastAPI web app with user auth'",
        lines=1,
        max_length=200
    )
    
    # Run buttons
    run_button = gr.Button("⚙️ Run Task")
    stream_button = gr.Button("📡 Stream (Live)")
    clear_button = gr.Button("🗑️ Clear History")
    
    # Output
    with gr.Accordion("📊 Output (Click to expand)").visible=True:
        output_text = gr.Textbox(
            label="📝 Output",
            lines=10,
            language="python
        )
        
        progress_meter = gr.Slider(
            minimum=0,
            maximum=100,
            value=0,
            label="🔄 Progress"
        )
        
        # JSON output
        json_code = gr.Code(
            label="📄 Code Generated",
            language="python",
            elem_id="code-output"
        )
        
        # Status
        status_display = gr.Textbox(
            label="📊 Status",
            value="Ready"
        )
        
        # History
        history = gr.DataFrame(
            label="📚 History",
            headers=["Task", "Status", "Duration (ms)", "Result"],
            row_count=10,
            col_types=["text", "text", "number", "text"]
        )
    
    # Events
    run_button.click(
        fn=lambda x: stream_task(x),
        inputs=task_input,
        outputs=[output_text, progress_meter, status_display],
        queue=True
    )
    
    stream_button.click(
        fn=stream_task,
        inputs=task_input,
        outputs=[output_text, progress_meter, status_display]
    )
    
    clear_button.click(
        fn=clear_history,
        inputs=None
    )
    
    # Update history
    demo.load(
        fn=clear_history,
        outputs=history
    )


# ==================== **4. LAUNCH** ====================

if __name__ == "__main__":
    demo.queue(concurrency_count=5)
    demo.launch(server_name="127.0.0.1", server_port=7860)