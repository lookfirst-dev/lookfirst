# lookfirst 0.1.1

Fixes found by trying lookfirst the way new users will: on its own repo, on well-known installers, packages and big repos. Update with `uv tool upgrade lookfirst`.

lookfirst lowers risk; it doesn't guarantee safety.

## Fewer false alarms

- **Prose about agents is no longer read as an instruction to one.** "Note for AI agents" now counts only as a label: at the start of a line or sentence, or followed by a colon or dash. A sentence such as "AGENTS.md holds instructions for AI agents" is left alone. This flagged lookfirst's own threat model.
- **Rules that make an agent ask first are no longer read as secrecy.** "Never rewrite commits without asking the user" and "don't ask the user to paste the context" are honest guidance. They gave VS Code a Caution. "Run the cleanup without asking the user" still counts.
- **A bare `curl | bash` in prose is no longer a download.** A `curl` or `wget` with nothing after it fetches nothing. It was flagged in lookfirst's own README tagline.

## Big repos

- **A repo too big to download or unpack now says what to do:** clone it with `git clone --depth 1`, which doesn't run its code, then check the folder. Before, the check just stopped.

## Dependencies

- **opentelemetry-api 1.45.2** (through the MCP library), which fixes a denial-of-service bug (GHSA-mf5v-w3w3-f6cg). The cooldown date for new dependency versions moved to 5 Nov 2026.

## Measured

- **The same 12 well-known repos as 0.1.0:** all Looks OK, 4 to 11 seconds each (median 5.0 s).
- **Well-known installers and packages:** the one-line installers for rustup, uv, Homebrew, bun, Ollama, Claude Code and Docker, and react, @anthropic-ai/claude-code and requests, all Looks OK, in 1 to 3 seconds.
- **microsoft/vscode:** Looks OK, where 0.1.0 said Caution, but it takes about 85 seconds.
- **lookfirst's own repo:** still Caution, and rightly: its test fixtures are fake attacks written for its tests.
- **Big repos** such as vercel/next.js (about 35,000 files) show the clone advice; checking the clone took 89 seconds.
- **Without a GitHub token,** a check uses 2 of GitHub's 60 requests an hour.

## Install

```bash
uv tool install lookfirst
```

For Claude Code: `/plugin marketplace add lookfirst-dev/lookfirst`, then `/plugin install lookfirst@lookfirst`.
