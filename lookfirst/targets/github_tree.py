"""For repos too big to download whole: list the files of one commit through GitHub's API,
and pick the ones that decide the verdict (docs/PLAN-v0.3.md).

Everything here is untrusted data from GitHub: paths go through the same checks as archive
entries, links are recorded and never followed, and submodules are skipped.
"""

from __future__ import annotations

import contextlib
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from urllib.parse import quote

import httpx

from lookfirst.core.archive import (
    ArchiveFile,
    ArchiveLink,
    ArchiveManifest,
    SkippedEntry,
    safe_relpath,
)
from lookfirst.core.config import MB, Limits
from lookfirst.core.errors import FetchError
from lookfirst.core.http import download, fetch, get_json
from lookfirst.static.files import SKIP_DIRS

API = "https://api.github.com"
_API_HOSTS = frozenset({"api.github.com"})
_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
_SHA = re.compile(r"^[0-9a-f]{40}$")
_FILE_MODES = {"100644": 0o644, "100755": 0o755}
_LINK_MODE = "120000"
_RAW = "https://raw.githubusercontent.com"
_RAW_HOSTS = frozenset({"raw.githubusercontent.com"})
_RAW_API_HEADERS = {"Accept": "application/vnd.github.raw", "X-GitHub-Api-Version": "2022-11-28"}
# The same words the archive reader uses, so the install-path checks report them alike.
OUTSIDE = "path points outside the archive's folder"

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
    mode: int = 0o644


@dataclass
class RepoTree:
    """The files of one commit. GitHub cuts very long lists short; then incomplete names the
    top-level folders that couldn't be listed in full."""

    files: list[TreeFile] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    skipped: list[SkippedEntry] = field(default_factory=list)  # unsafe or odd, not used
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
            tree.skipped.append(SkippedEntry(str(name)[:200], OUTSIDE))
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
            tree.skipped.append(SkippedEntry(str(raw)[:200], OUTSIDE))
            continue
        mode, size = entry.get("mode"), entry.get("size")
        if mode == _LINK_MODE:
            tree.links.append(rel)
        elif mode in _FILE_MODES and isinstance(size, int) and size >= 0:
            tree.files.append(TreeFile(rel, size, _FILE_MODES[mode]))
        else:
            tree.skipped.append(SkippedEntry(rel, "not a regular file in GitHub's list"))
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


MAX_LINKS = 200
_WORKERS = 8
_SLACK = 64 * 1024


def download_files(
    client: httpx.Client,
    full_name: str,
    sha: str,
    tree: RepoTree,
    picked: Picked,
    dest: Path,
    *,
    private: bool,
    limits: Limits,
) -> ArchiveManifest:
    """Download the picked files of commit sha into dest, and read where links point.
    Public repos come from raw.githubusercontent.com, which never gets a token; private ones
    from api.github.com. Each file may be no larger than GitHub's list said."""
    if not _SHA.match(sha):
        raise ValueError("download_files needs a full commit sha")
    dest.mkdir(parents=True, exist_ok=True)
    manifest = ArchiveManifest(skipped=list(tree.skipped))
    wanted: list[TreeFile] = []
    for f in picked.files:
        other = manifest._by_casefold.get(f.path.casefold())
        if other is not None:
            # On a Mac's default disk these two names would be the same file.
            manifest.skip(f.path, f"name differs from {other[:200]} only in letter case")
            continue
        manifest._by_casefold[f.path.casefold()] = f.path
        wanted.append(f)

    def one(f: TreeFile) -> str | None:
        """None when the file arrived, otherwise why it didn't."""
        target = dest.joinpath(*f.path.split("/"))
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            got = download(
                client,
                _url(full_name, sha, f.path, private=private),
                target,
                allowed_hosts=_API_HOSTS if private else _RAW_HOSTS,
                headers=_RAW_API_HEADERS if private else None,
                what=f"{f.path[:200]} in {full_name}",
                # Room for compression, which makes tiny files larger; the size must still
                # match GitHub's list exactly once unpacked.
                limits=replace(limits, max_download_bytes=f.size + _SLACK),
            )
        except FetchError as exc:
            target.unlink(missing_ok=True)
            if "limit on requests" in str(exc):
                raise
            return "couldn't be downloaded"
        except OSError:
            with contextlib.suppress(OSError):
                target.unlink(missing_ok=True)
            return "clashes with a folder or file of the same name"
        if got.size != f.size:
            target.unlink(missing_ok=True)
            return "differs in size from GitHub's list"
        return None

    with ThreadPoolExecutor(_WORKERS) as pool:
        results = list(pool.map(one, wanted))
    failed = 0
    for f, problem in zip(wanted, results, strict=True):
        if problem is None:
            manifest.files.append(ArchiveFile(f.path, f.size, f.mode))
            manifest.total_bytes += f.size
        else:
            failed += 1
            manifest.skip(f.path, problem)
    if wanted and (not manifest.files or (failed >= 3 and failed * 2 > len(wanted))):
        raise FetchError(f"Couldn't download most of the files picked from {full_name}.")

    with ThreadPoolExecutor(_WORKERS) as pool:
        targets = list(
            pool.map(
                lambda rel: _link_target(client, full_name, sha, rel, private, limits),
                tree.links[:MAX_LINKS],
            )
        )
    for rel, link_target in zip(tree.links[:MAX_LINKS], targets, strict=True):
        if link_target is None:
            manifest.skip(rel, "a link whose target couldn't be read")
        else:
            manifest.links.append(ArchiveLink(rel, link_target, "symlink"))
    return manifest


def _url(full_name: str, sha: str, path: str, *, private: bool) -> str:
    quoted = quote(path, safe="/")
    if private:
        return f"{API}/repos/{full_name}/contents/{quoted}?ref={sha}"
    return f"{_RAW}/{full_name}/{sha}/{quoted}"


def _link_target(
    client: httpx.Client, full_name: str, sha: str, rel: str, private: bool, limits: Limits
) -> str | None:
    """Where a link points: the text git stores for it, read and never followed."""
    try:
        got = fetch(
            client,
            _url(full_name, sha, rel, private=private),
            allowed_hosts=_API_HOSTS if private else _RAW_HOSTS,
            headers=_RAW_API_HEADERS if private else None,
            what=f"the link {rel[:200]}",
            max_bytes=4096,
            limits=limits,
        )
    except FetchError:
        return None
    if got.status != 200:
        return None
    return got.content.decode("utf-8", "replace")
