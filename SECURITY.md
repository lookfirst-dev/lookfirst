# Security policy

lookfirst reads hostile code by design, so a flaw in lookfirst itself can put its users at risk. If you find one, please report it privately, so it can be fixed before attackers learn about it.

lookfirst lowers risk; it doesn't guarantee safety.

## How to report

Use GitHub's private reporting: open the repository's **Security** tab and click **Report a vulnerability**, or go straight to [the private report form](https://github.com/lookfirst-dev/lookfirst/security/advisories/new). Only the maintainer can see the report.

Please don't open a public issue for a security flaw. Include:

- the lookfirst version (`lookfirst --version`) and your operating system;
- the steps that show the problem, ideally with a small, harmless example repo or command;
- what you expected, and what happened.

Use harmless examples: something that creates a file or contacts a test server is enough. Please don't send real malware.

## What counts

A flaw in lookfirst itself, for example:

- **A way to make lookfirst run a target's code on your computer,** outside the sandbox.
- **A way out of the sandbox,** or a way for the install inside it to reach your real files, credentials or Docker.
- **A way to put words in lookfirst's mouth:** text from a target that shows up in lookfirst's output, including the MCP tools and the hook, as if it were lookfirst's own, or that changes the verdict.
- **A way to get the GitHub token** logged, or sent anywhere but api.github.com.
- **A general trick that hides an install step from lookfirst,** or that slips a command past the hook, and would work in any repo.

## What goes elsewhere

- **One repo or package that lookfirst missed, or flagged wrongly:** use the [issue forms](https://github.com/lookfirst-dev/lookfirst/issues/new/choose). If the trick would work in any repo, report it privately instead.
- **A harmful repo or package itself:** report it to GitHub or to its package registry, following [GitHub's guide to reporting abuse](https://docs.github.com/en/communities/maintaining-your-safety-on-github/reporting-abuse-or-spam).
- **The known limits** in the [README](https://github.com/lookfirst-dev/lookfirst/blob/main/README.md#what-it-doesnt-check) and the [threat model](https://github.com/lookfirst-dev/lookfirst/blob/main/docs/THREAT_MODEL.md), such as code that waits or notices the sandbox, and the hook letting a command through when its check fails or takes more than 20 seconds.

## What happens next

lookfirst is maintained by one person, so please allow some time:

- **A first reply within 7 days.**
- **A fix in a new release,** published as a GitHub security advisory once the fix is out. You're credited in the advisory if you'd like to be.

Only the latest release gets security fixes. Update with `uv tool upgrade lookfirst`.
