# Research: the reason-string catalogue (UX sweep 2026-10-03, section d)

This is section (d) of the UX adoption sweep, pasted as the issue asks. It is the starting
text for every rewrite in this feature. Read it with these four notes:

1. Line numbers are from main at 0.12.0. Issues #383 to #409 landed since, so lines have
   moved and some strings changed or were removed. Match a row by file and message text,
   never by line. A row whose string no longer exists is skipped; a reason string added
   since the sweep gets its rewrite from the same rules (plan.md, "Rewrite rules").
2. KEEP rows stay as they are (3 rows).
3. The voice rule (spec.md, User Story 6) overrides the drafted text: 37 drafted rewrites
   say "you" or "your" and lose it in a seat-facing string; a rewrite in a person-facing
   module (`commands/doctor.py`, `commands/setup.py`, `commands/next.py` step rows,
   `commands/nudges.py`, widget questions and descriptions, the DM text) says "you" and
   never "the owner".
4. Section d2 families: each listed string keeps its current text and gains its family's
   shared text through the constants in `cli/wuwei/exits.py` (plan.md, Design 1). The
   shared texts below are the drafts; the plan holds the final wording, which drops "your"
   from the hook payload family.

## Classification (from the sweep)

Classification: an AST pass over `cli/wuwei` collects `print(..., file=sys.stderr)`, every raised
`ValueError` and its subclasses (`Refused`, `ParseError`, `StateError`, `ConfigError`), `Result(1|2, ...)`,
guard `return 1|2, "..."` tuples and the owner-action reason tables. A string counts as coaching when
it names an action (a verb such as run, use, set, add, or a `wuwei` command or flag), else as a wall.
Totals: 1184 strings, 353 coaching, 524 owner-facing walls (448 owner, 42 unmeasured, 30 config, 4
usage) and 307 internal invariants. The verb test is generous: some strings it counts as coaching
are still weak, for example `Opaque owner action; use the host terminal.` Rewrites in d1 were drafted
by reading the code at each location. Where a rewrite says "with `bin/wuwei config set`", that is the
owner command that replaces a hand edit of `config.toml`.

Walls seen live that come from adapters, outside `cli/wuwei`:

| Location | Message now | Coaching rewrite |
|---|---|---|
| adapters/code_host (default branch read) | `github.default_branch: could not run: gh exited 1` | `gh could not read acme/widget (<stderr line>); using main from git. Check gh auth status if that is wrong.` |
| adapters/vcs/git.py merge_base | `git.merge_base: could not run: git exited 128` | `origin/<branch> is not in this checkout; run git -C <repo> fetch origin, then retry.` |
| adapters/vcs/git.py identity | `git.identity: could not run: git exited 1` | `No global git identity; that is fine when each repository sets user.name and user.email (doctor checks them).` |
| commit_push via git push_commits | `git.push_commits: could not run: git exited 128` | `Could not compare with origin/<branch> (<stderr line>); run git -C <repo> fetch origin, then push again.` |

### d1. Owner-facing walls, with rewrites

524 strings. Group: `owner` (reaches the owner or the planner session), `unmeasured` (exit 2 with no default or next step), `config` (config validation) or `usage`. A rewrite that says KEEP is already fine and stays as it is.

| Location | Group | Message now | Coaching rewrite |
|---|---|---|---|
| cli/wuwei/__main__.py:40 | owner | plugin version must be a non-empty string | The plugin version in .claude-plugin/plugin.json is missing or empty, which means a damaged install; reinstall the plugin or run bin/wuwei doctor. |
| cli/wuwei/brief.py:103 | owner | no state.json for this day | Today has no state.json yet, so no brief can be written; run the morning plan (/wuwei:wuwei-plan) or bin/wuwei plan propose first. |
| cli/wuwei/brief.py:136 | owner | unknown gate item: {item} | No item named {item} is in today's plan; check the name with bin/wuwei status, or admit it with bin/wuwei plan add {item}. |
| cli/wuwei/brief.py:184 | owner | ruling id(s)   resolve in no decisions, specs or gate_policy | The brief cites ruling ids ({...}) that exist in no decision, spec or gate_policy; correct the ids in the body, or record the decision first (bin/wuwei decision template). |
| cli/wuwei/brief.py:207 | owner | gate verdict goes in its verdict file, never inline | Gate verdicts go in their own verdict file, never in the reply; remove the "return inline" wording from the brief body, since wuwei adds the verdict file line itself. |
| cli/wuwei/brief.py:209 | owner | body restates a verdict path | The body repeats a decisions/gate-... path; wuwei adds the verdict file line itself, so delete that path from the body. |
| cli/wuwei/brief.py:213 | owner | track must be SLICE or FULL | --track must be SLICE or FULL; use one of those two. |
| cli/wuwei/brief.py:217 | owner | gate requires a worktree | A gate brief needs a worktree to review; pass --worktree <path> or create one with bin/wuwei worktree add <item>. |
| cli/wuwei/brief.py:232 | owner | unknown charter: {charter} | Charter {charter} was not found, so the role name is wrong or the plugin install is damaged; check the role spelling (builder, planner, arch...) or run bin/wuwei doctor. |
| cli/wuwei/brief.py:252 | owner | gate brief on a dirty tree: , | The worktree has uncommitted changes ({...}) and a gate reviews committed work; have the builder commit or discard them, then write the gate brief again. |
| cli/wuwei/brief.py:307 | owner | gate brief on a dirty tree: , | The worktree became dirty while the brief was being written ({...}); commit or discard the changes, then write the gate brief again. |
| cli/wuwei/brief_pack.py:18 | unmeasured | {label} unavailable | The {label} adapter failed or is not set up, so the brief cannot use it. Check adapters.{label} with `bin/wuwei config set` (host terminal) (`bin/wuwei config check`) and run `bin/wuwei doctor`. |
| cli/wuwei/brief_pack.py:55 | owner | calendar returned invalid events | The calendar adapter returned something that is not a list of events, so the feed or adapter is broken. Check adapters.calendar and calendar.url, then run `bin/wuwei doctor`. |
| cli/wuwei/brief_pack.py:60 | owner | no attendee meeting in lead window | No meeting with attendees starts within brief.lead_minutes, so there is no meeting pack to build. Run `bin/wuwei brief pack` for the daily pack, or raise brief.lead_minutes. |
| cli/wuwei/brief_pack.py:88 | owner | transcripts returned invalid records | The transcripts adapter returned something that is not a list of records, so it is broken. Check adapters.transcripts with `bin/wuwei config set` (host terminal), or set it to none, then run `bin/wuwei doctor`. |
| cli/wuwei/brief_pack.py:105 | owner | brief exceeds five-minute audio limit | The brief is over 600 words, too long for five minutes of audio. Ask the owner to run `bin/wuwei config set brief.style.length '"concise"'` to shorten it. |
| cli/wuwei/brief_pack.py:131 | owner | tts returned invalid result | The tts adapter did not return a clear performed true or false, so it is broken. Fix it or set adapters.tts to none, then run `bin/wuwei doctor`. |
| cli/wuwei/brief_pack.py:153 | owner | no meeting pack | No meeting pack exists yet, so there is nothing to answer. Build it with `bin/wuwei brief pack --meeting`, then answer with `bin/wuwei brief answer <1-3> "<text>" --meeting`. |
| cli/wuwei/brief_pack.py:158 | owner | question must be 1, 2 or 3 | The question number must be 1, 2 or 3, for example `bin/wuwei brief answer 1 "<your answer>"`. |
| cli/wuwei/brief_pack.py:166 | owner | question already answered | Question {number} is already answered, and each is scored once. Answer another number (1, 2 or 3) or wait for the next pack. |
| cli/wuwei/calibrate.py:731 | owner | checkout is not a directory | The repository checkout is missing, so calibration drift is reported as unmeasured. Restore the checkout or fix repos.<n>.path with `bin/wuwei config set repos.<n>.path '"<dir>"'`. |
| cli/wuwei/closing.py:17 | owner | retro.charter_paths must not be empty | retro.charter_paths with `bin/wuwei config set` (host terminal) is empty. The owner lists the charter folders the retro may change, for example [".wuwei/charters"], on the host. |
| cli/wuwei/closing.py:22 | owner | retro paths must be literal repository-relative paths | retro.charter_paths and retro.changelog must be plain relative paths: no absolute paths, '..', wildcards or leading '-' or ':'. The owner fixes them with `bin/wuwei config set` (host terminal). |
| cli/wuwei/closing.py:42 | owner | retro evidence must belong to today | Retro evidence must sit in today's retro folder. Recapture with the retro session (bin/wuwei retro) instead of pointing at an older day's file. |
| cli/wuwei/closing.py:113 | owner | Applied path outside retro.charter_paths: {path} | The retro's Applied section lists {path}, which is outside retro.charter_paths. Remove it from Applied, or ask the owner to add its folder to retro.charter_paths. |
| cli/wuwei/closing.py:174 | owner | decisions directory must belong to today | Today's decisions folder is a symlink, which WUWEI refuses. Replace it with a real directory (the owner does this), then run bin/wuwei doctor. |
| cli/wuwei/commands/brief.py:46 | owner | REFUSED: {exc} | REFUSED: {exc}; fix the one thing the reason names (brief text, worktree or plan state) and rerun the same bin/wuwei brief command. |
| cli/wuwei/commands/build.py:27 | usage | usage: build next <item> [<brief> <worktree>] or build check <item> | Wrong arguments. Use `bin/wuwei build next <item>` for the next builder action, or `bin/wuwei build check <item>` after the builder stops. next also accepts `<brief> <worktree>` after the item. |
| cli/wuwei/commands/build.py:34 | owner | build: parked {item}: {action['reason']}; decision {action['decision']} | Build {...} is parked: {...}. Repeated failures or the iteration limit stopped it. The owner answers decision {...} with `bin/wuwei decision outcome <D-n> <option>`, then resume the item. |
| cli/wuwei/commands/build.py:41 | usage | usage: build next <item> or build <item> <brief> <worktree> (Codex only) | Wrong arguments. For a Claude builder use `bin/wuwei build next <item>`; for a Codex builder use `bin/wuwei build <item> <brief> <worktree>`. |
| cli/wuwei/commands/build.py:44 | owner | build: {exc} | The build step stopped: {...}. Fix that cause and rerun the same `bin/wuwei build ...` command; `bin/wuwei why <item>` shows the record, `bin/wuwei doctor` checks the runtime adapter. |
| cli/wuwei/commands/build.py:47 | owner | build: {exc} | The build step stopped: {...}. Fix that cause and rerun the same `bin/wuwei build ...` command; `bin/wuwei why <item>` shows the record, `bin/wuwei doctor` checks the setup. |
| cli/wuwei/commands/build.py:89 | config | worktree has no configured fast checks | No fast checks are configured for this repository, so the build cannot be verified. Add fast_checks to its [[repos]] entry with `bin/wuwei config set` (host terminal) (`bin/wuwei calibrate` can propose them), then retry. |
| cli/wuwei/commands/build.py:118 | owner | no logged builder brief for item | No builder brief was logged for this item. Write one with `bin/wuwei brief`, or pass the paths yourself: `bin/wuwei build next <item> <brief> <worktree>`. |
| cli/wuwei/commands/build.py:122 | owner | builder brief needs a worktree | The builder brief names no worktree. Create one with `bin/wuwei worktree add <item>` and write the brief with --worktree, or pass it: `bin/wuwei build next <item> <brief> <worktree>`. |
| cli/wuwei/commands/build.py:156 | owner | unknown item {item} | No item {item} in today's plan. Check the name with `bin/wuwei status`, or admit it after the morning gate with `bin/wuwei plan add {item}`. |
| cli/wuwei/commands/build.py:209 | owner | build is not ready for a seat | The build is not in the ready state, so no seat can start for it. Run `bin/wuwei build next <item>` for the current step; `bin/wuwei why <item>` explains the state. |
| cli/wuwei/commands/build.py:211 | owner | seat brief differs from active build | The seat was started with a different brief than the active build. Start the seat with the brief that `bin/wuwei build next <item>` returned. |
| cli/wuwei/commands/build.py:326 | owner | build is not awaiting checks | Checks were reported for a build that is not waiting for them. Run `bin/wuwei build next <item>` for the current step; if it repeats, run `bin/wuwei doctor`. |
| cli/wuwei/commands/build.py:329 | owner | incomplete fast checks | Fewer fast-check results arrived than commands are configured, which is an internal mismatch. Rerun `bin/wuwei fast-checks` in the worktree; if it repeats, run `bin/wuwei doctor`. |
| cli/wuwei/commands/build.py:373 | owner | build is not awaiting checks | Checks only run after the builder has stopped. Run `bin/wuwei build next <item>` to see the current step; call `bin/wuwei build check <item>` only when it says check. |
| cli/wuwei/commands/build.py:378 | owner | incomplete fast checks | Not every configured fast check has a recorded result. Run `bin/wuwei fast-checks` in the worktree, then `bin/wuwei build check <item>` again. |
| cli/wuwei/commands/build.py:422 | owner | runtime seat {status['status']} | The Codex builder job ended as {...}. Rerun `bin/wuwei build <item> <brief> <worktree>` to resume; if it fails again, `bin/wuwei doctor` tests the runtime adapter. |
| cli/wuwei/commands/build.py:434 | owner | Claude builders require build next <item> in the planner session | Claude builders run inside the planner session, not in this loop. Use `bin/wuwei build next <item>`, or switch the builder runtime to codex with `bin/wuwei config set` (host terminal). |
| cli/wuwei/commands/build.py:436 | usage | usage: build <item> <brief> <worktree> (Codex only) | A Codex build needs all three arguments: `bin/wuwei build <item> <brief> <worktree>`. |
| cli/wuwei/commands/build.py:447 | owner | build: parked {item}: {action['reason']}; decision {action['decision']} | Build {...} is parked: {...}. Repeated failures or the iteration limit stopped it. The owner answers decision {...} with `bin/wuwei decision outcome <D-n> <option>`, then resume the item. |
| cli/wuwei/commands/build.py:464 | owner | build: {exc} | The build step stopped: {...}. Fix that cause and rerun the same `bin/wuwei build ...` command; `bin/wuwei why <item>` shows the record, `bin/wuwei doctor` checks the runtime adapter. |
| cli/wuwei/commands/build.py:467 | owner | build: {exc} | The build step stopped: {...}. Fix that cause and rerun the same `bin/wuwei build ...` command; `bin/wuwei why <item>` shows the record, `bin/wuwei doctor` checks the setup. |
| cli/wuwei/commands/close.py:22 | owner | day state missing; close cannot infer empty ownership | There is no state for today, so close cannot tell what you own. Nothing was started today; run `bin/wuwei plan propose` first if you meant to work, or skip the close. |
| cli/wuwei/commands/config.py:141 | config | config.toml and calibration.json must not be symlinks | config.toml or calibration.json is a symlink; WUWEI refuses that so the file cannot be swapped silently. Replace it with a regular file in .wuwei, then retry. |
| cli/wuwei/commands/config.py:191 | owner | wuwei {label}: declined; nothing written | wuwei {...}: not confirmed, so nothing was changed. Rerun it and type the confirmation code shown on the host terminal to apply. |
| cli/wuwei/commands/dashboard.py:75 | owner | brief packs: expected records | state.json holds brief_packs in the wrong shape, which hand edits or a bug cause; run bin/wuwei doctor, or regenerate the pack with bin/wuwei brief pack. |
| cli/wuwei/commands/dashboard.py:81 | owner | briefing pack path is invalid | The recorded briefing pack path does not match today's expected location; regenerate it with bin/wuwei brief pack, and run bin/wuwei doctor if it repeats. |
| cli/wuwei/commands/dashboard.py:85 | owner | briefing pack path is invalid | The recorded briefing pack path does not match today's expected location; regenerate it with bin/wuwei brief pack, and run bin/wuwei doctor if it repeats. |
| cli/wuwei/commands/decision.py:50 | owner | decision: {exc} | decision route --external failed: {exc}; check the item name with bin/wuwei status, then rerun bin/wuwei decision route <id> --external <item>. |
| cli/wuwei/commands/decision.py:76 | unmeasured | decision show: could not read {path}: {exc} | decision show cannot read {path}: {exc}; check the id is one of today's decision files and that the file is readable. |
| cli/wuwei/commands/decision.py:78 | owner | decision show: {exc} | decision show found an invalid record: {exc}; fix the file (bin/wuwei decision lint <file> checks it, bin/wuwei decision template shows the format). |
| cli/wuwei/commands/decision.py:103 | owner | decision: already answered | This decision already has an owner answer; read it with bin/wuwei decision show <id>. To change course, write a new decision record. |
| cli/wuwei/commands/decision.py:107 | owner | decision: invalid prior outcome | The recorded outcome for this decision is in an unexpected state, which hand edits or a bug cause; run bin/wuwei doctor, then bin/wuwei why <id>. |
| cli/wuwei/commands/decision.py:110 | owner | decision: owner confirmation declined | The confirmation code was not typed, so no outcome was recorded; rerun bin/wuwei decision outcome <id> <option> in a host terminal and type the code it shows. |
| cli/wuwei/commands/doctor.py:126 | owner | no PreToolUse hooks | hooks/hooks.json has no PreToolUse list, so the guards would not run. The plugin install is damaged; reinstall the signed release, then run `bin/wuwei doctor`. |
| cli/wuwei/commands/git_hook.py:24 | owner | hook installation requires a workspace | Hooks need a WUWEI workspace. Run this from a folder that contains .wuwei, or create one first with bin/wuwei init <path>. |
| cli/wuwei/commands/git_hook.py:45 | owner | managed Git hook differs; refusing to overwrite it | A managed Git hook in .wuwei/git-hooks was edited by hand, so the new worktree is not set up. Ask the owner to delete that hook file and create the worktree again; bin/wuwei doctor shows which. |
| cli/wuwei/commands/hook.py:104 | owner |  | KEEP: prints the guard's own message; the coaching text lives in each guard. |
| cli/wuwei/commands/hook.py:112 | owner |  | KEEP: prints the guard's own message; the coaching text lives in each guard. |
| cli/wuwei/commands/init.py:69 | owner | workspace settings must not be owner global settings | bin/wuwei init cannot run in the home folder because it would write your global settings. Change into a project folder, for example ~/acme/widget, and run it there. |
| cli/wuwei/commands/init.py:72 | owner | workspace settings and permissions must be objects | .claude/settings.json in this folder must be a JSON object whose "permissions" is also an object. Fix or move that file, then rerun bin/wuwei init. |
| cli/wuwei/commands/outbound.py:40 | owner | outbound: {reason}deliver as a draft for the owner to send | outbound: {reason}save this as a draft; the owner reviews and sends it. If it said it cannot classify, check the JSON on stdin and run bin/wuwei doctor. |
| cli/wuwei/commands/plan.py:36 | owner | memory/goals.md needs at least one G-n goal for plan template | memory/goals.md has no "## G-1" goal heading for the template to use; the owner adds a goal with its fields (bin/wuwei goals edit in a host terminal), then rerun bin/wuwei plan template. |
| cli/wuwei/commands/rank.py:35 | owner | memory/goals.md needs at least one G-n goal for rank template | Ranking a template needs at least one goal. Add a G-1 line to memory/goals.md with `bin/wuwei goals edit` (owner), then run `bin/wuwei rank template` again. |
| cli/wuwei/commands/runtime.py:61 | owner | runtime: {exc} | runtime: {...}. Check the role, brief and worktree arguments and the runtime adapter with `bin/wuwei config set` (host terminal); `bin/wuwei doctor` tests the adapter. |
| cli/wuwei/commands/setup.py:44 | owner | wuwei {label}: {exc} | wuwei {label}: {exc}. The workspace or config.toml could not be read or is invalid. Fix what the message names; `bin/wuwei config check` and `bin/wuwei doctor` find the rest. |
| cli/wuwei/commands/setup.py:56 | owner | wuwei {label}: {exc} | wuwei {label}: {exc}. The proposed config does not validate, so nothing was changed. Fix the key or value named and run it again; `bin/wuwei config check` validates the current file. |
| cli/wuwei/commands/setup.py:61 | owner | wuwei {label}: {exc} | wuwei {label}: {exc}. The change was not applied. Run it again from the owner host terminal, where it asks for your confirmation; `bin/wuwei doctor` checks the host. |
| cli/wuwei/commands/setup.py:75 | usage | {args.value}: expected one TOML value | {args.value}: expected one TOML value. Quote text, as in `bin/wuwei config set owner.name '"<name>"'`; numbers, true, false and lists such as ["a"] need no extra quotes. |
| cli/wuwei/commands/status.py:240 | owner | calendar returned invalid events | The calendar adapter returned something other than a list of events, so the next meeting is left out (silently); check the adapters.calendar command with bin/wuwei doctor. |
| cli/wuwei/commands/status.py:247 | owner | calendar event needs timezone | A calendar event start has no timezone, so the next meeting is left out (silently); make the calendar adapter print ISO times with an offset, for example 2026-10-03T09:00:00+02:00. |
| cli/wuwei/commands/why.py:89 | owner | no item links {ref} | No recorded day links an item to {ref}; check the PR reference (owner/repo#123) or ask by item name: bin/wuwei why <item>. |
| cli/wuwei/commands/why.py:175 | owner | no recorded refusal | No hook refusal is recorded yet, so there is nothing to explain; after the next refusal run bin/wuwei why last refusal. |
| cli/wuwei/commands/why.py:181 | owner | no recorded refusal {target} | {target} is not a recorded refusal; use bin/wuwei why last refusal, or an event id from bin/wuwei why <item> --full. |
| cli/wuwei/commands/worktree.py:27 | owner | unknown repository: {args.repo} | No configured repository is named {args.repo}. Pass an exact name from the repos list with `bin/wuwei config set` (host terminal), or add it with `bin/wuwei config add-repo --name owner/repo --path <dir> --branch main`. |
| cli/wuwei/commands/worktree.py:31 | config | no repository configured | No repository is configured, so no worktree can be made. Run `bin/wuwei setup`, or `bin/wuwei config add-repo --name owner/repo --path <dir> --branch main`. |
| cli/wuwei/consolidation.py:72 | owner | day directories must be real directories | The days or archive folder is a symlink or missing, but both must be real directories. Replace the link with the real folder; if you did not create it, run `bin/wuwei doctor`. |
| cli/wuwei/consolidation.py:94 | owner | ; | The memory index failed its check before archiving: {...}. Fix the memory files it lists (`bin/wuwei memory lint` shows them) and run `bin/wuwei consolidate` again. |
| cli/wuwei/consolidation.py:100 | owner | ; | The memory index failed its check after old days were moved to the archive: {...}. Fix the listed memory files, then run `bin/wuwei index` to rebuild the index. |
| cli/wuwei/decision.py:56 | owner | Options: expected at least two options | Options needs at least two rows so the owner has a real choice. Add another option, for example a Do nothing row; `bin/wuwei decision template` prints a valid record. |
| cli/wuwei/decision.py:58 | owner | Options: invalid option id | An option id must start with a letter and use only letters, digits, dash or underscore, such as A or defer-1. Rename it in the Options table. |
| cli/wuwei/decision.py:60 | owner | Options: include Do nothing or Defer | Add an option whose description starts with Do nothing or Defer, so the owner can always say no. Add it as a row in Options, Musts and Wants. |
| cli/wuwei/decision.py:92 | owner | missing fields: , | The decision record is missing fields: {...}. Fill in each one; `bin/wuwei decision template` prints every required field with an example. |
| cli/wuwei/decision.py:100 | owner | {key}: expected {'\|'.join(allowed)} | {key} must be one of the allowed values shown ({...}). Edit that line to match exactly; `bin/wuwei decision template` shows the layout. |
| cli/wuwei/decision.py:107 | owner | Musts: no passing option | No option passes every Must. Add an option that meets all of them, or ask the owner whether a Must is too strict, before routing this decision. |
| cli/wuwei/decision.py:111 | owner | Recommendation {recommendation} ({scores[recommendation]}) {reason}requires top passing option {best} ({scores[best]}) | Recommendation {recommendation} must be the top-scoring option that passes every Must, which is {best} ({...}). Recommend {best}, or correct the Wants scores if they are wrong. |
| cli/wuwei/decision.py:151 | owner | {exc} / REJECT: send back to the seat | {exc}; REJECT. Fix what is named above and check again with `bin/wuwei decision lint <file>`, or send the record back to the seat that wrote it. |
| cli/wuwei/decision.py:178 | owner | clarification: unexpected {current} field | A clarification only has Question, Context and Options fields; {current} is not one of them. Remove that field or fold its text into Context. |
| cli/wuwei/decision.py:180 | owner | clarification: duplicate {current} field | Question and Context may appear only once; merge the two {current} fields into one. Only Options may repeat. |
| cli/wuwei/decision.py:184 | owner | clarification: expected Question, Context and Options | Every line must sit under a Question, Context or Options field. Move stray lines and headings under one of those three. |
| cli/wuwei/decision.py:201 | owner | clarification: require one-line Question, Context and at least two Options lines; no table | A clarification needs a one-line Question, a Context with evidence, and at least two different Options lines, written as lines and not a table. Rewrite the file to that shape and save it again. |
| cli/wuwei/decision.py:237 | owner | unknown item: {item} | Item {item} is not in today's state, so the decision cannot wait on it. Use an item id from `bin/wuwei status`. |
| cli/wuwei/decision.py:320 | owner | Decided-by must be seat for a seat-routed decision | Decided-by must match the route: seat only for a two-way decision with blast radius own branch or own PR, owner for everything else. Fix Decided-by, or Reversibility and Blast radius. |
| cli/wuwei/discovery.py:220 | owner | unknown discovery trigger | Discovery trigger must be sweep or seat-free. This is an internal call, so run bin/wuwei doctor and report it if you did not make the call. |
| cli/wuwei/dispatch.py:57 | owner | no worktree | Item {item} has no worktree, so its diff could not be measured and the gate tier rose to standard. Create one with `bin/wuwei worktree add {item}` before dispatching gates. |
| cli/wuwei/dispatch.py:113 | owner | tracker adapter is none | Tracker updates are skipped because adapters.tracker is none. If claims and state changes should reach the tracker, ask the owner to run `bin/wuwei config set adapters.tracker '"<adapter>"'`; otherwise ignore. |
| cli/wuwei/dispatch.py:121 | owner | unknown tracker action | Tracker action {action} is not claim, in_review or done. This is a caller bug nobody can fix by hand; run `bin/wuwei why last refusal` or `bin/wuwei doctor`. |
| cli/wuwei/dispatch.py:140 | owner | item is not approved at the morning gate | Item {item} is not approved at the morning gate, and only approved items run. Before the gate use `bin/wuwei plan approve --items <ids> --goals-confirmed`; after it use `bin/wuwei plan add {item}`. |
| cli/wuwei/dispatch.py:157 | owner | steward note {notes[0]['id']} requires planner acknowledgement: {notes[0]['text']} | Steward note {id} blocks dispatch until you act on it and acknowledge it: {text}. Do what the note says, then run `bin/wuwei steward ack {id}`. |
| cli/wuwei/dispatch.py:161 | owner | item phase {phase} is not dispatchable | Item {item} is in phase {phase}, and only gate, fix and delta phases dispatch. Run `bin/wuwei why {item}` to see where it stands and what comes next. |
| cli/wuwei/dispatch.py:169 | owner | builder must stand down before gates | The builder seat for {item} is still running, and gates must review a frozen HEAD. Let the builder stop, then run `bin/wuwei dispatch next {item}` again. |
| cli/wuwei/dispatch.py:195 | owner | delta phase requires all initial verdicts | The delta round needs every initial verdict, and one is missing from state. Record it with `bin/wuwei dispatch receive {item} <role> <seat>`, or run `bin/wuwei why {item}` to find what was skipped. |
| cli/wuwei/dispatch.py:297 | owner | unknown gate round | The gate round must be initial or delta. Pass `--round delta` to `bin/wuwei dispatch receive` for a delta, or leave the flag out for the initial round. |
| cli/wuwei/dispatch.py:303 | owner | gate round does not match item phase | Round {round} does not fit phase {phase}: initial verdicts belong to phase gate, delta verdicts to phase delta. Run `bin/wuwei dispatch next {item}` for the right round and its receive command. |
| cli/wuwei/dispatch.py:307 | owner | gate did not need a delta | Gate {role} did not return FIX in the initial round, so it has no delta to receive. Drop `--round delta`, or run `bin/wuwei dispatch next {item}` to see what is still open. |
| cli/wuwei/dispatch.py:312 | owner | matching sentinel must stand down before receive | No stopped seat {name} is recorded for this sentinel and item, and a verdict is only received after its seat stops. Wait for the seat to finish, then rerun the same `bin/wuwei dispatch receive`. |
| cli/wuwei/dispatch.py:315 | owner | gate role {role} needs its own runtime seat | Gate {role} must run on its own runtime, and the seat name must end with that runtime. Start a second opinion with `bin/wuwei dispatch opinion {item}` instead of launching it by hand. |
| cli/wuwei/dispatch.py:318 | owner | gate already received | The verdict for gate {role} round {round} on {item} is already recorded, and each gate counts once. Run `bin/wuwei dispatch next {item}` to see what remains. |
| cli/wuwei/dispatch.py:322 | owner | gate verdict must be a regular day file | The verdict file gate-{name}.md in today's decisions folder is a symlink, but it must be a real file. Replace the link with the file itself; if you did not create the link, run `bin/wuwei doctor`. |
| cli/wuwei/dispatch.py:336 | owner | verdict HEAD differs from dispatched brief | The verdict's Head line differs from the commit named in the gate brief, so the sentinel reviewed something else. Have it rewrite the verdict with the Head from its brief, then receive it again. |
| cli/wuwei/dispatch.py:342 | owner | gate brief has an invalid worktree | The gate brief's Worktree line is not an absolute path. Rewrite the brief with `bin/wuwei brief <role> {item} {name} --gate --worktree <absolute path>`; `bin/wuwei worktree add {item}` creates the worktree. |
| cli/wuwei/dispatch.py:346 | owner | verdict HEAD differs from current worktree HEAD | The item worktree has new commits since the sentinel reviewed it, so the verdict is stale. Write a fresh gate brief for the current HEAD and run `bin/wuwei dispatch next {item}`. |
| cli/wuwei/dispatch.py:349 | owner | gate HEAD differs from sibling verdict | This verdict reviewed a different commit than the other gates for the item, and all gates must see the same HEAD. Rerun the odd gate on the current HEAD via `bin/wuwei dispatch next {item}`. |
| cli/wuwei/dispatch.py:353 | unmeasured | scanner: unmeasured: missing reviewed worktree | The security scan needs the reviewed worktree, but the gate brief names none. Rewrite the security brief with `--worktree <absolute path>` (see `bin/wuwei brief`), then receive the verdict again. |
| cli/wuwei/dispatch.py:363 | unmeasured | scanner: unmeasured: {...} | The scanner findings merged into the security verdict failed lint: {...}. Fix the verdict as the message says; check it with `bin/wuwei verdict lint <file>` before receiving it again. |
| cli/wuwei/dispatch.py:399 | owner | item has no second opinion | Item {item} has no second opinion configured, so there is nothing to run. To enable one, ask the owner to run `bin/wuwei config set gates.second_opinion '"<runtime>:<model>"'`. |
| cli/wuwei/dispatch.py:404 | owner | item phase {row['phase']} has no second-opinion round | Second opinions run only in phase gate or delta, and {item} is in phase {phase}. Run `bin/wuwei dispatch next {item}` to see the current step. |
| cli/wuwei/dispatch.py:409 | owner | gate did not need a delta | The second opinion did not return FIX in the initial round, so there is no delta round to run. Run `bin/wuwei dispatch next {item}` for the next step. |
| cli/wuwei/dispatch.py:419 | owner | running seats at host seat ceiling host.seats={config['host']['seats']} | Running seats have reached the limit host.seats={...}; another would overload the machine. Wait for a seat to finish, or ask the owner to raise it with `bin/wuwei config set host.seats <n>`. |
| cli/wuwei/dispatch.py:422 | owner | second-opinion seat is missing | The delta round needs the second-opinion seat from the initial round, and none is recorded. Run `bin/wuwei why {item}` to see whether the initial round ran; if not, run `bin/wuwei dispatch next {item}`. |
| cli/wuwei/dispatch.py:454 | owner | gate verdict must be a regular day file | The second-opinion verdict file in today's decisions folder is a symlink, but it must be a real file. Replace the link with the file itself; if you did not create it, run `bin/wuwei doctor`. |
| cli/wuwei/dispatch.py:485 | owner | unknown discovery trigger | The discovery trigger must be sweep or seat-free. Run `bin/wuwei dispatch discovery sweep` or `bin/wuwei dispatch discovery seat-free`. |
| cli/wuwei/drafts.py:17 | owner | drafts: invalid queue | The drafts queue in day state is malformed. This is damage to state, not something to edit by hand; run `bin/wuwei doctor` or `bin/wuwei why last refusal`. |
| cli/wuwei/drafts.py:29 | owner | drafts: text differs from operation inputs | A draft's text no longer matches its stored message fields, so state was edited or damaged. Do not send it; run `bin/wuwei doctor`, drop it with `bin/wuwei drafts drop <id>` and create the draft again. |
| cli/wuwei/drafts.py:38 | owner | drafts: final text differs from operation inputs | A sent draft's final text does not match its recorded message fields, so state was edited or damaged. Do not resend; run `bin/wuwei doctor` and check the destination by hand. |
| cli/wuwei/drafts.py:44 | owner | drafts: unsupported operation | This channel does not support that operation (chat: post, dm; code host: comment; tracker: create). Use one of those, or ask the owner to act directly. |
| cli/wuwei/drafts.py:75 | owner | drafts: unknown draft ID | No draft has that id. List pending drafts with `bin/wuwei drafts` and copy the id exactly. |
| cli/wuwei/drafts.py:77 | owner | drafts: draft is {row['status']}; cannot decide again | This draft was already {status}, and each draft is decided once. Check `bin/wuwei drafts`; if the message still needs to go, ask for a new draft. |
| cli/wuwei/drafts.py:98 | owner | drafts: editor could not complete | The editor exited with an error, so nothing was sent. Run `bin/wuwei drafts approve <id> --edit` again and save and quit normally; set $EDITOR if you want a different editor than vi. |
| cli/wuwei/drafts.py:125 | config | drafts: adapter configuration changed; cannot replay destination | The adapter for this channel changed with `bin/wuwei config set` (host terminal) since the draft was made, so sending now could go somewhere else. Drop it with `bin/wuwei drafts drop <id>` and ask for a new draft. |
| cli/wuwei/drafts.py:128 | owner | drafts: DM destination changed; cannot replay destination | The owner DM channel setting differs from when the draft was made, so it will not be replayed. Restore the old setting to send it, or drop it with `bin/wuwei drafts drop <id>` and redraft. |
| cli/wuwei/drafts.py:152 | owner | drafts: owner confirmation declined | Nothing was sent: the confirmation text was not typed back. Run `bin/wuwei drafts approve <id>` again from the host terminal and type exactly what it shows. |
| cli/wuwei/drafts.py:172 | owner | drafts: send state changed | The draft changed state while it was sending, so its result may not be recorded. Do not resend; check the destination by hand, then run `bin/wuwei doctor`. |
| cli/wuwei/env.py:63 | owner | .wuwei/env: expected a regular file with mode 0600 | .wuwei/env must be a regular file (not a symlink) readable only by you; run chmod 600 .wuwei/env. |
| cli/wuwei/env.py:66 | owner | .wuwei/env: invalid or oversized credentials file | .wuwei/env is over 64 KB or contains a NUL byte; keep it to plain NAME=value lines and remove any binary content. |
| cli/wuwei/env.py:75 | owner | .wuwei/env: invalid assignment at line {number} | Line {number} of .wuwei/env is not NAME=value (names use letters, digits and underscore); fix the line or turn it into a # comment. |
| cli/wuwei/env.py:78 | owner | .wuwei/env: unmatched quote at line {number} | Line {number} of .wuwei/env opens a quote it never closes; close the quote or remove the quotes. |
| cli/wuwei/env.py:89 | unmeasured | .wuwei/env: cannot read credentials file | .wuwei/env exists but cannot be read (bad encoding or permissions); keep it UTF-8 and run chmod 600 .wuwei/env. |
| cli/wuwei/fast_checks.py:19 | owner | multiple running builds share the check worktree | Two running builds point at the same worktree, so checks cannot tell which one they belong to; stop the extra builder (bin/wuwei build next <item> shows state) or run bin/wuwei doctor. |
| cli/wuwei/goals.py:12 | owner | goals: expected text | The goals file was not read as text, which is an internal fault. Edit goals with `bin/wuwei goals edit`; if it repeats, run `bin/wuwei doctor`. |
| cli/wuwei/goals.py:30 | owner | goals line {number}: invalid or duplicate id | The heading on line {...} must look like `## G-1` and each id can be used once. Fix it with `bin/wuwei goals edit`. |
| cli/wuwei/goals.py:35 | owner | goals line {number}: expected goal field | Line {...} is not a `field: value` line. Under each `## G-n` heading use outcome, measure, target, date and priority, one per line. Fix it with `bin/wuwei goals edit`. |
| cli/wuwei/goals.py:38 | owner | goals line {number}: invalid {key} | Line {...}: {...} is unknown, empty or repeated. Use each of outcome, measure, target, date and priority once, with a value. Fix it with `bin/wuwei goals edit`. |
| cli/wuwei/goals.py:45 | owner | goals line {number}: invalid priority | Line {...}: priority must be a whole number from 1 up (1 is highest). Fix it with `bin/wuwei goals edit`. |
| cli/wuwei/goals.py:50 | owner | goals line {number}: invalid date | Line {...}: date must look like 2026-12-31. Fix it with `bin/wuwei goals edit`. |
| cli/wuwei/goals.py:57 | owner | goals line 1: no goals | No goals found. Add at least one `## G-1` section with outcome, measure, target, date and priority using `bin/wuwei goals edit`. |
| cli/wuwei/guards/__init__.py:80 | owner | warning: {message} | warning: {message}. Allowed this time because profile is standard; fix it now, or ask the owner to set profile to strict with `bin/wuwei config set` (host terminal) to make it a hard stop. |
| cli/wuwei/guards/agent_launch.py:23 | unmeasured | free memory unmeasured | Free memory could not be read (adapters.host may be "none" or the probe failed); set a working host adapter with `bin/wuwei config set` (host terminal), and run bin/wuwei doctor to see which. |
| cli/wuwei/guards/agent_launch.py:105 | unmeasured | events unavailable: {exc} | Today's events.jsonl is missing or corrupt: {exc}; run bin/wuwei doctor, then write the brief again with bin/wuwei brief. |
| cli/wuwei/guards/agent_launch.py:118 | owner | Agent role does not match logged brief role | The Agent subagent_type differs from the role in the logged brief; launch with the role you gave bin/wuwei brief (for example wuwei:builder) or write a new brief for the right role. |
| cli/wuwei/guards/agent_launch.py:122 | owner | brief modified since it was logged | The brief file changed after bin/wuwei brief logged it; never edit briefs by hand. Write a new brief with bin/wuwei brief <role> <item> <new-name> and launch with that. |
| cli/wuwei/guards/agent_launch.py:129 | owner | {role} uses {runtime.capitalize()} runtime, not Agent | {role} is set to the {Runtime} runtime, not Claude, so Agent is the wrong launcher; use bin/wuwei build or bin/wuwei dispatch for it, or set its runtime to claude in the plan's seat_policy. |
| cli/wuwei/guards/agent_launch.py:133 | owner | free memory {available} bytes below floor {floor} | Only {available} bytes of memory are free, below the floor {floor}; close other apps or wait and retry, or lower host.free_memory_mb with `bin/wuwei config set` (host terminal) if the floor is too high. |
| cli/wuwei/guards/agent_launch.py:163 | owner | worktree HEAD changed since brief was written | The worktree moved to a new commit after the brief was written, so the brief is stale; write a new brief with bin/wuwei brief so it records the current HEAD. |
| cli/wuwei/guards/agent_launch.py:171 | owner | gate requires a worktree | A gate brief has no worktree to review, which means it was not written by bin/wuwei brief; write a new one with --worktree <path> (bin/wuwei worktree add <item> makes one). |
| cli/wuwei/guards/agent_launch.py:174 | owner | item worktree changed since brief was written | The item's worktree in state differs from the one in the brief; write a new gate brief with bin/wuwei brief <role> <item> <name> --gate --worktree <current path>. |
| cli/wuwei/guards/agent_launch.py:181 | owner | running build seats {builders} at CAP {config['cap']}{...} | {builders} build seats are running and the cap is {...}; wait for one to finish or raise cap with `bin/wuwei config set` (host terminal); seats named as stale are likely dead, bin/wuwei doctor checks them. |
| cli/wuwei/guards/agent_launch.py:183 | owner | running seats {len(running)} at host seat ceiling host.seats={config['host']['seats']}{...} | {...} seats are running and host.seats allows {...}; wait for one to finish or raise host.seats with `bin/wuwei config set` (host terminal); seats named as stale are likely dead, bin/wuwei doctor checks them. |
| cli/wuwei/guards/agent_launch.py:255 | unmeasured | build result could not be recorded: {exc} | A builder stopped but wuwei could not record its result: {exc}; run bin/wuwei doctor, then bin/wuwei build next <item> to see where the item stands. |
| cli/wuwei/guards/agent_launch.py:268 | unmeasured | discovery failure could not be recorded: {log_error} | Seat-free discovery failed and the failure could not be logged either: {log_error}; run bin/wuwei doctor and check disk space and write access in .wuwei. |
| cli/wuwei/guards/agent_launch.py:269 | unmeasured | discovery unmeasured: {exc} | Seat-free discovery failed: {exc}; retry with bin/wuwei dispatch discovery seat-free, and run bin/wuwei doctor if it repeats. |
| cli/wuwei/guards/commit_push.py:36 | owner | HEAD author/committer do not match configured identity | HEAD was authored or committed under a different identity than the configured one. In the item worktree run `git commit --amend --reset-author --no-edit`, then push again. |
| cli/wuwei/guards/commit_push.py:39 | unmeasured | could not check identity: {exc} | The commit identity could not be read, so the push is blocked: {exc}. Check that repos.<n>.identity has a name and email with `bin/wuwei config set` (host terminal) (`bin/wuwei config add-repo --identity` sets it), then run `bin/wuwei doctor`. |
| cli/wuwei/guards/commit_push.py:59 | owner | GIT_COMMON_DIR overrides cannot be inspected safely | GIT_COMMON_DIR is set, so the guard cannot tell which repository you mean. Run `unset GIT_COMMON_DIR` and rerun plain git from the item worktree. |
| cli/wuwei/guards/commit_push.py:61 | owner | identity-free repository read takes no settings or env overrides | Internal check failed: a repository read without identity was given settings or environment overrides. Nobody can fix this by hand; run `bin/wuwei why last refusal` or `bin/wuwei doctor`. |
| cli/wuwei/guards/commit_push.py:81 | owner | missing repository context | Git did not report an absolute repository path here, so the guard cannot match it to a configured repository. Run the command from inside a repository checkout or worktree; if you are in one, run `bin/wuwei doctor`. |
| cli/wuwei/guards/commit_push.py:91 | config | repository is not configured in this workspace | This repository is not in the WUWEI config, so commits and pushes here are refused. Register it with `bin/wuwei config add-repo --name owner/repo --path <dir> --branch main`, or work in a configured repository. |
| cli/wuwei/guards/commit_push.py:112 | owner | missing default branch | repos.<n>.default_branch is empty with `bin/wuwei config set` (host terminal), so the guard cannot tell which push hits the default branch. Ask the owner to run `bin/wuwei config set repos.<n>.default_branch '"main"'`. |
| cli/wuwei/guards/commit_push.py:116 | owner | only branch pushes are supported; tags require deployment policy | Only pushes to branches are allowed; tags and other refs need deployment policy. Push a branch, for example `git push origin HEAD:refs/heads/<branch>`, and leave tagging to the owner. |
| cli/wuwei/guards/commit_push.py:138 | config | empty configured fast check | A fast_checks entry for this repository with `bin/wuwei config set` (host terminal) is blank, so nothing can run. Fix it with `bin/wuwei config set repos.<n>.fast_checks '["<command>"]'` or remove the empty entry. |
| cli/wuwei/guards/commit_push.py:141 | owner | fast check has not passed for current HEAD: {check} | Fast check `{check}` has no passing record for this HEAD yet. Run `bin/wuwei fast-checks` from the repository, fix any failure, then push again. |
| cli/wuwei/guards/commit_push.py:146 | owner | fast check has not passed for current HEAD: {check} | Fast check `{check}` failed, or passed only on an older commit than HEAD. Fix the failure and run `bin/wuwei fast-checks` again after your last commit, then push. |
| cli/wuwei/guards/commit_push.py:318 | owner | too many possible working directories; split the command | The command changes directory in so many ways that the guard cannot tell where git runs. Split it into separate calls, each using one `cd` or `git -C <dir>`. |
| cli/wuwei/guards/commit_push.py:345 | owner | unsupported environment clearing around Git | `env -i`, `env -u` and `exec -c` hide the Git identity from the guard. Run git with the normal environment, without clearing or unsetting variables. |
| cli/wuwei/guards/commit_push.py:347 | owner | standalone environment assignment before Git | A bare `NAME=value;` assignment before git changes the environment in a way the guard cannot follow. Put the assignment directly in front of the git command, or drop it. |
| cli/wuwei/guards/commit_push.py:379 | owner | changing Git hook configuration is refused | Changing core.hooksPath or extensions.worktreeConfig would switch off WUWEI's Git hooks, so it is refused. Leave hook settings alone; reading them with `git config --get` is fine. Only the owner changes them by hand. |
| cli/wuwei/guards/commit_push.py:386 | owner | unsupported compound Git command | The guard cannot check this git command inside a longer command line. Run it as its own call, without `&&`, `;` or pipes. |
| cli/wuwei/guards/commit_push.py:389 | config | unsupported Git configuration or executable environment override | Setting HOME, XDG_CONFIG_HOME or PATH on a git command could swap the Git config or binary the guard checks. Remove the override and run git with the normal environment. |
| cli/wuwei/guards/commit_push.py:392 | owner | unsupported GIT_* override | This GIT_* variable is not on the allowed list (identity, repository, editor and pager variables). Remove it from the command; if you truly need it, ask the owner. |
| cli/wuwei/guards/commit_push.py:404 | owner | Git configuration override differs from configured identity | A `-c user.name` or `user.email` override differs from the configured identity. Drop the override; commits already use the identity in repos.<n>.identity when the worktree comes from `bin/wuwei worktree add`. |
| cli/wuwei/guards/commit_push.py:408 | owner | Git environment override differs from configured identity | A GIT_AUTHOR_* or GIT_COMMITTER_* variable differs from the configured identity. Unset it, or set it to the exact name and email in repos.<n>.identity. |
| cli/wuwei/guards/decision.py:146 | owner | decision question: {exc} / {hint} | decision question: {...}. The check could not run. Cite a decision D-n that exists today (`bin/wuwei decision template`, then `bin/wuwei decision lint <file>`), or mark Morning gate and cite today's plan file. |
| cli/wuwei/guards/decision.py:189 | owner | decision question: {exc} | decision question: {...}. The seat-stop check could not run; run `bin/wuwei doctor`. A seat that asks the owner must cite a decision record D-n (`bin/wuwei decision template`). |
| cli/wuwei/guards/deploy.py:37 | owner | deploy: refused by {rule} | Deploy blocked by {rule}: deploying is an owner action. Stop and ask the owner to run it, or review {rule} with `bin/wuwei config set` (host terminal) if it should not apply. |
| cli/wuwei/guards/deploy.py:313 | unmeasured | deploy: could not inspect: {exc} | The deploy guard cannot read this command ({exc}), so it refuses. Rewrite it as plain literal commands without variables or eval, or ask the owner to run it. |
| cli/wuwei/guards/lifecycle.py:38 | unmeasured | session unmeasured: {exc} | Session start could not read the workspace: {exc}; run bin/wuwei doctor to find the broken config or state file. |
| cli/wuwei/guards/lifecycle.py:96 | unmeasured | compaction consistency unmeasured: {exc} | Saving state before compaction failed: {exc}; run bin/wuwei doctor, and check disk space and write access in .wuwei. |
| cli/wuwei/guards/pr.py:96 | owner | initial gate verdicts disagree on HEAD | The recorded arch, quality and security verdicts were written for different commits; re-run the gates on the current HEAD (bin/wuwei dispatch next <item>), then raise the PR. |
| cli/wuwei/guards/pr.py:110 | owner | gate verdict path is outside the day decisions | A recorded gate verdict points outside today's decisions folder or at a symlink, which only tampering or a bug causes; run bin/wuwei doctor, then bin/wuwei why last refusal. |
| cli/wuwei/guards/pr.py:114 | owner | {role} verdict: {reason} | The {role} verdict file failed its format check: {reason}; fix the file (bin/wuwei verdict lint <file> --role {role} shows the same check) or have the gate rewrite it. |
| cli/wuwei/guards/pr.py:119 | owner | {role} recorded verdict differs from file | The {role} verdict file changed after bin/wuwei dispatch receive recorded it, so the evidence no longer matches; re-run the {role} gate and record it again with bin/wuwei dispatch receive. |
| cli/wuwei/guards/pr.py:123 | owner | {role} recorded blocking status differs from file | The {role} verdict file's blocking status differs from what was recorded, so the file changed after recording; re-run the {role} gate and record it again with bin/wuwei dispatch receive. |
| cli/wuwei/guards/pr.py:182 | owner | {gate} verdict: {exc} | The {gate} gate verdict could not be used: {exc}; fix that verdict file (bin/wuwei verdict lint <file> --role {gate}) or re-run the gate for this HEAD. |
| cli/wuwei/guards/pr.py:197 | owner | repository override cannot be tied to the checked local HEAD | gh pr create with -R or --repo cannot be tied to the HEAD that was checked; drop it and run gh pr create from inside the repository checkout. |
| cli/wuwei/guards/pr.py:199 | owner | explicit head cannot be tied to the checked local HEAD | gh pr create --head cannot be tied to the HEAD that was checked; drop it and create the PR from the branch checked out in the worktree. |
| cli/wuwei/guards/pr.py:203 | owner | repository environment override cannot be verified | GIT_DIR, GIT_WORK_TREE, GIT_CONFIG*, GH_REPO, GH_HOST or GH_CONFIG_DIR is set, so the PR cannot be tied to the checked HEAD; unset it and run gh pr create from the repository checkout. |
| cli/wuwei/guards/pr.py:243 | owner | branch protection changes are refused | Changing branch protection or rulesets through gh api is the owner's call and is blocked here; ask the owner to change it in the repository settings. |
| cli/wuwei/guards/pr.py:256 | unmeasured | API repository default branch is unmeasured | This repository is not with `bin/wuwei config set` (host terminal), so its default branch is unknown and the ref update cannot be judged; the owner adds it with bin/wuwei config add-repo, or use a normal push on a feature branch. |
| cli/wuwei/guards/pr.py:262 | owner | PR approval is refused | Approving a PR through the API is blocked because approvals come from humans; post a comment (event=COMMENT) or request changes, and leave approval to the owner. |
| cli/wuwei/guards/pr.py:264 | owner | opaque review body; cannot rule out approval | The review body is hidden from the guard (--input, no event, or an unknown event), so approval cannot be ruled out; use -f event=COMMENT or REQUEST_CHANGES with -f body=... fields. |
| cli/wuwei/guards/pr.py:291 | owner | missing repository value | -R or --repo has no value; write -R owner/repo. |
| cli/wuwei/guards/pr.py:294 | owner | unsupported gh global option | The guard understands only -R or --repo before the gh subcommand; move other options after the subcommand or drop them. |
| cli/wuwei/guards/pr.py:307 | owner | gh alias changes are refused | gh alias set, import and delete can hide a blocked command behind a short name; use the full gh command instead. |
| cli/wuwei/guards/pr.py:321 | owner | admin merge is refused | gh pr merge --admin skips branch protection and is blocked; drop --admin, fix what blocks the merge (bin/wuwei merge check <pr> lists it), or ask the owner to merge. |
| cli/wuwei/guards/pr.py:329 | owner | PR approval is refused | gh pr review --approve is blocked because approvals come from humans; use --comment or --request-changes, and leave approval to the owner. |
| cli/wuwei/guards/pr.py:377 | owner | too many possible directories; split the command | The command has so many cd, pushd or GIT_DIR branches that the guard cannot follow where it runs; split it into separate commands, one directory each. |
| cli/wuwei/guards/protect_state.py:45 | owner | Decision outcomes require the owner terminal, outside agent tools. | Recording a decision outcome is an owner action. Stop and ask the owner to run bin/wuwei decision outcome in their own host terminal, outside the agent session. |
| cli/wuwei/guards/protect_state.py:46 | owner | Draft decisions require the owner terminal, outside agent tools. | Approving a draft is an owner action. Leave the draft pending and ask the owner to run bin/wuwei drafts approve in their own host terminal. |
| cli/wuwei/guards/protect_state.py:47 | owner | Draft decisions require the owner terminal, outside agent tools. | Dropping a draft is an owner action. Leave the draft as it is and ask the owner to run bin/wuwei drafts drop in their own host terminal. |
| cli/wuwei/guards/protect_state.py:48 | owner | MCP decisions require the owner terminal, outside agent tools. | Deciding an MCP server is an owner action. Ask the owner to run bin/wuwei mcp decide in their own host terminal, outside the agent session. |
| cli/wuwei/guards/protect_state.py:49 | owner | Integrity re-confirmation is an owner action on the host, outside agent tools. | Re-confirming plugin integrity is an owner action on the host. Report the integrity page and ask the owner to run bin/wuwei integrity reconfirm in their own terminal. |
| cli/wuwei/guards/protect_state.py:50 | owner | State recovery is an owner action on the host, outside agent tools. | Restoring broken state is an owner action on the host. Ask the owner to run bin/wuwei state recover in their own terminal; agents must not try workarounds. |
| cli/wuwei/guards/protect_state.py:52 | owner | Watch uninstall requires the owner terminal, outside agent tools. | Removing the watch would silence dead-watch alerts, so only the owner can. Ask the owner to run bin/wuwei watch uninstall in their own terminal. |
| cli/wuwei/guards/protect_state.py:54 | owner | Listener uninstall requires the owner terminal, outside agent tools. | Removing the listener would silence dead-listener alerts, so only the owner can. Ask the owner to run bin/wuwei listen uninstall in their own terminal. |
| cli/wuwei/guards/protect_state.py:55 | owner | Owner memory edits are an owner action on the host, outside agent tools. | Goals are edited by the owner only. Describe the change you want in your message and ask the owner to run bin/wuwei goals edit in their own terminal. |
| cli/wuwei/guards/protect_state.py:56 | owner | Owner memory edits are an owner action on the host, outside agent tools. | The voice profile is edited by the owner only. Describe the change you want in your message and ask the owner to run bin/wuwei voice edit in their own terminal. |
| cli/wuwei/guards/protect_state.py:58 | owner | Remote acknowledgements require the owner terminal, outside agent tools. | Acknowledging a remote refusal would stop paging, so only the owner can. Ask the owner to run bin/wuwei remote ack in their own terminal after reading the alert. |
| cli/wuwei/guards/protect_state.py:60 | owner | Calibration promotion is an owner action on the host, outside agent tools. | Promoting calibration changes config.toml, so only the owner runs it. Ask the owner to review the proposal, then run bin/wuwei config promote in their own terminal. |
| cli/wuwei/guards/protect_state.py:61 | owner | Config edits are an owner action on the host, outside agent tools. | config.toml holds commands and merge rules, so only the owner changes it. Ask the owner to run bin/wuwei config set in their own terminal with the key and value you want. |
| cli/wuwei/guards/protect_state.py:62 | owner | Config edits are an owner action on the host, outside agent tools. | config.toml holds the repository list, so only the owner adds a repo. Ask the owner to run bin/wuwei config add-repo in their own terminal. |
| cli/wuwei/guards/protect_state.py:64 | owner | Setup writes config.toml; it is an owner action on the host, outside agent tools. | Setup writes config.toml, so only the owner runs it. Ask the owner to run bin/wuwei setup in their own host terminal, outside the agent session. |
| cli/wuwei/guards/protect_state.py:285 | owner | missing target directory | The cp, mv or rsync command has -t without a directory after it. Add the target directory, for example mv -t dest/ file, and run it again. |
| cli/wuwei/guards/protect_state.py:373 | owner | cd requires a single literal directory | cd was given more than one argument. Use one literal directory, or run git -C <dir> ... or a subshell: (cd dir && command). |
| cli/wuwei/guards/protect_state.py:482 | owner | too many possible working directories; split the command | This command could end up in more than 64 possible directories, so it cannot be checked. Split it into separate Bash calls, or use git -C <dir>. |
| cli/wuwei/guards/stop.py:30 | owner | day close needs a registered planner session | Day close was requested, but no planner session is registered to run it. From the planner session run `bin/wuwei plan session <session-id>`, then `bin/wuwei close`. |
| cli/wuwei/guards/stop.py:34 | owner | day state missing for registered planner | The registered planner has no state file for today, so close cannot check what is open. Run `bin/wuwei doctor`; if state was lost it can point you to `bin/wuwei state recover`. |
| cli/wuwei/integrity.py:49 | owner | installed plugin directory missing | The plugin directory is missing (moved or deleted). Reinstall the plugin, then run bin/wuwei integrity check on the host. |
| cli/wuwei/integrity.py:80 | unmeasured | checkout tracked files unmeasured: {...} | Could not list the plugin checkout's tracked files ({...}), so integrity is unmeasured. Check that git works in the plugin directory, then run bin/wuwei integrity check. |
| cli/wuwei/integrity.py:126 | unmeasured | plugin integrity unmeasured: {exc} | Plugin integrity could not be measured ({exc}), usually a missing or unreadable plugin file. Run bin/wuwei integrity check on the host, then bin/wuwei doctor. |
| cli/wuwei/integrity.py:128 | owner | page: plugin integrity: {exc} | page: plugin integrity: {exc}. Files differ from the signed manifest; reinstall the plugin, or for a development checkout commit cleanly and run bin/wuwei integrity reconfirm on the host. |
| cli/wuwei/integrity.py:156 | unmeasured | checkout HEAD unmeasured: {...} | Could not read the plugin checkout's HEAD ({...}). Make sure git runs in the plugin directory, then run bin/wuwei integrity check. |
| cli/wuwei/integrity.py:162 | unmeasured | checkout tree unmeasured: {...} | Could not read the plugin checkout's status ({...}). Make sure git runs in the plugin directory, then run bin/wuwei integrity check. |
| cli/wuwei/integrity.py:190 | unmeasured | plugin integrity unmeasured: {exc} | Plugin integrity could not be measured ({exc}). Run bin/wuwei integrity check on the host to measure again, then bin/wuwei doctor if it repeats. |
| cli/wuwei/integrity.py:236 | unmeasured | plugin integrity unmeasured: {exc} | Plugin integrity could not be checked for changed files ({exc}). Run bin/wuwei integrity check on the host to measure again, then bin/wuwei doctor if it repeats. |
| cli/wuwei/integrity.py:267 | owner | integrity re-confirmation declined | Re-confirmation cancelled: the typed fingerprint did not match. Rerun bin/wuwei integrity reconfirm on the host and copy the fingerprint exactly. |
| cli/wuwei/integrity.py:277 | unmeasured | host confirmation unmeasured: {exc} | Host confirmation failed ({exc}). Run bin/wuwei integrity reconfirm in a real terminal (not via an agent or a pipe), where it can prompt you. |
| cli/wuwei/integrity.py:295 | unmeasured | workspace integrity unmeasured: {...} | Workspace history could not be read ({...}), so workspace integrity is unmeasured. Check that git works inside .wuwei, then run bin/wuwei doctor. |
| cli/wuwei/integrity.py:305 | unmeasured | workspace integrity unmeasured: {exc} | Workspace integrity could not be measured ({exc}). Check that .wuwei history is readable (git -C .wuwei status), then run bin/wuwei doctor. |
| cli/wuwei/interview.py:27 | owner | expected 1 to 20 comma-separated items of letters, digits, spaces and ._/()*@+- | Answer with 1 to 20 comma-separated items using only letters, digits, spaces and . _ / ( ) * @ + -; no sentences that read like instructions. Shorten the answer or split it into items. |
| cli/wuwei/interview.py:34 | owner | expected 1 to 20 comma-separated HH:MM-HH:MM windows | Give 1 to 20 comma-separated windows in 24-hour form HH:MM-HH:MM, for example 22:00-07:00, 12:00-13:00. |
| cli/wuwei/interview.py:45 | owner | unknown time zone {zone.strip()} | Unknown time zone {...}. Use an IANA name such as Europe/Berlin or America/New_York. |
| cli/wuwei/interview.py:194 | owner | {qid}: expected text | {qid}: the answer must be text, either one of the listed choice labels or free text where the question allows it. Run `bin/wuwei calibrate --questions` to see the choices. |
| cli/wuwei/interview.py:273 | config | {qid}: expected answers keyed by configured repositories | {qid}: today's interview.json answers a repository that is not in the config. Run `bin/wuwei calibrate --interview` again for the configured repositories, or remove the stale answer. |
| cli/wuwei/interview.py:278 | config | interview.json: {exc} | interview.json is invalid: {exc}. Run `bin/wuwei calibrate --interview` to replace today's answers. |
| cli/wuwei/interview.py:393 | owner | expected ID=VALUE, got {pair} | Each answer must be written ID=VALUE, but got {pair}. Run `bin/wuwei calibrate --questions` for the ids, then pass `--answer ID=VALUE`. |
| cli/wuwei/mcp.py:76 | owner | missing plugin project path | Claude's installed-plugins file has a project or local plugin entry without projectPath, so the registry cannot tell which repo it belongs to; reinstall that plugin, then run bin/wuwei mcp check. |
| cli/wuwei/mcp.py:84 | unmeasured | installed plugin directory unavailable | A plugin listed as installed has no folder on disk, so its MCP servers cannot be read; reinstall or uninstall that plugin in Claude Code, then run bin/wuwei mcp check. |
| cli/wuwei/mcp.py:280 | owner | MCP registry findings: owner decision required in {...} | The MCP scan found servers that need an owner decision in {...}; the owner reads the reports and runs bin/wuwei mcp decide in a host terminal, then seats can launch. |
| cli/wuwei/mcp.py:317 | unmeasured | MCP registry unmeasured: morning check is stale | The MCP registry was last checked on an earlier day; run bin/wuwei mcp check (or the morning plan) to refresh it. |
| cli/wuwei/mcp.py:469 | unmeasured | MCP registry servers not unmeasured today: , | {...} were not unmeasured in today's check, so there is nothing to proceed on; run bin/wuwei mcp check, then use a server name it lists with bin/wuwei mcp decide proceed-unmeasured <server>. |
| cli/wuwei/mcp.py:477 | owner | MCP registry owner confirmation declined | The confirmation code was not typed, so nothing was accepted; rerun bin/wuwei mcp decide proceed-unmeasured <server> in a host terminal and type the code it shows. |
| cli/wuwei/mcp.py:517 | owner | MCP registry has no pending decision | No MCP finding is waiting for a decision, so there is nothing to do; if you expected one, run bin/wuwei mcp check first. |
| cli/wuwei/mcp.py:521 | owner | MCP registry has no pending decision | No MCP finding is waiting for a decision, so there is nothing to do; if you expected one, run bin/wuwei mcp check first. |
| cli/wuwei/mcp.py:535 | owner | MCP registry owner confirmation declined | The confirmation code was not typed, so nothing was accepted; read the reports, then rerun bin/wuwei mcp decide in a host terminal and type the code it shows. |
| cli/wuwei/memory.py:236 | owner | {trace}:{number}: invalid trace: {exc} | A trace line at {...}:{...} is invalid: {...}. Traces are append-only logs, so do not hand-edit them; run `bin/wuwei doctor`. |
| cli/wuwei/merge.py:41 | owner | adapter returned an error body | The code host answered with an error instead of data (login, permission, rate limit or network); check the gh login, then retry bin/wuwei merge check <pr>. |
| cli/wuwei/merge.py:57 | config | numeric PR requires an unambiguous configured repository | A bare PR number needs exactly one matching configured repo; pass owner/repo#123, or run the command from inside the one repository checkout. |
| cli/wuwei/merge.py:83 | owner | PR identity differs from requested PR | The host returned a different PR than the one requested, which should not happen; retry with owner/repo#123, and if it repeats run bin/wuwei doctor. |
| cli/wuwei/merge.py:147 | owner | approved item risk evidence is missing; replan the item | The approved plan has no risk flags recorded for this item, so auto-merge cannot check them; replan the item (bin/wuwei plan add <item>) or ask the owner to merge it. |
| cli/wuwei/merge.py:167 | config | merge.bot_login required for a configured review bot | A review bot is configured but merge.bot_login is empty; the owner sets it with bin/wuwei config set repos.0.merge.bot_login '"acme-bot"' or sets adapters.review_bot to "none". |
| cli/wuwei/merge.py:221 | owner | missing base branch | The host returned no base branch for this PR, so the base rules cannot be checked; retry bin/wuwei merge check <pr>, and if it repeats the owner merges. |
| cli/wuwei/merge.py:232 | unmeasured | mergeability unmeasured | GitHub has not finished working out whether this PR merges cleanly; wait a minute and run bin/wuwei merge check <pr> again. |
| cli/wuwei/merge.py:235 | owner | incomplete changed files | The host listed a different number of changed files than the PR reports (a very large PR or paging), so the never-auto path check cannot be trusted; the owner reviews and merges this PR. |
| cli/wuwei/merge.py:239 | owner | incomplete diff size | The host's per-file line counts do not add up to the PR totals (a very large PR or paging), so the size limit cannot be trusted; the owner reviews and merges this PR. |
| cli/wuwei/merge.py:356 | owner | merge result could not be verified | The merge request was sent but the host's answer did not confirm this exact HEAD; do not retry. Look at the PR on GitHub; bin/wuwei watch reconciles the recorded intent. |
| cli/wuwei/merge.py:383 | unmeasured | outcome unmeasured: missing text patch | A changed file came back without a text diff (binary or too large), so the 14-day outcome of this merge cannot be tracked and stays unmeasured; the owner checks it by hand. |
| cli/wuwei/merge.py:390 | owner | truncated patch hunk | The host's diff for a file is cut off, so the 14-day outcome of this merge stays unmeasured; the owner checks that file by hand. |
| cli/wuwei/merge.py:415 | owner | incomplete file patch | The host's diff for a file does not match its line counts, so the 14-day outcome of this merge stays unmeasured; the owner checks that file by hand. |
| cli/wuwei/merge.py:438 | owner | nonchronological outcome history | The commit history from the host is out of order, which should not happen; run the watch again later (bin/wuwei watch), and if it repeats run bin/wuwei doctor. |
| cli/wuwei/merge.py:470 | owner | baseline needs one Escaped-defect-rate: fraction between 0 and 1 | The baseline note must contain exactly one line like "Escaped-defect-rate: 0.15" (a fraction from 0 to 1); fix that line in .wuwei/memory/notes/baseline.md. |
| cli/wuwei/merge.py:548 | owner | base checks still incomplete: {exc} | Checks on the merge commit were still incomplete after 14 days: {exc}; open the CI runs for that commit and rerun or fix them, the owner decides. |
| cli/wuwei/metrics.py:97 | owner | transcript unreadable or invalid | The Claude Code transcripts could not be read or parsed (details hidden on purpose). Check metrics.transcripts with `bin/wuwei config set` (host terminal) points at the transcript folder, then run `bin/wuwei doctor`. |
| cli/wuwei/metrics.py:99 | owner | transcript timestamp needs timezone | A transcript row has a time without a timezone, so attention time cannot be measured. The file is likely damaged; run `bin/wuwei doctor` and move that transcript away. |
| cli/wuwei/metrics.py:235 | unmeasured | outcome evidence unavailable from adapter | The code host or tracker returned no usable outcome evidence, so this metric stays unmeasured. Check the adapter token and network with `bin/wuwei doctor`, then rerun the report. |
| cli/wuwei/metrics.py:267 | owner | merge timestamp needs timezone | A merge time has no timezone, which should not happen. This metric stays unmeasured; run `bin/wuwei doctor` and report it. |
| cli/wuwei/metrics.py:315 | owner | empty review thread | The code host returned a review thread with no comments, which should not happen. Retry; if it repeats, run `bin/wuwei doctor` and report it. |
| cli/wuwei/metrics.py:348 | owner | merge predates In Progress | The tracker says work started after the PR merged, so lead time is not computed. Move the issue to In Progress at the real start in the tracker, or ignore this item's lead time. |
| cli/wuwei/metrics.py:353 | owner | merge predates creation | The tracker or PR dates show the merge before the issue or PR was created, so lead time is not computed. Check the item's links with `bin/wuwei why <item>`. |
| cli/wuwei/metrics.py:400 | config | events.jsonl: {exc} | Today's events.jsonl cannot be read: {...}. It is an append-only log and is probably damaged; run `bin/wuwei doctor` before touching it. |
| cli/wuwei/metrics.py:414 | owner | incomplete trace line | traces.jsonl ends in the middle of a line, probably from a cut-off write. Run `bin/wuwei doctor`; do not delete the file. |
| cli/wuwei/metrics.py:451 | owner | phase timestamps out of order | Event times for an item go backwards, so the clock jumped or the log was edited. Check the system clock and that WUWEI_NOW is unset, then run `bin/wuwei doctor`. |
| cli/wuwei/metrics.py:457 | owner | phase timestamp in the future | An item's phase starts in the future. Check the system clock and that WUWEI_NOW is unset, then run `bin/wuwei doctor`. |
| cli/wuwei/metrics.py:479 | owner | missing usage {key} | A seat.usage event lacks {...}, so cost cannot be attributed. This is a logging bug or an edited log, not something to fix by hand; run `bin/wuwei doctor`. |
| cli/wuwei/notes.py:19 | owner | missing frontmatter | A note must start with a `---` line, then type, summary, aliases and status fields, then a closing `---`. Create notes with `bin/wuwei note add <slug> --type <type> --summary "<text>"`. |
| cli/wuwei/notes.py:32 | owner | unknown or duplicate field: {key} | The field {...} is not allowed or is repeated. Each of type, summary, aliases, status and created can appear once; fix the note header. |
| cli/wuwei/notes.py:47 | owner | summary must be one nonempty line | The summary must be one nonempty line. Rewrite it as a single sentence, for example `--summary "How we pick reviewers"`. |
| cli/wuwei/notes.py:49 | owner | missing frontmatter closing delimiter | The frontmatter has no closing `---` line. Add it after the last field, before the note body. |
| cli/wuwei/notes.py:52 | owner | missing {key} | The frontmatter lacks {...}. Required fields are type, summary, aliases and status; `bin/wuwei note add` writes them for you. |
| cli/wuwei/notes.py:65 | owner | decision note requires a Why: line | A decision note needs a line starting `Why:` followed by the reason. Add it to the note body, or choose another note type. |
| cli/wuwei/obligations.py:24 | owner | expected complete evidence list | The code host returned incomplete review or thread data, usually a transient or adapter problem. Rerun bin/wuwei sweep obligations; if it repeats, run bin/wuwei doctor. |
| cli/wuwei/obligations.py:30 | owner | missing evidence timestamp | A review or comment from the code host has no timestamp, so obligations cannot be judged. Rerun bin/wuwei sweep obligations; if it repeats, run bin/wuwei doctor. |
| cli/wuwei/obligations.py:33 | owner | evidence timestamp needs timezone | A review or comment timestamp has no timezone, so ages cannot be judged. This is an adapter fault; run bin/wuwei doctor and report the adapter name. |
| cli/wuwei/obligations.py:47 | owner | unknown review state | The code host returned a review state WUWEI does not know (expected approved, commented, changes_requested or dismissed). Run bin/wuwei doctor and report the adapter. |
| cli/wuwei/obligations.py:205 | owner | no recorded PR state for today | Today's state.json has no recorded PR set in the event log, so it was not written by wuwei and an empty PR list is not trusted. Run bin/wuwei doctor; the owner runs bin/wuwei state recover. |
| cli/wuwei/obligations.py:212 | owner | owner.handles needs one unambiguous code-host login (excluding chat IDs) | owner.handles with `bin/wuwei config set` (host terminal) must hold exactly one code-host login, for example acme-dev, plus any chat IDs such as U12345. The owner fixes it on the host. |
| cli/wuwei/obligations.py:245 | owner | unknown PR state | The code host reported a PR state other than open or closed. Rerun bin/wuwei sweep obligations; if it repeats, run bin/wuwei doctor and report the adapter. |
| cli/wuwei/obligations.py:291 | owner | reply needs a surface, positive ID and nonempty body | bin/wuwei reply needs a surface (comment, review or thread), a positive numeric ID and a nonempty body. Get the ID from bin/wuwei sweep obligations. |
| cli/wuwei/obligations.py:293 | owner | day state missing | No state.json exists for today, so no PR is owned yet. Run bin/wuwei plan approve, then bin/wuwei pr raise or pr claim, before replying. |
| cli/wuwei/obligations.py:297 | owner | PR is not raised or claimed today | Replies go only to PRs owned today. Record it first with bin/wuwei pr claim, or check the ref with bin/wuwei state get claimed_prs. |
| cli/wuwei/obligations.py:309 | owner | no human obligation with that surface and ID | No unanswered human comment or review has that surface and ID. Run bin/wuwei sweep obligations to list what is OWED and reply to one of those IDs. |
| cli/wuwei/obligations.py:324 | owner | target changed while replying; acknowledgement not recorded | The comment was edited while you replied, so no acknowledgement was recorded. Reread it, then run bin/wuwei reply again if it still needs an answer. |
| cli/wuwei/obligations.py:328 | owner | posted reply could not be verified; acknowledgement not recorded | The reply was sent but could not be matched on the code host, so no acknowledgement was recorded. Check the PR thread, then run bin/wuwei sweep obligations. |
| cli/wuwei/obligations.py:357 | owner | thread is resolved, missing or already answered | That thread is resolved, outdated, missing, or already ends with the owner's reply. Run bin/wuwei sweep obligations to see which threads are still OWED. |
| cli/wuwei/obligations.py:370 | owner | posted thread reply could not be verified | The thread reply was sent but not confirmed on the code host. Check the PR before retrying so you do not post twice, then run bin/wuwei sweep obligations. |
| cli/wuwei/outward.py:119 | owner | expected input object | The outward input must be a JSON object of fields such as text and channel, not a list or string. Fix the tool call payload. |
| cli/wuwei/outward.py:124 | owner | expected plain text | Text fields (text, message, body, title, description) must be plain strings. Pass the message as one string, not a list or object. |
| cli/wuwei/outward.py:132 | owner | expected boolean audience flag | Audience flags (is_dm, is_external, is_shared, is_connected, is_client) must be true or false, not text. Set a real boolean. |
| cli/wuwei/outward.py:135 | owner | expected recipients list | recipients must be a list of non-empty strings, for example ["a@acme.com"]. Fix the list or drop the field. |
| cli/wuwei/outward.py:148 | owner | unsupported input field | This outward call carries a field WUWEI does not know, so it cannot be checked and is blocked. Remove the unknown field, or ask the owner if it is needed. |
| cli/wuwei/outward.py:210 | owner | PR evidence does not match destination | The code host returned a different PR than the one named, so the evidence cannot be trusted. Retry with the exact owner/repo#n; if it repeats, run `bin/wuwei doctor`. |
| cli/wuwei/plan.py:40 | owner | missing {key} | The proposal JSON lacks `{key}`; required keys are goals, candidates, seat_policy, envelope, sweep and cap. `bin/wuwei plan template` prints a valid example to start from. |
| cli/wuwei/plan.py:44 | owner | goals must cite identifiers in memory/goals.md | Every entry in goals must be a G-n id that exists in memory/goals.md. Use only ids listed there; the owner changes the goals with `bin/wuwei goals edit`. |
| cli/wuwei/plan.py:46 | owner | cap must be a positive integer | cap is how many builder seats may run at once, and must be a whole number of 1 or more, for example 2. Fix it in the proposal JSON. |
| cli/wuwei/plan.py:52 | owner | seat_policy requires runtime and model per role | seat_policy needs a non-empty runtime and model for every role, for example "builder": {"runtime": "claude", "model": "<model>"}. `bin/wuwei plan template` shows the shape. |
| cli/wuwei/plan.py:61 | unmeasured | sweep must report measured or unmeasured sources | sweep must be a non-empty object whose values are text such as "measured: ..." or "unmeasured: <reason>". Name every source you did not check instead of leaving it out; see `bin/wuwei plan template`. |
| cli/wuwei/plan.py:70 | owner | candidate id must be unique and safe | Each candidate needs a unique id starting with a letter or digit and using only letters, digits, dot, dash or underscore, such as widget-12. Rename the duplicate or unsafe id. |
| cli/wuwei/plan.py:122 | owner | morning gate already approved | Today's morning gate is already approved, so the plan is frozen and cannot be proposed again. Add a late item with `bin/wuwei plan add <id>` instead. |
| cli/wuwei/plan.py:149 | owner | goals must be confirmed at the morning gate | Approval needs the owner to confirm today's goals first. Show them the goals, then rerun `bin/wuwei plan approve --items <ids> --goals-confirmed`. |
| cli/wuwei/plan.py:151 | owner | today's plan.md is missing | There is no plan.md for today, so there is nothing to approve. Propose first with `bin/wuwei plan propose`; `bin/wuwei plan template` prints the JSON it expects. |
| cli/wuwei/plan.py:163 | owner | approved item is absent from proposal | --items names an id that is not in today's proposal. Use only candidate ids listed under Proposed queue in plan.md. |
| cli/wuwei/plan.py:171 | owner | no prior day state to import | --import-yesterday found no earlier day with a state file, so there is nothing to carry over. Run `bin/wuwei plan approve` again without that flag. |
| cli/wuwei/plan.py:178 | owner | imported and approved item ids overlap | An id is both imported from yesterday and listed in --items, and each item may enter once. Remove it from one of the two. |
| cli/wuwei/plan.py:182 | owner | morning gate already approved | The morning gate was approved while you were preparing this call, maybe from another session. Check `bin/wuwei status`; add late items with `bin/wuwei plan add <id>`. |
| cli/wuwei/plan.py:184 | owner | day item already exists | One of these ids is already an item in today's state. Drop it from --items and check `bin/wuwei status` for what exists. |
| cli/wuwei/plan.py:210 | owner | morning gate has not been approved | `plan add` only works after the morning gate. Approve the day first with `bin/wuwei plan approve --items <ids> --goals-confirmed`. |
| cli/wuwei/plan.py:213 | owner | unknown discovery candidate {item} | No discovered candidate called {item} exists in today's state. Use an id the discovery listed (`bin/wuwei discover`), or refresh the list with `bin/wuwei dispatch discovery sweep`. |
| cli/wuwei/plan.py:246 | owner | item {item} is already in the plan | Item {item} is already in today's plan, so it cannot also be proposed as new work. Check `bin/wuwei status`. |
| cli/wuwei/plan.py:255 | owner | item {item} is already in the plan | Item {item} is already in today's plan, so there is nothing to add. Check `bin/wuwei status` and continue with `bin/wuwei dispatch next {item}`. |
| cli/wuwei/pr_actions.py:22 | owner | disposition needs an owner-routed decision without a seat outcome | This disposition needs an owner-routed decision that no seat has already answered. Route it with `bin/wuwei decision route D-n`, let the owner answer, then rerun `bin/wuwei pr disposition`. |
| cli/wuwei/pr_actions.py:24 | owner | disposition decision changed; verify again | The decision record changed after the marker comment was written, so the marker is stale. Owner: post a fresh marker comment, then rerun `bin/wuwei pr disposition <pr> <parked\|carried> --decision D-n --comment <id>`. |
| cli/wuwei/pr_actions.py:31 | owner | disposition needs a fresh owner-authored comment: {...} | No fresh owner comment matches. Owner: post exactly `{...}` on the PR yourself (agents cannot), then rerun `bin/wuwei pr disposition <pr> <parked\|carried> --decision D-n --comment <comment id>`. |
| cli/wuwei/pr_actions.py:40 | owner | PR must be raised or claimed today | This PR is not one of today's PRs. Check the ref (owner/repo#n), or claim it with `bin/wuwei pr claim <pr> --item <item>`, then retry. |
| cli/wuwei/pr_actions.py:119 | unmeasured | mergeability unmeasured | The code host has not computed mergeability yet, so the PR cannot be classified. Wait a minute and rerun `bin/wuwei pr state <pr>`; if it persists, run `bin/wuwei doctor`. |
| cli/wuwei/pr_actions.py:125 | owner | unknown check state | The code host reported a check state WUWEI does not know, so CI status is unclear. Read the checks on the PR by hand; if it persists, run `bin/wuwei doctor` and report the state name. |
| cli/wuwei/pr_actions.py:129 | owner | unknown check conclusion | The code host reported a check result WUWEI does not know, so CI status is unclear. Read the checks on the PR by hand; if it persists, run `bin/wuwei doctor` and report the result name. |
| cli/wuwei/pr_actions.py:180 | owner | review post is in the future | A recorded review post is dated after now, so the clock or the day state is wrong. Check the system clock and unset WUWEI_NOW, then run `bin/wuwei doctor`. |
| cli/wuwei/pr_actions.py:185 | owner | review observation is in the future | A review observation is dated after now, so the clock or the day state is wrong. Check the system clock and unset WUWEI_NOW, then run `bin/wuwei doctor`. |
| cli/wuwei/pr_actions.py:232 | owner | day state missing | There is no state for today, so PRs cannot be checked. Start the day with `bin/wuwei plan propose <lead.json>` and approve it with `bin/wuwei plan approve`; `bin/wuwei doctor` shows what is missing. |
| cli/wuwei/pr_actions.py:241 | owner | PR must be raised or claimed today | This PR is not one of today's PRs. Check the ref (owner/repo#n), or claim it with `bin/wuwei pr claim <pr> --item <item>`, then retry. |
| cli/wuwei/pr_actions.py:255 | owner | owned PR needs exactly one linked item | Zero or several items link to this PR, so WUWEI cannot choose a worktree. Link exactly one item with `bin/wuwei pr claim <pr> --item <item>`; for duplicates see `bin/wuwei why <pr>`. |
| cli/wuwei/pr_actions.py:259 | owner | linked item has no worktree | The item linked to this PR has no worktree, so a rebase or fix cannot start. Create one with `bin/wuwei worktree add <item>` and write the builder brief with --worktree. |
| cli/wuwei/pr_actions.py:262 | owner | linked item worktree is missing | The recorded worktree for this item is gone or is not a directory. Recreate it with `bin/wuwei worktree add <item>`, then retry. |
| cli/wuwei/pr_actions.py:274 | owner | PR is no longer conflicted; refresh its action | The PR no longer has conflicts, so there is nothing to rebase. Refresh with `bin/wuwei pr state <pr>` and follow the new action. |
| cli/wuwei/pr_actions.py:281 | owner | item worktree belongs to another PR repository | The item worktree belongs to a different repository than the PR. Use the worktree made for this PR's item (`bin/wuwei worktree add <item> --repo <name>`), then retry. |
| cli/wuwei/pr_actions.py:284 | owner | item worktree HEAD differs from PR head | The worktree HEAD is not the PR head, so a rebase would rewrite the wrong commits. Bring the worktree to the PR head first, then rerun `bin/wuwei pr act <pr> --run`. |
| cli/wuwei/pr_actions.py:289 | owner | item worktree branch differs from PR branch | The worktree is on a different branch than the PR branch. Switch it to the PR branch, then rerun `bin/wuwei pr act <pr> --run`. |
| cli/wuwei/pr_actions.py:297 | owner | fetched base differs from current PR base | The base fetched from the remote is not the base the PR reports, probably because it moved. Rerun `bin/wuwei pr act <pr> --run`; if it repeats, check brief.remote with `bin/wuwei config set` (host terminal). |
| cli/wuwei/pr_actions.py:400 | owner | recorded scope decision is missing | The saved scope question for the owner is missing, so its answer cannot be read. Restore the decision file named in the day state; if you cannot, run `bin/wuwei doctor`. Do not delete decision files. |
| cli/wuwei/pr_actions.py:415 | owner | reply needs a nonempty body | The reply body is empty. Pass a one-line answer for the reviewer: `bin/wuwei pr act <pr> --reply "<answer>"`. |
| cli/wuwei/pr_actions.py:447 | owner | no unanswered review thread found | No review thread is waiting for an answer, so there is nothing to reply to. Drop --reply, or check the PR with `bin/wuwei pr state <pr>`. |
| cli/wuwei/profiles.py:109 | config | profile config must be an object, and its repos one table | The profile's "config" must be a JSON object and its "repos" one object, not a list. Fix the profile file, then rerun bin/wuwei calibrate import <source>. |
| cli/wuwei/profiles.py:116 | owner | charters.{role}: expected a shipped role with text and a list of reasons | Profile charters.{role} must name a shipped role and hold "text" (a string) and "reasons" (a list of strings). Fix the profile file and rerun bin/wuwei calibrate import <source>. |
| cli/wuwei/profiles.py:126 | owner | only https URLs are read | Profiles load over https only. Use an https:// URL, a starter name or a local file path with bin/wuwei calibrate import. |
| cli/wuwei/profiles.py:129 | owner | only https URLs are read; the source redirected elsewhere | The https URL redirected to a non-https address, which WUWEI will not follow. Download the profile yourself and import the local file with bin/wuwei calibrate import. |
| cli/wuwei/profiles.py:135 | owner | profile is over 1 MiB | The profile file is over 1 MiB. Trim it to config keys and charter additions only, then rerun bin/wuwei calibrate import <source>. |
| cli/wuwei/profiles.py:139 | owner | profile is not JSON: {exc} | The profile is not valid JSON ({exc}). Fix the syntax at that position, or re-export a fresh one with bin/wuwei calibrate export <name>. |
| cli/wuwei/profiles.py:243 | config | repos must list configured repositories | Today's profile.json lists repos that are no longer with `bin/wuwei config set` (host terminal). Rerun bin/wuwei calibrate import <source> against the current repos. |
| cli/wuwei/profiles.py:247 | owner | carries , | profile.json carries keys or text that the profile guard refuses or flags: {...}. Rerun bin/wuwei calibrate import <source> --skip <key> for each, or import a cleaner profile. |
| cli/wuwei/profiles.py:249 | config | profile.json: {exc} | Today's profile.json is invalid ({exc}). Rerun bin/wuwei calibrate import <source> to rewrite it, then bin/wuwei doctor to confirm. |
| cli/wuwei/profiles.py:326 | config | ledger.jsonl: {exc} | ledger.jsonl is damaged ({exc}); each line must be one JSON object. Repair or restore the file from .wuwei history (git -C .wuwei), then rerun bin/wuwei calibrate export. |
| cli/wuwei/promotion.py:17 | owner | unknown owner memory target | Owner memory targets are only goals or voice. The owner edits them with bin/wuwei goals edit or bin/wuwei voice edit in a host terminal. |
| cli/wuwei/promotion.py:47 | owner | {label} path must be workspace-relative | The {label} path must be relative to the workspace root, for example .wuwei/memory/notes/widget.md, not an absolute path. |
| cli/wuwei/promotion.py:50 | owner | {label} path must be inside .wuwei | The {label} path must start with .wuwei and contain no '..'; WUWEI only changes files under .wuwei. Fix the path in the proposal. |
| cli/wuwei/promotion.py:55 | owner | {label} path must be inside workspace | The {label} path resolves outside the workspace (a symlink or '..'). Point it at a real file under .wuwei in this workspace. |
| cli/wuwei/promotion.py:66 | owner | baseline is maintained by the owner outside agent tools | Baseline notes are owner-maintained and agents cannot change them. Propose a different note slug, or ask the owner to edit it on the host. |
| cli/wuwei/promotion.py:91 | owner | workspace integrity evidence unreadable | Cannot read the workspace history to check for unpromoted edits. Run bin/wuwei doctor; the owner may need to repair git inside .wuwei. |
| cli/wuwei/promotion.py:93 | owner | target has unpromoted changes; owner must review workspace history | This target has edits that were never promoted, so WUWEI will not build on them. The owner reviews them with git -C .wuwei status, commits or reverts, then retry bin/wuwei promote. |
| cli/wuwei/promotion.py:127 | owner | reason is required | Every proposal needs a reason. Add one sentence to "reason" in the proposal JSON saying why the change helps, then rerun bin/wuwei promote. |
| cli/wuwei/promotion.py:130 | owner | evidence does not exist | The proposal's "evidence" file does not exist. Point it at a real file under .wuwei, such as today's retro or a decision record, then rerun bin/wuwei promote. |
| cli/wuwei/promotion.py:140 | owner | target does not exist | Only action "add" can create a file; patch, fold and archive need an existing target. Check the target path, or use add (new notes: bin/wuwei note add). |
| cli/wuwei/promotion.py:144 | owner | text or delta is required | add and patch need a nonempty "text" (or "delta") holding the lines to write. Fill it in and rerun bin/wuwei promote. |
| cli/wuwei/promotion.py:155 | owner | target exceeds 200 line cap | The result would pass 200 lines, the cap for memory and charter files. Shorten the text, or archive or fold older notes first (bin/wuwei consolidate). |
| cli/wuwei/promotion.py:168 | owner | only notes can be archived or folded | Only notes can be archived or folded, not charters or voice. To retire a charter rule, use action "patch" with old_text and its replacement. |
| cli/wuwei/promotion.py:171 | owner | target is not active | Only an active note can be archived or folded, and this one has another status. Pick a live note from .wuwei/memory/index.md. |
| cli/wuwei/promotion.py:176 | owner | note is in probation | This note is still in probation: it cannot be archived or folded until memory.probation_days working days have passed. Retry later. |
| cli/wuwei/promotion.py:180 | owner | fold requires a live note survivor | fold needs a "survivor": a different, active note in the same folder that receives the folded text. Name one in the proposal, or use archive. |
| cli/wuwei/promotion.py:183 | owner | fold requires a live note survivor | The survivor note must be active to receive folded text. Name another live note as "survivor" in the proposal, or use archive. |
| cli/wuwei/promotion.py:191 | owner | folded survivor exceeds note line cap | The merged note would pass memory.note_line_cap lines. Shorten the retired or survivor note first, or archive instead of folding. |
| cli/wuwei/promotion.py:196 | owner | ; | Memory index check failed: {...}. Fix the listed notes (front matter, status, slug), then rerun bin/wuwei promote or run bin/wuwei doctor. |
| cli/wuwei/promotion.py:203 | owner | archive destination already exists | A note with this name is already in memory/archive. Rename the note you are archiving, or ask the owner to move the old archive file. |
| cli/wuwei/promotion.py:213 | owner | ; | Memory index check failed after the move: {...}. Fix the listed notes (front matter, status, slug), then run bin/wuwei doctor. |
| cli/wuwei/rank.py:13 | owner | framework must be wsjf or rice | Set prioritisation.framework to wsjf or rice with `bin/wuwei config set` (host terminal), then run `bin/wuwei config check`. |
| cli/wuwei/rank.py:15 | owner | candidate id required | Every candidate needs a string `id` such as widget-1. Add it, or print a valid example with `bin/wuwei rank template`. |
| cli/wuwei/references.py:8 | owner | expected owner/repo | Use owner/repo form, for example acme/widget, with letters, digits, dot, dash or underscore only. |
| cli/wuwei/references.py:16 | owner | expected owner/repo#number | Use owner/repo#number, for example acme/widget#42, with a number of 1 or more. |
| cli/wuwei/registry.py:67 | owner | unknown adapter kind: {kind} | {kind} is not an adapter kind WUWEI has (for example vcs, code_host, chat, scanner). Check the adapters key you changed with `bin/wuwei config set` (host terminal), or run bin/wuwei doctor. |
| cli/wuwei/remote.py:109 | owner | control_plane.owner must pin <team>/<user>; this message came from {event['sender']} | Set control_plane.owner with `bin/wuwei config set` (host terminal) to the sender id in <team>/<user> form; this message came from {...}. Copy that value only if it is you, then retry. |
| cli/wuwei/remote.py:133 | owner | remote ack: owner confirmation declined | Nothing was acknowledged because the confirmation was declined. To clear the pages, rerun `bin/wuwei remote ack` on the host terminal and type the code shown. |
| cli/wuwei/remote.py:169 | owner | WUWEI_TOTP_SECRET is not base32 | WUWEI_TOTP_SECRET must be the base32 secret from your authenticator setup (letters A-Z, digits 2-7, spaces allowed). Copy it again exactly. |
| cli/wuwei/retro.py:22 | owner | retro evidence must belong to today | A captured retro note points outside today's retro folder, so it is refused. This suggests a hand-edited event log; run `bin/wuwei doctor`. |
| cli/wuwei/retro.py:26 | owner | captured retro evidence mismatch | A retro note file differs from what was recorded when it was captured, so it was edited afterwards. Do not edit retro notes; have the role capture it again, or run `bin/wuwei doctor`. |
| cli/wuwei/retro.py:28 | owner | captured retro note is incomplete | A role's retro note has missing or invalid fields (Blocked, Gap, Change). Have that role write the note again with all fields, then rerun `bin/wuwei retro`. |
| cli/wuwei/retro.py:48 | owner | hard-rule change must be one nonempty line | A `Hard rule:` change must be one nonempty line. Have the role rewrite its Change field as `Hard rule: <one line>`, then rerun `bin/wuwei retro`. |
| cli/wuwei/retro.py:76 | owner | unknown charter role: {role} | There is no charter for role {...}, so this change has nowhere to go. Have the retro note name a real role from the charters folder, then rerun `bin/wuwei retro`. |
| cli/wuwei/scanner.py:14 | unmeasured | scanner: unmeasured: reviewed worktree is outside the workspace | The reviewed worktree is outside the workspace, so the scanner will not run on it. Create worktrees through bin/wuwei dispatch or bin/wuwei worktree, under the workspace. |
| cli/wuwei/scanner.py:18 | unmeasured | scanner: unmeasured: {...} | The security scan could not run: {...}. Check adapters.scanner with `bin/wuwei config set` (host terminal) and that the scanner tool is installed (bin/wuwei doctor), then retry. |
| cli/wuwei/scanner.py:22 | unmeasured | scanner: unmeasured: {...} | The security scan gate could not decide: {...}. Check adapters.scanner and scanner.severity_threshold with `bin/wuwei config set` (host terminal), then run bin/wuwei doctor and retry. |
| cli/wuwei/scanner.py:33 | unmeasured | scanner: unmeasured: finding source is unreadable or outside worktree | A scanner finding points at a file that is unreadable or outside the worktree. Rerun the scan from a clean checkout; if it repeats, run bin/wuwei doctor. |
| cli/wuwei/scanner.py:120 | owner | unreadable trace input | traces.jsonl is a broken symlink. Replace it with a real file or remove the link, then rerun bin/wuwei sweep watch. |
| cli/wuwei/security.py:20 | owner | honeytoken path must be a relative file in a private subdirectory | The decoy path must be relative, inside a subdirectory (default credentials/backup.env), and not under generated, charters, memory, days or archive. Pick another path. |
| cli/wuwei/security.py:31 | owner | honeytoken path already exists | A file already exists at the decoy path. Pick another honeytoken path so no real file is overwritten. |
| cli/wuwei/security.py:116 | owner | outward: , | outward: {...} found. The text carries a private WUWEI marker (canary or honeytoken). Remove it and resend; if you did not paste it, a seat read a protected file: `bin/wuwei why last refusal`. |
| cli/wuwei/security.py:171 | unmeasured | cannot inspect honeytoken read | The command mentions the decoy credential file but cannot be parsed, so WUWEI cannot rule out a read. Rewrite it as a simple command that does not name that file. |
| cli/wuwei/security.py:183 | owner | too many possible read directories | The command changes directory in too many branches to track. Split it into smaller commands with one cd each. |
| cli/wuwei/security.py:232 | owner | owner disposition markers must be posted by the owner | Comments starting `WUWEI parked` or `WUWEI carried` are owner-only. Ask the owner to post it, then run `bin/wuwei pr disposition`. |
| cli/wuwei/security.py:238 | owner | missing outbound body file | A body flag (--body-file, -F or --input) has no file name after it. Pass the path of the body file, for example `--body-file body.md`. |
| cli/wuwei/security.py:256 | unmeasured | outward: cannot inspect outbound stdin or missing body file | outward: WUWEI cannot scan a body read from stdin or with an empty name. Write the body to a file and pass `--body-file <file>`. |
| cli/wuwei/security.py:262 | unmeasured | outward: opaque request, cannot read outbound body file | outward: the body file is missing, unreadable, or invalid JSON for --input. Check the path (relative to the current directory) and retry. |
| cli/wuwei/security.py:267 | owner | owner disposition markers must be posted by the owner | Comments starting `WUWEI parked` or `WUWEI carried` are owner-only. Ask the owner to post it, then run `bin/wuwei pr disposition`. |
| cli/wuwei/sessions.py:38 | owner | session role must be one of {', '.join(ROLES)} | Session role must be one of {...}. Use one of those values; anything else means a wrong hook or CLI call, so run bin/wuwei doctor. |
| cli/wuwei/sessions.py:41 | owner | sessions: expected object | The sessions record in state.json is not an object, so state was hand-edited or damaged. Run bin/wuwei doctor; the owner runs bin/wuwei state recover on the host. |
| cli/wuwei/sessions.py:104 | owner | sessions and claims: expected objects | The sessions or claims record in state.json is not an object, so state was hand-edited or damaged. Run bin/wuwei doctor; the owner runs bin/wuwei state recover. |
| cli/wuwei/shell.py:53 | owner | missing option value | A gh option at the end of the command has no value, so the guard cannot tell what it targets; add the value after it (for example -R owner/repo) or remove the option. |
| cli/wuwei/shell.py:84 | owner | unaccounted git/gh mention | git or gh appears where the guard cannot inspect it (a comment, quoted text or here-doc body); remove the mention, or run git or gh as its own plain command. |
| cli/wuwei/shell.py:196 | owner | ANSI-C quoting is unsupported | $'...' quoting can hide a git or gh command from the guard; use plain 'single' or "double" quotes instead. |
| cli/wuwei/shell.py:227 | owner | unterminated here-doc | The here-doc has no closing delimiter line, so the guard cannot see where it ends; put the delimiter alone on its own line after the body. |
| cli/wuwei/shell.py:242 | owner | trailing backslash | The command ends in a lone backslash, so the guard cannot tell what continues it; remove the backslash or finish the line. |
| cli/wuwei/shell.py:251 | owner | command substitution is unsupported | $(...) hides what will run from the guard; run that command first and paste the result as a literal, or use a quoted cat here-doc ("$(cat <<'EOF' ...)"). |
| cli/wuwei/shell.py:255 | owner | command substitution contains more than a literal here-doc | Only a quoted cat here-doc may sit inside $( ) and it must be followed directly by the closing ); close it right after the delimiter line, or pass the text with --body-file. |
| cli/wuwei/shell.py:260 | owner | command substitution is unsupported | Backticks hide what will run from the guard; run that command first and write the result as a literal value. |
| cli/wuwei/shell.py:269 | owner | unbalanced quotes or missing word | A quote is never closed or an operator or redirect has no word after it; close the quote or add the missing word so the guard can read the command. |
| cli/wuwei/shell.py:295 | owner | only quoted here-doc delimiters are supported | Here-doc delimiters must be quoted so the body stays literal; write <<'EOF' instead of <<EOF. |
| cli/wuwei/shell.py:298 | owner | nonliteral redirection is unsupported | The redirect target uses a variable, glob or substitution, so the guard cannot tell which file is written; use a literal path. |
| cli/wuwei/shell.py:328 | owner | normalization hides a git/gh mention | Line continuations or quote tricks would hide a git or gh word from the guard; write git or gh as one plain unbroken word. |
| cli/wuwei/shell.py:338 | owner | missing here-doc body | A here-doc was opened but its body and closing delimiter are missing; add the body and the delimiter line, or drop the here-doc. |
| cli/wuwei/shell.py:355 | owner | unexpected shell separator | A stray ;, &, \| or newline sits where a command should be; remove the empty slot or split the line into separate commands. |
| cli/wuwei/shell.py:360 | owner | unbalanced or empty subshell | A ( ) group is empty or its parenthesis is not closed; close it, put a command inside, or drop the parentheses. |
| cli/wuwei/shell.py:400 | owner | expected shell separator | Two words run together with no ;, && or newline between commands; separate them, or run each command in its own call. |
| cli/wuwei/shell.py:404 | owner | missing command after separator | A &&, \|\| or \| ends the command with nothing after it; add the next command or remove the trailing operator. |
| cli/wuwei/shell.py:409 | owner | unmatched closing parenthesis | There is a ) with no matching (; remove it or add the opening parenthesis. |
| cli/wuwei/shell.py:419 | owner | expanding environment assignment is unsupported | An inline assignment like VAR=$x git ... expands a variable the guard cannot read; assign a literal value, or set it in an earlier separate command. |
| cli/wuwei/shell.py:430 | owner | nonliteral file or directory arguments are unsupported | cd, tee, cp, mv, sed, dd or truncate got a variable, glob or substitution as a path, so the guard cannot tell where it acts; write the literal path. |
| cli/wuwei/shell.py:438 | owner | dynamic command or shell control flow is unsupported | The guard cannot follow if, for, while, functions, export, source or command names built with $; run plain simple commands, one per call. |
| cli/wuwei/shell.py:441 | owner | expanding eval is unsupported | eval with a $variable runs text the guard cannot read; run the command directly, or give eval a literal string. |
| cli/wuwei/shell.py:452 | owner | unsupported busybox applet | Only busybox sh is understood; run the command directly or use busybox sh -c '...'. |
| cli/wuwei/shell.py:463 | owner | unsupported shell option | The guard understands only plain letter flags such as -c, -e and -u (no -o and no long options) on sh or bash; use bash -c '...' with simple flags. |
| cli/wuwei/shell.py:466 | owner | missing shell -c script | sh or bash was called without -c and a script, so it would read commands the guard cannot see; use bash -c 'command' or run the command directly. |
| cli/wuwei/shell.py:468 | owner | expanding shell script is unsupported | The sh -c script contains a $ expansion, so the guard cannot read what runs; put the script in single quotes or write the values literally. |
| cli/wuwei/shell.py:470 | owner | shell positional expansion is unsupported | $@, $*, $0 to $9 or ${...} in the sh -c script depends on extra arguments the guard cannot read; write the real values into the script text and drop the extra arguments. |
| cli/wuwei/shell.py:475 | owner | obfuscated git/gh mention in shell script | The sh -c script spells git or gh with quotes or backslashes inside the word (for example g"i"t), which looks like hiding; write git or gh plainly. |
| cli/wuwei/shell.py:482 | owner | nonliteral guarded arguments are unsupported | git or gh arguments contain a variable, glob or substitution, so the guard cannot tell which verb, branch or repo is meant; write the literal arguments. |
| cli/wuwei/shell.py:515 | owner | missing {program} option value | {program} ends with an option that needs a value; add the value (for example nice -n 5 or timeout -s TERM 30) or remove the option. |
| cli/wuwei/shell.py:522 | owner | unsupported {program} option | The guard does not know this {program} option; drop it, or run the inner command without the {program} wrapper. |
| cli/wuwei/shell.py:527 | owner | unsupported timeout duration | timeout needs a literal duration such as 30, 5m or 1.5h before the command; write it that way. |
| cli/wuwei/shell.py:540 | owner | input-driven guarded arguments are unsupported | xargs would feed unseen input to git, gh or a file command; run the command directly with literal arguments instead of piping into xargs. |
| cli/wuwei/shell.py:543 | owner | missing command after {program} | {program} has no command after it; add the command to run, or drop the {program} prefix. |
| cli/wuwei/shell.py:545 | owner | standalone directory environment assignments are unsupported | Setting HOME, OLDPWD or CDPATH on its own changes where later git or gh commands act, which the guard cannot follow; set it inline on the one command that needs it, or drop it. |
| cli/wuwei/shepherd.py:18 | config | PR repository is not configured | This PR's repository is not with `bin/wuwei config set` (host terminal), so WUWEI will not touch it. Add it with `bin/wuwei config add-repo` (owner, host terminal), then retry. |
| cli/wuwei/shepherd.py:55 | owner | shepherd.authors has no mapping for {email}: {exc} | Cannot tell who {...} is on the code host ({...}). Add them under shepherd.authors with `bin/wuwei config set` (host terminal) with their login and chat mention, then retry. |
| cli/wuwei/shepherd.py:57 | owner | shepherd.authors has no mapping for {email} | The code host returned no login for {...}. Add that email under shepherd.authors with `bin/wuwei config set` (host terminal) with the login and chat mention, then retry. |
| cli/wuwei/shepherd.py:73 | owner | fewer eligible reviewers than shepherd.min_reviewers | Not enough eligible reviewers for the changed files (fewer than shepherd.min_reviewers). Add people under shepherd.authors, set shepherd.lead_login, or lower shepherd.min_reviewers with `bin/wuwei config set` (host terminal). |
| cli/wuwei/shepherd.py:80 | config | reviewer needs a configured email | A selected reviewer has no email on file, so their login cannot be verified. Add their email, login and mention under shepherd.authors with `bin/wuwei config set` (host terminal). |
| cli/wuwei/shepherd.py:83 | config | configured reviewer login differs from code host | The login in shepherd.authors does not match the one the code host reports for that email. Correct the login under shepherd.authors with `bin/wuwei config set` (host terminal). |
| cli/wuwei/shepherd.py:96 | owner | incomplete changed files | The code host returned fewer changed files than the PR reports, so the list was cut off. Rerun `bin/wuwei pr ping <pr>`; if it repeats, run `bin/wuwei doctor`. |
| cli/wuwei/shepherd.py:99 | owner | no changed source paths for reviewer selection | Every changed file matches shepherd.source_exclude, so no reviewer can be picked from history. Narrow shepherd.source_exclude with `bin/wuwei config set` (host terminal), or request reviewers by hand. |
| cli/wuwei/shepherd.py:117 | unmeasured | mergeability unmeasured | The code host has not computed mergeability yet, so the review gate cannot run. Wait a minute and rerun `bin/wuwei pr ping-check <pr>`; if it persists, run `bin/wuwei doctor`. |
| cli/wuwei/shepherd.py:127 | owner | branch protection error body | Branch protection returned an error body instead of rules, so required checks are unknown. Give the token read access to branch protection, or set review_required_checks on the repo with `bin/wuwei config set` (host terminal). |
| cli/wuwei/shepherd.py:162 | unmeasured | ping gate unmeasured: {exc} | The review ping gate could not be measured: {...}. Fix that cause (usually the code host token or network; see `bin/wuwei doctor`) and rerun `bin/wuwei pr ping <pr>`. |
| cli/wuwei/shepherd.py:169 | config | reviewer needs a configured chat mention | A reviewer has no chat mention. Add a mention (the member id: capital letters and digits) for them under shepherd.authors with `bin/wuwei config set` (host terminal). |
| cli/wuwei/shepherd.py:180 | owner | PR is not owned today | This PR is not one of today's PRs. Claim it first with `bin/wuwei pr claim <pr> --item <item>`, then rerun `bin/wuwei pr ping <pr>`. |
| cli/wuwei/shepherd.py:204 | owner | shepherd.review_channel is required | shepherd.review_channel is not set. Put the chat channel id (capital letters and digits) in shepherd.review_channel with `bin/wuwei config set` (host terminal), then rerun `bin/wuwei pr ping <pr>`. |
| cli/wuwei/shepherd.py:274 | owner | repository identity does not match configured owner | The git email in the item repository does not match the repo identity with `bin/wuwei config set` (host terminal). Set the same email with `git config user.email` in that repo, or fix the repo identity, then retry `bin/wuwei pr raise`. |
| cli/wuwei/shepherd.py:276 | owner | repository identity does not match configured owner | The git name in the item repository does not match the repo identity with `bin/wuwei config set` (host terminal). Set the same name with `git config user.name` in that repo, or fix the repo identity, then retry `bin/wuwei pr raise`. |
| cli/wuwei/shepherd.py:279 | owner | author and committer identity differ from configured repository identity | Commit author or committer differs from the repository identity. Fix the identity in that repo (`git config`), amend the commits, then retry `bin/wuwei pr raise`. |
| cli/wuwei/shepherd.py:295 | owner | created PR does not match checked head and URL | The PR the host created does not match the pushed head or URL. Look at it on the host; if it is yours, use `bin/wuwei pr claim <pr> --item <item>` instead of raising again. |
| cli/wuwei/shepherd.py:301 | owner | reviewer request could not be verified | The PR exists but the reviewer request could not be verified. Rerun `bin/wuwei pr ping <pr>` to request and check reviewers again. |
| cli/wuwei/state.py:67 | owner | {phase} -> {target}: legal next phases: {', '.join(allowed) or 'none (terminal)'}{...} | Item cannot go {phase} -> {target}; legal next phases: {...}. Pick one with bin/wuwei state transition <item> <phase>; if it says the state is already at {target}, nothing to do. |
| cli/wuwei/state.py:75 | owner | cap: expected integer >= 1 | cap must be a whole number of 1 or more (how many seats run at once). Set it with bin/wuwei state set cap 2 before bin/wuwei plan approve. |
| cli/wuwei/state.py:77 | owner | items: removing an item is not allowed | An item cannot be removed from state once added. To stop work on it, park it with bin/wuwei state transition <item> parked. |
| cli/wuwei/state.py:80 | owner | {field}: removing a PR is not allowed | {field} only grows: a recorded PR cannot be removed. To stop work on it, park its item with bin/wuwei state transition <item> parked. |
| cli/wuwei/state.py:86 | owner | {path}.status: expected {', '.join(STATUSES)} | {path}.status must be one of {...}. Status is set by bin/wuwei brief and dispatch, so do not hand-edit state.json; run bin/wuwei doctor if it was edited. |
| cli/wuwei/state.py:98 | owner | {path}.resume_phase: managed by transitions | {path}.resume_phase is set only by phase changes. Do not edit it; move the item with bin/wuwei state transition <item> <phase>. |
| cli/wuwei/state.py:100 | owner | {path}.phase: expected {', '.join(PHASES)} | {path}.phase must be one of {...}; state.json was hand-edited or damaged. Run bin/wuwei doctor; if it stays broken, the owner runs bin/wuwei state recover on the host. |
| cli/wuwei/state.py:103 | owner | {path}.resume_phase: expected the prior active phase | {path}.resume_phase must name the phase the item had before it was parked; state.json looks hand-edited. Run bin/wuwei doctor, then the owner runs bin/wuwei state recover. |
| cli/wuwei/state.py:105 | owner | {path}.resume_phase: only valid while paused | {path}.resume_phase exists on an item that is not parked or escalated; state.json looks hand-edited. Run bin/wuwei doctor, then the owner runs bin/wuwei state recover. |
| cli/wuwei/state.py:127 | owner | {path}: day state missing while {SNAPSHOT} exists; {RECOVER} | {path}: today's state.json is missing but its snapshot exists. Agents cannot fix this; ask the owner to run bin/wuwei state recover in a host terminal. |
| cli/wuwei/state.py:130 | owner | {path}: {exc}; {RECOVER} | {path}: today's state.json is unreadable ({exc}). Ask the owner to run bin/wuwei state recover in a host terminal; it restores the last good snapshot. |
| cli/wuwei/state.py:278 | owner | {'.'.join(parts)}: reserved; written by {producer} | {path} is written only by {producer}, so a generic state set is refused. Use that command instead of editing the field. |
| cli/wuwei/state.py:310 | owner | path must contain nonempty dot-separated keys | A state path is dot-separated keys with none empty, for example items.widget.note. Check for a leading, trailing or doubled dot. |
| cli/wuwei/state.py:333 | owner | non-object parent in path: {path} | Cannot set {path}: a key on the way is a plain value, not a table. Check the parent with bin/wuwei state get and set a path that exists. |
| cli/wuwei/state.py:336 | owner | non-object parent in path: {path} | Cannot set {path}: the parent is a plain value, not a table. Check the parent with bin/wuwei state get and set a path that exists. |
| cli/wuwei/state.py:348 | owner | PR item must be in the approved plan | This PR's item is not in the approved plan. Add it with bin/wuwei plan add, approve with bin/wuwei plan approve, then rerun bin/wuwei pr raise or pr claim. |
| cli/wuwei/state.py:350 | owner | item already links another PR | This item already holds a different PR; one item owns one PR. Use that same PR ref, or add a separate item for the new PR with bin/wuwei plan add. |
| cli/wuwei/state.py:352 | owner | PR already links another item | This PR already belongs to another item; one PR has one item. Pass the item that owns it; see bin/wuwei state get items. |
| cli/wuwei/state.py:355 | owner | PR is already owned today | This PR is already recorded the other way today (raised vs claimed). Reuse the command that recorded it; see bin/wuwei state get raised_prs and claimed_prs. |
| cli/wuwei/state.py:417 | owner | state.json is readable; nothing to recover | state.json reads fine, so there is nothing to recover. If you still see a state error, run bin/wuwei doctor. |
| cli/wuwei/state.py:422 | owner | unusable state snapshot: {exc} | The snapshot (state.snapshot.json) is also unusable ({exc}), so recovery cannot restore state. Run bin/wuwei doctor; the owner restores from the last good copy of the day folder. |
| cli/wuwei/state.py:427 | owner | state recovery declined | Recovery cancelled: the typed fingerprint did not match. Rerun bin/wuwei state recover in a host terminal and type the shown code exactly. |
| cli/wuwei/steward.py:131 | owner | unknown steward note | No steering note has this id today; copy the exact id from the refusal "steward note <id> requires planner acknowledgement", then run bin/wuwei steward ack <id>. |
| cli/wuwei/steward.py:133 | owner | steward note already acknowledged | That steering note is already acknowledged; nothing more to do, carry on with the plan. |
| cli/wuwei/steward.py:231 | owner | steward runtime returned invalid or error data | The steward run returned an error or unreadable data, so no review was recorded; rerun bin/wuwei steward run, and run bin/wuwei doctor if it repeats. |
| cli/wuwei/voice.py:87 | owner | chat adapter is none | Voice learning reads your sent messages through the chat adapter, which is none. Ask the owner to run `bin/wuwei config set adapters.chat '"<adapter>"'`, or write the profile by hand with `bin/wuwei voice edit`. |
| cli/wuwei/voice.py:90 | owner | owner.handles is empty | owner.handles is empty, so WUWEI cannot tell which messages are yours. Add your chat handle with `bin/wuwei config set owner.handles '["<handle>"]'`. |
| cli/wuwei/voice.py:151 | owner | voice learn: {exc} | voice learn: {exc}. Nothing was written. Fix the cause named and run `bin/wuwei voice learn` again. |
| cli/wuwei/watch.py:26 | owner | incomplete event line | events.jsonl ends mid-line, so a write was cut off. Do not append by hand; run bin/wuwei doctor and ask the owner to trim or restore the last line. |
| cli/wuwei/watch.py:58 | owner | clock line is in the future | The newest watch clock line is dated in the future: the machine clock is wrong or the log was edited. Fix the system time, then run bin/wuwei doctor. |
| cli/wuwei/watch.py:96 | owner | digest timestamp is in the future | The last chat digest time is in the future. Fix the system clock or run bin/wuwei doctor; the digest resumes once the clock passes that time. |
| cli/wuwei/watch.py:121 | unmeasured | chat digest unavailable: {result.reason or 'unknown error'} | Could not send the two-way decision digest to chat: {...}. Check adapters.chat and its credentials with `bin/wuwei config set` (host terminal) (bin/wuwei doctor); a draft file is written when chat is not configured. |
| cli/wuwei/watch.py:154 | owner | running seat needs one logged brief | A running seat needs exactly one logged brief in events.jsonl and has none or several. Recreate it with bin/wuwei brief, or stop the seat; run bin/wuwei doctor to see which. |
| cli/wuwei/watch.py:160 | owner | running seat and item disagree on worktree | A running seat and its item point to different worktrees. Compare bin/wuwei state get items.<item>.worktree with the brief, then rerun bin/wuwei brief or run bin/wuwei doctor. |
| cli/wuwei/watch.py:186 | owner | activity timestamp is in the future | A worktree activity time is in the future, so staleness cannot be judged. Fix the system clock, then rerun bin/wuwei sweep watch. |
| cli/wuwei/watch.py:598 | owner | empty planner wake marker | The planner wake marker holds no PRs, inbox count or summaries, so nothing says why to wake. This is a bug or edited state; run bin/wuwei doctor. |
| cli/wuwei/watch.py:627 | owner | state has no event history | state.json exists but events.jsonl is empty or missing, so history is lost or the state was hand-written. Run bin/wuwei doctor; the owner may need bin/wuwei state recover. |
| cli/wuwei/workspace.py:283 | owner | missing worktree repository context | WUWEI cannot read the git context of this worktree. Run from a configured repository or a WUWEI worktree; `bin/wuwei doctor` checks the git setup. |
| cli/wuwei/workspace.py:344 | owner | time component required | KEEP: caught and replaced by the WUWEI_NOW message on the next line, never shown. |
| cli/wuwei/workspace.py:348 | owner | WUWEI_NOW must be an ISO datetime with a time component | WUWEI_NOW has no time part. It overrides the clock for tests; unset it, or use a full ISO datetime such as 2026-10-03T09:00:00. |
| cli/wuwei/workspace.py:411 | config | {key}: required{location} | {...} is empty and has no default. Fill it with `bin/wuwei config set` (host terminal), then run `bin/wuwei config check`. |
| cli/wuwei/workspace.py:414 | config | {key}: expected {expected.__name__} | {...} has the wrong type: expected {...}. Fix the value with `bin/wuwei config set <key> <value>` (host terminal) (quote text, leave numbers unquoted), then run `bin/wuwei config check`. |
| cli/wuwei/workspace.py:436 | config | {key}: expected integer >= {constraint} | {...} must be a whole number of at least {...}. Fix it with `bin/wuwei config set <key> <value>` (host terminal), then run `bin/wuwei config check`. |
| cli/wuwei/workspace.py:438 | config | {key}: expected integer <= {schema[3]} | {...} must be a whole number of at most {...}. Fix it with `bin/wuwei config set <key> <value>` (host terminal), then run `bin/wuwei config check`. |
| cli/wuwei/workspace.py:440 | config | {key}: expected {' or '.join(constraint)} | {...} must be one of the allowed words: {...}. Fix it with `bin/wuwei config set <key> <value>` (host terminal), then run `bin/wuwei config check`. |
| cli/wuwei/workspace.py:478 | config | guards.shadow_since: expected YYYY-MM-DD or "" | guards.shadow_since must be a date like 2026-10-03, or empty. Fix it with `bin/wuwei config set <key> <value>` (host terminal), then run `bin/wuwei config check`. |
| cli/wuwei/workspace.py:510 | config | repos.{index}.path: {exc} | The path of repository number {...} cannot be resolved: {...}. Give [[repos]] path a real directory with `bin/wuwei config set` (host terminal), then run `bin/wuwei config check`. |
| cli/wuwei/workspace.py:514 | config | repos.{index}.path: duplicate {repo['path']}{location} | Repository number {...} repeats the path {...}{...}. Each [[repos]] entry needs its own directory; remove the duplicate from .wuwei/config.toml. |
| cli/wuwei/workspace.py:523 | config | {exc}{location} | {...}{...}: pick a listed adapter name for that key under [adapters] with `bin/wuwei config set` (host terminal), then run `bin/wuwei config check`. |
| cli/wuwei/workspace.py:532 | config | config.toml: {exc}{hint} | config.toml is invalid: {...}{...}. Fix that line with `bin/wuwei config set <key> <value>` (host terminal) and run `bin/wuwei config check`; guards stay strict until it loads. |
| cli/wuwei/workspace.py:550 | owner | worktree creation requires a workspace | There is no .wuwei workspace here. Run from the workspace root, or create one with `bin/wuwei init`, then retry `bin/wuwei worktree add <item>`. |
| cli/wuwei/workspace.py:552 | owner | morning gate approval required before worktree creation | Worktrees open only after the morning gate. Approve today's plan with `bin/wuwei plan approve --items ...` (owner), then retry `bin/wuwei worktree add <item>`. |

### d2. Internal invariants, rewritten by family

307 strings fire only on damaged records, a payload or adapter WUWEI cannot read, a race, or a malformed plan JSON. Nobody can fix them by reading them, so each family gets one shared rewrite: say nothing was written, that it is not the owner's fault where that holds, and the one command that names the file. Every location is listed with its message.


**Damaged or inconsistent records** (197). Rewrite: A WUWEI record failed its consistency check, so the command stopped before writing. Run `bin/wuwei doctor` to name the file and its fix (`bin/wuwei state recover` for state.json).

| Location | Message now |
|---|---|
| cli/wuwei/brief.py:125 | seats must be an object |
| cli/wuwei/brief.py:150 | invalid worktree status |
| cli/wuwei/calibrate.py:711 | malformed calibration.json |
| cli/wuwei/closing.py:30 | invalid committed tree evidence |
| cli/wuwei/closing.py:49 | invalid captured retro evidence |
| cli/wuwei/closing.py:95 | invalid landed proposal target |
| cli/wuwei/closing.py:105 | invalid rejected proposal target |
| cli/wuwei/closing.py:117 | invalid changed paths evidence |
| cli/wuwei/closing.py:132 | invalid workspace history evidence |
| cli/wuwei/closing.py:165 | invalid decision ledger |
| cli/wuwei/closing.py:207 | invalid item worktree |
| cli/wuwei/closing.py:215 | invalid pushed branch evidence |
| cli/wuwei/commands/agents.py:44 | allowlist must contain exactly the nine roles |
| cli/wuwei/commands/agents.py:53 | {role}: expected a nonempty, explicit, unique tool list |
| cli/wuwei/commands/agents.py:121 | invalid WUWEI_WORKSPACE override |
| cli/wuwei/commands/build.py:59 | invalid {label} result |
| cli/wuwei/commands/build.py:71 | malformed check failure data |
| cli/wuwei/commands/build.py:339 | invalid environment check reason |
| cli/wuwei/commands/dashboard.py:88 | briefing pack must be a regular file |
| cli/wuwei/commands/event.py:80 | event kind must be a nonempty string |
| cli/wuwei/commands/git_hook.py:50 | invalid worktree Git directory |
| cli/wuwei/commands/hook.py:262 | missing or invalid {field} |
| cli/wuwei/commands/init.py:76 | workspace permissions.deny must be a list of strings |
| cli/wuwei/commands/outbound.py:21 | duplicate JSON field |
| cli/wuwei/commands/pr.py:61 | body file must be a regular file |
| cli/wuwei/commands/status.py:164 | invalid decision ledger |
| cli/wuwei/commands/status.py:217 | {key}: expected list |
| cli/wuwei/commands/status.py:223 | {key}: expected timezone-aware timestamps |
| cli/wuwei/control_plane.py:36 | invalid decision ledger |
| cli/wuwei/decision.py:84 | duplicate {current}: field |
| cli/wuwei/decision.py:95 | {key}: expected one line |
| cli/wuwei/discovery.py:42 | invalid discovery.autostart |
| cli/wuwei/discovery.py:48 | invalid candidate risk flags |
| cli/wuwei/discovery.py:50 | invalid candidate paths |
| cli/wuwei/discovery.py:58 | invalid candidate track |
| cli/wuwei/discovery.py:91 | invalid day PR references |
| cli/wuwei/discovery.py:106 | invalid review-bot result |
| cli/wuwei/discovery.py:111 | invalid review-bot findings |
| cli/wuwei/discovery.py:114 | invalid review-bot finding |
| cli/wuwei/discovery.py:139 | invalid follow-up threads |
| cli/wuwei/discovery.py:146 | invalid PR follow-up comment |
| cli/wuwei/discovery.py:152 | invalid follow-up thread |
| cli/wuwei/discovery.py:156 | invalid follow-up thread comment |
| cli/wuwei/discovery.py:169 | invalid PR result |
| cli/wuwei/discovery.py:174 | invalid base SHA |
| cli/wuwei/discovery.py:182 | invalid base checks |
| cli/wuwei/discovery.py:186 | invalid base check |
| cli/wuwei/discovery.py:224 | invalid discovery result |
| cli/wuwei/discovery.py:228 | invalid discovery candidate |
| cli/wuwei/fast_checks.py:32 | invalid HEAD for fast checks |
| cli/wuwei/guards/agent_launch.py:71 | invalid Agent subagent_type |
| cli/wuwei/guards/agent_launch.py:87 | invalid Agent {key} |
| cli/wuwei/guards/agent_launch.py:98 | invalid brief path |
| cli/wuwei/guards/agent_launch.py:111 | ambiguous brief events |
| cli/wuwei/guards/agent_launch.py:116 | invalid logged brief metadata |
| cli/wuwei/guards/commit_push.py:19 | missing or malformed identity |
| cli/wuwei/guards/commit_push.py:103 | invalid HEAD |
| cli/wuwei/guards/commit_push.py:105 | invalid force evidence |
| cli/wuwei/guards/commit_push.py:135 | malformed fast-check evidence |
| cli/wuwei/guards/commit_push.py:144 | malformed fast-check evidence |
| cli/wuwei/guards/decision.py:115 | expected nonempty questions |
| cli/wuwei/guards/decision.py:120 | invalid question |
| cli/wuwei/guards/outward.py:71 | invalid WUWEI_WORKSPACE override |
| cli/wuwei/guards/pr.py:142 | invalid current HEAD |
| cli/wuwei/guards/pr.py:162 | expected exactly one valid Head row |
| cli/wuwei/guards/pr.py:169 | invalid resolved Head |
| cli/wuwei/guards/pr.py:221 | expected one API endpoint |
| cli/wuwei/guards/pr.py:337 | command must be text |
| cli/wuwei/guards/protect_state.py:392 | missing or invalid command |
| cli/wuwei/guards/stop.py:21 | invalid day-close request |
| cli/wuwei/guards/verdict.py:19 | missing or invalid {key} |
| cli/wuwei/integrity.py:83 | invalid checkout tracked files evidence |
| cli/wuwei/integrity.py:109 | malformed MANIFEST.sha256 |
| cli/wuwei/integrity.py:159 | invalid checkout HEAD evidence |
| cli/wuwei/integrity.py:167 | invalid checkout status evidence |
| cli/wuwei/integrity.py:199 | invalid cached integrity verdict |
| cli/wuwei/integrity.py:297 | invalid workspace history evidence |
| cli/wuwei/interview.py:43 | expected one HH:MM-HH:MM window and a time zone |
| cli/wuwei/interview.py:53 | expected one signature without commas |
| cli/wuwei/interview.py:268 | expected an object |
| cli/wuwei/listen.py:27 | invalid listen cursor |
| cli/wuwei/mcp.py:29 | invalid registry input |
| cli/wuwei/mcp.py:47 | invalid MCP server map |
| cli/wuwei/mcp.py:66 | invalid installed plugin registry |
| cli/wuwei/mcp.py:69 | invalid plugin installations |
| cli/wuwei/mcp.py:72 | invalid plugin installation scope |
| cli/wuwei/mcp.py:125 | invalid MCP approval state |
| cli/wuwei/mcp.py:140 | invalid MCP approval state |
| cli/wuwei/mcp.py:142 | invalid MCP approval state |
| cli/wuwei/mcp.py:181 | invalid registry status |
| cli/wuwei/mcp.py:185 | invalid registry status |
| cli/wuwei/mcp.py:197 | invalid registry server pairs |
| cli/wuwei/mcp.py:210 | invalid MCP server map |
| cli/wuwei/mcp.py:235 | invalid MCP server entry |
| cli/wuwei/mcp.py:446 | invalid report path |
| cli/wuwei/memory.py:35 | invalid slug |
| cli/wuwei/merge.py:28 | invalid head SHA |
| cli/wuwei/merge.py:34 | expected nonnegative integer evidence |
| cli/wuwei/merge.py:74 | invalid merge journal |
| cli/wuwei/merge.py:87 | invalid PR boolean evidence |
| cli/wuwei/merge.py:89 | invalid PR author |
| cli/wuwei/merge.py:101 | invalid check evidence at head |
| cli/wuwei/merge.py:129 | invalid quiet hours, expected HH:MM-HH:MM |
| cli/wuwei/merge.py:150 | invalid item risk evidence |
| cli/wuwei/merge.py:229 | invalid branch protection evidence |
| cli/wuwei/merge.py:243 | invalid changed file path |
| cli/wuwei/merge.py:248 | invalid changed file path |
| cli/wuwei/merge.py:399 | invalid patch evidence |
| cli/wuwei/merge.py:490 | merged PR identity differs from checked evidence |
| cli/wuwei/merge.py:531 | invalid revert PR result |
| cli/wuwei/metrics.py:39 | duplicate {label} baseline |
| cli/wuwei/metrics.py:287 | invalid merge outcome |
| cli/wuwei/metrics.py:419 | invalid trace spans |
| cli/wuwei/metrics.py:431 | invalid planned items |
| cli/wuwei/metrics.py:435 | invalid approved items |
| cli/wuwei/metrics.py:438 | invalid planned items |
| cli/wuwei/metrics.py:443 | invalid phase changes |
| cli/wuwei/metrics.py:446 | invalid phase change |
| cli/wuwei/metrics.py:471 | invalid seat usage |
| cli/wuwei/metrics.py:476 | invalid seat cost |
| cli/wuwei/metrics.py:491 | invalid proposal for size calibration |
| cli/wuwei/notes.py:26 | invalid frontmatter line |
| cli/wuwei/notes.py:29 | invalid frontmatter line |
| cli/wuwei/notes.py:35 | aliases must be a list |
| cli/wuwei/notes.py:39 | invalid aliases |
| cli/wuwei/notes.py:43 | invalid aliases |
| cli/wuwei/notes.py:56 | invalid aliases |
| cli/wuwei/notes.py:58 | invalid status |
| cli/wuwei/notes.py:63 | invalid created date |
| cli/wuwei/obligations.py:42 | incomplete comment evidence |
| cli/wuwei/obligations.py:59 | incomplete thread evidence |
| cli/wuwei/obligations.py:61 | empty thread evidence |
| cli/wuwei/obligations.py:72 | invalid acknowledgement ledger |
| cli/wuwei/obligations.py:76 | invalid acknowledgement entries |
| cli/wuwei/obligations.py:126 | invalid PR head |
| cli/wuwei/obligations.py:158 | invalid requested reviewer |
| cli/wuwei/obligations.py:314 | invalid reply result |
| cli/wuwei/obligations.py:320 | invalid posted reply ID |
| cli/wuwei/outward.py:80 | invalid banned characters |
| cli/wuwei/outward.py:83 | invalid lengths |
| cli/wuwei/outward.py:138 | invalid issue or pull number |
| cli/wuwei/outward.py:142 | invalid metadata |
| cli/wuwei/outward.py:145 | invalid channel |
| cli/wuwei/outward.py:175 | invalid port result |
| cli/wuwei/outward.py:218 | invalid review evidence |
| cli/wuwei/outward.py:226 | invalid discussion evidence |
| cli/wuwei/outward.py:230 | invalid thread evidence |
| cli/wuwei/outward.py:234 | invalid comment evidence |
| cli/wuwei/pr_actions.py:16 | invalid PR disposition |
| cli/wuwei/pr_actions.py:113 | invalid merged evidence |
| cli/wuwei/pr_actions.py:153 | invalid PR disposition ledger |
| cli/wuwei/pr_actions.py:163 | invalid PR action or review ledger |
| cli/wuwei/pr_actions.py:198 | invalid action deadline |
| cli/wuwei/pr_actions.py:205 | invalid PR action completion |
| cli/wuwei/pr_actions.py:277 | invalid PR branch |
| cli/wuwei/pr_actions.py:292 | invalid PR base SHA |
| cli/wuwei/profiles.py:111 | profile charters must be an object |
| cli/wuwei/profiles.py:324 | expected one object per line |
| cli/wuwei/promotion.py:63 | invalid charter target |
| cli/wuwei/promotion.py:68 | invalid note target |
| cli/wuwei/promotion.py:240 | proposal must be an object |
| cli/wuwei/references.py:10 | invalid repository |
| cli/wuwei/registry.py:119 | malformed VCS data |
| cli/wuwei/retro.py:31 | no captured role evidence |
| cli/wuwei/security.py:63 | invalid security material |
| cli/wuwei/security.py:162 | invalid shell tool input |
| cli/wuwei/shell.py:275 | command must be text without NUL |
| cli/wuwei/shepherd.py:24 | invalid changed source path |
| cli/wuwei/shepherd.py:41 | invalid authorship evidence |
| cli/wuwei/shepherd.py:75 | invalid reviewer login |
| cli/wuwei/shepherd.py:213 | invalid chat post confirmation |
| cli/wuwei/state.py:54 | {path}: expected object |
| cli/wuwei/state.py:135 | event kind must be a nonempty string |
| cli/wuwei/state.py:138 | event payload must be an object |
| cli/wuwei/steward.py:127 | invalid steward note id |
| cli/wuwei/steward.py:193 | invalid steward trigger |
| cli/wuwei/steward.py:250 | invalid steward trace checkpoint |
| cli/wuwei/voice.py:36 | invalid voice audience |
| cli/wuwei/voice.py:42 | invalid voice rule |
| cli/wuwei/voice.py:45 | invalid voice max_length |
| cli/wuwei/voice.py:93 | invalid voice audience |
| cli/wuwei/voice.py:103 | invalid sent message |
| cli/wuwei/voice.py:117 | invalid PR comments |
| cli/wuwei/voice.py:120 | invalid PR thread |
| cli/wuwei/voice.py:124 | invalid PR comment |
| cli/wuwei/watch.py:72 | invalid watch state |
| cli/wuwei/watch.py:109 | invalid two-way decision evidence |
| cli/wuwei/watch.py:172 | invalid HEAD |
| cli/wuwei/watch.py:279 | invalid prior watch state |
| cli/wuwei/watch.py:300 | invalid PR evidence |
| cli/wuwei/watch.py:309 | invalid checks evidence |
| cli/wuwei/watch.py:391 | invalid PR baseline |
| cli/wuwei/watch.py:396 | invalid PR facts |
| cli/wuwei/watch.py:593 | invalid inbox wake |
| cli/wuwei/watch.py:596 | invalid wake summaries |
| cli/wuwei/workspace.py:249 | invalid worktree workspace anchor |
| cli/wuwei/workspace.py:264 | invalid WUWEI_WORKSPACE override |

**Plan and rank JSON** (5). Rewrite: The plan or rank JSON is missing or misshapes this field. Compare it with `bin/wuwei plan template` (or `rank template`) and fix that field; the error names it.

| Location | Message now |
|---|---|
| cli/wuwei/plan.py:37 | proposal must be an object |
| cli/wuwei/plan.py:63 | candidates must be a list |
| cli/wuwei/plan.py:67 | candidate must be an object |
| cli/wuwei/plan.py:160 | approved items must be a unique list |
| cli/wuwei/rank.py:41 | candidates must be a list |

**Adapter and runtime results** (21). Rewrite: An adapter or seat runtime returned data WUWEI cannot read, so the step is unmeasured and nothing was recorded. Retry once; if it repeats, run `bin/wuwei doctor`, which tests the adapter.

| Location | Message now |
|---|---|
| cli/wuwei/brief.py:88 | invalid adapter result |
| cli/wuwei/commands/build.py:218 | malformed runtime usage |
| cli/wuwei/commands/build.py:221 | malformed runtime usage |
| cli/wuwei/commands/build.py:225 | malformed runtime usage |
| cli/wuwei/commands/build.py:227 | malformed runtime usage |
| cli/wuwei/commands/build.py:240 | invalid runtime result |
| cli/wuwei/commands/build.py:301 | malformed runtime usage |
| cli/wuwei/commands/build.py:332 | invalid check result |
| cli/wuwei/commands/build.py:418 | invalid runtime status |
| cli/wuwei/commands/runtime.py:49 | invalid runtime result |
| cli/wuwei/commands/runtime.py:56 | invalid runtime job |
| cli/wuwei/discovery.py:133 | invalid code-host result |
| cli/wuwei/discovery.py:177 | invalid base-check result |
| cli/wuwei/discovery.py:203 | invalid scanner findings |
| cli/wuwei/dispatch.py:123 | invalid tracker result |
| cli/wuwei/dispatch.py:451 | invalid runtime result |
| cli/wuwei/fast_checks.py:40 | invalid fast-check result |
| cli/wuwei/mcp.py:424 | invalid scanner result |
| cli/wuwei/pr_actions.py:420 | invalid outward tier result |
| cli/wuwei/registry.py:104 | invalid runtime policy for {role} |
| cli/wuwei/steward.py:227 | invalid runtime result |

**Hook payloads** (26). Rewrite: Claude Code sent a hook payload this WUWEI version cannot read; nothing was done and it is not your mistake. Run `bin/wuwei doctor`, then update Claude Code or WUWEI.

| Location | Message now |
|---|---|
| cli/wuwei/__main__.py:67 | invalid exit status {status}; expected 0, 1, or 2 |
| cli/wuwei/commands/build.py:275 | SubagentStop omitted builder agent_id |
| cli/wuwei/commands/build.py:277 | SubagentStop agent_id differs from resumed builder |
| cli/wuwei/commands/build.py:280 | SubagentStop omitted builder result |
| cli/wuwei/commands/build.py:290 | SubagentStop has no matching assistant completion |
| cli/wuwei/commands/hook.py:80 | invalid guard result; expected (0\|1\|2, message) |
| cli/wuwei/commands/hook.py:254 | invalid JSON constant |
| cli/wuwei/commands/hook.py:259 | hook payload must be a JSON object |
| cli/wuwei/commands/hook.py:264 | hook_event_name does not match command event |
| cli/wuwei/guards/__init__.py:108 | unknown guard event |
| cli/wuwei/guards/agent_launch.py:66 | invalid tool_input |
| cli/wuwei/guards/agent_launch.py:204 | missing or invalid agent_transcript_path |
| cli/wuwei/guards/agent_launch.py:207 | SubagentStop has no brief reference |
| cli/wuwei/guards/agent_launch.py:218 | SubagentStop has no matching seat reservation |
| cli/wuwei/guards/agent_launch.py:220 | SubagentStop role does not match seat reservation |
| cli/wuwei/guards/decision.py:40 | missing or invalid tool_input |
| cli/wuwei/guards/decision.py:110 | missing or invalid tool_input |
| cli/wuwei/guards/lifecycle.py:17 | cwd must be absolute |
| cli/wuwei/guards/protect_state.py:169 | missing or invalid tool_input |
| cli/wuwei/guards/protect_state.py:257 | cwd must be absolute |
| cli/wuwei/guards/stop.py:14 | cwd must be absolute |
| cli/wuwei/guards/stop.py:36 | stop_hook_active must be boolean |
| cli/wuwei/guards/traces.py:104 | invalid agent_id |
| cli/wuwei/guards/verdict.py:63 | missing or invalid tool_input |
| cli/wuwei/plan.py:16 | planner session id must be a nonempty string |
| cli/wuwei/sessions.py:36 | session id must be a nonempty string |

**Races** (11). Rewrite: Another session changed this record while the command ran; nothing was written. Run the same command again.

| Location | Message now |
|---|---|
| cli/wuwei/commands/build.py:97 | build changed before recording action |
| cli/wuwei/commands/build.py:247 | build changed during result recording |
| cli/wuwei/commands/build.py:401 | build changed before parking |
| cli/wuwei/commands/decision.py:117 | decision changed during confirmation |
| cli/wuwei/dispatch.py:176 | gate tier changed during dispatch |
| cli/wuwei/dispatch.py:359 | scanner: unmeasured: worktree HEAD changed during audit |
| cli/wuwei/dispatch.py:378 | scanner: unmeasured: item flags changed during receive |
| cli/wuwei/dispatch.py:380 | gate state changed during receive |
| cli/wuwei/drafts.py:157 | drafts: draft changed during approval |
| cli/wuwei/mcp.py:537 | decision changed during confirmation |
| cli/wuwei/pr_actions.py:326 | conflict action changed before completion |

**Symlinked records** (47). Rewrite: A WUWEI record or setting is a symlink; links are refused so a write cannot be redirected. Replace it with a regular file (`bin/wuwei doctor` names it).

| Location | Message now |
|---|---|
| cli/wuwei/brief.py:199 | brief directory must not be a symlink |
| cli/wuwei/brief_pack.py:80 | brief pack path must not be a symlink |
| cli/wuwei/brief_pack.py:127 | brief audio path must not be a symlink |
| cli/wuwei/calibrate.py:706 | calibration.json must not be a symlink |
| cli/wuwei/closing.py:84 | proposals directory must not be a symlink |
| cli/wuwei/closing.py:91 | landed proposal must not be a symlink |
| cli/wuwei/closing.py:101 | rejected proposal must not be a symlink |
| cli/wuwei/commands/agents.py:144 | generated instructions must not traverse symlinks |
| cli/wuwei/commands/init.py:67 | workspace settings must not be symlinks |
| cli/wuwei/commands/note.py:47 | notes directory must be inside the workspace and not a symlink |
| cli/wuwei/consolidation.py:20 | note must not be a symlink |
| cli/wuwei/consolidation.py:34 | charters must not be a symlink |
| cli/wuwei/consolidation.py:39 | charter must not be a symlink |
| cli/wuwei/env.py:97 | .wuwei/env and .gitignore must not be symlinks |
| cli/wuwei/integrity.py:59 | symlink in installed plugin: {relative} |
| cli/wuwei/integrity.py:150 | checkout .git must not be a symlink |
| cli/wuwei/interview.py:262 | interview.json must not be a symlink |
| cli/wuwei/memory.py:24 | memory notes directory must be inside the workspace and not a symlink |
| cli/wuwei/memory.py:32 | note must not be a symlink: {path} |
| cli/wuwei/memory.py:51 | day directory must not be a symlink: {parent} |
| cli/wuwei/memory.py:56 | day directory must not be a symlink: {day} |
| cli/wuwei/memory.py:69 | report must not be a symlink: {report} |
| cli/wuwei/memory.py:148 | memory notes directory must be inside the workspace and not a symlink |
| cli/wuwei/memory.py:154 | note must not be a symlink: {path} |
| cli/wuwei/memory.py:193 | ledger must not be a symlink: {ledger} |
| cli/wuwei/memory.py:209 | trace directory must not be a symlink: {parent} |
| cli/wuwei/memory.py:214 | trace day must not be a symlink: {day} |
| cli/wuwei/memory.py:219 | trace must not be a symlink: {trace} |
| cli/wuwei/metrics.py:31 | baseline must not be a symlink |
| cli/wuwei/metrics.py:63 | transcript symlink |
| cli/wuwei/plan.py:154 | plan files must not be symlinks |
| cli/wuwei/plan.py:232 | proposal.json must not be a symlink |
| cli/wuwei/profiles.py:235 | profile.json must not be a symlink |
| cli/wuwei/promotion.py:111 | snapshot directory must not be a symlink |
| cli/wuwei/promotion.py:199 | archive path must not be a symlink |
| cli/wuwei/promotion.py:225 | proposals directory must not be a symlink |
| cli/wuwei/promotion.py:230 | ledger path must not be a symlink |
| cli/wuwei/promotion.py:235 | proposal must not be a symlink |
| cli/wuwei/promotion.py:275 | ledger must not be a symlink |
| cli/wuwei/promotion.py:291 | trace must not be a symlink |
| cli/wuwei/promotion.py:317 | events must not be a symlink |
| cli/wuwei/promotion.py:334 | note must not be a symlink |
| cli/wuwei/report.py:96 | parked decision must not be a symlink |
| cli/wuwei/retro.py:101 | gate verdict must not be a symlink |
| cli/wuwei/security.py:23 | honeytoken path must not traverse symlinks |
| cli/wuwei/security.py:57 | security material must not be a symlink |
| cli/wuwei/voice.py:131 | voice output path is a symlink |
