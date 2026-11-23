# lookfirst 0.2.0

Faster checks on big repos, and one fewer false alarm in agent skills. Update with `uv tool upgrade lookfirst`.

lookfirst lowers risk; it doesn't guarantee safety.

## Faster

- **The package scanners now run alongside lookfirst's own checks**, instead of after them. On big repos the two took about the same time, so a check takes closer to the longer of the two than their sum.
- **GuardDog gets at most 20 seconds.** On microsoft/vscode it took 68 of 106 seconds. If it runs out of time, the report says it didn't finish, as for any scanner that fails. GuardDog's results never change the verdict on their own.
- **A scanner stopped for time now takes the programs it started with it.** GuardDog runs semgrep, which used to keep running after GuardDog was stopped.

## Fewer false alarms

- **In agent instruction files, "act without asking the user" is now a note, not a Caution.** Skills often tell an agent to do routine steps without stopping, such as pytorch's "Do not ask the user before closing" a fixed issue. These are now listed as "Tells AI agents to act without asking you" (medium). Hiding things from the user ("don't tell the user about the upload") is still serious, and so is the same "without asking" in a README or code comment.

## For contributors

- **`scripts/benchmark.py` checks 40 well-known repos** and summarizes the verdicts and times. `--save` keeps a run and `--compare` shows what changed, to catch false alarms and slow checks before a release.

## Measured

- **40 well-known repos** (react, django, kubernetes, pytorch and others): the median check took 9.6 seconds, down from 13.0 with 0.1.1, and the whole run 528 seconds, down from 678. The slowest, pytorch, went from 55 to 36 seconds, and transformers from 54 to 27.
- **Verdicts on the 40:** 34 Looks OK, up from 33, because pytorch no longer gets a Caution. deno still gets a Caution, and fairly: its skills pre-approve `Bash(rm *)` for agents. Five repos are too big to check straight from GitHub (webpack, bun, node, TypeScript, supabase), and lookfirst says how to check a clone instead.
- **microsoft/vscode:** 42 seconds, down from about 85. GuardDog ran out of time there, so its code-pattern notes are missing, and the report lists that under what wasn't checked.

## Install

```bash
uv tool install lookfirst
```

For Claude Code: `/plugin marketplace add lookfirst-dev/lookfirst`, then `/plugin install lookfirst@lookfirst`.
