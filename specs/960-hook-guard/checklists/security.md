# Security requirements review

Reviewer-owned requirements checklist. Scope: issue #960 and its allowed fallback.

- [ ] CHK001 Are both field reproductions and every requested wrapper covered? [FR-001]
- [ ] CHK002 Is the narrow unparsed exception distinguished from ordinary calls? [FR-002, FR-003]
- [ ] CHK003 Are parsed text and option-value boundaries explicit? [Edge Cases]
- [ ] CHK004 Is the caller-authentication limitation and permitted fallback explicit? [FR-004, Assumptions]
- [ ] CHK005 Are legitimate hook replay and existing guard scope preserved? [FR-004, Plan]
- [ ] CHK006 Are offline verification and no new owner workflow constraints explicit? [FR-005, Plan]
- [ ] CHK007 Are variable/event and arbitrary-program literal hook/event boundaries explicit? [FR-006, Assumptions]
- [ ] CHK008 Are word normalization, launcher case, Python clusters and inline-code scope specified? [FR-006, FR-007]
- [ ] CHK009 Are every ordinary harness row and the runtime/script limit covered by requirements? [FR-003, FR-007, Assumptions]
