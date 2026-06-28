import os
import requests
import base64
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".ts", ".java", ".go",
    ".cpp", ".c", ".cs", ".rb", ".php",
    ".rs", ".kt", ".swift"
}

MAX_FILES = int(os.getenv("MAX_FILES_PER_REPO", 150))


def parse_github_url(url: str) -> tuple[str, str]:
    url = url.rstrip("/").replace("https://github.com/", "")
    parts = url.split("/")
    if len(parts) < 2:
        raise ValueError(f"Invalid GitHub URL: {url}")
    return parts[0], parts[1]


def fetch_repo_files(repo_url: str, github_token: str = None) -> List[Dict]:
    owner, repo = parse_github_url(repo_url)
    token = github_token or os.getenv("GITHUB_TOKEN", "")

    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    response = requests.get(tree_url, headers=headers, timeout=30)

    if response.status_code == 404:
        raise ValueError(f"Repo not found or private: {owner}/{repo}")
    if response.status_code == 403:
        raise ValueError("GitHub rate limit hit. Add a GITHUB_TOKEN in .env")
    response.raise_for_status()

    tree = response.json().get("tree", [])

    code_files = [
        item for item in tree
        if item["type"] == "blob"
        and any(item["path"].endswith(ext) for ext in SUPPORTED_EXTENSIONS)
        and item.get("size", 0) < 100_000
    ]

    code_files = code_files[:MAX_FILES]

    files = []
    for item in code_files:
        try:
            content = fetch_file_content(owner, repo, item["path"], headers)
            if content:
                files.append({
                    "path": item["path"],
                    "content": content,
                    "size": item.get("size", 0)
                })
        except Exception:
            continue

    return files


def fetch_file_content(owner: str, repo: str, path: str, headers: dict) -> str:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        return ""
    data = response.json()
    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    return ""


def get_repo_metadata(repo_url: str, github_token: str = None) -> Dict:
    owner, repo = parse_github_url(repo_url)
    token = github_token or os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{owner}/{repo}"
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        return {"name": repo, "owner": owner, "stars": 0, "language": "Unknown"}

    data = response.json()
    return {
        "name": data.get("name", repo),
        "owner": owner,
        "full_name": data.get("full_name", f"{owner}/{repo}"),
        "stars": data.get("stargazers_count", 0),
        "language": data.get("language", "Unknown"),
        "description": data.get("description", ""),
        "topics": data.get("topics", []),
    }
