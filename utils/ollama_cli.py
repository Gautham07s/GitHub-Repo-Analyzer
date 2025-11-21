# utils/ollama_cli.py
import os
import subprocess
import logging
from typing import Optional, Generator

log = logging.getLogger(__name__)

class OllamaClient:
    """
    Robust wrapper around Ollama:
      - Prefer LangChain ChatOllama (if installed)
      - Fallback to calling `ollama run <model> --prompt "<prompt>"`
    Provides:
      - .generate(prompt) -> str
      - .generate_stream(prompt) -> Generator[str, None, None]
    """

    def __init__(self, model: Optional[str] = None, timeout: int = 60, num_predict: int = 500):
        self.model = model or os.getenv("OLLAMA_MODEL", "deepseek-coder")
        self.timeout = timeout
        self.num_predict = num_predict
        self.mode = "cli"
        self.client = None

        # Try to import LangChain Ollama wrapper
        try:
            from langchain_ollama import ChatOllama  # type: ignore
            self.client = ChatOllama(
                model=self.model,
                temperature=0.2,
                num_predict=self.num_predict
            )
            self.mode = "langchain"
            log.info("OllamaClient: using LangChain ChatOllama (model=%s)", self.model)
        except Exception as e:
            log.info("OllamaClient: LangChain not available, using CLI. (%s)", e)
            self.mode = "cli"

    def generate(self, prompt: str) -> str:
        """Blocking call: waits until the model finishes generating."""
        if not prompt:
            return ""

        if self.mode == "langchain" and self.client is not None:
            try:
                out = self.client.invoke(prompt)
                return out.content.strip() if hasattr(out, "content") else str(out).strip()
            except Exception as e:
                log.exception("LangChain call failed, falling back to CLI. %s", e)

        # CLI fallback
        cmd = [
            "ollama", "run", self.model,
            "--num-predict", str(self.num_predict),
            "--prompt", prompt,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        except FileNotFoundError:
            raise RuntimeError("`ollama` not found. Install from https://ollama.ai and add to PATH.")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Ollama timed out after {self.timeout} seconds.")

        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip()
            raise RuntimeError(f"Ollama error: {err}")
        return proc.stdout.strip()

    def generate_stream(self, prompt: str) -> Generator[str, None, None]:
        """Streaming call: yields chunks as they arrive (faster UX)."""
        cmd = [
            "ollama", "run", self.model,
            "--num-predict", str(self.num_predict),
            "--prompt", prompt,
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
        except FileNotFoundError:
            raise RuntimeError("`ollama` not found in PATH.")
        
        if proc.stdout:
            for line in proc.stdout:
                yield line.strip()


# Singleton
_OLLAMA_SINGLETON: Optional[OllamaClient] = None

def get_ollama_client(model: Optional[str] = None, timeout: int = 60, num_predict: int = 500) -> OllamaClient:
    global _OLLAMA_SINGLETON
    if _OLLAMA_SINGLETON is None:
        _OLLAMA_SINGLETON = OllamaClient(model=model, timeout=timeout, num_predict=num_predict)
    return _OLLAMA_SINGLETON
