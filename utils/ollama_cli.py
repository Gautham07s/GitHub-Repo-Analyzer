# utils/ollama_cli.py
import subprocess
from typing import Optional

class OllamaCLI:
    """
    Simple thin wrapper around `ollama run <model> --prompt "<prompt>"`.
    Assumes ollama is installed and model is pulled locally (e.g. deepseek-coder).
    """

    def __init__(self, model: str = "deepseek-coder", timeout: int = 120):
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        """
        Run the model and return the text output.
        Raises RuntimeError if ollama is missing or the command fails.
        """
        cmd = ["ollama", "run", self.model, "--prompt", prompt]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        except FileNotFoundError:
            raise RuntimeError("`ollama` CLI not found in PATH. Install Ollama and ensure `ollama` is available.")
        if proc.returncode != 0:
            raise RuntimeError(f"Ollama CLI error: {proc.stderr.strip() or proc.stdout.strip()}")
        return proc.stdout.strip()
