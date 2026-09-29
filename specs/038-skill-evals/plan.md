# Implementation Plan: Skill triggering evals

## Context

The plugin ships three skill descriptions under `skills/`. Section 10 requires triggering evals with near-miss negatives. The issue supplies the runner format, grader fields and threshold.

## Design

Use one directory per query under `evals/`, each with a prompt and a Skill tool grader. Add one pytest structure test that discovers all shipped skills and validates frontmatter fields, grader fields, counts and references. Use only Python standard library parsing for the small fixed YAML subset. Add a separate CI job that installs Claude Code, checks for the API key and runs the authenticated suite. Document the local command and owner secret setup in README.

## Verification

First run the new structure test against no eval cases and observe missing coverage. Add cases and rerun. Run the full pytest suite with the requested interpreter. The live runner requires an owner-provided key and network and is deferred until available.

## Constraints

No runtime dependencies, skill description changes, model pin or unrelated guard changes. No commit or push.
