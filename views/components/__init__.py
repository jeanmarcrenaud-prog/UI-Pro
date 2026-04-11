# Views Components - Task Input Panel
import gradio as gr

def create_task_input():
    """Create task input section"""
    with gr.Column(visible=True, elem_id="section-task-input") as section:
        gr.Markdown("### 📝 Task Input")
        
        task_input = gr.TextArea(
            label="Task", 
            placeholder="Describe the task to run... (e.g., 'Create a FastAPI app that returns [1,2,3]')", 
            lines=6
        )
        
        task_id_display = gr.Textbox(label="Current Task ID", value="")
        
        submit_btn = gr.Button("Submit Task", variant="primary")
        
        gr.Markdown("*Task will execute through: Planner → Architect → Coder → Reviewer → Executor (with auto-fix loop)*")
    
    return {
        "section": section,
        "task_input": task_input,
        "task_id": task_id_display,
        "submit": submit_btn
    }


def create_realtime_output():
    """Create real-time output section"""
    with gr.Column(visible=False, elem_id="section-realtime") as section:
        gr.Markdown("### 💻 Generated Code")
        
        code_output = gr.Code(
            value="",
            language="python",
            label="Code",
            lines=20,
        )
        
        with gr.Row():
            copy_btn = gr.Button("📋 Copy", variant="secondary")
            download_btn = gr.Button("💾 Download", variant="secondary")
            run_sandbox_btn = gr.Button("▶️ Run in Sandbox", variant="primary")
        
        gr.Markdown("### 🧪 Execution Result")
        exec_output = gr.Textbox(
            label="Execution Output", 
            value="No output yet.", 
            lines=10, 
            interactive=False
        )
    
    return {
        "section": section,
        "code": code_output,
        "exec": exec_output,
        "buttons": {
            "copy": copy_btn,
            "download": download_btn,
            "run": run_sandbox_btn
        }
    }


def create_live_logs():
    """Create live logs section"""
    with gr.Column(visible=False, elem_id="section-logs") as section:
        logs = gr.Textbox(
            label="Live Logs", 
            value="No logs yet.", 
            lines=15, 
            interactive=False
        )
    
    return {"section": section, "logs": logs}


def create_status_panel():
    """Create status section"""
    with gr.Column(visible=False, elem_id="section-status") as section:
        status_mark = gr.Markdown("**Status**: idle")
        state_json = gr.JSON(label="State")
    
    return {"section": section, "status": status_mark, "state": state_json}


def create_memory_panel():
    """Create memory section"""
    with gr.Column(visible=False, elem_id="section-memory") as section:
        try:
            from core.memory import MemoryService
            MEMORY_AVAILABLE = True
        except ImportError:
            MEMORY_AVAILABLE = False
        
        if MEMORY_AVAILABLE:
            gr.Markdown("### 🧠 FAISS Memory Search")
            mem_q = gr.Textbox(
                label="Search query", 
                placeholder="Ask about previous tasks...",
                lines=3
            )
            mem_res = gr.Textbox(
                label="Results", 
                value="", 
                lines=6, 
                interactive=False
            )
            search_btn = gr.Button("🔍 Search", variant="primary")
        else:
            gr.Markdown("⚠️ Memory not available (FAISS not installed)")
            mem_q = None
            mem_res = None
            search_btn = None
    
    return {
        "section": section, 
        "query": mem_q, 
        "results": mem_res,
        "search": search_btn
    }


def create_metrics_panel():
    """Create metrics section"""
    with gr.Column(visible=False, elem_id="section-metrics") as section:
        try:
            from core.metrics import get_dashboard_data
            METRICS_AVAILABLE = True
        except ImportError:
            METRICS_AVAILABLE = False
        
        if METRICS_AVAILABLE:
            gr.Markdown("### 📊 Execution Metrics")
            
            metrics_success_rate = gr.Number(label="Success Rate %", value=0)
            metrics_total = gr.Number(label="Total Executions", value=0)
            metrics_avg_time = gr.Number(label="Avg Duration (ms)", value=0)
            
            refresh_metrics_btn = gr.Button("🔄 Refresh Metrics")
            
            gr.Markdown("#### Recent Executions")
            metrics_recent = gr.Dataframe(
                headers=["Task ID", "Task", "Status", "Duration (ms)", "Timestamp"],
                value=[],
            )
        else:
            gr.Markdown("⚠️ Metrics not available")
            metrics_success_rate = None
            metrics_total = None
            metrics_avg_time = None
            refresh_metrics_btn = None
            metrics_recent = None
    
    return {
        "section": section,
        "success_rate": metrics_success_rate,
        "total": metrics_total,
        "avg_time": metrics_avg_time,
        "refresh": refresh_metrics_btn,
        "recent": metrics_recent
    }


def create_history_panel():
    """Create history section"""
    import os, json
    from pathlib import Path
    
    with gr.Column(visible=False, elem_id="section-history") as section:
        gr.Markdown("### 📜 Previous Generations")
        gr.Markdown("*History is saved automatically after each task completion*")
        
        # Load history
        history_file = "workspace/history.json"
        
        def _load_history():
            try:
                if os.path.exists(history_file):
                    with open(history_file, "r") as f:
                        return json.load(f)
                return []
            except Exception:
                return []
        
        initial_history = _load_history()
        
        history_df = gr.Dataframe(
            headers=["Task ID", "Task", "Status", "Duration (ms)", "Timestamp"],
            value=initial_history,
            interactive=False,
            max_height=400,
        )
        
        refresh_history_btn = gr.Button("🔄 Refresh History")
        
        def _refresh_history():
            return _load_history()
        
        gr.Markdown("#### Last Creation")
        last_creation = gr.Textbox(
            label="Preview", 
            value="", 
            lines=8, 
            interactive=False,
        )
    
    return {
        "section": section,
        "dataframe": history_df,
        "refresh": refresh_history_btn,
        "preview": last_creation
    }


def create_advanced_panel():
    """Create advanced configuration section"""
    with gr.Column(visible=False, elem_id="section-advanced") as section:
        gr.Markdown("### ⚙️ Advanced Configuration")
        gr.Markdown("*Configure pipeline behavior and agent options*")
        
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
            choices=["auto", "qwen2.5-coder:32b", "qwen-opus", "deepseek-coder:33b"],
            value="auto",
            label="Preferred Model",
        )
        
        gr.Markdown("#### Additional Options")
        with gr.Row():
            enable_memory = gr.Checkbox(value=True, label="Memory Search")
            verbose_logs = gr.Checkbox(value=False, label="Verbose Logs")
            save_workspace = gr.Checkbox(value=True, label="Save to Workspace")
        
        gr.Markdown("*These settings affect pipeline execution. Changes take effect on next task.*")
    
    return {
        "section": section,
        "max_iterations": max_iterations,
        "timeout": timeout,
        "model": model_choice,
        "options": {
            "memory": enable_memory,
            "verbose": verbose_logs,
            "save": save_workspace
        }
    }