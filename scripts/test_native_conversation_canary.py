import argparse
import asyncio
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app/src'))
sys.path.insert(0, str(ROOT / 'utils/powerlifting-app'))


async def run(directory, extended=False):
    import httpx
    import uvicorn
    from fastapi import FastAPI, Header, HTTPException
    from execution.host import ConversationHost, create_app
    from execution.service import ExecutionService
    from execution.store import JobStore, TERMINAL
    from execution.schemas import JobRequest
    from api import jobs, job_tools
    from storage.factory import init_directive_store
    init_directive_store()
    from services import execution as domain_execution
    from services.contract import load_operations
    from services.dispatch import authorize, dispatch

    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    auth_home = directory / 'codex'
    auth_home.mkdir(exist_ok=True, mode=0o700)
    source_auth = Path(os.getenv('CODEX_HOME', str(Path.home() / '.codex'))) / 'auth.json'
    shutil.copy2(source_auth, auth_home / 'auth.json')
    (auth_home / 'auth.json').chmod(0o600)
    token = uuid.uuid4().hex
    os.environ.update(INTERNAL_API_TOKEN=token, IF_API_URL='http://127.0.0.1:18800', IF_CODEX_HOST_URL='http://127.0.0.1:18801',
        CODEX_HOME=str(auth_home), IF_ARTIFACT_DIR=str(directory / 'artifacts'), PL_SERVICE_URL_TEMPLATE='http://127.0.0.1:18802/{domain}')
    host = ConversationHost(directory / 'host')
    service = ExecutionService(JobStore(str(directory / 'legacy.sqlite3')))
    jobs.get_execution_service = lambda: service
    job_tools.get_execution_service = lambda: service
    operations = load_operations()
    original_schemas = job_tools.schemas
    def schemas(role):
        names = ['kg_to_lb'] if role in {'coordinator', 'summarizer'} else []
        if role in {'coordinator', 'powerlifting_coach'}:
            names.append('block_correlation_analysis')
        result = {name: {'name': name, 'description': operations[name].description, 'inputSchema': operations[name].input_schema} for name in names}
        if role in {'coordinator', 'powerlifting_coach'}:
            result['domain_resume'] = {'name': 'domain_resume', 'description': 'Return a native child answer to the existing domain continuation', 'inputSchema': {'type': 'object', 'properties': {'domain': {'type': 'string'}, 'execution_id': {'type': 'string'}, 'challenge_id': {'type': 'string'}, 'content': {}}, 'required': ['domain', 'execution_id']}}
        return result
    job_tools.schemas = schemas
    api = FastAPI()
    api.include_router(jobs.router)
    api.include_router(jobs.turn_router)
    api.include_router(job_tools.router)
    domains = FastAPI()
    @domains.post('/{domain}/operations/{name}')
    async def operation(domain: str, name: str, arguments: dict, x_internal_token: str = Header(default=''), x_athlete_pk: str = Header(default=''), x_person_pk: str = Header(default=''), x_if_turn_id: str = Header(default=''), x_if_generation_id: str = Header(default=''), x_if_generation_attempt: int = Header(default=0)):
        if x_internal_token != token:
            raise HTTPException(401)
        operation = operations[name]
        arguments = authorize(operation, arguments, x_athlete_pk, x_person_pk)
        operation.validate_input(arguments)
        if x_if_turn_id:
            if x_if_generation_id:
                arguments['_generation_id'] = x_if_generation_id
                arguments['_generation_attempt'] = x_if_generation_attempt
            return await domain_execution.start(operation, arguments, x_athlete_pk, x_if_turn_id)
        return await domain_execution.submit(operation, arguments, x_athlete_pk, x_person_pk)
    @domains.post('/{domain}/executions/{execution_id}')
    async def resume(domain: str, execution_id: str, arguments: dict, x_if_turn_id: str = Header(default=''), x_athlete_pk: str = Header(default=''), x_internal_token: str = Header(default='')):
        if x_internal_token != token:
            raise HTTPException(401)
        return await domain_execution.resume(execution_id, x_if_turn_id, x_athlete_pk, arguments.get('challenge_id'), arguments.get('content'))
    servers = [uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error')) for app, port in ((api, 18800), (create_app(host), 18801), (domains, 18802))]
    tasks = [asyncio.create_task(server.serve()) for server in servers]
    try:
        while not all(server.started for server in servers):
            await asyncio.sleep(.1)
        async def submit(conversation, text):
            job = await service.submit('native-canary', JobRequest(conversation_id=conversation, kind='conversation', idempotency_key=uuid.uuid4().hex, payload={'messages': [{'role': 'user', 'content': text}]}))
            result = await asyncio.wait_for(service.wait(job), 180)
            print(json.dumps({'check': conversation, 'thread_id': result['thread_id'], 'turn_id': result['turn_id'], 'content': result['content']}), flush=True)
            return result
        if not extended:
            first = await submit('greeting', 'Hello. Remember the marker cobalt-seven. Reply with a short greeting.')
            followup = await submit('greeting', 'What marker did I ask you to remember?')
            assert first['thread_id'] == followup['thread_id'] and 'cobalt-seven' in followup['content'].lower()
            concurrent = await asyncio.gather(submit('independent-a', 'Reply with ALPHA only.'), submit('independent-b', 'Reply with BETA only.'))
            assert concurrent[0]['thread_id'] != concurrent[1]['thread_id']
            delegated = await submit('delegation', 'Delegate two independent tasks to fresh native Specialists: summarizer using gpt-5.6-luna at medium reasoning should return LUNA; code_reviewer using gpt-5.6-terra at medium reasoning should return TERRA. Wait for both and report their answers.')
            delegated_events = await service.events(delegated['job_id'], 'native-canary')
            assert any(event.event == 'delegation' for event in delegated_events)
            scoped = await submit('scoped-tool', 'Call the scoped kg_to_lb tool for 100 kg and return the numeric result.')
            assert '220' in scoped['content']
            evidence = {'thread_reuse': True, 'independent_threads': True, 'concurrent': True, 'native_delegation': True, 'scoped_deterministic_tool': True,
                        'results': [first, followup, *concurrent, delegated, scoped]}
            (directory / 'evidence.json').write_text(json.dumps(evidence, indent=2))
        else:
            from services.generations import GenerationStore, status as generation_status
            from execution.native import recover
            sessions = [{'date': f'2026-08-{3 + i * 7:02d}', 'week_number': i + 1, 'block': 'current', 'completed': True,
                         'exercises': [{'name': 'Squat', 'sets': 3, 'reps': 5, 'kg': 100 + i * 2.5, 'rpe': 8}, {'name': 'Leg press', 'sets': 3, 'reps': 10, 'kg': 80 + i * 5}]} for i in range(4)]
            arguments = {'program': {'meta': {'name': 'Synthetic native canary ' + directory.name}, 'sessions': sessions, 'lift_profiles': []}, 'sessions': sessions, 'weeks': 4, 'window_start': '2026-08-03', 'pk': 'native-canary'}
            report = await domain_execution.submit(operations['block_correlation_analysis'], arguments, 'native-canary', 'native-canary')
            duplicate = await domain_execution.submit(operations['block_correlation_analysis'], arguments, 'native-canary', 'native-canary')
            assert report['generation_id'] == duplicate['generation_id'] and report['job_id'] == duplicate['job_id']
            job = await service.get(report['job_id'], 'native-canary')
            completed = await asyncio.wait_for(service.wait(job), 240)
            saved = await generation_status(report['generation_id'], 'native-canary')
            assert saved['status'] == 'succeeded' and saved['result'].get('summary') and not saved['result'].get('insufficient_data')
            cached = await domain_execution.submit(operations['block_correlation_analysis'], arguments, 'native-canary', 'native-canary')
            assert cached['cached'] is True
            report_events = await service.events(job.job_id, 'native-canary')
            assert any(event.event == 'delegation' for event in report_events)
            print(json.dumps({'check': 'report', 'generation_id': report['generation_id'], 'summary': saved['result']['summary']}), flush=True)
            recovered = await recover(await service.get(job.job_id, 'native-canary'), host.workspace('native-canary', job.request.conversation_id))
            assert recovered and recovered['recovered']
            start = await service.submit('native-canary', JobRequest(conversation_id='steering', idempotency_key=uuid.uuid4().hex, payload={'messages': [{'role': 'user', 'content': 'Write a careful explanation of prime numbers, including an example proof and several examples.'}]}))
            await asyncio.wait_for(host.ready[start.job_id].wait(), 45)
            edited = await service.submit('native-canary', JobRequest(conversation_id='steering', idempotency_key=uuid.uuid4().hex, payload={'messages': [{'role': 'user', 'content': 'Correction: end your answer with STEERING_CONFIRMED.'}]}))
            assert edited.turn_id == host.store.get(start.job_id).turn_id
            steered = await asyncio.wait_for(service.wait(edited), 180)
            assert 'STEERING_CONFIRMED' in steered['content']
            cancelled = await service.submit('native-canary', JobRequest(conversation_id='cancel', idempotency_key=uuid.uuid4().hex, payload={'messages': [{'role': 'user', 'content': 'Explain the history of mathematics in 30 detailed sections.'}]}))
            await asyncio.wait_for(host.ready[cancelled.job_id].wait(), 45)
            cancel_task = host.tasks[cancelled.job_id]
            await service.cancel(cancelled.job_id, 'native-canary')
            await asyncio.wait_for(cancel_task, 45)
            assert (await service.get(cancelled.job_id, 'native-canary')).status == 'uncertain'
            resumed = await submit('steering', 'What exact marker ended your last answer?')
            assert resumed['thread_id'] == steered['thread_id'] and 'STEERING_CONFIRMED' in resumed['content']
            evidence = {'report_generation': report, 'report_cached': True, 'report_native_delegation': True, 'read_only_status': True,
                        'persisted_result_recovery': True, 'steering': True, 'cancellation': True, 'sdk_restart_thread_reuse': True,
                        'results': [completed, steered, resumed]}
            (directory / 'extended-evidence.json').write_text(json.dumps(evidence, indent=2))
    finally:
        await host.close()
        for server in servers:
            server.should_exit = True
        await asyncio.gather(*tasks, return_exceptions=True)
        job_tools.schemas = original_schemas


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--extended', action='store_true')
    args = parser.parse_args()
    asyncio.run(run(args.state_dir, args.extended))
