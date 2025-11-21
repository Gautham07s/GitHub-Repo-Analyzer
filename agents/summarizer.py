# agents/summarizer.py
import logging
from typing import Dict, Any, List
from statistics import mean
import textwrap

from utils.ollama_cli import get_ollama_client

log = logging.getLogger(__name__)

SUMMARY_PROMPT = textwrap.dedent("""
You are an expert repository reviewer. Produce a concise, professional summary.

Inputs:
- repo: {repo}
- branch: {branch}
- health_score: {health}
- files_analyzed: {count}
- syntax_errors: {syntax_err}
- flake8_warn_files: {flake_warn}
- pylint_warn_files: {pylint_warn}
- example_issue_files: {examples}

Return:
1) A 4-line executive summary.
2) A prioritized bullet list of up to 8 improvements; mark [Auto] if it can be automated, otherwise [Human].
3) A one-line verdict: Healthy | Fair | Needs Work
Keep output concise and action-oriented.
""").strip()


class SummarizerAgent:
    """
    Compute a numeric health score and ask the LLM to produce an executive summary
    and prioritized improvements. Returns structured summary + raw LLM text.
    """

    def __init__(self, model: str = None, timeout: int = 120):
        self.llm = get_ollama_client(model, timeout)

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
        try:
            health = self._compute_health(validations, solutions)
            total = len(validations)
            syntax_err = sum(1 for v in validations.values() if v.get("syntax_ok") is False)
            flake_warn = sum(1 for v in validations.values() if v.get("flake8_returncode", 0) != 0 and v.get("flake8_issues"))
            pylint_warn = sum(1 for v in validations.values() if v.get("pylint_returncode", 0) != 0 and v.get("pylint_issues"))
            example_files = [p for p, v in validations.items() if (v.get("syntax_ok") is False) or v.get("flake8_issues") or v.get("pylint_issues")]
            example_files = example_files[:8]

            prompt = SUMMARY_PROMPT.format(
                repo=repo_full_name,
                branch=branch or "main",
                health=health,
                count=total,
                syntax_err=syntax_err,
                flake_warn=flake_warn,
                pylint_warn=pylint_warn,
                examples=example_files
            )

            try:
                llm_out = self.llm.generate(prompt)
            except Exception as e:
                log.exception("Summarizer LLM error")
                llm_out = f"LLM error: {e}"

            verdict = "Healthy" if health >= 85 else ("Fair" if health >= 65 else "Needs Work")

            # build a simple machine-readable summary
            sm = {
                "repo": repo_full_name,
                "branch": branch or "main",
                "health_score": health,
                "verdict": verdict,
                "stats": {
                    "files_analyzed": total,
                    "syntax_errors": syntax_err,
                    "flake8_warn_files": flake_warn,
                    "pylint_warn_files": pylint_warn
                },
                "llm_summary": llm_out.strip()
            }

            # Also produce a short human-friendly string (markdown-like)
            lines = [
                f"**Repo:** {repo_full_name}  ",
                f"**Branch:** {branch or 'main'}  ",
                f"**Health score:** {health} / 100 — *{verdict}*  ",
                f"Files analyzed: {total} — Syntax errors: {syntax_err}, Flake8: {flake_warn}, Pylint: {pylint_warn}"
            ]
            human_readable = "\n".join(lines)

            return {"status": "ok", "summary": sm, "human_readable": human_readable}
        except Exception as e:
            log.exception("Summarizer.run failed")
            return {"status": "error", "error": str(e)}
