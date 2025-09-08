# agents/authenticator.py
import logging
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse
import os

from github import Github

log = logging.getLogger(__name__)

class AuthenticatorAgent:
    """
    Parse repo URL (or owner/repo), optionally use a token for private repos,
    return owner, repo, branch, and list of file paths (not contents).
    """

    DEFAULT_EXTENSIONS = (
        ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
        ".js", ".ts", ".java", ".cpp", ".c", ".h", ".html", ".css"
    )

    def __init__(self, token: Optional[str] = None):
        token = token or os.getenv("GITHUB_TOKEN")
        if token:
            self.gh = Github(token)
        else:
            self.gh = Github()  # unauthenticated (rate limited for public repos)
        self.token = token

    @staticmethod
    def parse_repo_url(repo_url: str) -> Tuple[str, str]:
        """
        Accepts:
          - https://github.com/owner/repo.git
          - https://github.com/owner/repo
          - owner/repo
        Returns (owner, repo)
        """
        repo_url = repo_url.strip()
        if "/" in repo_url and not repo_url.startswith("http"):
            # owner/repo
            parts = repo_url.split("/")
            if len(parts) >= 2:
                return parts[0], parts[1]
        # parse possible https URL
        parsed = urlparse(repo_url)
        path = parsed.path.lstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        parts = path.split("/")
        if len(parts) < 2:
            raise ValueError("Could not parse repository owner/name from URL.")
        return parts[0], parts[1]

    def list_files(self, repo_url: str, branch: Optional[str] = None, include_ext: Optional[List[str]] = None, max_files: int = 400) -> Dict[str, Any]:
        owner, repo = self.parse_repo_url(repo_url)
        include = tuple(include_ext) if include_ext else self.DEFAULT_EXTENSIONS
        try:
            repo_obj = self.gh.get_repo(f"{owner}/{repo}")
            if branch is None:
                branch = repo_obj.default_branch
            contents = repo_obj.get_contents("", ref=branch)
            all_paths = []
            while contents:
                item = contents.pop(0)
                if item.type == "dir":
                    contents.extend(repo_obj.get_contents(item.path, ref=branch))
                else:
                    p = item.path
                    if p.lower().endswith(include):
                        all_paths.append(p)
                    # safety cap
                    if len(all_paths) >= max_files:
                        break
            return {
                "status": "ok",
                "owner": owner,
                "repo": repo,
                "repo_full_name": f"{owner}/{repo}",
                "branch": branch,
                "file_paths": all_paths,
                "file_count": len(all_paths)
            }
        except Exception as e:
            log.exception("AuthAgent error")
            return {"status": "error", "error": str(e)}
