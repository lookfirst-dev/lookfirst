"""Big repos: GitHub's list of files, and which files lookfirst picks to read."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from lookfirst.core.config import DEFAULT_LIMITS
from lookfirst.core.errors import FetchError
from lookfirst.core.http import make_client
from lookfirst.targets.github_tree import (
    RepoTree,
    TreeFile,
    download_files,
    list_files,
    pick_files,
)

SHA = "a" * 40
SUB = "b" * 40


def blob(path: str, size: int = 10, mode: str = "100644") -> dict:
    return {"path": path, "mode": mode, "type": "blob", "sha": "c" * 40, "size": size}


def folder(path: str, sha: str = SUB) -> dict:
    return {"path": path, "mode": "040000", "type": "tree", "sha": sha}


def serve(mock_http, answers: dict[str, dict]) -> list[httpx.Request]:
    def handler(request: httpx.Request) -> httpx.Response:
        key = request.url.path.rsplit("/", 1)[-1] + (
            "?recursive" if request.url.params.get("recursive") else ""
        )
        return httpx.Response(200, json=answers[key])

    return mock_http(handler)


def listed(mock_http, answers: dict[str, dict]) -> tuple[RepoTree, list[httpx.Request]]:
    sent = serve(mock_http, answers)
    with make_client() as client:
        return list_files(client, "octo/big", SHA, DEFAULT_LIMITS), sent


def test_a_complete_list(mock_http) -> None:
    entries = [
        blob("README.md"),
        folder("src"),
        blob("src/app.js", 99),
        blob("bin/run", mode="100755"),
        blob("latest", mode="120000"),
        {"path": "deps/lib", "mode": "160000", "type": "commit", "sha": "d" * 40},
    ]
    tree, sent = listed(mock_http, {f"{SHA}?recursive": {"tree": entries, "truncated": False}})
    assert tree.files == [
        TreeFile("README.md", 10),
        TreeFile("src/app.js", 99),
        TreeFile("bin/run", 10, 0o755),
    ]
    assert tree.links == ["latest"]  # recorded, never followed
    assert tree.complete
    assert len(sent) == 1
    assert all(r.url.host == "api.github.com" for r in sent)


@pytest.mark.parametrize("path", ["../escape.sh", "/etc/passwd", "a/../../b", "", "x\x00y"])
def test_unsafe_paths_are_set_aside(mock_http, path: str) -> None:
    answers = {f"{SHA}?recursive": {"tree": [blob(path), blob("ok.txt")]}}
    tree, _ = listed(mock_http, answers)
    assert [f.path for f in tree.files] == ["ok.txt"]
    assert len(tree.skipped) == 1


def test_a_list_cut_short_is_listed_folder_by_folder(mock_http) -> None:
    answers = {
        f"{SHA}?recursive": {"tree": [blob("a.txt")], "truncated": True},
        SHA: {
            "tree": [
                blob("README.md"),
                folder("src", "e" * 40),
                folder(".claude", SUB),
                folder("test", "f" * 40),
            ]
        },
        f"{SUB}?recursive": {"tree": [folder("skills"), blob("skills/x/SKILL.md")]},
        f"{'e' * 40}?recursive": {"tree": [blob("pkg/package.json")]},
        f"{'f' * 40}?recursive": {"tree": [blob("t1.js")], "truncated": True},
    }
    tree, sent = listed(mock_http, answers)
    assert [f.path for f in tree.files] == [
        "README.md",
        ".claude/skills/x/SKILL.md",  # agent folders are listed first
        "src/pkg/package.json",
        "test/t1.js",
    ]
    assert tree.incomplete == ["test"]  # GitHub cut this one short too
    assert not tree.complete
    assert len(sent) == 5


def test_folder_lists_are_capped(mock_http, monkeypatch) -> None:
    from lookfirst.targets import github_tree

    monkeypatch.setattr(github_tree, "MAX_FOLDER_LISTS", 1)
    answers = {
        f"{SHA}?recursive": {"tree": [], "truncated": True},
        SHA: {"tree": [folder("a", SUB), folder("b", "e" * 40)]},
        f"{SUB}?recursive": {"tree": [blob("x.txt")]},
    }
    tree, sent = listed(mock_http, answers)
    assert [f.path for f in tree.files] == ["a/x.txt"]
    assert tree.incomplete == ["b"]
    assert len(sent) == 3


def test_an_odd_answer_gives_an_empty_list(mock_http) -> None:
    tree, _ = listed(mock_http, {f"{SHA}?recursive": {"tree": "nope"}})
    assert tree.files == []


def files(*paths: str, size: int = 10) -> RepoTree:
    return RepoTree(files=[TreeFile(p, size) for p in paths])


def test_picks_the_files_that_decide_the_verdict() -> None:
    tree = files(
        "README.md",
        "package.json",
        ".github/workflows/ci.yml",
        ".claude/settings.json",
        ".agents/skills/triage/SKILL.md",
        "docs/AGENTS.md",
        "tools/install-deps.sh",
        "packages/web/package.json",
        "services/api/requirements-dev.txt",
        "crates/core/Cargo.toml",
        "src/index.js",
        "docs/guide.md",
        "node_modules/left-pad/package.json",
        "examples/vendor/x/package.json",
        "test/fixtures/build/setup.sh",  # in a build folder, which the checks skip
    )
    picked = pick_files(tree)
    assert [f.path for f in picked.files] == [
        "README.md",
        "package.json",
        ".claude/settings.json",
        ".github/workflows/ci.yml",
        ".agents/skills/triage/SKILL.md",
        "docs/AGENTS.md",
        "tools/install-deps.sh",
        "crates/core/Cargo.toml",
        "packages/web/package.json",
        "services/api/requirements-dev.txt",
    ]
    assert picked.left_out == 0


def test_the_caps_keep_the_most_important_files() -> None:
    tree = files("pkg/a/package.json", "pkg/b/package.json", "install.sh", ".claude/x.md")
    picked = pick_files(tree, max_files=2)
    assert [f.path for f in picked.files] == ["install.sh", ".claude/x.md"]
    assert picked.left_out == 2


def test_package_files_in_tests_and_examples_come_last() -> None:
    tree = files("test/fixtures/a/package.json", "examples/demo/package.json", "pkg/b/package.json")
    picked = pick_files(tree, max_files=2)
    assert [f.path for f in picked.files] == ["pkg/b/package.json", "examples/demo/package.json"]


def test_the_size_caps() -> None:
    tree = RepoTree(
        files=[TreeFile("huge.bin", 50), TreeFile("README.md", 10), TreeFile("go.mod", 10)]
    )
    picked = pick_files(tree, max_file_bytes=40, max_bytes=15)
    assert [f.path for f in picked.files] == ["README.md"]
    assert picked.total_bytes == 10
    assert picked.left_out == 2


# --- downloading the picked files ----------------------------------------------------

BODIES = {
    "README.md": b"# Big\n",
    "install.sh": b"echo hi\n",
    ".claude/settings.json": b"{}\n",
}


def fetched(
    mock_http,
    tmp_path: Path,
    tree: RepoTree,
    *,
    private: bool = False,
    token: str | None = None,
    bodies: dict[str, bytes] = BODIES,
    status: int = 200,
):
    def handler(request: httpx.Request) -> httpx.Response:
        if private:
            path = request.url.path.split("/contents/", 1)[1]
        else:
            path = request.url.path.split(f"/{SHA}/", 1)[1]
        body = bodies.get(path)
        return httpx.Response(404 if body is None else status, content=body or b"")

    sent = mock_http(handler)
    with make_client(token=token) as client:
        manifest = download_files(
            client,
            "octo/big",
            SHA,
            tree,
            pick_files(tree),
            tmp_path / "src",
            private=private,
            limits=DEFAULT_LIMITS,
        )
    return manifest, sent


def tree_of(sizes: dict[str, int]) -> RepoTree:
    return RepoTree(files=[TreeFile(p, n) for p, n in sizes.items()])


def test_public_files_come_from_raw_without_the_token(mock_http, tmp_path: Path) -> None:
    tree = RepoTree(files=[TreeFile(p, len(b)) for p, b in BODIES.items()], links=["latest"])
    bodies = {**BODIES, "latest": b"../../etc"}
    manifest, sent = fetched(mock_http, tmp_path, tree, token="t0ken", bodies=bodies)
    assert (tmp_path / "src" / "install.sh").read_bytes() == b"echo hi\n"
    assert sorted(f.path for f in manifest.files) == sorted(BODIES)
    assert [(link.path, link.target) for link in manifest.links] == [("latest", "../../etc")]
    assert not (tmp_path / "src" / "latest").exists()  # a link is read, never made
    assert {r.url.host for r in sent} == {"raw.githubusercontent.com"}
    assert all("authorization" not in r.headers for r in sent)
    assert all(f"/octo/big/{SHA}/" in r.url.path for r in sent)  # the exact commit


def test_private_files_come_from_the_api_with_the_token(mock_http, tmp_path: Path) -> None:
    manifest, sent = fetched(
        mock_http, tmp_path, tree_of({"README.md": 6}), private=True, token="t0ken"
    )
    assert [f.path for f in manifest.files] == ["README.md"]
    assert [r.url.host for r in sent] == ["api.github.com"]
    assert sent[0].headers["authorization"] == "Bearer t0ken"
    assert sent[0].url.params["ref"] == SHA


def test_a_file_larger_than_listed_is_not_kept(mock_http, tmp_path: Path) -> None:
    tree = tree_of({"README.md": 6, "install.sh": 3, ".claude/settings.json": 3})
    manifest, _ = fetched(mock_http, tmp_path, tree)
    assert [f.path for f in manifest.files] == ["README.md", ".claude/settings.json"]
    assert {e.path: e.reason for e in manifest.skipped} == {
        "install.sh": "differs in size from GitHub's list",
    }
    assert not (tmp_path / "src" / "install.sh").exists()


def test_a_file_far_larger_than_listed_stops_downloading(mock_http, tmp_path: Path) -> None:
    big = b"x" * (200 * 1024)
    manifest, _ = fetched(
        mock_http,
        tmp_path,
        tree_of({"README.md": 6, "go.mod": 10}),
        bodies={**BODIES, "go.mod": big},
    )
    assert {e.path: e.reason for e in manifest.skipped} == {"go.mod": "couldn't be downloaded"}
    assert not (tmp_path / "src" / "go.mod").exists()


def test_tiny_files_that_arrive_compressed_are_kept(mock_http, tmp_path: Path) -> None:
    """Compression makes a tiny file larger than the file itself on the way."""
    import gzip

    def handler(request: httpx.Request) -> httpx.Response:
        packed = gzip.compress(b"{}\n")
        return httpx.Response(200, content=packed, headers={"content-encoding": "gzip"})

    mock_http(handler)
    tree = tree_of({".npmrc": 3})
    with make_client() as client:
        manifest = download_files(
            client,
            "octo/big",
            SHA,
            tree,
            pick_files(tree),
            tmp_path,
            private=False,
            limits=DEFAULT_LIMITS,
        )
    assert [f.path for f in manifest.files] == [".npmrc"]
    assert (tmp_path / ".npmrc").read_bytes() == b"{}\n"


def test_a_file_smaller_than_listed_is_not_kept(mock_http, tmp_path: Path) -> None:
    manifest, _ = fetched(mock_http, tmp_path, tree_of({"README.md": 60, "install.sh": 8}))
    assert [f.path for f in manifest.files] == ["install.sh"]
    assert manifest.skipped[0].reason == "differs in size from GitHub's list"
    assert not (tmp_path / "src" / "README.md").exists()  # never read by the checks


def test_when_no_file_arrives_the_check_stops(mock_http, tmp_path: Path) -> None:
    with pytest.raises(FetchError, match="most of the files"):
        fetched(mock_http, tmp_path, tree_of({"README.md": 60}))


def test_names_that_differ_only_in_case_are_kept_once(mock_http, tmp_path: Path) -> None:
    tree = tree_of({"README.md": 6, "readme.md": 6})
    manifest, sent = fetched(mock_http, tmp_path, tree)
    assert [f.path for f in manifest.files] == ["README.md"]
    assert "letter case" in manifest.skipped[0].reason
    assert len(sent) == 1


def test_unsafe_paths_from_the_list_are_reported(mock_http, tmp_path: Path) -> None:
    answers = {f"{SHA}?recursive": {"tree": [blob("../escape.sh"), blob("README.md", 6)]}}
    tree, _ = listed(mock_http, answers)
    manifest, _ = fetched(mock_http, tmp_path, tree)
    assert [e.path for e in manifest.skipped] == ["../escape.sh"]
    assert "outside" in manifest.skipped[0].reason  # read as install_path.escaping_archive_path


def test_when_most_files_fail_the_check_stops(mock_http, tmp_path: Path) -> None:
    tree = tree_of({"README.md": 6, "install.sh": 8, "go.mod": 4})
    with pytest.raises(FetchError, match="most of the files"):
        fetched(mock_http, tmp_path, tree, status=500)


def test_a_used_up_rate_limit_stops_the_check(mock_http, tmp_path: Path) -> None:
    mock_http(lambda request: httpx.Response(403, headers={"x-ratelimit-remaining": "0"}))
    tree = tree_of({"README.md": 6})
    with make_client() as client, pytest.raises(FetchError, match="limit on requests"):
        download_files(
            client,
            "octo/big",
            SHA,
            tree,
            pick_files(tree),
            tmp_path,
            private=True,
            limits=DEFAULT_LIMITS,
        )
