# Research

Decision: reuse the existing typed launch reservation and stop paths.
Rationale: retaining the WUWEI role makes capacity, gate readiness and report
recovery work without another seat lifecycle. Prompt SHA-256 already binds
legacy ad-hoc traces. Extend that binding instead of inventing another key.
Alternatives: enabling the permissive legacy fallback loses guard checks and
recovery; generating a full brief adds discovery and evidence work unrelated
to an ad-hoc prompt. Neither is appropriate.
