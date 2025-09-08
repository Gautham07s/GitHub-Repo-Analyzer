# app.py
import os
import json
import logging
from typing import Tuple

import gradio as gr
from dotenv import load_dotenv

from orchestrator import Orchestrator

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-coder")

def run_analysis(repo_url: str, token: str) -> Tuple[str, str, str, str]:
    repo_url = (repo_url or "").strip()
    token_val = token.strip() if token else None
    if not repo_url:
        return "Error: Provide repository URL.", "", "", ""
    try:
        orch = Orchestrator(token=token_val, ollama_model=OLLAMA_MODEL)
        result = orch.run(repo_url)
    except Exception as e:
        return f"Exception: {e}", "", "", ""

    if result.get("status") != "ok":
        return f"Error at step {result.get('step')}: {result.get('detail')}", "", "", ""

    # Build outputs
    files = sorted(result.get("validations", {}).keys())
    files_text = "\n".join(files) or "No files scanned."

    validations = json.dumps(result.get("validations", {}), indent=2, ensure_ascii=False)
    # Compose fixes as a concatenation of diffs
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

    summary = json.dumps(result.get("summary", {}), indent=2, ensure_ascii=False)

    # Save full report for debugging
    with open("repo_report.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return files_text, validations, fixes_text, summary

with gr.Blocks(title="RepoGuardian — Multi-Agent Repo Health") as demo:
    gr.Markdown("# RepoGuardian — Multi-Agent GitHub Health Analyzer")
    with gr.Row():
        repo_url = gr.Textbox(label="GitHub repository (URL or owner/repo)", placeholder="https://github.com/owner/repo.git or owner/repo")
        token = gr.Textbox(label="GitHub Personal Access Token (Optional — required for private repos)", type="password", placeholder="Leave empty for public repos")
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
