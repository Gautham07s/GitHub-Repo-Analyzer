# orchestrator.py
import logging
from typing import Dict, Any

from agents.authenticator import AuthenticatorAgent
from agents.fetcher import FetcherAgent
from agents.validator import ValidatorAgent
from agents.fixer import FixerAgent
from agents.summarizer import SummarizerAgent

log = logging.getLogger(__name__)

class Orchestrator:
    """
    Run agents in sequence and return a consolidated result dict.
    """

    def __init__(self, token: str = None, ollama_model: str = "deepseek-coder"):
        self.token = token
        self.auth = AuthenticatorAgent(token=token)
        self.fetcher = FetcherAgent(token=token)
        self.validator = ValidatorAgent()
        self.fixer = FixerAgent(model=ollama_model)
        self.summarizer = SummarizerAgent(model=ollama_model)

    def run(self, repo_url: str, branch: str = None) -> Dict[str, Any]:
        # 1) Auth & list
        auth_res = self.auth.list_files(repo_url, branch=branch)
        if auth_res.get("status") != "ok":
            return {"status": "error", "step": "auth", "detail": auth_res}
        owner = auth_res["owner"]
        repo = auth_res["repo"]
        branch = auth_res["branch"]
        files = auth_res["file_paths"]

        # 2) fetch contents
        fetch_res = self.fetcher.fetch(owner, repo, files, branch)
        if fetch_res.get("status") != "ok":
            return {"status": "error", "step": "fetch", "detail": fetch_res}

        file_contents = fetch_res["files"]

        # 3) validate
        val_res = self.validator.run(file_contents)
        if val_res.get("status") != "ok":
            return {"status": "error", "step": "validate", "detail": val_res}
        validations = val_res["validations"]

        # 4) fixer (LLM)
        fix_res = self.fixer.run(validations, file_contents)
        if fix_res.get("status") != "ok":
            return {"status": "error", "step": "fixer", "detail": fix_res}
        solutions = fix_res["solutions"]

        # 5) summarizer
        sum_res = self.summarizer.run(auth_res["repo_full_name"], branch, validations, solutions)
        if sum_res.get("status") != "ok":
            return {"status": "error", "step": "summarizer", "detail": sum_res}

        return {
            "status": "ok",
            "repo": auth_res["repo_full_name"],
            "branch": branch,
            "files_scanned": len(file_contents),
            "validations": validations,
            "solutions": solutions,
            "summary": sum_res["summary"],
            "fetch_details": fetch_res.get("details", {})
        }
