# agents/summarizer.py
import logging
from typing import Dict, Any, List
from statistics import mean
import textwrap

from utils.ollama_cli import OllamaCLI

log = logging.getLogger(__name__)

SUMMARY_PROMPT_TEMPLATE = textwrap.dedent("""
You are an expert repository reviewer. Given the repo name, a numeric health score, counts and example files with issues,
produce:
1) A 4-line executive summary.
2) A bullet list of 8 prioritized improvements. For each improvement mark [Auto] if it can be automated, else [Human].
3) A one-line verdict: Healthy / Fair / Needs Work

INPUT:
REPO: {repo}
BRANCH: {branch}
HEALTH_SCORE: {health}
FILES_ANALYZED: {count}
SYNTAX_ERRORS: {syntax_err}
FLAKE8_WARN_FILES: {flake_warn}
PYLINT_WARN_FILES: {pylint_warn}
EXAMPLE_ISSUE_FILES: {examples}

Provide concise output.
""").strip()

class SummarizerAgent:
    def __init__(self, model: str = "deepseek-coder", timeout: int = 120):
        self.llm = OllamaCLI(model=model, timeout=timeout)

    def _compute_health(self, validations: Dict[str, Any], solutions: Dict[str, Any]) -> int:
        scores = []
        for path, v in validations.items():
            score = 100
            if path.lower().endswith(".py"):
                if v.get("syntax_ok") is False:
                    score -= 50
                if v.get("flake8_returncode", 0) != 0 and v.get("flake8_issues"):
                    score -= 15
                if v.get("pylint_returncode", 0) != 0 and v.get("pylint_issues"):
                    score -= 15
            else:
                score -= 2
            if solutions.get(path, {}).get("action") == "suggest_fix":
                score -= 5
            scores.append(max(0, score))
        return int(mean(scores)) if scores else 100

    def run(self, repo_full_name: str, branch: str, validations: Dict[str, Any], solutions: Dict[str, Any]) -> Dict[str, Any]:
        health = self._compute_health(validations, solutions)
        total = len(validations)
        syntax_err = sum(1 for v in validations.values() if v.get("syntax_ok") is False)
        flake_warn = sum(1 for v in validations.values() if v.get("flake8_returncode", 0) != 0 and v.get("flake8_issues"))
        pylint_warn = sum(1 for v in validations.values() if v.get("pylint_returncode", 0) != 0 and v.get("pylint_issues"))
        example_files = [p for p,v in validations.items() if (v.get("syntax_ok") is False) or v.get("flake8_issues") or v.get("pylint_issues")]
        example_files = example_files[:8]

        prompt = SUMMARY_PROMPT_TEMPLATE.format(
            repo=repo_full_name,
            branch=branch,
            health=health,
            count=total,
            syntax_err=syntax_err,
            flake_warn=flake_warn,
            pylint_warn=pylint_warn,
            examples=example_files
        )

        try:
            text = self.llm.generate(prompt)
        except Exception as e:
            text = f"LLM error: {e}"

        verdict = "Healthy"
        if health < 85:
            verdict = "Fair"
        if health < 65:
            verdict = "Needs Work"

        return {"status": "ok", "summary": {
            "repo": repo_full_name,
            "branch": branch,
            "health_score": health,
            "verdict": verdict,
            "llm_summary": text,
            "stats": {
                "files_analyzed": total,
                "syntax_errors": syntax_err,
                "flake8_warn_files": flake_warn,
                "pylint_warn_files": pylint_warn
            }
        }}
