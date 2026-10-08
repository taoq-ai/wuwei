# Feature: The basic workflow in the README is a Mermaid diagram (#561)

## Promise

The "The basic workflow" section of the README shows the day as one Mermaid flowchart that
GitHub and the docs site render, with a one-line text alternative above it and one caption
line below it.

## Root cause

README.md lines 56 to 66 tell the workflow as seven numbered steps. The owner asked for a
picture (owner comment on #561, 2026-10-08). tests/test_docs.py
(`test_readme_tells_the_day_in_superpowers_shape`, around line 197) pins the seven numbered
steps and the "not built" note on step 3.

## Acceptance scenarios

1. Given the README, when you read "The basic workflow", then it holds exactly one
   `mermaid` block, left to right, with the stages Setup and calibration, Plan and the
   morning gate, Build, Review by tier, Shepherd to merge, Close and retro, and a return
   edge from Close to Plan labelled "memory into tomorrow".
2. Given the diagram, then "you" joins Plan and Review and "hooks check every action" sits
   under the flow, both on dashed edges.
3. Given the section, then a one-line text alternative sits above the block, it is under 25
   lines, and the step 3 "designed, not built" note is gone (specification mode is built, #412).
4. Given mkdocs.yml, then the superfences mermaid fence is enabled (it already is).
5. Given the tone lint (#522), then the docs class stays within budget.

## Assumptions

- The relayed request for this run is only the Mermaid diagram. The Principles section and
  the removal of the comparison table, also part of #561, are left for a later run.
- The seventh stage, memory into tomorrow, is the labelled return edge, as the owner comment says.
- The caption keeps the concepts link the docs index mirror test needs.
