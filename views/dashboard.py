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

# ===== PHASE 3: Use Services Layer =====
# Import from services layer (decoupled)
try:
    from services import get_chat, get_model, get_memory, get_service_api
    SERVICES_AVAILABLE = True
except Exception as e:
    print(f"Services import error: {e}")
    SERVICES_AVAILABLE = False

# Legacy imports (for backward compat until full migration)
from controllers.orchestrator import Orchestrator
from models.state import StateManager
from controllers.executor import CodeExecutor

# Metrics integration
try:
    from models.metrics import get_dashboard_data, MetricsManager
    METRICS_AVAILABLE = True
except Exception as e:
    print(f"Metrics import error: {e}")
    METRICS_AVAILABLE = False
    get_dashboard_data = None

# Memory integration (legacy, for backward compat)
try:
    from models.memory import MemoryManager
    MEMORY_AVAILABLE = True
except Exception as e:
    print(f"Memory import error: {e}")
    MEMORY_AVAILABLE = False
    MemoryManager = None

# Global service instances (Phase 3)
_service_api = None
_orchestrator = None  # Legacy fallback


def get_service_api_instance():
    """Get ServiceAPI singleton"""
    global _service_api
    if _service_api is None and SERVICES_AVAILABLE:
        try:
            _service_api = get_service_api()
        except Exception as e:
            print(f"ServiceAPI init error: {e}")
    return _service_api


def get_orchestrator():
    """Legacy: Get orchestrator for backward compatibility"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


# ---------------- Gradio UI -----------------
def _build_main_ui():
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
                nav = gr.Radio(
                    ["Task Input", "Real-time Output", "Live Logs", "Status", "Memory", "Metrics", "History", "Advanced"], 
                    value="Task Input", 
                    label="Navigation", 
                    show_label=False
                )
            with gr.Column(scale=4):  # main content
                # Section: Task Input - store reference for navigation
                section_task_input = gr.Column(visible=True, elem_id="section-task-input")
                with section_task_input:
                    task_input = gr.TextArea(
                        label="Task Input", 
                        placeholder="Describe the task to run... (e.g., 'Create a FastAPI app that returns [1,2,3]')", 
                        lines=6
                    )
                    task_id_display = gr.Textbox(label="Current Task ID", value="")
                    submit_btn = gr.Button("Submit Task")
                    gr.Markdown("*Task will execute through: Planner → Architect → Coder → Reviewer → Executor (with auto-fix loop)*")
                
                # Section: Real-time Output
                section_realtime = gr.Column(visible=False, elem_id="section-realtime")
                with section_realtime:
                    gr.Markdown("### Generated Code")
                    
                    # Code display with syntax highlighting
                    code_output = gr.Code(
                        value="",
                        language="python",
                        label="Code",
                        lines=20,
                    )
                    
                    # Action buttons row
                    with gr.Row():
                        copy_btn = gr.Button("Copy", variant="secondary")
                        download_btn = gr.Button("Download", variant="secondary")
                        run_sandbox_btn = gr.Button("Run in Sandbox", variant="primary")
                    
                    # Execution output
                    gr.Markdown("### Execution Result")
                    exec_output = gr.Textbox(
                        label="Execution Output", 
                        value="No output yet.", 
                        lines=10, 
                        interactive=False
                    )
                
                # Section: Live Logs
                section_logs = gr.Column(visible=False, elem_id="section-logs")
                with section_logs:
                    logs = gr.Textbox(
                        label="Live Logs", 
                        value="No logs yet.", 
                        lines=10, 
                        interactive=False
                    )
                
                # Section: Status
                section_status = gr.Column(visible=False, elem_id="section-status")
                with section_status:
                    status_mark = gr.Markdown("**Status**: idle")
                    state_json = gr.JSON(label="State")
                
                # Section: Memory
                section_memory = gr.Column(visible=False, elem_id="section-memory")
                with section_memory:
                    if MEMORY_AVAILABLE:
                        gr.Markdown("### FAISS Memory Search")
                        mem_q = gr.Textbox(label="Search query", placeholder="Ask about previous tasks...")
                        mem_res = gr.Textbox(label="Results", value="", lines=6, interactive=False)
                    else:
                        gr.Markdown("⚠️ Memory not available (FAISS not installed)")
                
                # Section: Metrics
                section_metrics = gr.Column(visible=False, elem_id="section-metrics")
                with section_metrics:
                    if METRICS_AVAILABLE:
                        gr.Markdown("### Execution Metrics")
                        metrics_success_rate = gr.Number(label="Success Rate %", value=0)
                        metrics_total = gr.Number(label="Total Executions", value=0)
                        metrics_avg_time = gr.Number(label="Avg Duration (ms)", value=0)
                        refresh_metrics_btn = gr.Button("Refresh Metrics")
                        gr.Markdown("#### Recent Executions")
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

                # Section: History
                section_history = gr.Column(visible=False, elem_id="section-history")
                with section_history:
                    gr.Markdown("### Previous Generations")
                    gr.Markdown("*History is saved automatically after each task completion*")
                    
                    # History storage
                    history_file = "workspace/history.json"
                    
                    def _load_history():
                        try:
                            if os.path.exists(history_file):
                                with open(history_file, "r") as f:
                                    return json.load(f)
                            return []
                        except Exception:
                            return []
                    
                    # Load initial history
                    initial_history = _load_history()
                    
                    # Display as dataframe
                    history_df = gr.Dataframe(
                        headers=["Task ID", "Task", "Status", "Duration (ms)", "Timestamp"],
                        value=initial_history,
                        interactive=False,
                    )
                    
                    # Reload button
                    refresh_history_btn = gr.Button("Refresh History")
                    
                    def _refresh_history():
                        return _load_history()
                    
                    refresh_history_btn.click(_refresh_history, outputs=[history_df])
                    
                    # Last creation preview
                    gr.Markdown("#### Last Creation")
                    last_creation = gr.Textbox(
                        label="Preview", 
                        value="", 
                        lines=8, 
                        interactive=False,
                    )

                # Section: Advanced
                section_advanced = gr.Column(visible=False, elem_id="section-advanced")
                with section_advanced:
                    gr.Markdown("### Advanced Configuration")
                    
                    with gr.Row():
                        max_iterations = gr.Slider(
                            minimum=1, maximum=10, value=3, step=1,
                            label="Max Auto-fix Iterations",
                        )
                        timeout = gr.Slider(
                            minimum=10, maximum=300, value=60, step=10,
                            label="Timeout (seconds)",
                        )
                    
                    model_choice = gr.Dropdown(
                        choices=["auto", "qwen2.5-coder:32b", "qwen-opus"],
                        value="auto",
                        label="Preferred Model",
                    )
                    
                    gr.Markdown("*These settings affect pipeline execution.*")
        def _on_submit(text):
            if not text or not text.strip():
                return "task-0", "Please enter a task", "No task entered", "**Status**: idle"
            
            tid = f"task-{int(time.time())}"
            output_lines = []
            log_lines = []
            
            try:
                # ===== PHASE 3: Use ChatService =====
                if SERVICES_AVAILABLE:
                    api = get_service_api_instance()
                    if api:
                        log_lines.append(f"[{tid}] Starting ChatService...")
                        
                        # Run async pipeline in thread
                        def run_sync():
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                # Initialize services if needed
                                if not api._initialized:
                                    return loop.run_until_complete(api.initialize())
                                return loop.run_until_complete(api.chat.execute(text))
                            finally:
                                loop.close()
                        
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(run_sync)
                            try:
                                result = future.result(timeout=120)
                            except concurrent.futures.TimeoutError:
                                result = {"status": "timeout", "error": "Execution timeout after 2 minutes"}
                    else:
                        result = {"status": "error", "error": "ServiceAPI not available"}
                else:
                    # Fallback to legacy orchestrator
                    orch = get_orchestrator()
                    log_lines.append(f"[{tid}] Starting orchestrator (legacy)...")
                    
                    def run_sync():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            return loop.run_until_complete(orch.run(text))
                        finally:
                            loop.close()
                    
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(run_sync)
                        try:
                            result = future.result(timeout=120)
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
        
        # Navigation visibility handler - use gr.update for Gradio 6
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
                section_task_input,
                section_realtime,
                section_logs,
                section_status,
                section_memory,
                section_metrics,
            ]
        )
        
        # ===== PHASE 3: Memory search via services =====
        # Try services first, fallback to legacy
        if SERVICES_AVAILABLE:
            def _do_memory_search_services(q):
                if q and q.strip():
                    try:
                        mem = get_memory()
                        results = mem.search(q, k=5)
                        if results:
                            return "\n".join([f"{i+1}. {r.get('text', '')[:100]}" for i, r in enumerate(results)])
                        return "No results found"
                    except Exception as e:
                        return f"Error: {str(e)}"
                return "Enter a query"
            
            # Use services-based memory search if components exist
            try:
                mem_q.change(_do_memory_search_services, inputs=mem_q, outputs=mem_res)
            except NameError:
                pass  # Components don't exist
        elif MEMORY_AVAILABLE:
            # Legacy memory search
            _memory_manager = None
            def _do_memory_search_legacy(q):
                global _memory_manager
                if _memory_manager is None:
                    try:
                        from models.memory import MemoryManager
                        _memory_manager = MemoryManager()
                    except:
                        pass
                if _memory_manager and q:
                    try:
                        results = _memory_manager.search(q, k=5)
                        if results:
                            return "\n".join([f"{i+1}. {r.get('text', '')[:100]}" for i, r in enumerate(results)])
                        return "No results found"
                    except Exception as e:
                        return f"Error: {str(e)}"
                return "Memory not initialized"
            
            try:
                mem_q.change(_do_memory_search_legacy, inputs=mem_q, outputs=mem_res)
            except NameError:
                pass
        
        # Theme - Premium violet/blue
        try:
            from gradio.themes import Default
            custom_theme = Default(
                primary_hue="violet",
                secondary_hue="blue",
            )
            GRADIO_APP.theme = custom_theme
        except Exception:
            pass
        
        # Custom CSS for premium look
        premium_css = """
        .gradio-container { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%) !important; }
        #section-task-input, #section-realtime, #section-logs, #section-status, #section-memory, #section-metrics, #section-history, #section-advanced {
            background: white !important;
            border-radius: 12px !important;
            padding: 20px !important;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
        }
        """
        GRADIO_APP.css = (GRADIO_APP.css or "") + premium_css
    
    return ui


GRADIO_APP = _build_main_ui()

# Export for uvicorn
app = GRADIO_APP


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
    
    # Add navigation change handler at the end
    # Note: Need to reference sections - simplified approach since we don't have nav.change handler


if __name__ == "__main__":
    run()