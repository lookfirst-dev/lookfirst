"""The release setup stays consistent: one version everywhere, a release workflow that
matches the publisher PyPI trusts, pinned actions, and an npm pointer that runs nothing."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
RELEASE = WORKFLOWS / "release.yml"
NPM = ROOT / "npm"


def version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def workflow(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    data["on"] = data.pop(True, data.get("on"))  # YAML reads a bare `on:` key as true
    return data


def test_the_plugin_and_the_release_notes_match_the_package_version() -> None:
    plugin = json.loads((ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["version"] == version()
    assert (ROOT / "docs" / f"RELEASE-NOTES-{version()}.md").exists()


def test_the_release_workflow_matches_the_publisher_pypi_trusts() -> None:
    """PyPI trusts owner lookfirst-dev, repo lookfirst, workflow release.yml, environment pypi."""
    data = workflow(RELEASE)
    assert data["on"] == {"push": {"tags": ["v*"]}}
    publish = data["jobs"]["publish"]
    assert publish["environment"]["name"] == "pypi"
    assert publish["permissions"]["id-token"] == "write"
    assert "uv publish --trusted-publishing always" in str(publish["steps"])


def test_only_the_publish_job_can_ask_for_a_publishing_identity() -> None:
    data = workflow(RELEASE)
    assert data["permissions"] == {"contents": "read"}
    for name, job in data["jobs"].items():
        if name != "publish":
            assert "id-token" not in job.get("permissions", {}), name


def test_a_release_checks_the_tag_and_runs_the_tests_before_publishing() -> None:
    jobs = workflow(RELEASE)["jobs"]
    assert jobs["publish"]["needs"] == "check"
    steps = str(jobs["check"]["steps"])
    assert "uv version --short" in steps
    assert "RELEASE-NOTES-" in steps
    assert "uv run pytest" in steps


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_commit(path: Path) -> None:
    for line in path.read_text().splitlines():
        m = re.search(r"uses:\s*(\S+)", line)
        if m:
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", m.group(1)), line.strip()


def test_the_npm_pointer_installs_and_runs_nothing() -> None:
    package = json.loads((NPM / "package.json").read_text())
    assert package["name"] == "lookfirst"
    assert package["license"] == "Apache-2.0"
    assert "scripts" not in package  # no install scripts of any kind
    for key in ("dependencies", "optionalDependencies", "peerDependencies", "bundleDependencies"):
        assert key not in package, key
    assert set(package["files"]) == {"bin/lookfirst.js", "README.md"}
    assert package["bin"] == {"lookfirst": "bin/lookfirst.js"}
    script = (NPM / "bin" / "lookfirst.js").read_text()
    for risky in ("require(", "import ", "import(", "fetch(", "eval(", "Function("):
        assert risky not in script, risky  # it only prints a message
    assert "uv tool install lookfirst" in (NPM / "README.md").read_text()


def test_the_readme_names_the_npm_pointer_as_an_official_source() -> None:
    text = (ROOT / "README.md").read_text()
    assert "package on npm only points here and installs nothing" in text
