# Implementation Plan: Hooks are cooperative mistake prevention; publication policy is enforced where changes land

**Branch**: `237-spec-guard-boundaries` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

## Summary

A documents-only change. The design spec amendment (4.5, 9.1, section 10), the constitution
amendment and the one-paragraph security page fix are already written in the working tree
by the spec author. The builder adds one docs test that pins them, confirms it is red
against main and green here, reviews the wording for consistency, and runs the suite. No
runtime code, no guard behaviour, no existing test changes.

## Technical Context

Markdown documents plus one pytest function in `tests/test_docs.py`. Stdlib only in the
test (`pathlib`, `re`, already imported there). No new files besides this feature's
`specs/` directory.

## Constitution Check

- I (stdlib) and II (three-state exits): not touched; no runtime code.
- III (one behaviour, one test): the documents' agreement is one behaviour, one test.
- IV (test first): the docs test is written and seen red against main before the
  amendment is accepted. Because the amendment text already exists, red is shown against
  a `git archive main` export (the same "before" method the #222 review used), never by
  stashing or reverting the working tree.
- V (ponytail): one test function, phrase asserts, reusing the module's `ROOT` and `SITE`
  and the whitespace normalisation (`' '.join(text.split())`) the #231 latency test uses.
  No helper module, no fixture, no parser for Markdown.
- VII (security): the amendment weakens no refusal; it moves the claimed guarantee to
  where it actually holds.
- Governance: this change amends the constitution (1.0.0 to 1.1.0). Its commit message
  needs a dated line (orchestrator).

## What was changed (spec author, already in the working tree)

1. `docs/specs/2026-09-24-wuwei-design.md` 4.5 (heading now "(owner, 2026-09-28; amended
   2026-09-30, #237)"): the normalisation paragraph is kept word for word except that the
   "second anchor" sentence moved out; the bypass-table sentence stays. New: a two-item
   list (own records: parser is the only local check, normalisation and bypass table stay;
   publishing actions: refuse what is recognisable, guarantee is host plus credential
   layout, documented by `wuwei init` and verified by `wuwei config check`; `pre-push` hook
   and `permissions.deny` are further local checks, not boundaries), then the argv
   allowlist paragraph (privileged publish only, example `wuwei merge`'s exact
   `gh pr merge --squash --match-head-commit <sha>`; a development-wide allowlist is
   rejected because allowing an interpreter or the test runner allows arbitrary code).
2. Same file, 9.1: first paragraph now says "cooperative mistake prevention", "never an
   isolation boundary", and that no hook, Claude Code or git, is a hard boundary. The hard
   boundary list gains "publication credentials kept out of seat environments" and the
   host item reads "protected refs, required checks, required reviews"; the list is
   introduced with "they hold when no hook runs". "Local anchors" became "Local checks ...
   none of them is a boundary". Guard scope paragraph unchanged.
3. Same file, section 10: last bullet "What a real day must prove (owner, 2026-09-30)",
   naming #239's live rehearsal as a release precondition and a skipped rehearsal as
   unmeasured.
4. `.specify/memory/constitution.md` Workflow: the cycle budget bullet names the
   consequence (no further fix rounds; design reconsideration recorded in the spec, agreed
   with the owner, before more code) and cites #222 (six rounds). Footer: Version 1.1.0,
   Last Amended 2026-09-30.
5. `docs/site/security.md:48` (Threat model 9.1 paragraph): "cooperative mistake
   prevention, not an isolation boundary", the same hard-boundary list as 9.1 including
   credentials, and one sentence that for push, merge, deploy and PR approval the guards
   refuse what they recognise while the guarantee is the host rules and credential layout.

## What the builder adds

`tests/test_docs.py`, appended after the last test, one function:

```python
def test_guard_boundaries_are_stated_once():
    flat = lambda text: ' '.join(text.split())
    spec = (ROOT / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
    section = lambda number: flat(re.search(rf'^### {number} .*?(?=^##)', spec, re.S | re.M)[0])
    matching, threat = section(r'4\.5'), section(r'9\.1')
    testing = flat(re.search(r'^## 10\. .*?(?=^## )', spec, re.S | re.M)[0])
    security = flat((SITE / 'security.md').read_text())
    constitution = flat((ROOT / '.specify/memory/constitution.md').read_text())
    for phrase in ('the parser is the only local check',
                   'the guarantee comes from the code host and the credential layout',
                   'no publishing token in seat environments', '`wuwei config check` verifies',
                   'further local checks, not boundaries',
                   'narrow argv allowlist may be used for privileged publish actions only',
                   'allowing an interpreter or the test runner allows arbitrary code'):
        assert phrase in matching, phrase
    for text in (threat, security):
        for phrase in ('cooperative mistake prevention', 'isolation boundary',
                       'protected refs, required checks, required reviews',
                       'publication credentials kept out of seat environments'):
            assert phrase in text, phrase
    assert 'none of them is a boundary' in threat
    assert not re.search(r'second anchor|local anchors', spec, re.I)
    for phrase in ('What a real day must prove', 'live rehearsal', 'unmeasured, never a pass'):
        assert phrase in testing, phrase
    assert 'design reconsideration recorded in its spec' in constitution and '#222' in constitution
```

The sketch is the contract, not the letter: keep the phrases, tighten the code if a
shorter form reads as clearly. The regexes stop at the next heading of level 2 or 3
(`^##` also matches `###`); 9.1 is the last `###` before `## 10`, so both extractions end
where the sections end.

## What must not change

- Any file under `cli/`, `adapters/`, `hooks/`, `bin/`, `agents/`, `charters/`, `skills/`,
  `templates/`, `scripts/`, `.github/`.
- Any existing test function, including every guard table, mutation and hook test
  (`tests/test_owner_actions.py`, `tests/test_protect_state.py`, the commit, push, PR,
  merge and deploy guard tests). Only the new function is added to `tests/test_docs.py`.
- Design 4.6, 4.7, 5.3 (the product's per-gate cycle budget) and 13; `docs/integrity.md`;
  the "planned" line on the security page (owned by #238).
- The `'9.1' in security.md` assertion in `test_site_pages_and_links` keeps passing (the
  heading "Threat model 9.1" is unchanged).

## Consistency review (builder)

Read these side by side and fix only wording conflicts, only in the files already changed:
design 4.1 (hook table rows for push, merge, approve, deploy), 4.5, 4.6 ("Never `--admin`,
never a change to branch protection, never an approval"), 4.7, 7.1 ("Tamper evidence, not
tamper-proofing (9.1)"), 9.1; `docs/site/security.md`; `docs/integrity.md:42-47`;
`docs/site/reference.md:59` ("cooperative hook threat model in spec 9.1") and `:71` (a raw
worktree has no anchor; this refers to the workspace anchor file, not a boundary claim,
and stays). Expected result: no further edits.

## Verification commands

```sh
# red against main's documents (scratch directory outside the repository)
git archive main | tar -x -C "$SCRATCH/base"
cp tests/test_docs.py "$SCRATCH/base/tests/test_docs.py"
(cd "$SCRATCH/base" && python -m pytest -q tests/test_docs.py -k guard_boundaries)   # fails
python -m pytest -q tests/test_docs.py -k guard_boundaries                            # passes
git diff --stat $(git merge-base HEAD main) -- cli adapters hooks bin agents charters skills templates scripts .github  # empty
git diff $(git merge-base HEAD main) -- tests | grep '^-[^-]'                                                  # empty
grep -nE 'second anchor|[Ll]ocal anchors' docs/specs/2026-09-24-wuwei-design.md        # empty
python -m pytest -q
```

## Deferred (follow-up issues, not this one)

- `wuwei config check` verifying the host and credential layout per configured repository
  (protected base branch, required checks, no publishing token in seat environments)
  through the existing `code_host.protection(repo, branch)` port, and `wuwei init`
  printing or writing that layout. Runtime work; the issue forbids it here.
- The security page's "planned" line for manifests and canaries (#238).
- The live rehearsal itself (#239).
