# Merge policy configuration and operation

The owner configures each repository in the workspace's `.wuwei/config.toml`:

```toml
[[repos]]
name = "example/project"
path = "repo"
default_branch = "main"
merge_deploys = false

[repos.merge]
auto = true
max_changed_lines = 400
max_per_day = 5
soak_minutes = 30
quiet_hours = ["22:00-08:00"]
reset_epoch = 0
```

Omitting `merge_deploys` is a refusal. Quiet hours use the workspace clock's local timezone;
an empty list disables quiet hours. A configured review bot also needs `bot_login` here.
`bot_min_score` defaults to 5; `bot_score_pattern` defaults to the confidence-score summary
format. A summary must contain exactly one reviewed commit link and the adapter's score.

`never_auto_paths` replaces the default path patterns, matched at any directory depth and
against both sides of a rename. Defaults cover CI, dependency manifests and locks, schemas,
migrations, deployment and infrastructure files. `fix_pattern` identifies follow-up fixes
in commit messages; the default recognizes fix, fixes, fixed, bugfix, hotfix and revert.

Link the approved item to its canonical PR using the existing state writer. A plan created
before this feature needs to be replanned because its approval event lacks risk evidence.
This evidence is coordination data, not proof of an owner action or a host override.

```sh
bin/wuwei state set items.item-7.pr '"example/project#7"'
bin/wuwei merge check example/project#7
bin/wuwei merge example/project#7
bin/wuwei watch --once
```

A numeric PR works from the configured repository or its anchored worktree. Raw merge
commands are refused even after a clean check: the dedicated command writes the evidence,
undo entry and monitoring intent before calling the port. Exit 2 after an external failure
leaves an intent for reconciliation; it never retries the merge automatically.

The watch pages through the existing `base.red` and `merge.breaker` event classification.
It trips before trying the revert. Successful revert PR URLs are retained in the original
day journal. Failed revert creation is retried on later polls. A tripped repository remains
disabled across days. After investigating, the owner increments `reset_epoch` in config;
previously recorded incidents will not undo that reset. A new incident can trip it again.

The owner's `.wuwei/memory/notes/baseline.md` must include one line:

```text
Escaped-defect-rate: 0.1
```

The owner maintains this note outside agent tools; generic note creation and promotion
cannot create, patch, fold or archive it. The value is a fraction from 0 to 1. Each PR is observed for 14 full days. The rolling cohort
contains PRs merged between 14 and 28 days ago. The monitor follows actual merge-commit
patch lines through fresh, linear base-branch history, including intervening line shifts
and renames. Reverts trip immediately; same-line fixes affect the mature outcome rate.
Missing or truncated patches, nonlinear or incomplete history, missing baseline and
incomplete mature checks are unmeasured. An unreadable post-merge observation blocks further
merges for that repository until the watch can measure it. The reference adapter's bounded
history read is deliberately conservative; general metric reporting is a separate feature.
