# agents/fetcher.py
import logging
from typing import Dict, Any, List, Optional
import os

from github import Github

log = logging.getLogger(__name__)

class FetcherAgent:
    """
    Fetch file contents (text files) using PyGithub. Skips binaries and very large files.
    """

    BINARY_EXT = (".png", ".jpg", ".jpeg", ".gif", ".zip", ".tar.gz", ".gz", ".ico", ".pdf", ".exe", ".dll")
    MAX_BYTES = 200_000  # skip files larger than ~200 KB by default
    MAX_FILES = 200

    def __init__(self, token: Optional[str] = None):
        token = token or os.getenv("GITHUB_TOKEN")
        if token:
            self.gh = Github(token)
        else:
            self.gh = Github()

    def fetch(self, owner: str, repo: str, file_paths: List[str], branch: str, max_files: Optional[int] = None) -> Dict[str, Any]:
        repo_obj = self.gh.get_repo(f"{owner}/{repo}")
        file_contents: Dict[str, str] = {}
        details: Dict[str, Any] = {}
        count = 0
        max_files = max_files if max_files is not None else self.MAX_FILES

        for path in file_paths:
            if count >= max_files:
                details["skipped_by_limit"] = True
                break
            low = path.lower()
            if any(low.endswith(ext) for ext in self.BINARY_EXT):
                details[path] = {"skipped": "binary"}
                continue
            try:
                f = repo_obj.get_contents(path, ref=branch)
                raw = f.decoded_content
                size = len(raw)
                if size > self.MAX_BYTES:
                    details[path] = {"skipped": "too_large", "size_bytes": size}
                    continue
                try:
                    text = raw.decode("utf-8", errors="replace")
                except Exception:
                    text = raw.decode("latin-1", errors="replace")
                file_contents[path] = text
                details[path] = {"size_bytes": size, "fetched": True}
                count += 1
            except Exception as e:
                log.exception("fetch error for %s", path)
                details[path] = {"error": str(e)}
        return {"status": "ok", "files": file_contents, "details": details, "fetched_count": len(file_contents)}
