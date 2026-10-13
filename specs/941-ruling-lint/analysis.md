# Specification Analysis Report: 941-ruling-lint

| ID | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| A1 | HIGH | Broad matching rejects item IDs before writing a brief. | FR-001 and field-case test cover the shared extractor. |
| A2 | MEDIUM | Broad suppression could hide genuine rulings. | FR-002 retains the existing standalone ruling test. |
| A3 | MEDIUM | An unreadable body file and an absent file have different remedies. | FR-003 applies only when the file does not exist. |
| A4 | LOW | A long file name can raise before the read handler and expose a path. | The existence check is inside the handler; the 300-character test checks refusal text. |

CRITICAL 0 open, HIGH 0 open. Requirements map to T001 through T004; A4 maps to T006.
