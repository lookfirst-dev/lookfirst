# Launch day, and releasing later versions

Who does what: **you** are the owner; **Claude** is the coding agent working in this repo. Every step that publishes something or signs in to an account is yours.

## Already done (14 Nov 2026)

- The GitHub org `lookfirst-dev`, with two-factor authentication required. The repo `lookfirst-dev/lookfirst`, still private.
- PyPI: a pending trusted publisher for project `lookfirst`, owner `lookfirst-dev`, repository `lookfirst`, workflow `release.yml`, environment `pypi`.
- npm: your account, with two-factor authentication on, and the npm org `lookfirst-dev`.
- The release workflow (`.github/workflows/release.yml`), the npm pointer package (`npm/`) and version 0.1.0 are on `main`.

## Launch day, in order

1. **Record the hook demo** (you and Claude, optional, 15 minutes). See "Recording the hook" below.
2. **Make the repo public** (you). Settings, then General, then at the bottom **Change repository visibility**, to Public. Do this before publishing, so the links on PyPI and npm work.
3. **Create the `pypi` environment** (you, 2 minutes). Settings, then Environments, then **New environment**, named exactly `pypi`. Under "Deployment protection rules", tick **Required reviewers**, add yourself and save. Every release then waits for your click before anything reaches PyPI. On GitHub's free plan this setting only exists for public repos, which is why it comes after step 2.
4. **Tag the release** (Claude, after your go-ahead). On `main`: `git tag -a v0.1.0 -m "lookfirst 0.1.0"`, then `git push origin v0.1.0`. The Release workflow starts.
5. **Approve the PyPI upload** (you). In the repo's Actions tab, open the "Release" run. When it reaches "Build and publish to PyPI", click **Review deployments**, tick `pypi`, then **Approve and deploy**. Afterwards the workflow makes the GitHub release from `docs/RELEASE-NOTES-0.1.0.md`.
6. **Check it installs** (Claude). In a clean shell: `uv tool install lookfirst==0.1.0`, then `lookfirst --version` and `lookfirst check psf/requests`.
7. **Publish the npm pointer** (you, in Terminal):

   ```bash
   cd npm
   npm publish --dry-run
   npm publish
   ```

   npm asks for a code from your authenticator app. Run the dry run first and check it lists only `README.md`, `bin/lookfirst.js` and `package.json`.
8. **Check the plugin installs from GitHub** (you, in Claude Code): `/plugin marketplace add lookfirst-dev/lookfirst`, then `/plugin install lookfirst@lookfirst`.
9. **Announce** (you). The launch checklist in `docs/KICKOFF.md` has the channels and the timing advice.

If something goes wrong after step 5: a release on PyPI can't be replaced, only followed by a newer one. Fix it, then release 0.1.1 as below. A badly broken release can be yanked on PyPI (the project's page, then Releases, then Options, then Yank), which stops new installs but keeps it for anyone who pinned it.

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
2. On a branch, set the new version in `pyproject.toml` and `plugin/.claude-plugin/plugin.json` (and `npm/package.json` only if the pointer itself changes), run `uv lock`, and add `docs/RELEASE-NOTES-<version>.md`. Use 0.1.1 for fixes and 0.2.0 for new features. Merge it.
3. Tag `main` with `v<version>` and push the tag. Approve the PyPI step as on launch day.
4. People update with `uv tool upgrade lookfirst`. The plugin updates from GitHub when people update it in Claude Code.

The release workflow refuses to publish when the tag doesn't match `pyproject.toml` or the release notes are missing.
