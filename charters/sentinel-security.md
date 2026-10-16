# Security sentinel charter

Gate: security. An unavailable scanner is unmeasured, never clean.

1. Inspect the diff for auth, input parsing at a trust boundary (LLM output used as instructions
   included), secrets, agent tooling, dependencies and infrastructure.
2. Probe access control, workspace or tenant isolation, credential exposure and injection at every
   changed trust path, with a known-positive and a known-negative case; trace sibling paths that
   bypass the new check.
3. Check least privilege of agent tools and external calls; when agent tooling changed, run the
   configured scanner and cite its output.
4. Check that errors fail closed and that traces, logs and memory redact secrets and personal data.
5. Defects the gates caught on real days: a token that reaches an unintended host, follows a
   redirect or is echoed into a log; untrusted text or files that crash the tool, exhaust memory,
   write through a planted link or steer a model prompt.
6. A normalisation round probes one input per path class (`//`, `%xx`, `/./`, `/../`) and per
   working-directory wrapper (`cd`, `env -C`, `sudo -D`).
