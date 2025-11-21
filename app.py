# app.py
import os
import json
import logging
from typing import Tuple

import gradio as gr
from dotenv import load_dotenv

# Import the new graph builder
from graph_orchestrator import build_graph

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-coder")

# Initialize the graph once
app_graph = build_graph()

def run_analysis(repo_url: str, token: str) -> Tuple[str, str, str, str]:
    repo_url = (repo_url or "").strip()
    token_val = token.strip() if token else None
    
    if not repo_url:
        return "Error: Provide repository URL.", "", "", ""

    # Initial State
    initial_state = {
        "repo_url": repo_url,
        "github_token": token_val,
        "ollama_model": OLLAMA_MODEL,
        "status": "start",
        "file_contents": {},
        "validations": {},
        "solutions": {},
        "summary": {}
    }

    try:
        # Invoke the LangGraph
        result = app_graph.invoke(initial_state)
    except Exception as e:
        log.exception("Graph execution failed")
        return f"Exception during graph execution: {e}", "", "", ""

    # Check for functional errors handled inside the graph
    if result.get("status") == "error":
        return f"Error at step '{result.get('step_failed')}': {result.get('error_message')}", "", "", ""

    # --- The rest of the UI formatting logic remains similar, just accessing the 'result' dict ---

    # 1. Files Scanned
    files = sorted(result.get("validations", {}).keys())
    files_text = "\n".join(files) or "No files scanned."

    # 2. Validations
    validations = json.dumps(result.get("validations", {}), indent=2, ensure_ascii=False)

    # 3. Fixes
    sol = result.get("solutions", {})
    fixes_text_builder = []
    for path, s in sol.items():
        fixes_text_builder.append(f"--- {path} ---\nAction: {s.get('action')}\n")
        if s.get("diff"):
            fixes_text_builder.append(s["diff"])
        if s.get("notes"):
            fixes_text_builder.append("\nNotes:\n" + str(s.get("notes")))
        fixes_text_builder.append("\n\n")
    fixes_text = "\n".join(fixes_text_builder) or "No fixes proposed."

    # 4. Summary
    summary = json.dumps(result.get("summary", {}), indent=2, ensure_ascii=False)

    # Optional: Save debug report
    with open("repo_report.json", "w", encoding="utf-8") as f:
        # Filter out non-serializable objects if any
        serializable_res = {k: v for k, v in result.items() if k != "file_contents"}
        json.dump(serializable_res, f, indent=2, ensure_ascii=False)

    return files_text, validations, fixes_text, summary

# The Gradio UI definition remains exactly the same
with gr.Blocks(title="RepoGuardian — LangGraph Edition") as demo:
    gr.Markdown("# RepoGuardian — LangGraph Edition")
    with gr.Row():
        repo_url = gr.Textbox(label="GitHub repository", placeholder="https://github.com/owner/repo")
        token = gr.Textbox(label="GitHub Token (Optional)", type="password")
    run_btn = gr.Button("Run Analysis", variant="primary")
    
    with gr.Tabs():
        with gr.TabItem("📂 Files Scanned"):
            files_out = gr.Textbox(lines=10, interactive=False)
        with gr.TabItem("🔍 Validations"):
            val_out = gr.Code(label="Validations (JSON)", language="json")
        with gr.TabItem("🛠 Fix Suggestions"):
            fixes_out = gr.Textbox(lines=20, interactive=False)
        with gr.TabItem("📊 Repo Summary"):
            summ_out = gr.Code(label="Summary", language="json")

    run_btn.click(fn=run_analysis, inputs=[repo_url, token], outputs=[files_out, val_out, fixes_out, summ_out])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", share=False)