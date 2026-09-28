# Implementation Plan: PR guards

## Technical Context

Python 3.11+, standard library runtime, pytest for development. One discovered
PreToolUse/Bash guard in cli/wuwei/guards/pr.py and one in-process test module.
No new dependencies, configuration, state schema or adapter operations.

## Constitution Check

Pass: three-state exits, ports-only tool reads, test before implementation,
existing guard registration, short scoped diff. Do not commit, push or run gh.

## Design

1. Use shell.mentions before shell.normalize. Resolve scope from cwd and normalized
   directory and repository-environment targets using workspace helpers; use VCS context for external worktrees.
2. Inspect normalized argv and env. Parse command options, never shell text. Unknown
   relevant option shapes or opaque execution return 2. Preserve out-of-scope calls.
3. PR creation measures head through registry.load('vcs', config).head. Inspect today's
   gate-<item>-<gate>.md files with verdict.active_text, rows and lint. Resolve short
   heads through vcs.resolve. Require one complete item set and --reviewer/-r.
4. PR merge and API merge call merge_check(repo, pr, cwd, root, config). Its #77 placeholder returns 1 with the
   exact required hint. Approvals, admin merges and protection writes return 1.
5. API review bodies supplied indirectly cannot prove a non-approval, so return 2.
   Read-only API requests pass; unknown GraphQL requests fail closed in scope.
   REST endpoint matching includes enterprise prefixes, encoded paths and dot segments.
   Repeated method options use the last value, including short/long aliases.
6. Reuse shell.operands for PR and deploy option reading. Extend the existing
   deploy PERMISSIONS_DENY list for init; retain the single settings writer.

## Validation

Test each story before implementation, including aliases of short/long options,
wrappers, API method inference, state spoofing, short SHA resolution, scope, port
errors, malformed files and a registration mutation. Use tests/fakes/vcs.py.
Run the full suite with the interpreter specified by the task. Scan all changed
files for local machine paths, emojis and em-dashes.

## Deferred

#77 replaces merge_check with the current-head merge policy. No merge execution is
implemented here.

## Review refinements

Regression tests cover global repository flags between subcommands, organization
rulesets, enterprise GraphQL, inherited repository targets and home-relative repo
paths. Creation requires an isolated command so HEAD and verdict writes cannot be
changed earlier in the same shell action. Security evidence uses the existing
class-sweep lint, just like arch and quality. On outside parse failures, inspect
cd/pushd candidates with shlex and validate their operands with the shared normalizer.
Only nonliteral or workspace directory targets activate that fallback refusal.
Branch-merge API writes use the same merge policy; protected branch ref writes refuse.
Endpoint routes match without case sensitivity, preserving case-sensitive branch names.
