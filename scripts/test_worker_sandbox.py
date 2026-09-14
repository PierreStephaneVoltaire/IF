import subprocess


probe = '''
import os
import subprocess
import time
from pathlib import Path

assert Path('/proc/1/comm').read_text().strip() == 'tini'
child = os.fork()
if child == 0:
    if os.fork() == 0:
        os._exit(0)
    os._exit(0)
os.waitpid(child, 0)
for attempt in range(20):
    zombies = []
    for process in Path('/proc').iterdir():
        if process.name.isdigit():
            try:
                if any(line.startswith('State:') and 'Z' in line for line in (process / 'status').read_text().splitlines()):
                    zombies.append(process.name)
            except FileNotFoundError:
                pass
    if not zombies:
        break
    time.sleep(0.1)
assert not zombies, zombies
root = Path('/work/probe')
root.mkdir()
for name in ('.git', '.agents', '.codex'):
    (root / name).mkdir()
scopes = Path('/work/probe.scopes.json')
scopes.write_text('original')
command = [
    '/usr/local/lib/python3.12/site-packages/codex_cli_bin/bin/codex',
    '-c', 'features.use_legacy_landlock=true',
    '-c', 'sandbox_workspace_write.exclude_tmpdir_env_var=true',
    '-c', 'sandbox_workspace_write.exclude_slash_tmp=true',
    '-c', 'sandbox_mode="workspace-write"',
    'sandbox', '--',
    'sh', '-c', 'echo report > report.md; echo changed > ../probe.scopes.json',
]
result = subprocess.run(command, cwd=root, capture_output=True, text=True)
assert (root / 'report.md').is_file(), result.stderr
assert (root / 'report.md').read_text().strip() == 'report'
assert result.returncode != 0, result
assert scopes.read_text() == 'original'
print('PASS worker: init reaps orphans, workspace writable, external scope file protected')
'''
subprocess.run([
    'docker', 'run', '--rm', '-i', '--network=none', '--memory=512m', '--cpus=1',
    'if-codex-worker:rewrite', 'python', '-',
], input=probe, text=True, check=True)
