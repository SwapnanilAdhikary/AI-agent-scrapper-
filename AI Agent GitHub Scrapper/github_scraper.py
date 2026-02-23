import re
import time
import base64
import requests

GITHUB_API = "https://api.github.com"

DEPENDENCY_FILES = {
    "Python": ["requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "Pipfile"],
    "JavaScript/TypeScript": ["package.json"],
    "Go": ["go.mod"],
    "Rust": ["Cargo.toml"],
    "Java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "Ruby": ["Gemfile"],
    "PHP": ["composer.json"],
    "C#": ["*.csproj"],  # handled specially
}

README_MAX_CHARS = 4000


def parse_repo_url(url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL."""
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]

    patterns = [
        r"github\.com/([^/]+)/([^/]+)",
        r"^([^/]+)/([^/]+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)

    raise ValueError(f"Could not parse GitHub URL: {url}")


def _api_get(endpoint: str, token: str | None = None) -> requests.Response:
    """Make a GitHub API GET request with rate-limit handling."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    max_retries = 3
    for attempt in range(max_retries):
        resp = requests.get(f"{GITHUB_API}{endpoint}", headers=headers, timeout=30)

        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
            wait = max(reset_time - int(time.time()), 5)
            wait = min(wait, 120)
            print(f"  [Rate limited] Waiting {wait}s before retry ({attempt + 1}/{max_retries})...")
            time.sleep(wait)
            continue

        return resp

    return resp


def fetch_repo_metadata(owner: str, repo: str, token: str | None = None) -> dict:
    """Fetch basic repository metadata."""
    resp = _api_get(f"/repos/{owner}/{repo}", token)
    if resp.status_code != 200:
        return {"error": f"Failed to fetch repo: HTTP {resp.status_code}"}

    data = resp.json()
    return {
        "name": data.get("name", ""),
        "full_name": data.get("full_name", ""),
        "description": data.get("description", ""),
        "language": data.get("language", ""),
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "open_issues": data.get("open_issues_count", 0),
        "topics": data.get("topics", []),
        "license": data.get("license", {}).get("spdx_id", "None") if data.get("license") else "None",
        "created_at": data.get("created_at", ""),
        "updated_at": data.get("updated_at", ""),
        "homepage": data.get("homepage", ""),
        "default_branch": data.get("default_branch", "main"),
    }


def fetch_file_content(owner: str, repo: str, path: str, token: str | None = None) -> str | None:
    """Fetch a single file's content from the repo, decoded from base64."""
    resp = _api_get(f"/repos/{owner}/{repo}/contents/{path}", token)
    if resp.status_code != 200:
        return None

    data = resp.json()
    if isinstance(data, list):
        return None

    encoding = data.get("encoding", "")
    content = data.get("content", "")

    if encoding == "base64" and content:
        try:
            return base64.b64decode(content).decode("utf-8", errors="replace")
        except Exception:
            return None
    return content or None


def fetch_root_file_list(owner: str, repo: str, token: str | None = None) -> list[str]:
    """Get the list of files in the repo root."""
    resp = _api_get(f"/repos/{owner}/{repo}/contents/", token)
    if resp.status_code != 200:
        return []

    data = resp.json()
    if not isinstance(data, list):
        return []

    return [item["name"] for item in data if item.get("type") == "file"]


def fetch_dependency_files(owner: str, repo: str, root_files: list[str], token: str | None = None) -> dict[str, str]:
    """Fetch all recognized dependency files from the repo root."""
    target_filenames = set()
    for files in DEPENDENCY_FILES.values():
        for f in files:
            if "*" not in f:
                target_filenames.add(f)

    found = {}
    for filename in root_files:
        if filename in target_filenames or filename.endswith(".csproj"):
            content = fetch_file_content(owner, repo, filename, token)
            if content:
                found[filename] = content[:3000]

    return found


def fetch_readme(owner: str, repo: str, token: str | None = None) -> str:
    """Fetch the README file, trying common names."""
    for name in ["README.md", "readme.md", "README.rst", "README.txt", "README"]:
        content = fetch_file_content(owner, repo, name, token)
        if content:
            return content[:README_MAX_CHARS]
    return ""


def scrape_repo(url: str, token: str | None = None) -> dict:
    """
    Main entry point: scrape all relevant data from a single GitHub repo.
    Returns a structured dict with metadata, dependencies, and README.
    """
    try:
        owner, repo = parse_repo_url(url)
    except ValueError as e:
        return {"url": url, "error": str(e)}

    print(f"  Scraping {owner}/{repo}...")

    metadata = fetch_repo_metadata(owner, repo, token)
    if "error" in metadata:
        return {"url": url, "owner": owner, "repo": repo, **metadata}

    root_files = fetch_root_file_list(owner, repo, token)
    dep_files = fetch_dependency_files(owner, repo, root_files, token)
    readme = fetch_readme(owner, repo, token)

    return {
        "url": url,
        "owner": owner,
        "repo": repo,
        "metadata": metadata,
        "dependency_files": dep_files,
        "root_files": root_files,
        "readme": readme,
    }
