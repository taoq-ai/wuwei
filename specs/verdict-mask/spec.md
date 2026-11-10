# Feature Specification: verdict files and the verdict.missing row are masked before they sync

**Feature branch**: `fix/verdict-mask`
**Item**: verdict-mask, tier full, goal G-2
**Input**: the security gate on #1285 at c70bbcb found two raw write sites in `cli/wuwei/hook.py`:
the worktree copy-in in `_verdict_problem` writes the gate's bytes as they are, and the
`verdict.missing` row in `_seat_stop` keeps `problem[:300]` unmasked. `.wuwei/verdicts` and
`.wuwei/ledger` are not in `sync.LOCAL`, so both push to `wuwei/state`, a public branch of a public
repository.

## The promise in my words

No `guards.SECRETS` match and no workspace canary that a gate writes reaches `wuwei/state` through
a verdict file or a ledger row. Three places carry a gate's text there:

1. a verdict written in a worktree and copied into the workspace's `.wuwei/verdicts`;
2. a verdict the gate wrote straight into the workspace's `.wuwei/verdicts`;
3. the `verdict.missing` row, whose `problem` quotes the gate's `Verdict file:` path and the
   parser's errors.

Each is masked with `hook.mask` (the canary first, then `guards.SECRETS`, as the reports-mask fix
set). The file is masked before its sha256 is taken, so the `attest` row and every later read by
`evidence.verdicts` see the same masked bytes. The `attest` row's parsed fields come from the masked
body. A verdict with neither is written and attested byte for byte as before. Files already on disk
or already on `wuwei/state` stay as they are; a history rewrite is the owner's call.

The acceptance scenario, restated: a verdict holding a token or the canary, written in a worktree
or straight into `.wuwei/verdicts`, leaves a file there that holds `***` in place of both, and its
attest row's sha256 matches that file.

## How this fails

1. The copy check compares the raw worktree bytes with the masked copy, so a gate stopping a second
   time with the same verdict is told the copy "already holds another verdict". Guarded by masking
   before the compare, with a test that stops twice.
2. The direct write is masked after its sha256 is taken, so the attest row names a hash no file
   holds and `evidence.verdicts` drops the verdict as edited. Guarded by masking before the hash,
   with a test that reads the file's hash against the row.
3. Masking decodes and re-encodes the bytes, so a verdict holding invalid UTF-8 changes and its
   hash moves. Guarded by `surrogateescape` both ways and a test with a stray byte.

## Clarifications

### Session 2026-11-10

- Q: A new masking helper? A: No. `hook.mask(text, canary)` already exists; the verdict path wraps
  it in one bytes lambda so the copy-in and the direct write share it.
- Q: Is a gate's direct write rewritten in place? A: Yes, only when masking changes it, through
  `ws.atomic_write` rooted at the resolved verdicts folder, so no link is followed.
- Q: The block reason sent back to the gate? A: Unchanged. It goes to the seat, not to a synced file.
- Q: A token or canary in the verdict's file name? A: Outside: the attest `path` and the file name
  stay as written (see Assumptions).

## User Scenarios & Testing

### US1: a copied-in verdict holds no secret or canary (P1)

A worktree verdict with a `ghp_` token and the canary: the workspace copy holds `***` for both, the
attest row's sha256 is the copy's, and a second stop with the same verdict passes.

### US2: a direct verdict holds no secret or canary (P1)

A verdict written straight into `.wuwei/verdicts` with both: the file is rewritten masked and its
sha256 matches the attest row; a clean verdict, or one with a stray non-UTF-8 byte, keeps its bytes.

### US3: verdict.missing quotes no secret or canary (P1)

A gate that names a `Verdict file:` holding a token and the canary, after a reminder: the row's
`problem` holds `***` for both.

## Requirements

- FR-001: `_verdict_problem` masks the worktree verdict before the copy check and the copy write.
- FR-002: `_verdict_problem` masks a verdict already in the workspace before its sha256, rewriting
  it only when masking changes it.
- FR-003: `_seat_stop` masks `problem` before the 300-character cut of `verdict.missing`.
- FR-004: Bytes masking leaves no match unchanged, invalid UTF-8 included.
- FR-005: The runtime stays at 4,000 lines or fewer.

## Assumptions

- A secret or canary in a verdict's file name is left alone: gates name files `<gate>-<sha7>.md`,
  and renaming would break the `Verdict file:` link the gate reports. Overturned if a synced file
  name ever holds one.
- Verdicts already on `wuwei/state` are not rewritten. Overturned if a scan finds a match there.

## Rollback

Revert the commit. No config key, ledger kind or file format changes; masked files stay masked.
