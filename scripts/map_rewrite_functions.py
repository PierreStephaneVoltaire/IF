import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PL = 'utils/powerlifting-app/lambda/'
cache = {}


def functions(path):
    if path not in cache:
        try:
            cache[path] = {node.name: node.lineno for node in ast.walk(ast.parse((ROOT / path).read_text())) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        except FileNotFoundError:
            cache[path] = {}
    return cache[path]


def target(path, name):
    assert name in functions(path), (path, name)
    return {'path': path, 'function': name, 'line': functions(path)[name]}


def replacement(row):
    path, name = row['path'], row['function']
    if name in functions(path):
        return {'kind': 'retained', 'targets': [target(path, name)]}
    if path == 'app/src/channels/channel_coordinator.py':
        return {'kind': 'replaced', 'targets': [target(path, 'handle_discord_event'), target(path, 'recover_deliveries')], 'detail': 'Discord inputs submit or steer native Conversations directly; durable delivery recovers completed turns.'}
    if path == 'app/src/channels/listeners/discord_listener.py':
        return {'kind': 'merged_duplicate', 'targets': [target(path, '_start_runtime'), target(path, 'create_discord_listener')], 'detail': 'Per-channel clients share one restartable gateway per bot token; channel-specific records retain routing.'}
    if '/pod_import/' in path:
        active = path.replace('/pod_import/', '/pod_imports/')
        if name in functions(active):
            return {'kind': 'merged_duplicate', 'targets': [target(active, name)]}
        return {'kind': 'replaced', 'targets': [target(PL + 'pod_imports/handlers/import_parse_file/core.py', 'import_parse_file'), target(PL + 'pod_imports/handlers/import_apply/core.py', 'import_apply')], 'detail': 'Inactive compatibility package merged into the registered Imports handlers; staged review and explicit apply remain.'}
    if path == 'tools/health_lambda_mcp/server.py' or path.startswith(PL + 'fission') or path == PL + 'tool_registry/handler.py':
        return {'kind': 'retired', 'targets': [target('utils/powerlifting-app/services/app.py', 'operation'), target('utils/powerlifting-app/services/app.py', 'mcp')], 'detail': 'Sixteen Deployments replace nano-function packaging; typed operation inventory supplies shared HTTP and MCP discovery, dispatch and authentication.'}
    if path.endswith('/analytics.py') and '/pod_analysis/' in path:
        return {'kind': 'merged_duplicate', 'targets': [target(PL + 'get_analysis_markdown/analytics.py', name)]}
    if path.endswith('/regenerate_analysis/export.py'):
        return {'kind': 'merged_duplicate', 'targets': [target(PL + 'get_analysis_markdown/export.py', name)]}
    if '/pod_weight/' in path:
        return {'kind': 'merged_duplicate', 'targets': [target(PL + 'pod_weight/handlers/_weight_store.py', 'get_store'), target(PL + 'pod_weight/handlers/_weight_store.py', 'resolve')], 'detail': 'Six aliases use one scoped WeightStore; conversion and cache invalidation are centralized.'}
    if '/pod_calc/' in path:
        calculation = 'calculate_dots' if 'calculate_dots' in path else 'estimate_1rm'
        return {'kind': 'merged_duplicate', 'targets': [target(PL + 'layers/pl-core/python/lift_calculations.py', calculation)]}
    if path == 'app/src/api/template_imports.py':
        return {'kind': 'replaced', 'targets': [target('app/src/api/jobs.py', 'submit'), target(PL + 'pod_imports/handlers/import_parse_file/core.py', 'import_parse_file')], 'detail': 'Portal staged import uses typed Imports operations and explicit Templates apply; legacy shared-path endpoint removed.'}
    if path in {'app/src/main.py', 'app/src/storage/model_registry.py'}:
        return {'kind': 'retired', 'targets': [target('app/src/flow/codex_llm.py', '_preflight')], 'detail': 'Paid-provider endpoint refresh and model seeding removed; subscription catalog is checked before execution.'}
    if path == 'app/src/channels/slash_commands.py':
        return {'kind': 'retired', 'targets': [target('app/src/flow/runner.py', 'run_if_flow')], 'detail': 'No persistent OpenCode session remains to clear; Conversations resume persistent native Codex threads.'}
    if path == 'app/src/agent/condenser.py':
        return {'kind': 'renamed', 'targets': [target(path, 'condense_with_codex')]}
    if path == 'app/src/api/completions.py':
        return {'kind': 'replaced', 'targets': [target('app/src/api/jobs.py', 'events')], 'detail': 'Completion streaming consumes the same durable worker events.'}
    if path in {'app/src/flow/batch_classifier.py', 'app/src/flow/plan.py', 'app/src/channels/decision_applier.py', 'app/src/channels/task_worker.py', 'app/src/channels/cancellable_executor.py', 'app/src/channels/execution_store.py'}:
        return {'kind': 'retired', 'targets': [target('app/src/execution/host.py', 'submit')], 'detail': 'Native Conversations replace classification, planning and queued implementation tasks; historical records remain.'}
    if path == 'app/src/flow/opencode_config.py':
        return {'kind': 'replaced', 'targets': [target('app/src/execution/codex_worker.py', '_write_agent_config'), target('app/src/execution/tool_policy.py', 'evaluate')]}
    if path == 'app/src/flow/runner.py':
        return {'kind': 'replaced', 'targets': [target(path, 'prepare_conversation'), target('app/src/execution/host.py', 'submit')], 'detail': 'Sol selects native workflows inside a persistent Conversation; persona, Directives, context and artifacts cross the scoped runtime boundary.'}
    if path in {'app/src/flow/direct_llm.py', 'app/src/flow/opencode.py', 'app/src/flow/opencode_fission.py'}:
        return {'kind': 'replaced', 'targets': [target('app/src/flow/codex_llm.py', 'call_codex_chat'), target('app/src/execution/host.py', 'submit')]}
    raise AssertionError(f'Unmapped baseline function: {path}::{name}')


if __name__ == '__main__':
    rows = json.loads((ROOT / 'docs/contracts/function-inventory.json').read_text())
    mapped = [{**row, 'replacement': replacement(row)} for row in rows]
    (ROOT / 'docs/contracts/function-replacements.json').write_text(json.dumps(mapped, indent=2) + '\n')
    print(f'PASS {len(mapped)} baseline Python functions mapped to retained, merged, replaced or retired behavior')
