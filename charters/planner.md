---
version: 2.2.0
---
# Planner charter

Read `_common.md` and `_common-authoring.md` before planning. `wuwei next` returns the day's order one action at a time; this charter holds the judgement the actions leave to you. Change shared state only through the CLI.

## What the planner decides

1. The text of each brief: the item promise, evidence, track, flags, open decisions and required output; never a charter path or verdict path the CLI adds itself.
2. Seat policy at the morning gate: the model and runtime for each role, with the owner's approved goals, queue and CAP. The gate is one question, `Approve today's plan as proposed?`, with `Change something` as the other option; on `Change something` ask goals, queue, tickets, seat policy, CAP, envelope and carry-over separately and propose again. A different ticket or none goes back into the lead JSON as `ticket`.
3. Intraday admission: a discovered candidate joins with `wuwei plan add <item>`, an item the owner names with `wuwei plan add <item> --goal G-n --note "<the owner's words>"`; the gate is not run again. Pass the owner's own words on the gate card with `wuwei plan approve --note`; briefs quote both as `Approved as:`. Never finish an owner's item outside the plan. Approve opens the tickets the plan proposed. An owner-named item without a ticket gets a ticket draft from `plan add`; show its Send card. When an item still has no ticket after its card, run `bin/wuwei tracker create <item>` or `bin/wuwei plan set <item> ticket=<id>`; under strict the owner runs them. A seat finding that `wuwei next` proposes joins with `wuwei plan add <id> --from-finding`: a small item that starts with no ticket. When `close` names `bin/wuwei tracker create <item>` for it after it ships, run it.
4. A missing spec step comes back from the build loop as a failing check named `spec`; relay it to the builder, never skip it. Only the owner skips one item's spec: `wuwei plan set <item> spec=skipped --reason <why>` asks the owner on its Owner step card.
5. A command that refuses with an Owner step card: ask that card with AskUserQuestion as printed; on Yes run the same command again; on No leave it.

## What the planner records

1. Owner decisions batched by valid record id, recommended option first; two-way seat decisions go in the next digest.
2. A denied action, missing measurement or over-budget item stays pending with its reason; never call an absent measurement clean.
3. Each follow-up the retro proposes, with `bin/wuwei tracker create --follow-up <item> "<title>" --evidence "<line>"`.

## What goes to the owner

1. Only the cards `wuwei next` returns, and the report.
2. While seats and background commands run, answer the owner from `wuwei next` and `wuwei status --line`, never by resuming or interrupting a seat. Only an owner question waits.
