# Research

Decision: Reuse review_contexts without broadening classification. The existing review_gate fixture records 1067-probe's ai-stacks status: target_url points to an Actions pull_request run whose workflow also has pull_request_review runs. gh.pr maps target_url to url before evidence reads it.

The issue's ready-door failure is not reproduced by this fixture: ready_door already reads evidence.gaps, which excludes recognized review statuses from CI. Preserve that regression coverage. The auto-merge failure reproduces because AUTO excludes waiting on review.

A readonly gh lookup of taoq-ai/ai-stacks failed because the repository was not accessible. No new production URL/status shape was inferred. Context-name classification was rejected.

Decision: Classifier errors propagate as unreadable evidence. Returning an empty set currently converts failed reads to ordinary running CI, which auto-merge permits. Absence of matching review workflows still returns an empty set and remains CI.
