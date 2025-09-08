# agents/fixer.py
import logging
from typing import Dict, Any, List, Optional
import difflib
import textwrap

from utils.ollama_cli import OllamaCLI

log = logging.getLogger(__name__)

FIXER_PROMPT_BASE = textwrap.dedent("""
You are a careful senior Python engineer. For the provided file:
- Fix syntax errors and clear lint issues.
- Make **minimal** changes and preserve intent/style.
- Do NOT add new external dependencies.
If no changes are needed, return exactly: NO_CHANGE

Return the corrected file **only** between markers:
<START_FILE>
...corrected file content...
<END_FILE>

After that markers, optionally include a short "SUGGESTIONS:" bullet list (3 max) describing repo-level improvements relevant to this file (testing, types, docs).
""").strip()

class FixerAgent:
    def __init__(self, model: str = "deepseek-coder", timeout: int = 120, max_files: int = 6):
        self.llm = OllamaCLI(model=model, timeout=timeout)
        self.max_files = max_files

    def _build_prompt(self, path: str, content: str, issues_summary: Dict[str, Any]) -> str:
        # If file is too large, include only context lines near reported issues.
        content_to_send = content
        # Try to extract line numbers from issues for context (flake8 lines look like "12:1:W292:...").
        line_numbers = set()
        for l in issues_summary.get("flake8_issues", []):
            try:
                ln = int(l.split(":", 1)[0])
                line_numbers.add(ln)
            except Exception:
                pass
        for item in issues_summary.get("pylint_issues", []) or []:
            try:
                ln = int(item.get("line"))
                if ln:
                    line_numbers.add(ln)
            except Exception:
                pass

        if line_numbers and len(content) > 10000:
            # build snippet around those lines
            lines = content.splitlines()
            snippets = []
            for ln in sorted(line_numbers):
                start = max(0, ln - 4)
                end = min(len(lines), ln + 3)
                snippet = "\n".join(lines[start:end])
                snippets.append(f"# --- context for line {ln} ---\n{snippet}\n")
            content_to_send = "\n\n".join(snippets)
            content_to_send = f"# NOTE: sending only context snippets because file is large\n{content_to_send}"
        elif len(content) > 15000:
            # file still big: send head + tail
            head = content[:8000]
            tail = content[-8000:]
            content_to_send = f"# NOTE: head...\n{head}\n\n# NOTE: tail...\n{tail}"

        prompt = (
            f"{FIXER_PROMPT_BASE}\n\nFILE_PATH: {path}\n\nISSUES:\n{issues_summary}\n\n"
            f"CURRENT_CONTENT:\n<START_ORIGINAL>\n{content_to_send}\n<END_ORIGINAL>\n\n"
            "Produce corrected file between <START_FILE> and <END_FILE>."
        )
        return prompt

    def _mkdiff(self, old: str, new: str, path: str) -> str:
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        return "".join(difflib.unified_diff(old_lines, new_lines, fromfile=path, tofile=f"{path}.fixed", lineterm=""))

    def run(self, validations: Dict[str, Any], files: Dict[str, str]) -> Dict[str, Any]:
        suggestions: Dict[str, Any] = {}
        fixed = 0
        for path, val in validations.items():
            if fixed >= self.max_files:
                suggestions[path] = {"action": "skipped_max_files"}
                continue
            if not path.lower().endswith(".py"):
                suggestions[path] = {"action": "no_python_analysis"}
                continue

            needs = False
            if val.get("syntax_ok") is False:
                needs = True
            if val.get("flake8_returncode", 0) != 0 and val.get("flake8_issues"):
                needs = True
            if val.get("pylint_returncode", 0) != 0 and val.get("pylint_issues"):
                needs = True
            if not needs:
                suggestions[path] = {"action": "no_change_needed"}
                continue

            content = files.get(path, "")
            issues_summary = {
                "syntax_ok": val.get("syntax_ok"),
                "syntax_error": val.get("syntax_error"),
                "flake8_issues": val.get("flake8_issues"),
                "pylint_issues": val.get("pylint_issues"),
            }

            prompt = self._build_prompt(path, content, issues_summary)
            try:
                out = self.llm.generate(prompt)
            except Exception as e:
                suggestions[path] = {"action": "llm_error", "error": str(e)}
                continue

            corrected = None
            if "<START_FILE>" in out and "<END_FILE>" in out:
                corrected = out.split("<START_FILE>", 1)[1].split("<END_FILE>", 1)[0].strip()
            elif out.strip() == "NO_CHANGE":
                suggestions[path] = {"action": "no_change_needed"}
                continue
            else:
                # fallback: if response too short, mark as failed
                corrected = None

            if corrected:
                diff = self._mkdiff(content, corrected, path)
                # Try to extract suggestions text if any
                post = out.split("</END_FILE>", 1)
                suggestion_text = ""
                if len(post) > 1:
                    suggestion_text = post[1].strip()
                suggestions[path] = {
                    "action": "suggest_fix",
                    "diff": diff,
                    "corrected_preview": corrected[:2000],
                    "notes": suggestion_text[:1000]
                }
                fixed += 1
            else:
                suggestions[path] = {"action": "failed_to_extract_fix", "raw_output": out[:1000]}

        return {"status": "ok", "solutions": suggestions}
