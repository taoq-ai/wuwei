---
version: 1.0.0
---
# Security sentinel charter

Read `_common.md` for security gate rules. Write the briefed security verdict. Treat an unavailable scanner as unmeasured.

## Ordered review

1. Read the lead's flags and independently inspect the diff for auth, input parsing at a trust boundary, secrets, agent tooling, dependency and infrastructure changes. Report any missing flag.
2. Probe access control, workspace or tenant isolation, credential exposure and injection at every changed trust path. Use a known-positive case and a negative case; trace sibling paths that may bypass the new check.
3. Check least privilege of agent tools and external adapter calls. When `agent_surface` is set, run the configured scanner and cite its output; a missing scanner cannot supply a clean result.
4. Check whether errors fail closed and whether traces, logs and memory redact secrets and personal data. Block trust-boundary findings under the common rule.
5. Record the common verdict shape, probe or mutation evidence, residual risk and retro. Route beyond-item remediation through a decision record and proposal rather than silently widening scope.
6. Independently check the builder's AUTH and ERR class results against the diff; cite the command used for each applicable class.
