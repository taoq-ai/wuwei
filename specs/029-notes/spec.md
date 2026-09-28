# Feature Specification: Notes

**Feature Branch**: `029-notes`  
**Created**: 2026-09-28  
**Status**: Draft  
**Input**: Issue #29, amended 2026-09-28.

## User Scenarios & Testing

### User Story 1: Create a semantic note (Priority: P1)

A seat creates a new workspace note with a valid summary and metadata.

**Independent Test**: Add a note through the CLI, inspect its frontmatter and body, and parse it with the shared validator.

**Acceptance Scenarios**:

1. Given a note without a summary, when adding it, then the write is refused and no file is created.
2. Given a valid note, when adding it, then `memory/notes/<slug>.md` contains type, summary, aliases, status, and a created date from the shared clock.
3. Given an existing slug, when adding it, then the existing note is preserved and exit 1 is returned.
4. Given a decision without a `Why:` body line, when adding it, then the write is refused.

### User Story 2: Validate notes for later consumers (Priority: P1)

The index and promote commands can parse and validate the same frontmatter contract.

**Independent Test**: Call the exported parser on valid and malformed note text; invalid required fields and unsupported values raise a validation error.

### Edge Cases

Missing workspace, invalid slug, malformed frontmatter, multiline summary, malformed aliases, and I/O failures must not create a note. An operational failure exits 2 with a reason.

## Requirements

- FR-001: `wuwei note add` creates one Markdown note in `.wuwei/memory/notes/`.
- FR-002: A reusable function parses and validates frontmatter with stdlib Python: `type` is hub, reference, decision, person, or question; `summary` is nonempty and one line; `aliases` is a list; `status` is active or archived.
- FR-003: New notes start active and carry `created:` set to the shared clock's local date.
- FR-004: A decision note requires a body line beginning `Why:` with a nonempty explanation.
- FR-005: Duplicate slugs and invalid note content return exit 1 without modifying an existing note; inability to run returns exit 2.
- FR-006: Existing notes are changed only through proposals and `wuwei promote`.

### Key Entities

A note is a Markdown file with YAML-subset frontmatter, optional body, and a stable slug filename.

## Success Criteria

- SC-001: Every accepted note parses with the shared validator and has all four contract fields plus a created date.
- SC-002: Missing summaries, invalid decision rationale, and duplicate slugs create no write.
- SC-003: The full repository test suite passes.

## Assumptions

- `wuwei note add <slug> --type <type> --summary <summary> [--alias <alias>] [--body <text>]` is the CLI syntax; aliases can be repeated and the body defaults to empty.
- Slugs use lowercase ASCII letters, numbers and interior hyphens. Aliases are simple one-line strings without commas or brackets so the stdlib subset stays unambiguous.
- The frontmatter parser accepts only the supported `key: value` and `[a, b]` forms. It accepts `created` as an optional metadata field for older notes but creates it for every new note.
- New notes are active for their probation period; the probation calculation belongs to a later issue.
- `note update` and `note archive` moved to issue #81 under the 2026-09-28 amendment.

## Deferred

- Proposal handling, `wuwei promote`, update, and archive: issue #81.
- Index generation and probation load tracking: issue #30 and later memory work.
