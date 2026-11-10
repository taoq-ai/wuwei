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
carries "Announced at <link>" and asks the owner to proceed. The hook reads each by its own marker,
"Treat as breaking?" or "Announced at <link> Proceed?", and records nothing for any other
`breaking:` question. It records a classification answer as the owner's classification at that head,
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
- An owner option label the hook does not read ("Y", "Sure", "It breaks") records nothing. Safe
  direction: the gap stays, and the question can be asked again in the explicit shape.
- An owner no clears a break the author declared. Mitigation: a declared break ignores the no.

## Requirements

- FR-001: a `breaking:` question holding "Treat as breaking?" and no "Announced at <http(s) link>"
  records `{'kind': 'breaking', 'breaking': <yes>, 'approved': False}` at its head, only on an
  explicit answer: yes or breaking, no, not breaking or non-breaking. Any other answer records
  nothing, so the gap stays. A Proceed is only "Announced at <link> Proceed?" without "Treat as
  breaking?". A `breaking:` question of neither shape records nothing (fix round on fc4364d).
- FR-002: the confirmation gap clears only on a breaking row with `approved` true and no
  `breaking` field, at the head.
- FR-003: the latest classification at the head decides whether the change is breaking, unless
  the PR declares it. A yes makes it breaking; a no clears an arch yes.
- FR-004: the guard refusal and the shepherd charter name the classification shape.

## Assumptions

- Each shape is read by its own exact marker ("Treat as breaking?"; "Announced at <link>
  Proceed?"), so a misspelt question records nothing and the gap stays. Why: the gates showed a
  substring test fails open. Overturned if the owner wants looser matching.
- A classification yes makes the change breaking even with no arch yes or declaration. Why: the
  owner's word outranks the gate's; it only adds a gap. Overturned if the owner wants the yes
  recorded but not acted on.
- A declared break (`!` or `BREAKING CHANGE:`) ignores a classification no. Why: the PR's own
  text says it breaks; fix the text instead. Overturned if the owner wants the no to win.
- Old misrecorded rows are not rewritten. Why: the ledger is append-only and they bind one head.
