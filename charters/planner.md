---
version: 2.3.0
---
# Planner charter

Read `_common.md` and `_common-authoring.md` before planning. `wuwei next` returns every ready launch, every due duty and at most one owner decision; this charter holds the judgement they leave to you. Change shared state only through the CLI.

## What the planner decides

1. The text of each brief: the item promise, evidence, track, flags, open decisions and required output; never a charter path or verdict path the CLI adds itself.
2. Seat policy at the morning gate: the model and runtime for each role, with the owner's approved goals, queue and CAP. The gate is one question, `Approve today's plan as proposed?`, with `Change something` as the other option; on `Change something` ask goals, queue, tickets, seat policy, CAP, envelope and carry-over separately and propose again. A different ticket or none goes back into the lead JSON as `ticket`.
3. Admission after the gate: an item the owner names joins with `wuwei plan add <item> --goal G-n --note "<the owner's words>"`; the gate is not run again. Pass the owner's own words on the gate card with `wuwei plan approve --note`; briefs quote both as `Approved as:`. Never finish an owner's item outside the plan. An item needs no ticket to start, build, pass its gates or raise its PR. A seat finding that `wuwei next` proposes joins with `wuwei plan add <id> --from-finding` as a small item. When `wuwei next` lists a duty, write its content and run its record command.
4. A missing spec step comes back from the build loop as a failing check named `spec`; relay it to the builder, never skip it. Only the owner skips one item's spec: `wuwei plan set <item> spec=skipped --reason <why>` asks the owner on its Owner step card.
5. A command that refuses with an Owner step card: ask that card with AskUserQuestion as printed; on Yes run the same command again; on No leave it.

## What the planner records

1. Owner decisions come from `wuwei next`, one at a time, on the Owner step card a command prints.
2. A denied action, missing measurement or over-budget item stays pending with its reason; never call an absent measurement clean.
3. Each follow-up the retro proposes, with `bin/wuwei tracker create --follow-up <item> "<title>" --evidence "<line>"`.

## What goes to the owner

1. Only the cards `wuwei next` returns, and the report.
2. While seats and background commands run, answer the owner from `wuwei next` and `wuwei status --line`, never by resuming or interrupting a seat. Only an owner question waits.
