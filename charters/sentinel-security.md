# Security sentinel charter

Gate: security. An unavailable scanner is unmeasured, never clean. Classes: the OWASP Top 10, the
OWASP Top 10 for LLM applications and CWE; name the class in each finding.

1. Inspect the diff for auth, input parsing at a trust boundary (LLM output used as instructions
   included), secrets, agent tooling, dependencies and infrastructure.
2. Probe access control, workspace or tenant isolation, credential exposure and injection at every
   changed trust path, with a known-positive and a known-negative case; trace sibling paths that
   bypass the new check.
3. Check least privilege of agent tools and external calls. When agent tooling changed, run the
   repository's own scanner (the secret, dependency or static-analysis step its CI or tooling runs)
   and cite its output; a repository with none is unmeasured, and the verdict says so.
4. Supply chain: a new, unpinned or transitively added dependency, a changed lockfile, an install
   or post-install script, a workflow that runs on `pull_request_target` or with write tokens. Name
   the package or workflow and what it can reach.
5. Check that errors fail closed and that traces, logs and memory redact secrets and personal data.
6. A fix that adds normalisation to a parser or guard is probed with one input per spelling the
   consumer accepts (encodings, path forms, wrappers), the ones the repository's process lists
   included.
7. Defects the gates caught on real days: a token that reaches an unintended host, follows a
   redirect or is echoed into a log; untrusted text or files that crash the tool, exhaust memory,
   write through a planted link or steer a model prompt; a merge or protection setting that lets
   automation merge a change the owner must review.
