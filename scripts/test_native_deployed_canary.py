import json, os, sys, time, uuid
from pathlib import Path
import httpx

phase = sys.argv[1] if len(sys.argv) > 1 else 'basic'
state_path = Path('/tmp/if-native-live-' + phase + '.json') if phase in {'report', 'import'} else Path('/tmp/if-native-live-evidence.json')
owner = 'native-deployed-canary'
headers = {'X-Internal-Token': os.environ['INTERNAL_API_TOKEN'], 'X-Person-Pk': owner, 'X-Athlete-Pk': owner}
client = httpx.Client(base_url='http://127.0.0.1:8000', headers=headers, timeout=45)
terminal = {'succeeded','failed','cancelled','uncertain'}
evidence = json.loads(state_path.read_text()) if state_path.exists() else {'checks': {}, 'jobs': {}}

def mark(name, **data):
    evidence['checks'][name] = data or True
    state_path.write_text(json.dumps(evidence, indent=2))
    print(json.dumps({'check': name, **data}), flush=True)

def submit(conversation, content, key=None):
    body = {'messages': [{'role': 'user', 'content': content}], 'idempotency_key': key or uuid.uuid4().hex}
    response = client.post(f'/v1/conversations/{conversation}/turns', json=body)
    response.raise_for_status()
    job = response.json()
    evidence['jobs'][job['job_id']] = {'conversation': conversation, 'thread_id': job.get('thread_id'), 'turn_id': job.get('turn_id')}
    state_path.write_text(json.dumps(evidence, indent=2))
    return job

def wait(job, running=False, timeout=240):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get('/v1/jobs/' + job['job_id'])
        response.raise_for_status()
        current = response.json()
        if current['status'] in terminal or (running and current['status']=='running'):
            evidence['jobs'].setdefault(current['job_id'], {}).update({k: current.get(k) for k in ('status','thread_id','turn_id','error')})
            state_path.write_text(json.dumps(evidence, indent=2))
            return current
        time.sleep(.5)
    raise TimeoutError(job['job_id'])

def success(job):
    result = wait(job)
    assert result['status'] == 'succeeded', {k: result.get(k) for k in ('job_id','status','error')}
    return result

if phase == 'basic':
    key = uuid.uuid4().hex
    first = submit('live-marker', 'Hello. Remember the exact marker COBALT_NATIVE_LIVE. Reply with a short greeting.', key)
    duplicate = submit('live-marker', 'Hello. Remember the exact marker COBALT_NATIVE_LIVE. Reply with a short greeting.', key)
    assert first['job_id'] == duplicate['job_id']
    first = success(first)
    second = success(submit('live-marker', 'What exact marker did I ask you to remember?'))
    assert first['thread_id'] == second['thread_id'] and 'COBALT_NATIVE_LIVE' in second['result']['content']
    evidence['marker_thread'] = first['thread_id']
    mark('thread_reuse_and_dedup')
    a = submit('live-concurrent-a', 'Write twelve short paragraphs about prime numbers, starting with ALPHA.')
    b = submit('live-concurrent-b', 'Write twelve short paragraphs about triangles, starting with BETA.')
    rejected = client.post('/v1/conversations/live-capacity/turns', json={'messages':[{'role':'user','content':'Busy check.'}]})
    assert rejected.status_code == 429, (rejected.status_code,rejected.text)
    assert client.get('/v1/jobs/'+a['job_id']).is_success
    current_a, current_b = success(a), success(b)
    assert current_a['thread_id'] != current_b['thread_id']
    mark('concurrency_capacity_status')
    wrong = client.get('/v1/jobs/'+first['job_id'], headers={'X-Person-Pk':'different-canary'})
    assert wrong.status_code in {403,404}
    invalid = httpx.get('http://127.0.0.1:8000/v1/conversations/live-marker/turns')
    assert invalid.status_code == 401
    mark('person_and_token_authorization')
    delegated = success(submit('live-delegation', 'Delegate two independent tasks to fresh native Specialists: summarizer using gpt-5.6-luna at medium reasoning returns LUNA; code_reviewer using gpt-5.6-terra at medium reasoning returns TERRA. Wait for both and report their answers.'))
    events = client.get('/v1/jobs/'+delegated['job_id']+'/events').text
    assert 'delegation' in events and 'LUNA' in delegated['result']['content'] and 'TERRA' in delegated['result']['content']
    mark('native_specialists')
    calculation = success(submit('live-calculation','Call the scoped kg_to_lb tool for 100 kg and return the numeric result.'))
    assert '220' in calculation['result']['content']
    mark('scoped_calculation')
    steering = submit('live-steering','Write a careful explanation of prime numbers, with a proof and examples.')
    assert wait(steering,running=True)['status']=='running'
    edited = submit('live-steering','Correction: end your answer with STEERING_NATIVE_LIVE.')
    assert edited['job_id'] == steering['job_id']
    steered = success(edited)
    assert 'STEERING_NATIVE_LIVE' in steered['result']['content']
    mark('native_steering')
    cancel = submit('live-cancel','Explain the history of mathematics in thirty detailed sections.')
    assert wait(cancel,running=True)['status']=='running'
    response = client.post('/v1/conversations/live-cancel/turns/'+cancel['job_id']+'/cancel')
    response.raise_for_status()
    assert wait(cancel)['status'] in {'cancelled','uncertain'}
    mark('native_cancellation')
    with client.stream('POST','/v1/chat/completions',json={'model':'gpt-5.6-sol','stream':True,'messages':[{'role':'user','content':'Reply STREAM_NATIVE_OK only.'}]}) as stream:
        stream.raise_for_status()
        chunks='\n'.join(stream.iter_lines())
        assert 'STREAM_NATIVE_OK' in chunks and '[DONE]' in chunks, chunks[-500:]
    mark('chat_completions_sse')
elif phase == 'report':
    sessions = [{'date':f'2026-08-{3+i*7:02d}','week_number':i+1,'block':'current','completed':True,'exercises':[{'name':'Squat','sets':3,'reps':5,'kg':100+i*2.5,'rpe':8},{'name':'Leg press','sets':3,'reps':10,'kg':80+i*5}]} for i in range(4)]
    args = {'program':{'meta':{'name':'Synthetic deployed native canary'},'sessions':sessions,'lift_profiles':[]},'sessions':sessions,'weeks':4,'window_start':'2026-08-03','pk':owner}
    domain = httpx.Client(base_url='http://pl-analytics:8000',headers=headers,timeout=45)
    started = time.monotonic()
    response = domain.post('/operations/block_correlation_analysis',json=args)
    response.raise_for_status()
    report = response.json()
    assert 'generation_id' in report,report
    assert time.monotonic()-started < 20
    duplicate = domain.post('/operations/block_correlation_analysis',json=args)
    duplicate.raise_for_status()
    assert duplicate.json()['generation_id']==report['generation_id']
    completed = success(report)
    saved = domain.get('/generations/'+report['generation_id'])
    saved.raise_for_status()
    saved = saved.json()
    assert saved['status']=='succeeded' and saved['result'].get('summary') and not saved['result'].get('insufficient_data'),saved
    cached = domain.post('/operations/block_correlation_analysis',json=args)
    cached.raise_for_status()
    assert cached.json().get('cached') is True
    mark('deployed_report_generation_cache',generation_id=report['generation_id'],job_id=report['job_id'])
elif phase == 'import':
    import base64
    domain = httpx.Client(base_url='http://pl-imports:8000',headers=headers,timeout=45)
    csv = 'week,day,exercise,sets,reps,percentage,rpe\n1,1,Squat,3,5,75,8\n1,1,Bench Press,3,5,70,8\n2,1,Squat,3,5,77.5,8\n2,1,Bench Press,3,5,72.5,8\n'
    response = domain.post('/operations/import_parse_file',json={'pk':owner,'filename':'native-deployed-template.csv','base64_content':base64.b64encode(csv.encode()).decode()})
    response.raise_for_status()
    job=success(response.json())
    parsed=job['result']['domain_result']
    assert parsed['classification']=='template',parsed
    pending=domain.post('/operations/import_get_pending',json={'pk':owner,'import_id':parsed['import_id']})
    pending.raise_for_status()
    assert pending.json()['status']=='awaiting_review' and pending.json()['ai_parse_result']['sessions']
    applied=domain.post('/operations/import_apply',json={'pk':owner,'import_id':parsed['import_id'],'classification_override':'template','author':'Native deployment canary'})
    applied.raise_for_status()
    assert applied.json()['status']=='applied' and applied.json()['target_sk']
    replay=domain.post('/operations/import_apply',json={'pk':owner,'import_id':parsed['import_id']})
    assert replay.status_code >= 400
    mark('template_import_review_apply',job_id=job['job_id'],import_id=parsed['import_id'],target_sk=applied.json()['target_sk'])
elif phase == 'restart_start':
    job=submit('live-restart','Explain the history of mathematics in fifty detailed sections.')
    assert wait(job,running=True)['status']=='running'
    evidence['restart_job']=job['job_id']
    mark('restart_inflight_started',job_id=job['job_id'])
elif phase == 'restart_check':
    job=wait({'job_id':evidence['restart_job']})
    assert job['status'] in {'uncertain','succeeded'},job['status']
    resumed=success(submit('live-marker','What exact marker did I ask you to remember?'))
    assert resumed['thread_id']==evidence['marker_thread'] and 'COBALT_NATIVE_LIVE' in resumed['result']['content']
    mark('actual_host_pod_restart',interrupted_status=job['status'],same_thread=True)
else:
    raise ValueError(phase)
