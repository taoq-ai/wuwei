# Amendment text for issue #416

The builder pastes these blocks into `docs/specs/2026-09-24-wuwei-design.md` and
`.specify/memory/constitution.md` as plan.md "What changes" places them, then reviews them
against the surrounding sections. Wording may be tightened in review; every phrase the
check script in plan.md pins must survive.

## A. New section 5.11 (design spec)

Insert after the last `### 5.x` section and before `## 6. Memory`.

```markdown
### 5.11 Tracker hygiene (owner, 2026-10-03, #416)

Every work item lives in a ticket in the team's tracker, and the ticket carries the item's
story: its decisions, progress, verdicts, pull request and close. The tracker port (section
8) already reads the backlog and moves states (claim, in review, done, 4.6); this section
makes the ticket required, lets the day open tickets for what it finds, and writes the story
as comments.

Configuration. `adapters.tracker` is `linear`, `jira`, `github` (issues, plus Projects v2
when a board is set) or `none`. The schema default stays `none`, so a first day works on
defaults; `setup` and the interview recommend `linear`. `[tracker]` in `config.toml`:

| Key | Default | Meaning |
|---|---|---|
| `required` | `true` | every item needs a ticket; in force only when `adapters.tracker` is not `none` |
| `skip_tiers` | `[]` | tiers (`light`, `standard`, `full`, as in `repos.gates.floor`) whose items need no ticket |
| `strict_close` | `true` | day close refuses a merged item whose ticket did not reach the done state |
| `create` | `["bugs", "triage", "follow-ups"]` | the classes seats may open tickets for |
| `log` | `["decisions", "progress", "verdicts", "pr", "close"]` | the comment kinds written to an item's ticket |
| `auto` | `["progress", "pr", "close"]` | the write kinds sent without approval; every other write is a draft |
| `max_per_item_per_day` | `10` | comments per ticket per day, the fold included |
| `project` | `""` | where tickets are created: a Linear team id (empty: `backlog_filter`), a Jira project key, or a GitHub `owner/repo` (empty: the first configured repository) |
| `board` | `""` | GitHub only: a Projects v2 board as `<owner>/<number>`; empty uses labels |

`backlog_filter`, `states.in_review` and `states.done` keep their meaning for every adapter.
`auto` accepts the comment kinds and the creation classes plus `items`. The config check
refuses an unknown value in `create`, `log`, `auto` or `skip_tiers`.

Ticket of an item. `tickets` in `state.json` maps an item id to its ticket id and source,
written only by the CLI: `plan approve` and `plan add` record the candidate's `ticket` field
(the lead names it; GitHub ticket ids such as `owner/repo#12` are never item ids) or, for a
candidate discovered from the tracker backlog, the candidate id itself; `wuwei tracker
create <item>` records the ticket it opens; `wuwei plan set <item> ticket=<id>` records an
existing ticket once the adapter's `created(item)` confirms it exists. `plan approve
--import-yesterday` carries yesterday's tickets with the items. Every tracker operation on an
item (claim, transitions, comments, history for lead time) uses its ticket id; only while
`required` is not in force does an item without one fall back to its own id, as before.

Enforcement. While `required` is in force, an item whose tier is not in `skip_tiers` and that
has no ticket is refused by one CLI function, `tracker.check`, with one reason: `<item> has no
ticket: bin/wuwei tracker create <item> (opens one from the item's record) or bin/wuwei plan
set <item> ticket=<id>`, or, while a ticket draft for it is pending, `bin/wuwei drafts approve
<draft>`. The refusal points:

- `plan approve`: one refusal lists every approved item without a ticket; nothing is approved;
- `plan add` (intraday intake, 5.7): the candidate becomes an owner proposal with the reason;
- `build next`, before the claim, and `dispatch next`, before the gates;
- PreToolUse `Agent` launch for a brief whose item has none (4.1), part of the seat launch
  contract and so under the `seats` area (9.1).

The tier that decides is the item's recorded gate tier when there is one, else the lead's
tier; an item with neither is not exempt. An exempt item gets one `tracker.skipped` event at
admission. A gate tier that later rises out of `skip_tiers` makes `dispatch next` refuse until
the ticket exists.

Close. While `required` is in force and `strict_close` is on, `wuwei close` refuses while an
item merged today has no successful done transition (the `tracker.call` event that the merge
path writes, 4.6), naming `bin/wuwei tracker done <item>`, which runs the same transition
again. Carried and parked items keep their tickets open. With `strict_close = false` the same
line is printed and does not refuse.

Creation. `wuwei tracker create <item>` opens the item's own ticket (class `items`) from its
record: the title from the candidate's scope, the description from its evidence, goal and
track. `wuwei tracker create --bug|--triage|--follow-up <subject> "<title>" --evidence
"<line>"` opens a ticket of that class: a builder or a gate that finds a bug outside its
item's scope (`--bug`), the on-call seat for a triage result (`--triage`, 5.10; its subject
is the incident id), the planner for a follow-up the retro proposes (`--follow-up`). The
class must be in `create`, or the command refuses (exit 1) naming the key. The subject's
ticket is the parent: Linear creates a sub-issue, Jira links the two with a Relates link,
GitHub writes a `Related: <parent>` line that the host cross-references; a bug is a Jira
`Bug` and carries the GitHub `bug` label. Evidence lines are repository-relative (`file:line`,
a failing test id, a command); a line holding an absolute path is refused. Creation is
idempotent per class, subject and title: a second call prints the existing ticket or draft
and writes nothing. Each ticket that exists records one `tracker.created` event (class,
subject, ticket, parent), and the board lists the day's created tickets per item.

Comments. One CLI writer, `wuwei tracker log`, run by the watch sweep (4.2), by `wuwei close`
once the close passes, and on demand, turns the day's CLI events into comments on each
item's ticket, once each. Every entry has a stable key (its kind and subject), kept in
`tracker_log` in `state.json` with its outcome (written, drafted, refused, folded), so a
second run writes nothing new. The text is a template filled from the record and prefixed
`[<day> <item>]`; it is never a raw record and never holds an absolute path, and it passes
the outward lint (4.3) like any message. A refused entry is recorded with its reason and not
retried.

| Kind | From (CLI events) | Comment |
|---|---|---|
| `decisions` | `decision.decided` for a record naming the item | `Decision D-<n>: <question>. Outcome: <outcome>.` |
| `progress` | phase changes, builder and gate starts and stops, fast-check results, a park | one line each, such as `Phase: implement.` or `Fast checks: 3 passed, 1 failed.` |
| `verdicts` | `gate.received` | `Review <role> (<round>): <verdict>, <n> blocking findings.` |
| `pr` | `pr.raised`, `pr.claimed` | `Pull request: <url>.` |
| `close` | `wuwei close` | `Merged in <pr>.`, `Carried to <date> (D-<n>).` or `Parked (D-<n>).` |

Approval. Comments and creations are external writes sent as the owner, so they go through
the tracker port's text-bearing operations and the outward policy (4.9, 9.1): a write whose
kind or class is in `auto` is sent, and any other write becomes a draft in the draft queue
that the owner approves, edits or drops; the writer records it as drafted and never sends it
again. `auto` plays for the tracker the part that work channels play for chat: mechanical
text derived from records. The 4.9 rules still come first: a text that names a person,
matches a sensitive, commitment or disagreement pattern, or cannot be classified is a draft
whatever `auto` says, so the `message` ceiling of cruise mode (5.8.1) holds; tracker writes
are not decision records and cruise levels do not apply to them. A GitHub `project` or
`board` whose owner is not in `outbound.code_host_orgs` is an external party, so every write
to it is a draft whatever `auto` says; Linear and Jira tickets are internal to the
configured workspace or site. Every tracker write, comments and creations, passes the
humanizer pass of the outward policy (`[outward] humanize`, default true, #420) before it is
drafted or sent. With the defaults,
progress, pull request and close comments are sent; decisions, verdicts and every creation,
the item's own ticket included, are drafts. When the owner approves an `items` draft and the
adapter confirms the ticket, the CLI records it in `tickets`.

Loop cap. A ticket receives at most `max_per_item_per_day` comments a day. When the entries
waiting for a ticket at one run would pass the cap, the last allowed comment is one fold,
`Folded <n> updates: <kind> <count>, ...`, and the CLI writes one `tracker.folded` event with
the counts; entries after it that day are counted in `tracker_log` only and shown on the
board. A looping seat therefore cannot flood a ticket. Creations are not capped; they are
idempotent.

Adapters. The tracker port gains `comment(item, text, category)`. `create(draft)` takes the
draft `{title, description, item, category, parent}` and returns `{id, url}`, where `id` is
the ticket id every other operation accepts; `category` and `parent` are metadata to the
outward policy. Each adapter implements the whole port with `urllib`, reads its credentials
by name from `.wuwei/env` (kept out of seat environments), and passes the port contract test
against recorded fixtures. `claim` assigns the ticket to the credential's user; `history`
returns state changes in one shape for lead time (5.6).

| Adapter | Ticket id | Credentials | backlog, create, comment, transition |
|---|---|---|---|
| `linear` | `ENG-123` | `LINEAR_API_KEY` | GraphQL: the team's open issues; `issueCreate` with `parentId`; `commentCreate`; the workflow state with the configured name |
| `jira` | `PROJ-123` | `JIRA_SITE` (https), `JIRA_EMAIL`, `JIRA_API_TOKEN` | REST: JQL search of `project` not in the Done category, narrowed by `backlog_filter`; create a Task or Bug and a Relates link; add a comment; the transition whose target status has the configured name |
| `github` | `owner/repo#123` | `GITHUB_TRACKER_TOKEN`, a fine-grained token for issues and projects only | GraphQL: open issues of `project`, `backlog_filter` as a label; create an issue; add a comment; with `board`, the Projects v2 Status option with the configured name, otherwise a label for `in_review` and closing the issue for `done` |

Setup and health. `setup` reads each repository's README, CONTRIBUTING and pull request
template for tracker links (`linear.app`, `atlassian.net`) and prints what it found before
the interview. The interview asks where the backlog lives (Linear first, as recommended;
Jira; GitHub; none; or `<tracker> <project>` typed in), whether every item needs a ticket
(every item; all but `light` items; optional), and which tracker updates go without approval
(progress, pull request and close; those plus new tickets; everything; nothing). `doctor`
fails the tracker row when `required` is in force and the adapter cannot read the backlog,
naming the missing credentials or `bin/wuwei config set tracker.required false`.

Owner-facing. The board, `wuwei next` and the DM show an item's ticket id beside its name.
The documentation adds a `[tracker]` section to configuration.md, glossary entries (ticket,
tracker hygiene, fold), one paragraph in daily.md ("every item has a ticket; you see the
ticket id on the board and in the DM") and reference rows for `tracker create`, `tracker
log`, `tracker done` and `plan set`.
```

## B. Section 4.1 hook table (design spec)

In the `Agent` launch row, append to "Refuses when": `; an item without a ticket while
tracker hygiene requires one (5.11)`.

## C. Section 4.9 (design spec)

Append one bullet after "Precedence:":

```markdown
- Tracker writes (5.11): comments and ticket creations whose kind is in `tracker.auto` are
  auto-sent; every other tracker write is a draft, and the approve rules above still apply
  to each message. A GitHub `project` or `board` whose owner is not in
  `outbound.code_host_orgs` is an external party, so every write to it is a draft whatever
  `auto` says; Linear and Jira tickets are internal to the configured workspace or site.
```

## D. Section 8 adapter table (design spec)

Replace the tracker row with:

```markdown
| tracker | `backlog(filter)`, `claim(item)`, `transition(item, state)`, `create(draft)`, `comment(item, text, category)`, `history(item)`, `created(item)` | Linear (recommended), Jira, GitHub issues and Projects (5.11) |
```

## E. Constitution

Add under `## Workflow`, after the cycle budget bullet:

```markdown
- Tracker hygiene (design 5.11) applies to WUWEI's own work: every feature has its GitHub
  issue as its ticket; a bug or follow-up found mid-feature becomes its own issue linked to
  the parent (recorded under Deferred in the feature's spec until it is filed), never
  silent scope; decisions, verdicts and the pull request link are recorded on the issue or
  its pull request.
```

Footer: `**Version**: 1.2.0 | **Ratified**: 2026-09-28 | **Last Amended**: 2026-10-03`. If
#411 has already raised the version, raise its minor number by one instead.
