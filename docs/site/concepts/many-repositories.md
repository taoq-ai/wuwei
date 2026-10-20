# Many repositories

WUWEI is built for one person's team working across several repositories, and for adopters who
want the same process everywhere without forcing every repository into one shape.

## One workspace, many repositories

A workspace (`.wuwei/`) lists its repositories in `repos`. There is one plan, one board, one
ledger, one report and one set of standards across all of them. Each plan item names its
repository.

## The same principles everywhere

What does not vary by repository is the backbone:

- the evidence contract and the tiers;
- the doors;
- the owner question classes and the reversibility and confidence rule;
- the charters and the standards;
- the learning loop.

These live in the plugin and in `.wuwei/standards.md`, not in per-repository configuration. There
is nothing to configure differently, so nothing drifts.

## The shape of each repository

What adapts is read, not configured:

| Fact | Read from |
| --- | --- |
| PR template sections | the repository's template |
| Spec engine | `.specify/` or `openspec/` |
| Default branch | the code host |
| Protection and rulesets | the code host (and `wuwei doctor` shows the door strength) |
| CI | the repository's own checks |
| Change failure rate | its merges, reverts and production deployments |
| Repository memory | its `CLAUDE.md` or `AGENTS.md` |

**Why:** a process that ignores a repository's own conventions fights its maintainers. Reading
them means WUWEI fills gaps instead of adding a second process.

## Consistency you can see

- `wuwei doctor` prints, per repository, how strongly each door holds (wall, refused or detected).
  A repository you cannot protect with rulesets is visible as one.
- The report shows each repository's change failure rate and whether its tiers are raised.
- Unplanned PRs are listed per repository.

## For a team

Each person runs their own workspace. To share the backbone across a team, keep the standards you
agree on in a repository the team owns and copy them into each workspace's `.wuwei/standards.md`;
the retro of each workspace proposes changes back as a PR to that repository. Repository memory
(`CLAUDE.md`, `AGENTS.md`, project skills) already lives in each repository and is shared through
the normal review.
