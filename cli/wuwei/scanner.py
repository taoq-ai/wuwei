"""Mandatory S4 measurement and verdict rows at the security receive boundary."""

import re

from wuwei import redact, registry, security, state, workspace


# Static checks for secrets, unvalidated input, execution and data exposure.
TRUST_RULES = {'SA001', 'SA002', 'SA003', 'SA007', 'SA008', 'SA009', 'SA010'}


def rows(tree, item, flags, config, root):
    if workspace.guard_scope({'cwd': str(tree)}) != root:
        raise OSError('scanner: unmeasured: reviewed worktree is outside the workspace')
    scanner = registry.load('scanner', config)
    audit = scanner.audit(str(tree), root=root)
    if audit.exit not in (0, 1):
        raise OSError('scanner: unmeasured: ' + audit.reason)
    threshold = config['scanner']['severity_threshold']
    gate = scanner.gate(audit.data, threshold, root=root)
    if gate.exit not in (0, 1):
        raise OSError('scanner: unmeasured: ' + gate.reason)
    levels = ('critical', 'high', 'medium', 'low')
    markers = security.load(root)
    result = []
    for finding in audit.data['findings']:
        try:
            source = (tree / finding['file_path']).resolve(strict=True)
            location = source.relative_to(tree.resolve())
            with source.open(encoding='utf-8') as stream:
                stream.read()
        except (OSError, ValueError):
            raise OSError('scanner: unmeasured: finding source is unreadable or outside worktree') from None
        blocks = (flags['trust_surface'] or flags['boundary_relevant']
                  or finding.get('trust_boundary', False)
                  or finding['check_id'] in TRUST_RULES
                  or levels.index(finding['severity']) <= levels.index(threshold))
        rule, location, message = redact.redact(security.redact(
            [finding['check_id'], str(location), finding['message']], markers))
        message = re.sub(r'[^a-zA-Z0-9 .,:()/=_-]', ' ', message)
        result.append(f"- {finding['severity']} | {location}:{finding['line_number']} | "
                      f"ZIRAN {rule} scenario: {message} | "
                      f"blocks: {'yes' if blocks else 'no'}")
        state.append_event('scanner.finding', {
            'source': 'ziran', 'item': item, 'rule': rule,
            'severity': finding['severity'], 'blocks': blocks,
        }, root)
    return result


def merge(text, findings):
    if not findings:
        return text
    if any(finding.endswith('blocks: yes') for finding in findings):
        text = re.sub(r'^(?:## |- )?Verdict:? *PASS\b', 'Verdict: FIX', text, flags=re.M)
    return text + '\n\n## ZIRAN findings\n' + '\n'.join(findings) + '\nProbe: ziran audit and ci\n'
