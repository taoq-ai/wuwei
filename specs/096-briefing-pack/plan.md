# Implementation Plan: Briefing pack

**Branch**: `096-briefing-pack` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Add `brief pack` and `brief answer` to the existing command. Keep seat brief syntax. A small core module assembles recorded evidence and writes markdown plus JSON drill data through the shared atomic writer. Calendar and TTS run only through closed port adapters. The daily and meeting due window uses existing workspace time and event records.

## Technical Context

Python 3.11+ stdlib runtime. pytest development tests. Reuse registry, config validation, event reader, atomic writer, state writer and metrics collector. Fake ports and fixture ICS in tests. No new dependencies.

## Constitution Check

Before and after design: stdlib runtime; 0/1/2 exits; adapter failures remain exit 2; producer-owned state and event kinds; test first; no URL in durable output. No new guard or shell parsing. The worktree already isolates the issue.

## Design

- Extend registry and config with `calendar`, `tts`, `transcripts`; adapters provide `none`, `ics` and `say` implementations. ICS parses basic VEVENT fields, folded lines, UTC and local date-time, and attendees. The adapter reads the URL from config or environment and sanitizes all error reasons.
- `brief pack` selects daily or the next attendee event within `brief.lead_minutes`, deduplicates by state, reads events and decisions, builds fixed sections and three-item card/drill, writes a markdown visual and optional audio, then records pack metadata. `tts = none` writes an explicit no-audio line.
- `brief answer` reads producer-owned drill state, gives feedback immediately and records score/streak through state writer. Metrics reads this state as the steward drill score.
- Keep the pack content deterministic. `brief.style` controls concise/standard length and speech speed. Chapter headings stay fixed.

## Validation

Write a failing test for each behavior, run it to observe the expected failure, implement the minimum to pass, then run the full suite with the requested interpreter. Scan authored files for forbidden characters and machine-specific paths.
