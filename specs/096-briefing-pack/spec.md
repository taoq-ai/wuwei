# Feature Specification: Briefing pack

**Feature Branch**: `096-briefing-pack`  
**Created**: 2026-09-29  
**Status**: Ready for implementation

## User Scenarios & Testing

### User Story 1 - Prepare a meeting or daily pack (P1)

The owner runs `wuwei brief pack` for the day or an upcoming meeting. The pack reads recorded events, decisions, metrics and an optional calendar feed. It presents the most consequential change first, then fixed sections, a static what-changed visual, three meeting bullets and three drill questions.

**Acceptance Scenarios**

1. Given a fixture calendar event and fixture events, the pack has headline, changed, decided, at risk and you will be asked in that order, and the card has exactly three bullets.
2. Given `tts = none`, the pack is produced without audio and says so.
3. Given a calendar event with no attendees, no meeting pack is due; the daily pack remains available.
4. Given a configured lead time, a meeting pack is due only during its lead window and is produced once.
5. A failed calendar or TTS adapter returns exit 2 with a safe reason. The feed URL never appears in outputs or records.

### User Story 2 - Practice the defend drill (P1)

The owner answers each pack's three questions by text. Feedback is immediate, hardest question first, and the recorded streak and score appear in steward metrics.

**Acceptance Scenarios**

1. Given an answer to a drill question, feedback and updated streak are recorded.
2. An incorrect answer resets the streak; a correct answer advances it.
3. Answers cannot be entered through generic state or event commands.

## Requirements

- **FR-001**: Register closed `tts`, `calendar` and `transcripts` port allowlists. Default transcripts to none. Only adapters invoke external tools or HTTP.
- **FR-002**: The private calendar URL comes from config or environment, is never printed, logged, or written to events, traces or packs, and is redacted from adapter errors.
- **FR-003**: Pack sections have a fixed order. The meeting card has exactly three bullets. The drill has exactly three questions, hardest first.
- **FR-004**: The visual is static text or HTML with optional source deep dives. Audio has chapters and is bounded to five minutes of speech text.
- **FR-005**: `brief.style` tunes length and speed without breaking the fixed shape or three-item counts.
- **FR-006**: Pack generation and drill answers are producer-only state; drill score is a steward metric.

## Assumptions

- `wuwei brief pack` generates the daily pack by default. `--meeting` selects the next attendee meeting within the lead window.
- Without a language model, likely questions and answers are deterministic prompts based on recorded evidence. Text answers are compared to key terms in the expected answer.
- The five-minute bound is a conservative 600-word ceiling at the slowest supported voice speed.
- The existing `wuwei brief <role> <item> <name>` seat brief remains available.

## Deferred

- Recorder-specific transcript adapters and voice-answer transcription need a recorder integration.
- Automatic scheduling and phone delivery belong to the later routine and control-plane work; this issue provides the callable pack command and due-window behavior.
