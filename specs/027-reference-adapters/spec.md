# Feature 027: Reference adapters

## User stories

### US1: Linear tracker

A workspace with the Linear adapter selected can claim, transition, create and inspect issue history through its fixed port. Writes perform one mutation each.

### US2: Slack chat

A workspace with the Slack adapter selected can post in a channel or send a direct message when outward policy permits. An approval-tier post yields the text for owner delivery and never sends it.

### US3: Greptile review bot

A workspace with the Greptile adapter selected can read a PR score and unresolved findings. Missing or incomplete review evidence is unmeasured.

## Acceptance scenarios

1. Given recorded HTTP responses for each adapter, replayed with patched `urllib.request.urlopen`, every port operation returns a plain `Result` without network access.
2. Given a removed or unselected adapter, the `none` implementation returns exit 2 where a measurement was expected.
3. Given absent credentials, timeout, non-2xx response, malformed data or a provider error body, the operation returns exit 2 with a redacted reason.
4. Given an approval-tier Slack post, no HTTP send occurs and the text is returned with exit 1 for owner delivery.
5. Given an auto-send Slack post and configured identity, the request uses a token from the process environment and never from config.

## Requirements

- Preserve registry signatures and three-state results.
- Runtime dependencies are Python standard library only.
- Every HTTP request has a timeout. Error bodies and credentials are not logged.
- Config holds only the Slack identity choice, never a credential.

## Assumptions

- The workspace environment file is loaded by the launcher into the process environment before an adapter call. Adapters only read `os.environ`.
- Linear `claim` uses the API key's identity and `issueUpdate` to set assignee; `transition` accepts a Linear state ID.
- Slack `dm` takes a Slack conversation ID. Opening a DM by user ID would require a second write-like API call and is left to a caller.
- Greptile's documented MCP HTTP endpoint is the available read surface. A PR is `owner/repo#number`; the repository default branch is supplied by the workspace repo register.
- A Greptile confidence score is read from the completed review summary. If it cannot be established, score is unmeasured.

## Deferred

- Outbound tier classification is owned by issue #95. This adapter honors the existing outward policy and draft result.
- Owner delivery through cockpit or phone is owned by later control-plane work.
