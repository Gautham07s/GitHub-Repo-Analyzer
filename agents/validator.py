# agents/validator.py
import logging
from typing import Dict, Any, Tuple, List
import ast
import tempfile
import subprocess
import sys
import json
import os

log = logging.getLogger(__name__)

class ValidatorAgent:
    """
    For .py files: check syntax (ast.parse), run flake8 and pylint (via subprocess).
    For other files: basic checks (e.g., non-empty).
    """

    def __init__(self):
        self.python = sys.executable  # use current python interpreter to run flake8/pylint

    def _run_flake8(self, source: str, hint: str) -> Tuple[int, List[str], str]:
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, hint)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(source)
            try:
                proc = subprocess.run([self.python, "-m", "flake8", p, "--format=%(row)d:%(col)d:%(code)s:%(text)s"], capture_output=True, text=True)
                out = proc.stdout.strip()
                lines = [l for l in out.splitlines() if l.strip()]
                return proc.returncode, lines, proc.stderr.strip()
            except FileNotFoundError:
                return 0, [], "flake8 not installed"

    def _run_pylint(self, source: str, hint: str) -> Tuple[int, Any, str]:
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, hint)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(source)
            try:
                proc = subprocess.run([self.python, "-m", "pylint", p, "--output-format=json", "--score=n"], capture_output=True, text=True, timeout=60)
                out = proc.stdout.strip()
                items = []
                if out:
                    try:
                        items = json.loads(out)
                    except json.JSONDecodeError:
                        items = [{"raw": out}]
                return proc.returncode, items, proc.stderr.strip()
            except FileNotFoundError:
                return 0, [], "pylint not installed"
            except Exception as e:
                log.exception("pylint run error")
                return 1, [], str(e)

    def _py_syntax_check(self, source: str) -> Tuple[bool, str]:
        try:
            ast.parse(source)
            return True, ""
        except SyntaxError as e:
            return False, f"{e.msg} at line {e.lineno}:{e.offset}"

    def run(self, files: Dict[str, str]) -> Dict[str, Any]:
        validations: Dict[str, Any] = {}
        for path, content in files.items():
            rec = {"lines": len(content.splitlines()), "chars": len(content)}
            if path.lower().endswith(".py"):
                ok, err = self._py_syntax_check(content)
                rec["syntax_ok"] = ok
                if not ok:
                    rec["syntax_error"] = err
                rc_f8, f8_lines, f8_err = self._run_flake8(content, path.replace("/", "_"))
                rec["flake8_returncode"] = rc_f8
                rec["flake8_issues"] = f8_lines
                if f8_err:
                    rec["flake8_stderr"] = f8_err
                rc_pl, pl_items, pl_err = self._run_pylint(content, path.replace("/", "_"))
                rec["pylint_returncode"] = rc_pl
                rec["pylint_issues"] = pl_items
                if pl_err:
                    rec["pylint_stderr"] = pl_err
            else:
                # generic basic check for text files
                rec["note"] = "non-python file; basic metadata only"
            validations[path] = rec
        return {"status": "ok", "validations": validations}
