"""
UI-Pro Dashboard - Version Refactorisée en Composants
Orchestrateur principal
"""

import gradio as gr
import asyncio
import time
import os
import json
from pathlib import Path

# Imports des composants
from .components import (
    create_task_input,
    create_realtime_output,
    create_live_logs,
    create_status_panel,
    create_memory_panel,
    create_metrics_panel,
    create_history_panel,
    create_advanced_panel,
)


def _build_main_ui():
    """Construction de l'interface principale"""
    
    # Get CSS
    css_file = Path("assets/styles/dashboard.css")
    css = ""
    try:
        css = css_file.read_text(encoding="utf-8")
    except Exception:
        pass
    
    # Premium theme
    try:
        from gradio.themes import Default
        theme = Default(primary_hue="violet", secondary_hue="blue")
    except Exception:
        theme = None
    
    with gr.Blocks(title="UI-Pro - AI Agent Orchestration", css=css, theme=theme) as demo:
        
        with gr.Row():
            # Sidebar Navigation
            with gr.Column(scale=1):
                nav = gr.Radio(
                    choices=[
                        "Task Input", "Real-time Output", "Live Logs",
                        "Status", "Memory", "Metrics", "History", "Advanced"
                    ],
                    value="Task Input",
                    label="Navigation",
                    show_label=False,
                )

            # Main content
            with gr.Column(scale=4):
                # Create sections via components
                sections = {
                    "Task Input": create_task_input(),
                    "Real-time Output": create_realtime_output(),
                    "Live Logs": create_live_logs(),
                    "Status": create_status_panel(),
                    "Memory": create_memory_panel(),
                    "Metrics": create_metrics_panel(),
                    "History": create_history_panel(),
                    "Advanced": create_advanced_panel(),
                }
                
                # Extract refs for visibility toggle
                task_input_section = sections["Task Input"]["section"]
                realtime_section = sections["Real-time Output"]["section"]
                logs_section = sections["Live Logs"]["section"]
                status_section = sections["Status"]["section"]
                memory_section = sections["Memory"]["section"]
                metrics_section = sections["Metrics"]["section"]
                history_section = sections["History"]["section"]
                advanced_section = sections["Advanced"]["section"]
                
                task_input = sections["Task Input"]["task_input"]
                task_id_display = sections["Task Input"]["task_id"]
                submit_btn = sections["Task Input"]["submit"]
                
                code_output = sections["Real-time Output"]["code"]
                exec_output = sections["Real-time Output"]["exec"]
                
                logs = sections["Live Logs"]["logs"]
                
                status_mark = sections["Status"]["status"]
                state_json = sections["Status"]["state"]
                
                # ========== SUBMIT HANDLER ==========
                def on_submit(text):
                    if not text or not text.strip():
                        return "task-0", "Please enter a task", "No logs", "**Status**: idle", {}, ""
                    
                    tid = f"task-{int(time.time())}"
                    log_lines = []
                    output_lines = []
                    
                    # Try ChatService
                    try:
                        from services.chat_service import get_chat_service
                        api = get_chat_service()
                        if api:
                            log_lines.append(f"[{tid}] Starting...")
                            
                            def run_sync():
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                try:
                                    return loop.run_until_complete(api.execute(text))
                                finally:
                                    loop.close()
                            
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as pool:
                                future = pool.submit(run_sync)
                                result = future.result(timeout=120)
                        else:
                            result = {"status": "error", "error": "Service not available"}
                    except Exception as e:
                        log_lines.append(f"[{tid}] Error: {str(e)}")
                        result = {"status": "error", "error": str(e)}
                    
                    # Format output
                    output = ""
                    if "code" in result:
                        code = result.get("code", {})
                        if isinstance(code, dict):
                            for fname, fcode in code.items():
                                output += f"# {fname}\n{fcode[:500]}\n"
                    
                    status = f"**Status**: {result.get('status', 'unknown')}"
                    
                    return tid, output, "\n".join(log_lines), status, result, ""
                
                submit_btn.click(
                    on_submit,
                    inputs=task_input,
                    outputs=[task_id_display, code_output, logs, status_mark, state_json, exec_output]
                )
                
                # Navigation handler
                all_sections = [task_input_section, realtime_section, logs_section, status_section, 
                              memory_section, metrics_section, history_section, advanced_section]
                
                def switch_tab(choice):
                    return [gr.update(visible=(name == choice)) for name in [
                        "Task Input", "Real-time Output", "Live Logs", "Status", 
                        "Memory", "Metrics", "History", "Advanced"
                    ]]
                
                nav.change(
                    fn=switch_tab,
                    inputs=nav,
                    outputs=all_sections
                )
    
    return demo


# Export for launcher
GRADIO_APP = _build_main_ui()


def run():
    """Point d'entrée du dashboard"""
    print("🚀 Lancement du Dashboard UI-Pro...")
    GRADIO_APP.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
    )


if __name__ == "__main__":
    run()