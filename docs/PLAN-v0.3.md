# Plan for 0.3.0: checking repos too big to download whole

Status: proposal, 24 Nov 2026. Nothing is built yet. The decisions marked **Owner decides** come first.

## The problem

lookfirst downloads a GitHub repo as one archive and stops if the archive is over 200 MB or holds more than 50,000 entries. In the 0.2.0 benchmark, 5 of 40 well-known repos stopped this way: webpack, bun, node, TypeScript and supabase. So did next.js and rust. Today the user gets advice to clone the repo and check the clone. That works, but many people won't do it, and an agent using the MCP tool or the hook can't.

## The idea: read the parts that matter

When the archive is too big, lookfirst asks GitHub for the repo's list of files and downloads only the files that decide the verdict.

1. **List the files.** One GitHub API call returns every path in the repo at the commit being checked, with each file's size and type. (Measured: node has 57,484 files, next.js 35,315, supabase 18,390.)
2. **Pick the files that matter**, by rules written in advance:
   - every file in the top folder (README, install scripts, Makefile, package manifests);
   - everything under the agent and editor folders: `.claude/`, `.agents/`, `.cursor/`, `.github/`, `.vscode/`, `.gemini/`, `.roo/`, `.windsurf/`, `.devcontainer/`;
   - agent instruction files anywhere: `SKILL.md`, `AGENTS.md`, `CLAUDE.md`;
   - package manifests and lockfiles anywhere (`package.json`, lockfiles, `pyproject.toml`, `setup.py`, `requirements*.txt`, `Cargo.toml`, `go.mod` and others), shallowest first;
   - install scripts anywhere (`install*.sh`, `setup*.sh`).
   Package files and scripts in test, example and benchmark folders come last; bun's `test` folder alone has about 4,900 `package.json` files.
   Measured with an early version of these rules: node 591 files, next.js 1,209, supabase 252, TypeScript 66.
3. **Download them**, at most 2,000 files and 100 MB, several at a time, from the same commit. Public repos download from `raw.githubusercontent.com`, which doesn't use up GitHub's hourly API limit. lookfirst never sends a token there. Private repos download through `api.github.com` with the user's token, as today.
4. **Run the usual checks** on that folder: agent settings, install paths, hidden instructions, the package scanners and identity.
5. **Say plainly what wasn't read.** The report adds a "not checked" line, for example: "Read 591 of 57,484 files: the top folder, agent settings, package files and install scripts. The rest of the code wasn't read." The text output shows it under the verdict, and so do the JSON, the MCP tool and the hook. This uses the existing `not_checked` field, so the JSON schema stays at 1.0.

What this misses: hidden instructions or tricky characters in ordinary source files and docs deep in the tree, and GuardDog's code patterns outside the files read. Those are exactly what the "not checked" line names.

## Owner decides

1. **The verdict on a partly read repo.**
   - **(Recommended) Keep the verdict, and always show the "not checked" line.** A big repo can still get Looks OK, but the line under it says what was skipped. The files most likely to hurt someone (install scripts, agent settings, manifests) are always read.
   - Never give Looks OK: a partly read repo gets Caution at best. This is safer to read, but then every big repo gets a Caution, which teaches people to ignore Caution.
2. **When to switch to partial reading.**
   - **(Recommended) Only after the full download fails.** Normal repos are unchanged and use no extra API calls. A too-big repo wastes 10 to 30 seconds on the failed download first.
   - Up front, when GitHub's figures say the repo is huge. This is faster for big repos, but the figure GitHub gives counts the full history, which predicts download size poorly.
3. **`--sandbox` on a partly read repo.** (Recommended) Not offered: the sandbox runs the install, which needs the whole repo. The report says to clone it and check the clone with `--sandbox`.

## Safety rules (from CLAUDE.md, unchanged)

- Nothing from the repo runs. Partial reading only downloads files and reads them.
- Paths from GitHub's file list go through the same checks as archive entries: nothing outside the folder, no names that differ only in letter case. Links are recorded, not followed, and submodules are skipped.
- A token goes only to `api.github.com`, never to `raw.githubusercontent.com`.
- The file list and every file are untrusted data, capped in count and size.
- If GitHub cuts the file list short (it does above about 100,000 entries or 7 MB), lookfirst lists the top folder, then each top-level folder on its own, agent folders first, up to 30 folders. Any folder still cut short is named in the "not checked" line.

## Work

1. **The file list and the picking rules,** with tests on recorded GitHub answers. Tests never use the network.
2. **Downloading the picked files** into a folder, with the caps, the host rules and the token rule. Tests use a local test server.
3. **Falling back** from the too-big error to partial reading, and the "not checked" line in all outputs: text, JSON, MCP and hook.
4. **Measuring:** the 40-repo benchmark plus next.js and rust. The goal is no "couldn't check" results, a check of a big repo in under 60 seconds, and no new Cautions on the 35 repos that fit today.
5. **Release 0.3.0** with release notes, as before.

Estimate: two to three working sessions, each ending in a pull request you merge.

## Progress

**Step 1 done (24 Nov 2026):** `lookfirst/targets/github_tree.py` lists the files and picks them, with 13 tests on made-up GitHub answers. It isn't used by `lookfirst check` yet. Measured on the seven big repos:

| Repo | Files listed | Picked | MB | Listing |
|---|---|---|---|---|
| webpack | 39,599 | 197 | 2.6 | `test` cut short |
| bun | 47,332 | 2,000 (3,252 left out, nearly all in `test`) | 2.6 | `test` cut short |
| node | 57,478 | 236 | 2.4 | complete |
| TypeScript | 53,107 | 66 | 0.5 | `tsc` cut short |
| supabase | 18,388 | 254 | 2.4 | complete |
| next.js | 35,160 | 960 | 9.0 | complete |
| rust | 64,874 | 530 | 2.7 | complete |

GitHub cut the whole list short for webpack, bun, TypeScript and rust, so the folder-by-folder fallback matters. It used 6 to 17 extra GitHub API calls on those repos, which takes about 6 to 11 seconds. Without a token, GitHub allows 60 calls an hour. A check of such a repo then uses 10 to 21 of them, and 34 at most, against 2 for a repo that downloads whole.

**Step 2 done (24 Nov 2026):** `download_files` downloads the picked files of the exact commit, eight at a time:
- Public repos come from `raw.githubusercontent.com`, which never gets the token. Private repos come from `api.github.com`.
- Each file must match the size in GitHub's list once unpacked, or it is deleted and listed as skipped.
- Names that differ only in letter case are kept once.
- Link targets are read as text, so the existing "link points outside" check works. Links are never made on disk.
- If no file arrives, or most fail, the check stops with an error rather than judging a near-empty folder.

Measured on the seven big repos, every picked file arrived:

| Repo | Listing | Downloading | Files |
|---|---|---|---|
| webpack | 7.6 s | 0.9 s | 197 |
| bun | 8.3 s | 8.1 s | 2,000 |
| node | 5.8 s | 4.4 s | 236 |
| TypeScript | 8.7 s | 1.2 s | 66 |
| supabase | 2.3 s | 3.8 s | 254 |
| next.js | 3.2 s | 16.3 s | 960 |
| rust | 8.8 s | 8.2 s | 530 |

A first run lost about 40% of webpack's files. GitHub compresses downloads, and a tiny compressed file is larger than the file itself, so the size cap refused it. The cap now allows 64 KB for compression, and a test covers it.
