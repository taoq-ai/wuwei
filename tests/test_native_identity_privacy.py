import json

import pytest

from conftest import verdict_text
from test_native_evidence import native, report
from wuwei import guards, hook, ws


@pytest.mark.parametrize('shape', ['token', 'canary'])
def test_native_task_identity_redacts_known_secret_shapes(root, native, shape):
    payload, parent, child, save = native
    secret = 'ghp_'+'a'*36 if shape == 'token' else 'wuweicanaryidentity'
    if shape == 'canary':
        (root/'.wuwei/canary').write_text(secret)
    else:
        assert guards.SECRETS.search(secret)
    task = '/root/'+secret
    child[0]['payload']['agent_path'] = task
    args = json.loads(parent[1]['payload']['arguments'])
    args['task_name'] = secret
    parent[1]['payload']['arguments'] = json.dumps(args)
    parent[2]['payload']['output'] = json.dumps({'task_name':task})
    path = root/'.wuwei/verdicts/I-1/security.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text().replace('Gate: quality', 'Gate: security'))
    report(native, 'Verdict file: .wuwei/verdicts/I-1/security.md', 'sentinel-security')
    args = json.loads(parent[1]['payload']['arguments'])
    args['task_name'] = secret
    parent[1]['payload']['arguments'] = json.dumps(args)
    save()
    # A synthetic function call in the archived tree, with only fixture roots.
    hook.subagent_stop(root, payload)
    rows = [*ws.rows(root,'seat.stopped'), *ws.rows(root,'attest')]
    assert {r['kind'] for r in rows} == {'seat.stopped','attest'}
    leaked = [r['kind'] for r in rows if secret in r['data']['agent']]
    assert not leaked, f'{shape} found raw in agent fields: {leaked}'


@pytest.mark.parametrize('shape', ['token', 'canary', 'ordinary'])
def test_native_identity_is_stable_distinct_and_matches_start_stop_consumers(root, native, shape):
    from pathlib import Path
    from wuwei import board
    payload, parent, child, save = native
    canary = 'wuweicanaryidentity'
    if shape == 'canary': (root/'.wuwei/canary').write_text(canary)
    names = ['ghp_'+'a'*36, 'ghp_'+'b'*36] if shape == 'token' else [canary+'_one',canary+'_two'] if shape == 'canary' else ['ordinary_one','ordinary_two']
    base_call, base_output = json.loads(json.dumps(parent[1])),json.loads(json.dumps(parent[2]))
    children=[]
    parent[:] = parent[:1]
    for i,name in enumerate(names):
        task='/root/'+name
        call=json.loads(json.dumps(base_call)); output=json.loads(json.dumps(base_output))
        call['ordinal']=86+i*10; output['ordinal']=89+i*10
        call['payload']['call_id']=output['payload']['call_id']='call-'+str(i)
        call['payload']['arguments']=json.dumps({'task_name':name,'agent_type':'builder'})
        output['payload']['output']=json.dumps({'task_name':task})
        parent.extend([call,output])
        rows=json.loads(json.dumps(child)); rows[0]['payload'].update(agent_path=task,id='native-'+str(i))
        rows[1]['payload']['content'][0]['text']=rows[2]['payload']['last_agent_message']='REPORT '+str(i)
        path=Path(payload['agent_transcript_path']).with_name('child-'+str(i)+'.jsonl')
        path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
        children.append({**payload,'agent_id':'native-'+str(i),'agent_transcript_path':str(path),'last_assistant_message':'REPORT '+str(i)})
        hook.handle(root,'PostToolUse',{'tool_name':'collaborationspawn_agent','session_id':'id-1',
            'tool_input':{'agent_type':'builder','task_name':name,'message':'Item: I-1'},'tool_response':json.dumps({'task_name':task})})
    save()
    started=[r['data']['agent'] for r in ws.rows(root,'seat.started')]
    assert len(started)==len(set(started))==2
    assert {r['agent'] for r in board.running(root)}==set(started)
    if shape=='ordinary': assert started==['/root/'+n for n in names]
    else: assert all(not any(n in key for n in names) for key in started)
    hook.handle(root,'SubagentStop',children[0])
    assert [r['agent'] for r in board.running(root)]==[started[1]]
    hook.handle(root,'SubagentStop',children[1])
    assert board.running(root)==[]
    assert [r['data']['agent'] for r in ws.rows(root,'seat.stopped')]==started
    pending=root/'.wuwei/reports/pending'
    assert len(list(pending.glob('*.md')))==2
    assert len({p.name.split('--')[1] for p in pending.glob('*.md')})==2
    if shape!='ordinary':
        encoded=json.dumps(ws.ledger(root))
        assert all(n not in encoded for n in names)
    # The native notification uses the raw canonical sender; the kept filename uses the stable key's hash.
    for i,name in enumerate(names):
        parent.append({'type':'response_item','ordinal':200+i,'timestamp':'2099-01-01T00:00:00+00:00','payload':{
            'type':'agent_message','author':'/root/'+name,'recipient':'/root','content':[{'type':'input_text',
            'text':'Message Type: FINAL_ANSWER\nTask name: /root\nSender: /root/'+name+'\nPayload:\nREPORT '+str(i)}]}})
    save()
    assert hook.deliver(root,'Stop',{'session_id':'id-1','transcript_path':payload['transcript_path']},None,[]) is None
    out=hook.deliver(root,'PreToolUse',{'session_id':'id-1','transcript_path':payload['transcript_path']},None,[])
    note=out['hookSpecificOutput']['additionalContext']
    assert note.count('report already notified')==2 and '\nREPORT ' not in note


@pytest.mark.parametrize('shape', ['token', 'canary'])
def test_rejected_native_proof_keeps_unconfirmed_identity_private(root, native, shape):
    payload, parent, child, save = native
    secret = 'ghp_'+'a'*36 if shape == 'token' else 'wuweicanaryidentity'
    if shape == 'canary': (root/'.wuwei/canary').write_text(secret)
    task = '/root/'+secret
    child[0]['payload'].update(agent_path=task, parent_thread_id='mismatched-parent')
    args = json.loads(parent[1]['payload']['arguments'])
    parent[1]['payload']['arguments'] = json.dumps({**args, 'task_name':secret})
    parent[2]['payload']['output'] = json.dumps({'task_name':task})
    payload['agent_id'] = task
    save()
    hook.handle(root, 'SubagentStop', payload)
    [row] = ws.rows(root, 'seat.unconfirmed')
    assert row['data']['agent'].startswith('sha256-')
    assert secret not in json.dumps(row)
    assert not ws.rows(root, 'seat.stopped') and not ws.rows(root, 'attest')
