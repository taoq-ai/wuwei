# Scanner contract and compatibility

Existing WUWEI ports expose audit(path), gate(result, threshold), traces(file), mcp(servers).
The security gate writer is dispatch.receive; item flags and gate_verdicts are reserved.

The upstream static analyzer has AnalysisReport.files_analyzed/findings and StaticFinding
check_id, severity, file_path, line_number, message, context and recommendation fields.
The available upstream CLI has console-only audit output and campaign-oriented CI with
--gate-config, not the --severity-threshold required by this issue. References:

- https://taoq-ai.github.io/ziran/guides/static-analysis/
- https://taoq-ai.github.io/ziran/guides/cicd-integration/

Implement the issue's adapter contract explicitly: `ziran audit PATH --format json`
returns the AnalysisReport JSON shape. `ziran ci REPORT --severity-threshold LEVEL
--format json` returns `{"passed": true}` or `{"passed": false}`. CI exit 1 is a finding
only with passed=false and findings in the validated input; any other nonzero result
is unmeasured. Audit exit 1 likewise requires valid findings. No console scraping or
conversion to fabricated campaign data. Both commands have a fixed 60-second timeout.

The checked-in audit payload is a contract fixture based on the upstream dataclass
fields, not claimed to be captured from a released JSON CLI. A compatible upstream JSON
CLI release is required for live S4 use; older versions fail closed. No real scanner is
run in tests. This compatibility work is deferred upstream alongside the separately
tracked trace and MCP work, not silently implemented in WUWEI.
