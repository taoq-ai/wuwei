# The day

```mermaid
flowchart LR
    goals([goals: the direction]) --> pass
    pass --> view{{"plan view: you approve"}}
    pass["plan pass<br/>(any number per day)"]
    view --> work["builders, gates, shepherd"]
    work --> evidence{"evidence<br/>complete?"}
    evidence -- gaps --> work
    evidence -- yes --> merge["merge"]
    merge --> checkpoint["checkpoint<br/>report + retro"]
    checkpoint -- "standards, vaccines, proposals" --> pass
```

## Goals and the plan view

Your goals live in `.wuwei/goals.md`: outcome, measure, target, date and priority. They set the
direction the lead ranks against.

Each plan pass ends with the plan as a picture: `wuwei plan view` writes `.wuwei/plan.html` (light
and dark, readable on a phone) with the ranking formula, the estimated build hours (one WSJF size
point is one hour), and a card per goal with its items by score. Then one question: approve or
change. New items wait on the board as `awaiting plan approval` until you approve; work you already
approved keeps running.

**Why:** you own the direction and the trade-offs, and you should see them at a glance, not in a
two-kilobyte paragraph. One picture, one answer.

## Plan passes

A plan pass (`/wuwei-run`) adds, drops or re-ranks items in `.wuwei/plan.json`. Run it as often as
the day needs: in the morning, when the queue runs dry, when you add something, when priorities
shift. The plan is a running queue that carries across days, not a daily document.

The lead does the thinking in a pass. It reads every source it can reach (issues, red checks,
review threads, follow-ups, regressions), returns only ready candidates (a promise, acceptance
scenarios, the repository and files), and red-teams the plan: it names the riskiest item and the
cheapest way to learn early whether it works, and ranks that learning first.

**Why:** days change. A plan you can only make once goes stale by lunch, and a team that cannot
re-plan either stalls or improvises.

## Ranking

The configured framework ranks the queue, never a hand order.

- **WSJF** (default): value to the goal, time criticality, risk reduction, each on 1, 2, 3, 5, 8,
  13, 20, divided by job size.
- **RICE**: reach times impact times confidence, divided by effort.

Every score carries one line of evidence. **Why:** a ranking you can read the reasons for is a
ranking you can correct.

## Flow

Work already in progress follows Kanban flow policy, not the last event:

1. **Class of service**, most urgent first: `expedite`, `fixed-date`, `standard`, `intangible`. Set it
   with `wuwei plan add --class`. An item is `standard` by default and `fixed-date` when its goal has a
   date. Only one expedite item is open at a time; a second is refused, and so is a restore of one.
2. **Closest to done**, right to left: ready to merge, owner review, gates, fix round, building.
3. **Age**, oldest first.

Each board row shows its class and the hours since its last event. A PR idle 4 hours with no live
seat on its item shows `stale` with its last event, first in its class. A WSJF item's time
criticality rises one Fibonacci step per day its first PR is open.

An item can wait on another: `wuwei plan add <id> --after <other>`. While the other is open, the
board shows `waiting on <other>`, the Stop reminder leaves it out, and the other's score adds the
waiting item's cost of delay. A wait that would close a cycle (an item waiting on itself, or on an
item that already waits on it) is refused.

**Why:** attention goes to whatever moved last, so an old draft starves. Finishing what is closest
to done, in class order, keeps work flowing.

## Checkpoints

A close (`/wuwei-close`) writes the report for the day so far and launches the steward for the
retro. It locks nothing: the next plan pass reopens the day. A second checkpoint starts with what
changed since the first. There is no end time.

**Why:** you stop when you stop. A checkpoint gives you the picture whenever you want it without
pretending the day has a fixed shape.

## Tiers

Each item has a tier that sets how much evidence it needs:

| Tier | For | Gates |
| --- | --- | --- |
| light | a trivial, local change | quality |
| standard | the default | arch, quality, security |
| full | contracts, schemas, boundaries, auth, secrets, agent tooling, infrastructure | arch, quality, security, goal |

When unsure, the lead goes up. A repository over its [error budget](learning.md#error-budget) raises
every tier one step, and a light item whose code touches a trust path is raised to standard.
