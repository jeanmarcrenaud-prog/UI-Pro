import gradio as gr
import asyncio
import threading
import time
import json
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import real orchestrator components
from core.orchestrator_async import Orchestrator
from core.state_manager import StateManager
from core.executor import CodeExecutor

# Translation imports
from api.translations import (
    get_current_translations,
    LANGUAGE_OPTIONS,
    DEFAULT_LANGUAGE,
    LANGUAGES,
)

# Metrics integration
try:
    from core.metrics import get_dashboard_data, MetricsManager
    METRICS_AVAILABLE = True
except Exception as e:
    print(f"Metrics import error: {e}")
    METRICS_AVAILABLE = False
    get_dashboard_data = None

# Memory integration
try:
    from core.memory import MemoryManager
    MEMORY_AVAILABLE = True
except Exception as e:
    print(f"Memory import error: {e}")
    MEMORY_AVAILABLE = False
    MemoryManager = None

# Global orchestrator instance
_orchestrator = None
_executor = None
_memory_manager = None


def get_orchestrator():
    global _orchestrator, _executor, _memory_manager
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    if _executor is None:
        _executor = CodeExecutor()
    if _memory_manager is None and MEMORY_AVAILABLE:
        try:
            _memory_manager = MemoryManager()
        except Exception as e:
            print(f"MemoryManager init error: {e}")
            _memory_manager = None
    return _orchestrator


# ---------------- Gradio UI -----------------
def _build_main_ui():
    # Get translations for default language
    t = get_current_translations(DEFAULT_LANGUAGE)
    
    # Get CSS path if available
    css_file = "assets/styles/dashboard.css"
    css_content = ""
    try:
        with open(css_file, "r") as f:
            css_content = f.read()
    except Exception:
        pass
    
    ui = gr.Blocks()
    
    with ui:
        
        with gr.Row():
            with gr.Column(scale=1):  # sidebar
                # Language selector
                lang_dropdown = gr.Dropdown(
                    choices=[opt[1] for opt in LANGUAGE_OPTIONS],
                    value=DEFAULT_LANGUAGE,
                    label=t.get("language", "Langue"),
                    show_label=True,
                )
                nav = gr.Radio(
                    [t.get("nav_item_task_input", "Task Input"), t.get("nav_item_realtime", "Real-time Output"), 
                     t.get("nav_item_logs", "Live Logs"), t.get("nav_item_status", "Status"), 
                     t.get("nav_item_memory", "Memory"), t.get("nav_item_metrics", "Metrics")], 
                    value=t.get("nav_item_task_input", "Task Input"), 
                    label=t.get("nav_task_input", "Navigation"), 
                    show_label=False
                )
            with gr.Column(scale=4):  # main content
                # Section: Task Input
                with gr.Column(visible=True, elem_id="section-task-input"):
                    task_input = gr.TextArea(
                        label=t.get("task_input_label", "Task Input"), 
                        placeholder=t.get("task_input_placeholder", "Describe the task..."), 
                        lines=6
                    )
                    task_id_display = gr.Textbox(label=t.get("current_task_id", "Current Task ID"), value="")
                    submit_btn = gr.Button(t.get("btn_submit", "Submit Task"))
                    gr.Markdown(f"*{t.get('pipeline_desc', 'Task will execute through pipeline')}*")
                
                # Section: Real-time Output
                with gr.Column(visible=False, elem_id="section-realtime"):
                    rt_output = gr.Textbox(
                        label=t.get("realtime_label", "Execution Output"), 
                        value=t.get("realtime_placeholder", "No output yet."), 
                        lines=15, 
                        interactive=False
                    )
                
                # Section: Live Logs
                with gr.Column(visible=False, elem_id="section-logs"):
                    logs = gr.Textbox(
                        label=t.get("logs_label", "Live Logs"), 
                        value=t.get("logs_placeholder", "No logs yet."), 
                        lines=10, 
                        interactive=False
                    )
                
                # Section: Status
                with gr.Column(visible=False, elem_id="section-status"):
                    status_mark = gr.Markdown(f"**{t.get('status_label', 'Status')}**: {t.get('status_idle', 'idle')}")
                    state_json = gr.JSON(label=t.get("state_label", "State"))
                
                # Section: Memory
                with gr.Column(visible=False, elem_id="section-memory"):
                    if MEMORY_AVAILABLE:
                        gr.Markdown(f"### {t.get('memory_title', 'FAISS Memory Search')}")
                        mem_q = gr.Textbox(label=t.get("memory_search", "Search query"), placeholder=t.get("memory_placeholder", "Ask about previous tasks..."))
                        mem_res = gr.Textbox(label=t.get("memory_results", "Results"), value="", lines=6, interactive=False)
                    else:
                        gr.Markdown(t.get("memory_not_available", "⚠️ Memory not available"))
                
                # Section: Metrics
                with gr.Column(visible=False, elem_id="section-metrics"):
                    if METRICS_AVAILABLE:
                        gr.Markdown(f"### {t.get('metrics_title', 'Execution Metrics')}")
                        metrics_success_rate = gr.Number(label=t.get("metrics_success_rate", "Success Rate %"), value=0)
                        metrics_total = gr.Number(label=t.get("metrics_total", "Total Executions"), value=0)
                        metrics_avg_time = gr.Number(label=t.get("metrics_avg", "Avg Duration (ms)"), value=0)
                        refresh_metrics_btn = gr.Button(t.get("metrics_refresh", "Refresh Metrics"))
                        gr.Markdown(f"#### {t.get('metrics_recent', 'Recent Executions')}")
                        metrics_recent = gr.Dataframe(
                            headers=["Task ID", "Task", "Status", "Duration (ms)", "Timestamp"],
                            value=[],
                        )
                        
                        # Metrics refresh function
                        def _refresh_metrics():
                            try:
                                data = get_dashboard_data()
                                metrics_data = data.get("metrics", {})
                                return (
                                    data.get("success_rate", 0),
                                    metrics_data.get("total_executions", 0),
                                    metrics_data.get("avg_duration_ms", 0),
                                    data.get("recent", []),
                                )
                            except Exception as e:
                                return 0, 0, 0, []
                        
                        # Initialize metrics on load
                        init_metrics = _refresh_metrics()
                        metrics_success_rate.value = init_metrics[0]
                        metrics_total.value = init_metrics[1]
                        metrics_avg_time.value = init_metrics[2]
                        metrics_recent.value = init_metrics[3]
                        
                        refresh_metrics_btn.click(_refresh_metrics, outputs=[metrics_success_rate, metrics_total, metrics_avg_time, metrics_recent])
                    else:
                        gr.Markdown("⚠️ Metrics not available")

        # Submit handler - runs real pipeline
        def _on_submit(text):
            if not text or not text.strip():
                return "task-0", "Please enter a task", "No task entered", "**Status**: idle"
            
            tid = f"task-{int(time.time())}"
            output_lines = []
            log_lines = []
            
            try:
                # Get orchestrator
                orch = get_orchestrator()
                
                log_lines.append(f"[{tid}] Starting orchestrator...")
                
                # Run the async pipeline in a thread
                def run_sync():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(orch.run(text))
                        return result
                    finally:
                        loop.close()
                
                # Execute with timeout
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(run_sync)
                    try:
                        result = future.result(timeout=120)  # 2 min timeout
                    except concurrent.futures.TimeoutError:
                        result = {"status": "timeout", "error": "Execution timeout after 2 minutes"}
                
                # Format output
                output_lines.append("=" * 50)
                output_lines.append(f"Task: {text[:50]}...")
                output_lines.append("=" * 50)
                output_lines.append("")
                
                if "plan" in result:
                    output_lines.append("📋 **Plan**:")
                    output_lines.append(json.dumps(result.get("plan", {}), indent=2))
                
                if "architecture" in result:
                    output_lines.append("")
                    output_lines.append("🏗️ **Architecture**:")
                    output_lines.append(json.dumps(result.get("architecture", {}), indent=2))
                
                if "code" in result:
                    output_lines.append("")
                    output_lines.append("💻 **Code**:")
                    code = result.get("code", {})
                    if isinstance(code, dict):
                        for fname, fcode in code.items():
                            output_lines.append(f"--- {fname} ---")
                            output_lines.append(str(fcode)[:500])
                    else:
                        output_lines.append(str(code)[:500])
                
                if "tests" in result:
                    output_lines.append("")
                    output_lines.append("🧪 **Execution Result**:")
                    tests = result.get("tests", {})
                    output_lines.append(f"Success: {tests.get('success', 'N/A')}")
                    if tests.get("stdout"):
                        output_lines.append(f"STDOUT: {tests.get('stdout', '')[:200]}")
                    if tests.get("stderr"):
                        output_lines.append(f"STDERR: {tests.get('stderr', '')[:200]}")
                    output_lines.append(f"Duration: {tests.get('duration_ms', 'N/A')}ms")
                
                output_lines.append("")
                output_lines.append("=" * 50)
                output_lines.append(f"Status: {result.get('status', 'unknown')}")
                if "error" in result:
                    output_lines.append(f"Error: {result.get('error', '')}")
                output_lines.append("=" * 50)
                
                # Logs
                log_lines.append(f"[{tid}] Status: {result.get('status', 'unknown')}")
                if result.get("metrics"):
                    log_lines.append(f"[{tid}] Metrics: {result.get('metrics', {})}")
                
                status = f"**Status**: {result.get('status', 'unknown')}"
                
                return tid, "\n".join(output_lines), "\n".join(log_lines), status, result
                
            except Exception as e:
                log_lines.append(f"[{tid}] ERROR: {str(e)}")
                return tid, f"Error: {str(e)}", "\n".join(log_lines), "**Status**: error", {}
        
        submit_btn.click(
            _on_submit, 
            inputs=task_input, 
            outputs=[task_id_display, rt_output, logs, status_mark, state_json]
        )
        
        # Navigation visibility handler
        def _on_nav_change(tab_name):
            return [
                gr.update(visible=tab_name == "Task Input"),
                gr.update(visible=tab_name == "Real-time Output"),
                gr.update(visible=tab_name == "Live Logs"),
                gr.update(visible=tab_name == "Status"),
                gr.update(visible=tab_name == "Memory"),
                gr.update(visible=tab_name == "Metrics"),
            ]
        
        nav.change(
            _on_nav_change,
            inputs=nav,
            outputs=[
                gr.Column(visible=True, elem_id="section-task-input"),
                gr.Column(visible=True, elem_id="section-realtime"),
                gr.Column(visible=True, elem_id="section-logs"),
                gr.Column(visible=True, elem_id="section-status"),
                gr.Column(visible=True, elem_id="section-memory"),
                gr.Column(visible=True, elem_id="section-metrics"),
            ]
        )
        
        # Language change handler - update UI labels
        def _on_lang_change(lang):
            t = get_current_translations(lang)
            return (
                gr.update(label=t.get("language", "Langue")),  # lang_dropdown label
                gr.update(label=t.get("task_input_label", "Task Input"), placeholder=t.get("task_input_placeholder", "...")),
                gr.update(label=t.get("current_task_id", "Task ID")),
                gr.update(label=t.get("btn_submit", "Submit")),
                # gr.update(value=t.get("pipeline_desc", "...")),  # Markdown - can't update this way
                gr.update(label=t.get("realtime_label", "Output"), value=t.get("realtime_placeholder", "...")),
                gr.update(label=t.get("logs_label", "Logs"), value=t.get("logs_placeholder", "...")),
                gr.update(value=f"**{t.get('status_label', 'Status')}**: {t.get('status_idle', 'idle')}"),
                gr.update(label=t.get("state_label", "State")),
            )
        
        lang_dropdown.change(
            _on_lang_change,
            inputs=lang_dropdown,
            outputs=[
                lang_dropdown, task_input, task_id_display, submit_btn,
                rt_output, logs, status_mark, state_json
            ]
        )
        
        # Memory search
        if MEMORY_AVAILABLE:
            def _do_memory_search(q):
                if _memory_manager and q:
                    try:
                        results = _memory_manager.search(q, k=5)
                        if results:
                            return "\n".join([f"{i+1}. {r.get('text', '')[:100]}" for i, r in enumerate(results)])
                        return "No results found"
                    except Exception as e:
                        return f"Error: {str(e)}"
                return "Memory not initialized"
            
            mem_q.change(_do_memory_search, inputs=mem_q, outputs=mem_res)
    
    return ui


GRADIO_APP = _build_main_ui()


def run():
    print("🚀 Starting UI-Pro Dashboard on http://localhost:7860")
    print("📋 Pipeline: Planner → Architect → Coder → Reviewer → Executor (auto-fix)")
    
    # Get CSS content
    css_file = "assets/styles/dashboard.css"
    css_content = ""
    try:
        with open(css_file, "r") as f:
            css_content = f.read()
    except Exception:
        pass
    
    GRADIO_APP.launch(
        share=False, 
        server_name="0.0.0.0", 
        server_port=7860,
        css=css_content if css_content else None
    )


if __name__ == "__main__":
    run()