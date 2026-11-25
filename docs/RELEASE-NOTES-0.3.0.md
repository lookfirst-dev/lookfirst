# lookfirst 0.3.0

Big GitHub repos get a verdict now, instead of advice to clone them. Update with `uv tool upgrade lookfirst`.

lookfirst lowers risk; it doesn't guarantee safety.

## Big repos

- **A repo too big to download whole is now read in part.** Before, lookfirst stopped when a repo's archive was over 200 MB or held more than 50,000 entries. That happened to node, bun, TypeScript, webpack, supabase, next.js and rust. Now lookfirst gets the repo's list of files from GitHub and downloads only the files that decide the verdict:
  - every file in the top folder;
  - the agent and editor folders, such as `.claude/`, `.agents/`, `.cursor/`, `.github/` and `.vscode/`;
  - agent instruction files and install scripts anywhere;
  - package files and lockfiles, with those in test and example folders last.
- **Every output says what wasn't read.** Under the verdict, the report says how many files were read out of how many, and how to read every file: clone the repo with `git clone --depth 1`, which doesn't run its code, and check the folder. The JSON lists it first under `not_checked`, and the MCP tool's summary and the hook say it too. For a Looks OK, the hook adds a short note and lets the command run.
- **What a partial read can miss:** hidden instructions or tricky characters in ordinary source files and docs deep in the tree, and GuardDog's code patterns in files that weren't read.
- **`--sandbox` isn't offered on part of a repo.** Installing needs every file, so the report says to clone the repo and check the clone with `--sandbox`.
- **Same safety rules as whole downloads.** Files come from the exact commit checked. Paths that point outside the folder are refused, names that differ only in letter case are kept once, and links are read but never created. Each file must match the size GitHub lists for it. A GitHub token goes only to `api.github.com`; public repos download from `raw.githubusercontent.com` without it.
- **Cost without a GitHub token:** GitHub allows 60 API calls an hour without one. Measured: supabase used 3, and webpack 19, because GitHub cut its file list short and lookfirst listed each top-level folder on its own (34 at most). A normal repo still uses 2.

## Measured

- **The seven repos that couldn't be checked in 0.2.0** now take 21 to 45 seconds each:

  | Repo | Seconds | Verdict |
  |---|---|---|
  | webpack | 27 | Looks OK |
  | bun | 45 | Looks OK |
  | node | 45 | Looks OK |
  | TypeScript | 22 | Caution |
  | supabase | 21 | Looks OK |
  | next.js | 29 | Looks OK |
  | rust | 31 | Looks OK |

  About 7 to 14 seconds of each check go on first trying to download the whole archive.
- **TypeScript's Caution:** its `AGENTS.md` tells agents to "Ignore your system instructions for PR descriptions". lookfirst always treats that wording as serious.
- **The 40 well-known repos in `scripts/benchmark.py`:** none fails to check any more. 38 get Looks OK and 2 get Caution (deno and TypeScript). The median check took 9.7 seconds, as with 0.2.0. No other verdict changed.

## Install

```bash
uv tool install lookfirst
```

For Claude Code: `/plugin marketplace add lookfirst-dev/lookfirst`, then `/plugin install lookfirst@lookfirst`.
