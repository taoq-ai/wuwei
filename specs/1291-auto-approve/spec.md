# Spec: an owner setting auto-approves plans (#1291)

## In my words

Today every plan pass ends with a `plan: approve this plan?` question, and every item added later
waits on the board as `awaiting plan approval` until the owner answers another one. On 2026-11-06
that was about seven interruptions in one day, each for work the owner had just named.

After this change the owner can put `auto-approve` in the `allow` list of `.wuwei/config.toml`
(item 1290 adds the key). With it, `wuwei plan view` and `wuwei plan add` (one item or `--from`)
mark each open item on an open goal approved, without a question. An open goal is a heading
of `.wuwei/goals.md` (any case) that the owner has not ruled met. Each approval is a
`plan.approved` ledger row with `auto: true` and the line `wuwei plan view` prints, and
`wuwei report` lists those rows for the day. An item with no open goal (empty, `unplanned`, a typed
label such as `none` or `G-99`, or a met goal) still waits for the owner's `plan:` answer, because scope is the owner's. When nothing waits, the view
prints no `Ask: plan:` line, so the planner, the plan pass and the wuwei-run skill ask nothing.
Every other owner question class (one-way, scope, goal, trust, infra, breaking, exception, owner
review) is unchanged. Without the value nothing changes. A seat can neither set the value nor edit
the file: the config door already refuses `wuwei config allow ...` and writes to the file.

## Acceptance scenarios

1. `allow = ["auto-approve"]`, items with goals: `wuwei plan view` approves each, records one
   `plan.approved` row with `auto: true` and the view line, and prints no `Ask: plan:` line.
2. `allow = ["auto-approve"]`: `wuwei plan add` or `--from` approves the new item with its own
   auto row; the board shows no `awaiting plan approval` for it.
3. An item with no open goal (empty, `unplanned`, `none`, `n/a`, `-`, blank, a goal not in
   goals.md, a met goal), added with auto-approve on: it stays unapproved, the board shows
   `awaiting plan approval`, and `wuwei plan view` still prints the `Ask: plan:` line.
4. No auto-approve in `allow`: the view prints the Ask line and new items wait, as today.
5. A day with auto-approvals: `wuwei report` lists each with its time, items and view line.
6. A seat running `wuwei config allow auto-approve`, or writing `.wuwei/config.toml` with Edit,
   Write or a redirect: the guard refuses it.

## How this fails

- A seat turns the value on for itself. It rests on the config door (#1290's corpus, #1297 for
  the remaining writer routes); a test adds `wuwei config allow auto-approve` to the seat corpus.
- An item outside the owner's goals slips through as approved, because the planner types the goal
  label. Approval matches the label against the open goals of goals.md, and a test holds `none`,
  `G-99`, a blank and a met goal waiting (fix round 1, arch at a2eb3a6).
- Every `plan view` writes an empty ledger row, flooding the report. A row is written only when
  an item was approved.

## Assumptions

- Depends on #1298 (item 1290) for the `allow` key; this branch starts from it and rebases onto
  main once it merges. Overturn: #1298 is dropped or renames the key.
- Auto-approval trusts goals.md as the owner's. A seat can still write it today (no guard holds
  it); that gap predates this item and is a follow-up candidate. Overturn: a guard lands for it.
- With auto-approve on, `plan add` approves every open item with a goal that waits, not only the
  one just added (an item whose promise changed waits too). One row lists them all.
- The ledger row keeps `answer` (set to `auto-approve`, the value that approved it) beside `auto`
  and `line`, so readers of `answer` keep working.
