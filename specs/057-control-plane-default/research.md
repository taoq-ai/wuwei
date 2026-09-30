# Research: what Claude Code provides and what WUWEI adds

Verified against the Claude Code docs on 2026-09-30 (pages "Continue local sessions from any
device with Remote Control" and "Hooks reference", code.claude.com/docs). Nothing below is
assumed; anything the docs do not state is listed as not relied on.

## Claude Code Remote Control (provided, no WUWEI code)

- Connects claude.ai/code or the Claude mobile app to a Claude Code session running on the
  host. The session keeps running locally; the phone is a window into it.
- Started with `claude remote-control` (server mode), `claude --remote-control` (or `--rc`),
  or `/remote-control` (`/rc`) inside a session. Auto-connect for every interactive session
  via `/config` ("Enable Remote Control for all sessions") or `remoteControlAtStartup` in
  user or managed settings; a project `.claude/settings.json` can only turn it off.
- Plans: Pro, Max, Team and Enterprise; API keys are not supported. On Team and Enterprise
  an organisation Owner must first enable it in the Claude Code admin settings (matches
  design 15.4). `disableRemoteControl` turns it off; Zero Data Retention organisations
  cannot enable it. Optional "Require trusted devices" ties phone access to enrolled
  devices.
- The host must stay on and the `claude` process running; it reconnects after sleep or a
  network drop. Outbound HTTPS only, no inbound port.
- Permission prompts and `AskUserQuestion` questions stay open until answered, from any
  connected device.

## Mobile push (provided, no WUWEI code)

- With Remote Control active, Claude can push to the phone. Two toggles in `/config`:
  "Push when Claude decides" (proactive, for example a finished long task) and "Push when
  actions required" (permission prompts and questions). No per-event configuration.
- Pushes are skipped while the owner is typing in or focused on the connected terminal;
  `CLAUDE_CLIENT_PRESENCE_FILE` extends that to "at the machine".
- Needs the Claude mobile app with notifications allowed.

## Hooks

- The `Notification` hook event (types include `permission_prompt`, `idle_prompt`,
  `elicitation_dialog`, `agent_needs_input`) is observational: it cannot block, and the docs
  describe no way for a hook or CLI to send a mobile push. A hook can only emit desktop
  terminal notifications.

## Consequence for the default implementation

- A decision reaches the phone when the planner asks it as an `AskUserQuestion` widget in a
  Remote Control session with "Push when actions required" on. WUWEI cannot push by itself,
  so the default `escalate` renders the widget text and sends nothing, and the default
  `notify` returns the summary for the session to show ("Push when Claude decides" may push
  it; not guaranteed).
- The answer to a widget arrives in the planner session, so the default `poll_replies` has
  nothing to poll and returns an empty list.
- Not relied on: any guarantee that a proactive push fires; enabling Remote Control for a
  headless `claude -p` run (design 15.9 already lists it as unconfirmed).

## What WUWEI adds in #57

- One rendering of a pending decision (id, one-line question, options) shared by the widget
  and messaging transports, with `control_plane.content = summary | none`.
- The shared reply parser ("approve D-n", "option X on D-n", "drop it") with echo on
  anything else.
- The `decision.replied` record against the decision id.
