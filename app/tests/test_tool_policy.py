import json
import tomllib
from pathlib import Path

from execution.tool_policy import evaluate, scope_path
from flow.codex_llm import _config


def test_native_policy_selects_fresh_role_and_denies_scope_escalation():
    scopes = {'reader': {'tools': ['read'], 'token': 'scoped'}}
    spawn = evaluate({'tool_name': 'collaborationspawn_agent', 'tool_input': {'task_name': 'reader__audit', 'fork_turns': 'all'}}, scopes)['hookSpecificOutput']
    assert spawn['updatedInput']['agent_type'] == 'reader'
    assert spawn['updatedInput']['fork_turns'] == 'none'
    event = {'agent_id': 'child', 'agent_type': 'reader', 'tool_name': 'mcp__if_tools__read', 'tool_input': {'query': 'x', '__if_scope': {'role': 'coordinator'}}}
    allowed = evaluate(event, scopes)['hookSpecificOutput']
    assert allowed['updatedInput']['__if_scope'] == {'role': 'reader', 'token': 'scoped'}
    for tool in ['mcp__if_tools__write', 'Bash', 'apply_patch', 'collaborationspawn_agent']:
        assert evaluate({**event, 'tool_name': tool}, scopes)['hookSpecificOutput']['permissionDecision'] == 'deny'
    assert evaluate({**event, 'agent_type': None}, scopes)['hookSpecificOutput']['permissionDecision'] == 'deny'


def test_sdk_trust_path_and_environment_overrides(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'must-not-reach-worker')
    monkeypatch.setenv('INTERNAL_API_TOKEN', 'must-not-reach-worker')
    config = _config(cwd='/tmp/worker.with.dots')
    assert config.env['OPENAI_API_KEY'] == config.env['INTERNAL_API_TOKEN'] == ''
    projects = next(override for override in config.config_overrides if override.startswith('projects='))
    assert tomllib.loads(projects)['projects']['/tmp/worker.with.dots']['trust_level'] == 'trusted'


def test_scope_path_is_outside_the_writable_workspace():
    assert scope_path('/work/job') == Path('/work/job.scopes.json')


def test_delegation_rejects_unavailable_models_and_efforts():
    scopes = {'reader': {'tools': [], 'token': 'scope'}, '_models': {'gpt-5.6-luna': ['medium']}}
    event = {'tool_name': 'spawn_agent', 'tool_input': {'task_name': 'reader', 'model': 'missing'}}
    assert evaluate(event, scopes)['hookSpecificOutput']['permissionDecision'] == 'deny'
    event['tool_input'].update(model='gpt-5.6-luna', reasoning_effort='ultra')
    assert evaluate(event, scopes)['hookSpecificOutput']['permissionDecision'] == 'deny'
    event['tool_input']['reasoning_effort'] = 'medium'
    assert evaluate(event, scopes)['hookSpecificOutput']['permissionDecision'] == 'allow'
