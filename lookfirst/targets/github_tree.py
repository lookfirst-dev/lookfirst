"""For repos too big to download whole: list the files of one commit through GitHub's API,
and pick the ones that decide the verdict (docs/PLAN-v0.3.md).

Everything here is untrusted data from GitHub: paths go through the same checks as archive
entries, links are recorded and never followed, and submodules are skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx

from lookfirst.core.archive import safe_relpath
from lookfirst.core.config import MB, Limits
from lookfirst.core.http import get_json
from lookfirst.static.files import SKIP_DIRS

API = "https://api.github.com"
_API_HOSTS = frozenset({"api.github.com"})
_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
_SHA = re.compile(r"^[0-9a-f]{40}$")
_FILE_MODES = ("100644", "100755")
_LINK_MODE = "120000"

# Read whole, wherever they are in the top folder: the folders agents and editors act on.
AGENT_FOLDERS = (
    ".agents",
    ".claude",
    ".cursor",
    ".devcontainer",
    ".gemini",
    ".github",
    ".roo",
    ".vscode",
    ".windsurf",
)
# Read wherever they are (outside dependency and build folders).
_AGENT_FILES = frozenset({"skill.md", "agents.md", "claude.md", "gemini.md", ".mcp.json"})
_MANIFESTS = frozenset(
    {
        "package.json",
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "bun.lock",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "pipfile",
        "pipfile.lock",
        "uv.lock",
        "poetry.lock",
        "pdm.lock",
        "cargo.toml",
        "cargo.lock",
        "go.mod",
        "go.sum",
        "gemfile",
        "gemfile.lock",
        "composer.json",
        "composer.lock",
    }
)
_REQUIREMENTS = re.compile(r"^requirements[\w.-]*\.(?:txt|in)$")
_SCRIPTS = re.compile(r"^(?:install|setup|bootstrap|get)[\w.-]*\.(?:sh|bash|ps1)$")
# Test, example and benchmark folders: their package files come last (bun has about 4,900).
_SAMPLES = re.compile(
    r"(?:^|/)(?:tests?|__tests__|specs?|fixtures|testdata|examples?|bench(?:marks?)?)/"
)

MAX_FILES = 2_000
MAX_BYTES = 100 * MB
MAX_FILE_BYTES = 20 * MB


@dataclass(frozen=True)
class TreeFile:
    path: str
    size: int


@dataclass
class RepoTree:
    """The files of one commit. GitHub cuts very long lists short; then incomplete names the
    top-level folders that couldn't be listed in full."""

    files: list[TreeFile] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # unsafe or odd paths, not used
    incomplete: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.incomplete

    def add(self, other: RepoTree) -> None:
        self.files += other.files
        self.links += other.links
        self.skipped += other.skipped


@dataclass(frozen=True)
class Picked:
    files: list[TreeFile]
    total_bytes: int
    left_out: int  # files the rules wanted but the caps didn't allow


MAX_FOLDER_LISTS = 30  # extra API calls when GitHub cuts the whole list short


def list_files(client: httpx.Client, full_name: str, sha: str, limits: Limits) -> RepoTree:
    """All files of the commit sha. If GitHub cuts the whole list short, list the top folder,
    then each top-level folder on its own (agent folders first), up to MAX_FOLDER_LISTS."""
    if not _SHA.match(sha):
        raise ValueError("list_files needs a full commit sha")
    whole = _tree(client, full_name, sha, recursive=True, limits=limits)
    if not whole.get("truncated"):
        return _collect(whole.get("tree"), prefix="")
    top = _tree(client, full_name, sha, recursive=False, limits=limits)
    tree = _collect(top.get("tree"), prefix="")
    folders = []
    entries = top.get("tree")
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or entry.get("type") != "tree":
            continue
        name, sub = entry.get("path"), entry.get("sha")
        if not isinstance(name, str) or safe_relpath(name) != name or "/" in name:
            tree.skipped.append(str(name)[:200])
        elif not (isinstance(sub, str) and _SHA.match(sub)):
            tree.incomplete.append(name)
        else:
            folders.append((name not in AGENT_FOLDERS, name, sub))
    for listed, (_, name, sub) in enumerate(sorted(folders)):
        if listed >= MAX_FOLDER_LISTS:
            tree.incomplete.append(name)
            continue
        part = _tree(client, full_name, sub, recursive=True, limits=limits)
        tree.add(_collect(part.get("tree"), prefix=f"{name}/"))
        if part.get("truncated"):
            tree.incomplete.append(name)
    return tree


def _tree(
    client: httpx.Client, full_name: str, sha: str, *, recursive: bool, limits: Limits
) -> dict:
    url = f"{API}/repos/{full_name}/git/trees/{quote(sha)}"
    data = get_json(
        client,
        url + ("?recursive=1" if recursive else ""),
        allowed_hosts=_API_HOSTS,
        headers=_HEADERS,
        what=f"The list of files in {full_name}",
        limits=limits,
    )
    return data if isinstance(data, dict) else {}


def _collect(entries: object, *, prefix: str) -> RepoTree:
    tree = RepoTree()
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or entry.get("type") != "blob":
            continue  # folders, and submodules ("commit"), which point outside the repo
        raw = entry.get("path")
        rel = safe_relpath(prefix + raw) if isinstance(raw, str) else None
        if rel is None:
            tree.skipped.append(str(raw)[:200])
            continue
        mode, size = entry.get("mode"), entry.get("size")
        if mode == _LINK_MODE:
            tree.links.append(rel)
        elif mode in _FILE_MODES and isinstance(size, int) and size >= 0:
            tree.files.append(TreeFile(rel, size))
        else:
            tree.skipped.append(rel)
    return tree


def _rank(path: str) -> int | None:
    """How much a file matters for the verdict, lower first; None if it isn't read."""
    parts = path.split("/")
    name = parts[-1].lower()
    if len(parts) == 1:
        return 0  # the top folder: README, install scripts, manifests, config
    if parts[0] in AGENT_FOLDERS:
        return 1
    if any(p in SKIP_DIRS for p in parts[:-1]):
        return None  # dependency and build folders, which lookfirst's checks skip too
    if name in _AGENT_FILES:
        rank = 2
    elif _SCRIPTS.match(name):
        rank = 3
    elif name in _MANIFESTS or _REQUIREMENTS.match(name):
        rank = 4
    else:
        return None
    return 5 if _SAMPLES.search(path) else rank


def pick_files(
    tree: RepoTree,
    *,
    max_files: int = MAX_FILES,
    max_bytes: int = MAX_BYTES,
    max_file_bytes: int = MAX_FILE_BYTES,
) -> Picked:
    """The files that decide the verdict, most important first, shallowest first within
    each kind, within the caps."""
    wanted = []
    for f in tree.files:
        rank = _rank(f.path)
        if rank is not None:
            wanted.append((rank, f.path.count("/"), f.path, f))
    wanted.sort(key=lambda w: w[:3])
    chosen: list[TreeFile] = []
    total = left_out = 0
    for *_, f in wanted:
        if f.size > max_file_bytes or len(chosen) >= max_files or total + f.size > max_bytes:
            left_out += 1
            continue
        chosen.append(f)
        total += f.size
    return Picked(chosen, total, left_out)
