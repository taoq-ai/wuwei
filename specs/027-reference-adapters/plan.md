# Implementation plan

Use existing ports in `cli/wuwei/registry.py`, `Result`, `outward_operation` and `none` adapters. Add one module for each provider and one private shared urllib helper for bounded JSON requests and redacted errors. Add `chat.identity` to validated config with `connector` as default. Replay sanitized HTTP JSON fixtures in-process by patching `urllib.request.urlopen`; assert request bodies, headers, timeout, results and failures. No runtime dependencies or external execution.

Linear uses GraphQL with one mutation per write. Slack uses Web API JSON requests and returns draft text for approval-tier posts. Greptile uses its documented MCP HTTP tools for read-only review evidence. If a provider schema or authorization is unavailable, return exit 2.
