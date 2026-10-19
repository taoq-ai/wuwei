Verdict: PASS
Gate: arch
Item: semver-policy
PR: taoq-ai/wuwei#1154
Head: 32cee4b876e0b61241e63a9a881f01a2aecc950d
Confidence: medium
Breaking: yes: read against the API at base 5fe8347, the arch `Breaking:` verdict field and the `!` / `BREAKING CHANGE:` PR lines get another meaning (a SemVer major only, not any visible behaviour change), so owners and every audited repository stop getting an `Announcement:` and `breaking:` hold on stricter checks that fix a documented rule; no client fails to parse anything, and the owner's `breaking:` answer picks 4.1.0 or 5.0.0

## Findings
- [low] blocks: no. One class still has no row: a new check, on by default, that holds only some clients and fixes no rule the docs stated (#1142's spec-contract arch trigger; base `_common.md` named only OpenAPI, protobuf, GraphQL and JSON schema contract files). It is not a patch, not a minor (it is not off by default and does more than add information), and "an input every client must now give" excludes it. Only "given another meaning" (the gate table) reaches it. A seat lands on ESCALATE with Breaking: yes, which is the designed safe path, so nothing merges wrongly. The owner will see this class as a `breaking:` question. Class: requirement (FR-001 classification edge). A later item could name it in the major row.
- [low] blocks: no. #1148 is still at the edge: v4.0.0 documented `Announcement: <link>`, and a relative path was arguably a link. The PR's Assumption calls it a patch, and the owner's `breaking:` answer on this PR covers it.
- [low] blocks: no. The announcement comment (issuecomment-6260116968), item 2, lists the major cases without "a documented exit code's meaning changed". The docs and rule 7 carry it. The comment is outward text and can be edited.
- [low] blocks: no. Carried from 937883f: with `Release-As: 4.1.0`, release-please still lists #1148 and #1150 under BREAKING CHANGES in the 4.1.0 notes, because their commits carry `!`. Edit the release PR's notes before it merges. `charters/_gate.md:59` still shows `Breaking: no` alone, and the parser reads `no (patch)` as no.

## Probes
- Delta: `git diff --stat 937883f 32cee4b` in the builder worktree shows 17 files, none under cli/. The tree was copied with `git archive 32cee4b` into sentinel-arch-semver-policy-r1/head.
- Suite at the head copy: `pytest -q` gave 1926 passed, 2 skipped. Runtime `wc -l cli/wuwei/*.py` is 3026, under 3,400.
- Word ceiling: `wc -w agents/*.md` at the head gives builder 1995, lead 1687, sentinel-arch 2248, sentinel-goal 1961, sentinel-quality 2052, sentinel-security 2087, shepherd 1795, steward 1714. All are at or under 2,250. `bin/wuwei agents build` printed "agents match the charters". `diff -r` against the committed agents was empty. `.claude/wuwei/charters` matches charters, and `.claude/agents` differs only by the two JSON files that live only in agents/.
- Rule 7 measured the test's way (str.split after ` 7. ` up to ` Trust boundaries`): 65 words at 5fe8347, 79 at 32cee4b, within the test bound of 79.
- Trims to sentinel-arch.md: the vocabulary line keeps C4/arc42, ADRs and fitness functions and drops only their glosses. `test_each_gate_names_the_frameworks_it_stands_on` passes. The closing "and leave the verdict to that gate" became "note it". Under gate rule 5 a note is `blocks: no`, so arch still does not block on an open measure. No rule was cut.
- Stale wording: `grep -rn -i -E "minor|refuse or report more|stricter check"` over charters/, skills/, docs/design.md and docs/site found no "stricter check is a minor" left. builder.md:41-43 and reference.md:70 say a stricter check of a documented rule is a `fix:` (patch). _common.md:35, decisions.md:40 and shepherd.md:42 key on "a breaking change (a SemVer major)".
- PR read once: `gh api repos/taoq-ai/wuwei/pulls/1154` (draft, head 32cee4b). `Announcement: https://github.com/taoq-ai/wuwei/pull/1154#issuecomment-6260116968` and `Release-As: 4.1.0` are each alone on their line. The comment exists (read with `gh api .../issues/comments/6260116968`). The bodies of #1114, #1142, #1152, #1151, #1102, #1101 and #1091 were read once each. Docs at the bases were read with `git show <base>:charters/_common.md` and `git show 5fe8347:docs/design.md`.
- Pending release `git log v4.0.0..5fe8347`: #1145 is a feat, and #1148, #1150, #1141, #1144 are fixes. With #1148 and #1150 read as patches, 4.1.0 is the strict SemVer number if the owner accepts this PR as not a major. 5.0.0 is the number if they take this PR's own Breaking: yes as a major. Both are left to the owner's `breaking:` answer, as the PR body says.
- Cases ruled under the new text:
  - #1108 to #1122 (closed bypasses of documented doors) are patches.
  - #1114 is a patch. It fixes owner review counted from breaking and exception rulings, and CI-not-started missing `pull_request_target`. The prose-only skip refuses less, and the unreadable-host suffix only adds information.
  - #1150 is a patch: v4.0.0 design.md:70 says an exception "drops that gap".
  - #1152 is a patch. It enforces "passed at the head", and the exit code 1 still means gaps.
  - #1102 is a minor. Draft create is a new capability, a non-draft create is refused as before, and the GraphQL ready routes it closed are patch parts.
  - The #1101 alias removal is a major. At the base the alias ships, so it is on the list, and removing it removes a documented element. The base-commit read closes the "while its alias ships" circularity.
  - A doctor check that now warns (#1091 kind) is a patch, or a minor for a new check, because exit 1 still means warnings. Moving warnings to exit 2 would be a major.
  - #1151 is a patch. A copy-in that follows a swapped link writes the ledger, against the documented boundary, and the loop now ends in the documented `verdict.missing` refusal.
  - #1148 is at the edge (note). #1142 is ambiguous and ends at ESCALATE with Breaking: yes (note).
- closed: finding 1 (rule 7 minor without its documented-API condition) at 32cee4b. Rule 7 now says "a patch only when the old behaviour contradicted the documented API".
- closed: finding 2 (major row collides with stricter checks) at 32cee4b. The new wording is "a documented exit code's meaning changed" and "an input every client must now give", plus evidence.md's "judged by its meaning, not by which inputs reach it".
- closed: finding 3 (closed API list) at 32cee4b. Skills, plugin and marketplace names, role names, owner-written files and the alias while it ships were added, read at the base commit.
- closed: finding 4 (builder `fix:` against a minor) at 32cee4b. A stricter check of a documented rule is a `fix:` (a patch), a new capability is a `feat:`, and evidence.md says both follow release-please.
- closed: finding 5 (this PR's breaking evidence) at 32cee4b. The `Announcement:` line points at an existing comment. The owner's `breaking:` confirmation is the evidence gap WUWEI holds the merge on, not a gate finding.
- Mutants: not run. No guard or validation changed. The one test is a charter text check.
- Confidence medium: the rulings come from reading the text against each case's PR body and the docs at its base, not from running a seat on a brief. Release-please's handling of `Release-As:` is its documented behaviour, unmeasured here.

## Residual risk
The policy is a reading rule for model seats, so an edge class (an on-by-default check that holds only some clients) shows up as an owner `breaking:` question, not as a failing test. Only the word-level test pins the text.
