"""The issue forms for misses and false alarms stay valid, ask for what a report needs,
warn people off pasting secrets, and don't trip lookfirst's own checks."""

from __future__ import annotations

import shutil
from pathlib import Path

import httpx
import pytest
import yaml

from lookfirst.core import http as lf_http
from lookfirst.pipeline import run_check

ROOT = Path(__file__).parent.parent
FORMS_DIR = ROOT / ".github" / "ISSUE_TEMPLATE"
FORMS = [FORMS_DIR / "missed.yml", FORMS_DIR / "false-alarm.yml"]
REPO_FILES = "https://github.com/lookfirst-dev/lookfirst/blob/main/"
FIELD_TYPES = {"markdown", "input", "textarea", "dropdown", "checkboxes"}


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


@pytest.mark.parametrize("path", FORMS, ids=lambda p: p.name)
def test_each_form_has_the_shape_github_expects(path: Path) -> None:
    form = load(path)
    assert {"name", "description", "body"} <= form.keys()
    ids = [field["id"] for field in form["body"] if "id" in field]
    assert len(ids) == len(set(ids)), "field ids must be unique"
    for field in form["body"]:
        assert field["type"] in FIELD_TYPES
        if field["type"] == "dropdown":
            assert all(isinstance(o, str) for o in field["attributes"]["options"])  # not booleans


@pytest.mark.parametrize("path", FORMS, ids=lambda p: p.name)
def test_each_form_requires_the_target_verdict_and_version(path: Path) -> None:
    required = {
        field["id"] for field in load(path)["body"] if field.get("validations", {}).get("required")
    }
    assert {"target", "verdict", "sandbox", "version"} <= required


def test_the_verdict_choices_match_each_kind_of_report() -> None:
    def options(path: Path) -> list[str]:
        field = next(f for f in load(path)["body"] if f.get("id") == "verdict")
        return field["attributes"]["options"]

    assert options(FORMS_DIR / "missed.yml") == ["Looks OK", "Caution"]
    assert options(FORMS_DIR / "false-alarm.yml") == ["Caution", "Don't run"]


@pytest.mark.parametrize("path", FORMS, ids=lambda p: p.name)
def test_each_form_warns_against_pasting_secrets(path: Path) -> None:
    assert "don't paste tokens, passwords or personal data" in path.read_text().lower()


def test_the_miss_form_asks_for_no_harmful_code_and_no_accusations() -> None:
    text = (FORMS_DIR / "missed.yml").read_text()
    assert "Don't paste harmful code." in text
    assert "rather than calling it malware" in text


def test_the_chooser_links_to_files_in_the_repo() -> None:
    config = load(FORMS_DIR / "config.yml")
    for link in config["contact_links"]:
        assert link["url"].startswith(REPO_FILES)
        assert (ROOT / link["url"].removeprefix(REPO_FILES)).exists()


def test_lookfirst_finds_nothing_in_its_own_issue_forms(tmp_path: Path, monkeypatch) -> None:
    def no_network(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"checking a folder shouldn't reach {request.url}")

    monkeypatch.setattr(lf_http, "_TRANSPORT", httpx.MockTransport(no_network))
    repo = tmp_path / "repo"
    shutil.copytree(FORMS_DIR, repo / ".github" / "ISSUE_TEMPLATE")
    report = run_check(str(repo), cwd=tmp_path)
    assert report.verdict == "looks_ok", [f.id for f in report.findings]


def test_the_chooser_sends_security_flaws_to_the_private_policy() -> None:
    urls = [link["url"] for link in load(FORMS_DIR / "config.yml")["contact_links"]]
    assert REPO_FILES + "SECURITY.md" in urls


def test_the_security_policy_points_at_private_reporting_not_public_issues() -> None:
    text = (ROOT / "SECURITY.md").read_text()
    assert "https://github.com/lookfirst-dev/lookfirst/security/advisories/new" in text
    assert "don't open a public issue" in text
    assert "@" not in text  # no email address to leak or to spam
    assert "Please don't send real malware." in text
