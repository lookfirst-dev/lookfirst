# The launch, and releasing later versions

Who does what: **you** are the owner; **Claude** is the coding agent working in this repo. Every step that publishes something or signs in to an account is yours.

## The launch (done 18 Nov 2026)

lookfirst 0.1.0 is out:

- **GitHub:** `lookfirst-dev/lookfirst` is public, with the release `v0.1.0`, the issue forms and the security policy. The org requires two-factor authentication. The old `RuikunWang506/preflight` is private and archived.
- **PyPI:** `lookfirst` 0.1.0, published by `.github/workflows/release.yml` through trusted publishing. The `pypi` environment makes every upload wait for your approval.
- **npm:** `lookfirst` 0.1.0, the pointer package from `npm/`. It installs and runs nothing.
- **The plugin:** installs from GitHub with `/plugin marketplace add lookfirst-dev/lookfirst`, then `/plugin install lookfirst@lookfirst`.

Released since: **0.1.1** (20 Nov) and **0.2.0** (23 Nov), each on PyPI and as a GitHub release; their notes are in `docs/RELEASE-NOTES-<version>.md`. The npm pointer stays at 0.1.0, since it only says how to install lookfirst.

Still to do: **announce** (you). The launch checklist in `docs/KICKOFF.md` has the channels and the timing advice. For the first 48 hours, answer every issue.

## Security reports

`SECURITY.md` asks people to report flaws in lookfirst privately through GitHub. For that to work, **Private vulnerability reporting** must be on: Settings, then Advanced Security (or Code security), then Private vulnerability reporting.

When a report arrives, GitHub emails you and it appears under the repo's Security tab. Reply within 7 days, as the policy promises. Fix it in the advisory's temporary private fork, so the fix isn't public before the release, then release a new version as below and publish the advisory.

## Recording the hook

Every live try so far ended with the agent reading the install code and refusing before the hook was needed (`docs/PLAN-v0.1.md`, M6 and M7). So the recording works best when the agent is told openly what's going on:

1. Open a Claude Code session in `~/code/lookfirst-demo`, where the plugin is on, and start a screen recording.
2. Ask plainly: "This is a demo of the lookfirst hook. Please run `npm install` in `csvplot/` so the hook can check it."
3. When the agent runs it, the hook blocks it, and the agent shows you lookfirst's evidence. That's the recording.

If the agent still won't run it, `docs/demo/hook.svg` already shows the exact answer Claude Code receives, and that's enough for launch.

Before recording, check that:

- `~/code/lookfirst-demo/csvplot` was cloned in the last 24 hours, since the hook only checks fresh clones. Re-clone it from `~/code/lookfirst-demo-origin/csvplot` if not.
- `~/LOOKFIRST_HOST_CANARY` doesn't exist.
- The installed `lookfirst` command is current: `uv tool install --editable ~/code/preflight --force`.

If the hook ever let it through, the fixture's script would only create the canary file and stop: it does nothing else outside the sandbox.

## Releasing a new version

1. Make the change on a branch, open a pull request, let CI pass, and merge, as for any change.
2. On a branch, set the new version in `pyproject.toml` and `plugin/.claude-plugin/plugin.json` (and `npm/package.json` only if the pointer itself changes), run `uv lock`, and add `docs/RELEASE-NOTES-<version>.md`. Raise the last number for fixes (0.2.0 to 0.2.1) and the middle one for new features (0.2.0 to 0.3.0). Merge it.
3. Tag `main` with `v<version>` and push the tag. The Release workflow starts. In the repo's Actions tab, open the "Release" run; when it reaches "Build and publish to PyPI", click **Review deployments**, tick `pypi`, then **Approve and deploy**. The workflow then makes the GitHub release from the release notes.
4. People update with `uv tool upgrade lookfirst`. The plugin updates from GitHub when people update it in Claude Code.

The release workflow refuses to publish when the tag doesn't match `pyproject.toml` or the release notes are missing.

A release on PyPI can't be replaced, only followed by a newer one. A badly broken release can be yanked on PyPI (the project's page, then Releases, then Options, then Yank), which stops new installs but keeps it for anyone who pinned it.
