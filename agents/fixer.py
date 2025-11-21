# agents/fixer.py
import logging
from typing import Dict, Any, Optional
import difflib
import textwrap
import re

from utils.ollama_cli import get_ollama_client

log = logging.getLogger(__name__)

FIXER_PROMPT_HEADER = textwrap.dedent("""
You are a careful, detail-oriented senior Python engineer.
Goal:
  1) Fix syntax errors and clear lint issues with minimal changes.
  2) Preserve code intent and style.
  3) Do not introduce new external dependencies.
Output format:
  - If no changes are needed, reply exactly: NO_CHANGE
  - Otherwise return the full corrected file content between markers:
    <START_FILE>
    ... corrected file content ...
    <END_FILE>

After the <END_FILE> marker, optionally include a short "SUGGESTIONS:" bullet list (3 items max)
about repository-level improvements related to this file (e.g., add tests, typing, refactor).
""").strip()


def _extract_corrected(response: str) -> Optional[str]:
    # Extract content between markers
    if "<START_FILE>" in response and "<END_FILE>" in response:
        return response.split("<START_FILE>", 1)[1].split("<END_FILE>", 1)[0].strip()
    # direct NO_CHANGE
    if response.strip() == "NO_CHANGE":
        return "NO_CHANGE"
    # sometimes model returns the entire file without markers -> be forgiving:
    # heuristic: if response is long and looks like code, return it
    if len(response) > 50 and ("\n" in response) and ("def " in response or "import " in response):
        return response.strip()
    return None


class FixerAgent:
    """
    Uses Ollama (deepseek-coder) to propose fixes.
    Method: run(validations, files) -> {status, solutions}
    Each solution entry: action, diff (unified), corrected_preview, notes
    """

    def __init__(self, model: Optional[str] = None, timeout: int = 120, max_files: int = 6):
        self.llm = get_ollama_client(model, timeout)
        self.max_files = max_files

    def _make_diff(self, old: str, new: str, path: str) -> str:
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        diff = difflib.unified_diff(old_lines, new_lines, fromfile=path, tofile=f"{path}.fixed", lineterm="")
        return "".join(diff) or ""

    def _gather_issue_lines(self, val: Dict[str, Any]) -> set:
        lines = set()
        # flake8 issues look like "12:1:W292:..."
        for l in val.get("flake8_issues", []) or []:
            try:
                ln = int(l.split(":", 1)[0])
                lines.add(ln)
            except Exception:
                pass
        for item in val.get("pylint_issues", []) or []:
            # pylint JSON items often include "line"
            ln = item.get("line") if isinstance(item, dict) else None
            try:
                if ln:
                    lines.add(int(ln))
            except Exception:
                pass
        # syntax_error might contain "line X"
        se = val.get("syntax_error", "")
        m = re.search(r"line (\d+)", str(se))
        if m:
            try:
                lines.add(int(m.group(1)))
            except Exception:
                pass
        return lines

    def _build_prompt(self, path: str, content: str, val: Dict[str, Any]) -> str:
        issues_summary = {
            "syntax_ok": val.get("syntax_ok"),
            "syntax_error": val.get("syntax_error"),
            "flake8_issues": val.get("flake8_issues"),
            "pylint_issues": val.get("pylint_issues"),
        }

        # If file is very large, only send snippets around issue lines (for performance)
        content_to_send = content
        if len(content) > 14000:
            line_nums = sorted(self._gather_issue_lines(val))
            if line_nums:
                lines = content.splitlines()
                snippets = []
                for ln in line_nums:
                    start = max(0, ln - 4)
                    end = min(len(lines), ln + 3)
                    snippets.append("\n".join(lines[start:end]))
                content_to_send = "# NOTE: sending only context snippets because file is large\n\n" + "\n\n".join(snippets)
            else:
                head = content[:7000]
                tail = content[-7000:]
                content_to_send = f"# NOTE: file large — sending head and tail\n{head}\n\n# ...\n\n{tail}"

        prompt = f"{FIXER_PROMPT_HEADER}\n\nFILE_PATH: {path}\n\nISSUES:\n{issues_summary}\n\nCURRENT_CONTENT:\n<START_ORIGINAL>\n{content_to_send}\n<END_ORIGINAL>\n\nProduce the corrected full file between <START_FILE> and <END_FILE>."
        return prompt

    def run(self, validations: Dict[str, Any], files: Dict[str, str]) -> Dict[str, Any]:
        solutions: Dict[str, Any] = {}
        fixed_count = 0

        for path, val in validations.items():
            # limit total files processed
            if fixed_count >= self.max_files:
                solutions[path] = {"action": "skipped_limit", "message": "max files reached for suggestions"}
                continue

            if not path.lower().endswith(".py"):
                solutions[path] = {"action": "skip_non_python"}
                continue

            needs_fix = False
            if val.get("syntax_ok") is False:
                needs_fix = True
            if val.get("flake8_returncode", 0) != 0 and val.get("flake8_issues"):
                needs_fix = True
            if val.get("pylint_returncode", 0) != 0 and val.get("pylint_issues"):
                needs_fix = True

            if not needs_fix:
                solutions[path] = {"action": "no_change_needed"}
                continue

            original = files.get(path, "")
            if not original:
                solutions[path] = {"action": "no_content"}
                continue

            prompt = self._build_prompt(path, original, val)

            try:
                response = self.llm.generate(prompt)
            except Exception as e:
                log.exception("LLM error for path %s", path)
                solutions[path] = {"action": "llm_error", "error": str(e)}
                continue

            corrected = _extract_corrected(response)
            if corrected is None:
                # couldn't extract corrected content
                solutions[path] = {"action": "extract_failed", "raw_output": response[:2000]}
                continue
            if corrected == "NO_CHANGE":
                solutions[path] = {"action": "no_change_needed"}
                continue

            # Build unified diff
            diff = self._make_diff(original, corrected, path)
            summary_note = ""
            if "<END_FILE>" in response:
                after = response.split("<END_FILE>", 1)[1].strip()
                if after:
                    summary_note = after.strip()

            solutions[path] = {
                "action": "suggest_fix",
                "diff": diff or "(no textual diff — change may be whitespace)",
                "corrected_preview": corrected[:2000],
                "notes": summary_note[:1000]
            }
            fixed_count += 1

        return {"status": "ok", "solutions": solutions}
