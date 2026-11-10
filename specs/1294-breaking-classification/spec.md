# Feature Specification: a breaking: question asked before an announcement records the owner's classification

**Feature branch**: `fix/1294-breaking-classification`
**Item**: 1294, tier smart (complex), goal G-2
**Input**: issue #1294. The lead found the stated cause wrong: the 5.4.0 guard already passes
`breaking: o/r#n at <sha7>: <what changes>. Treat as breaking?`. The real defects: the shepherd
charter says to ask only once an announcement exists; `hook._answers` records any yes to a
`breaking:` question as the approval, so a "yes, it is breaking" reads later as the Proceed; and a
"no" never clears the breaking gap.

## The promise in my words

There are two `breaking:` questions. The first, asked before any announcement, is a
classification: "is this change breaking?". The second, asked once an `Announcement:` line exists,
carries "Announced at <link>" and asks the owner to proceed. The hook tells them apart by the words
"Announced at". It records a classification answer as the owner's classification at that head,
never as the approval. A classification yes therefore never clears the confirmation gap; only a
Proceed yes does. A classification no clears the breaking gap at that head, unless the PR declares
the break itself (a `!` title or a `BREAKING CHANGE:` line). A new head asks again. The guard hint
and the shepherd charter name both shapes.

Acceptance, restated:

1. The guard passes `breaking: o/r#n at <sha7>: <what changes>. Treat as breaking?`, and its
   refusal of a malformed `breaking:` question names this shape beside the Proceed shape.
2. The owner answers Yes to the classification at head H; the PR at H has an `Announcement:` line;
   `wuwei evidence` still shows "breaking change needs the owner's confirmation" until a Proceed
   yes at H.
3. The owner answers No at H; the title has no `!`; an arch verdict says Breaking: yes; evidence at
   H shows no breaking gap. At a new head the arch verdict holds again.

## How this fails

- An old ledger row from before this fix (a classification yes recorded as `approved: true`) still
  reads as the Proceed at its head. Mitigation: rows bind to one head; such a head is rare.
- A Proceed question phrased without "Announced at" is read as a classification, so its yes does
  not approve. Safe direction: the gap stays and names the Proceed shape.
- An owner no clears a break the author declared. Mitigation: a declared break ignores the no.

## Requirements

- FR-001: a `breaking:` question without "Announced at" records `{'kind': 'breaking', 'breaking':
  <yes>, 'approved': False}` at its head.
- FR-002: the confirmation gap clears only on a breaking row with `approved` true and no
  `breaking` field, at the head.
- FR-003: the latest classification at the head decides whether the change is breaking, unless
  the PR declares it. A yes makes it breaking; a no clears an arch yes.
- FR-004: the guard refusal and the shepherd charter name the classification shape.

## Assumptions

- "Announced at" (any case) marks the Proceed question; its absence marks a classification. Why:
  the item's promise says so. Overturned if the owner wants a separate keyword.
- A classification yes makes the change breaking even with no arch yes or declaration. Why: the
  owner's word outranks the gate's; it only adds a gap. Overturned if the owner wants the yes
  recorded but not acted on.
- A declared break (`!` or `BREAKING CHANGE:`) ignores a classification no. Why: the PR's own
  text says it breaks; fix the text instead. Overturned if the owner wants the no to win.
- Old misrecorded rows are not rewritten. Why: the ledger is append-only and they bind one head.
