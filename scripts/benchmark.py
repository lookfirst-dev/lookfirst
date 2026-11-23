"""Check 40 well-known public repos and summarize the verdicts and times, to catch false
alarms and slow checks before a release.

    uv run python scripts/benchmark.py                        the 40 repos below
    uv run python scripts/benchmark.py owner/repo ...         just the repos you name
    uv run python scripts/benchmark.py --save before.json     also keep the results
    uv run python scripts/benchmark.py --compare before.json  show what changed since then

Every repo here is well known and presumed fine, so any verdict other than Looks OK is
worth a look: either a real risk worth explaining or a false alarm worth fixing. Uses the
network and your GitHub token if you have one, exactly like `lookfirst check`. Nothing is
run: the check only reads. The repos change over time, so compare runs made close together.
A full run takes about 15 minutes.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOS = [
    # JavaScript and TypeScript
    "facebook/react",
    "vuejs/core",
    "sveltejs/svelte",
    "angular/angular",
    "tailwindlabs/tailwindcss",
    "vitejs/vite",
    "webpack/webpack",
    "prettier/prettier",
    "eslint/eslint",
    "denoland/deno",
    "oven-sh/bun",
    "nodejs/node",
    "microsoft/TypeScript",
    "supabase/supabase",
    # Python
    "django/django",
    "pandas-dev/pandas",
    "numpy/numpy",
    "scikit-learn/scikit-learn",
    "huggingface/transformers",
    "langchain-ai/langchain",
    "openai/openai-python",
    "anthropics/anthropic-sdk-python",
    "pytorch/pytorch",
    "tiangolo/sqlmodel",
    # Go
    "golang/go",
    "kubernetes/kubernetes",
    "docker/compose",
    "hashicorp/terraform",
    "prometheus/prometheus",
    "traefik/traefik",
    "cli/cli",
    # Rust
    "rust-lang/rustup",
    "tokio-rs/tokio",
    "alacritty/alacritty",
    "starship/starship",
    "zed-industries/zed",
    # C and Ruby
    "neovim/neovim",
    "tmux/tmux",
    "jqlang/jq",
    "Homebrew/brew",
]


def check(repo: str) -> dict:
    lookfirst = ROOT / ".venv" / "bin" / "lookfirst"
    start = time.perf_counter()
    done = subprocess.run(  # noqa: S603
        [str(lookfirst), "check", repo, "--json"],
        capture_output=True,
        text=True,
        env={**os.environ, "NO_COLOR": "1"},
        check=False,
    )
    took = round(time.perf_counter() - start, 1)
    try:
        report = json.loads(done.stdout)
    except json.JSONDecodeError:
        lines = [line for line in done.stderr.splitlines() if line.strip()]
        error = (
            " ".join(line.strip() for line in lines[:2]).removeprefix("lookfirst: ")[:100]
            or "no output"
        )
        return {"repo": repo, "seconds": took, "verdict": "couldnt_check", "error": error}
    serious = sorted({f["id"] for f in report["findings"] if f["severity"] in ("critical", "high")})
    return {"repo": repo, "seconds": took, "verdict": report["verdict"], "serious": serious}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repos", nargs="*", help="owner/repo (default: the 40 repos)")
    parser.add_argument("--save", type=Path, help="write the results to this JSON file")
    parser.add_argument("--compare", type=Path, help="an earlier --save file to compare with")
    args = parser.parse_args()
    before = {}
    if args.compare:
        before = {r["repo"]: r for r in json.loads(args.compare.read_text())}

    results = []
    print(f"{'repo':32} {'seconds':>8}  verdict")
    for repo in args.repos or REPOS:
        result = check(repo)
        results.append(result)
        line = f"{repo:32} {result['seconds']:8.1f}  {result['verdict']}"
        if result.get("serious"):
            line += "  (" + ", ".join(result["serious"]) + ")"
        if result.get("error"):
            line += f"  {result['error']}"
        old = before.get(repo)
        if old:
            change = f"was {old['seconds']:.0f} s"
            if old["verdict"] != result["verdict"]:
                change += f", {old['verdict']}"
            line += f"  [{change}]"
        print(line, flush=True)

    if args.save:
        args.save.write_text(json.dumps(results, indent=1) + "\n")
    times = [r["seconds"] for r in results]
    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print("\n" + ", ".join(f"{n} {verdict}" for verdict, n in sorted(counts.items())))
    print(f"median {statistics.median(times):.1f} s, slowest {max(times):.1f} s")
    if before:
        both = [r for r in results if r["repo"] in before]
        if both:
            then = statistics.median(before[r["repo"]]["seconds"] for r in both)
            now = statistics.median(r["seconds"] for r in both)
            print(
                f"median for the {len(both)} repos in both runs: {then:.1f} s then, {now:.1f} s now"
            )
        changed = [r["repo"] for r in both if r["verdict"] != before[r["repo"]]["verdict"]]
        print("verdicts that changed:", ", ".join(changed) or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
