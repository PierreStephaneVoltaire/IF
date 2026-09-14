import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from execution.host import BusyError, ConversationHost
from execution.native import history_items
from execution.schemas import JobRequest


class Session:
    starts = []

    def __init__(self, job, workspace):
        self.job, self.workspace = job, workspace
        self.finish = asyncio.Event()
        self.inputs = []
        self.interrupted = False

    async def start(self, bind):
        self.job.thread_id = self.job.thread_id or "thread-" + self.job.job_id
        self.job.turn_id = "turn-" + self.job.job_id
        self.job.status = "running"
        self.starts.append(self.job.job_id)
        bind(self.job)

    async def consume(self, emit):
        await self.finish.wait()
        emit("delta", {"delta": "done"})
        return {"content": "done"}

    async def steer(self, request):
        self.inputs.append(request.payload)

    async def interrupt(self):
        self.interrupted = True

    async def close(self):
        pass


def request(conversation, key, kind="conversation", priority=0):
    return JobRequest(conversation_id=conversation, idempotency_key=key, kind=kind, priority=priority, payload={"messages": [{"role": "user", "content": "hello"}]})


def test_concurrency_steering_isolation_and_resume(tmp_path):
    async def check():
        host = ConversationHost(tmp_path, Session)
        first = await host.submit("alice", request("one", "first"))
        second = await host.submit("alice", request("two", "second"))
        await asyncio.sleep(0)
        with pytest.raises(BusyError):
            await host.submit("alice", request("three", "third"))
        assert len(host.store.list()) == 2
        steered = await host.submit("alice", request("one", "edit"))
        repeated = await host.submit("alice", request("one", "edit"))
        assert steered.job_id == repeated.job_id == first.job_id
        assert len(host.active[("alice", "one")].inputs) == 1
        assert first.thread_id != second.thread_id
        session = host.active[("alice", "one")]
        session.finish.set()
        await host.tasks[first.job_id]
        next_turn = await host.submit("alice", request("one", "next"))
        assert next_turn.thread_id == first.thread_id
        with pytest.raises(KeyError):
            host.store.get(first.job_id, "bob")
        assert host.workspace("alice", "one") != host.workspace("bob", "one")
        await host.close()
    asyncio.run(check())


def test_cancel_and_idle_work_do_not_queue(tmp_path):
    async def check():
        host = ConversationHost(tmp_path, Session)
        job = await host.submit("alice", request("one", "first"))
        await asyncio.sleep(0)
        session = host.active[("alice", "one")]
        with pytest.raises(BusyError):
            await host.submit("alice", request("reflection", "reflection", priority=10))
        await host.cancel(job.job_id, "alice")
        assert host.store.get(job.job_id).status == "cancel_requested"
        await host.tasks[job.job_id]
        assert session.interrupted
        assert host.store.get(job.job_id).status == "uncertain"
        assert not host.active
    asyncio.run(check())


def test_restart_recovers_completion_without_reexecution(tmp_path):
    async def check():
        store_host = ConversationHost(tmp_path, Session)
        completed = store_host.store.start("alice", request("one", "first"))
        lost = store_host.store.start("alice", request("two", "lost"))
        async def recover(job, workspace):
            return {"content": "recovered"} if job.job_id == completed.job_id else None
        host = ConversationHost(tmp_path, Session, recover)
        count = len(Session.starts)
        await host.reconcile()
        assert len(Session.starts) == count
        assert host.store.get(completed.job_id).result["content"] == "recovered"
        assert host.store.get(lost.job_id).status == "uncertain"
        assert (await host.submit("alice", request("two", "lost"))).status == "uncertain"
    asyncio.run(check())


def test_bootstrap_preserves_roles():
    items = history_items([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}])
    assert [item["role"] for item in items] == ["user", "assistant"]
    assert items[1]["content"] == [{"type": "output_text", "text": "hello"}]


def test_completion_admits_followup_while_sdk_closes(tmp_path):
    async def check():
        closing = asyncio.Event()
        release = asyncio.Event()
        class SlowClose(Session):
            async def close(self):
                closing.set()
                await release.wait()
        host = ConversationHost(tmp_path, SlowClose)
        first = await host.submit('alice', request('one', 'first'))
        task = host.tasks[first.job_id]
        host.active[('alice', 'one')].finish.set()
        await closing.wait()
        assert host.store.get(first.job_id).status == 'succeeded'
        second = await host.submit('alice', request('one', 'second'))
        assert second.job_id != first.job_id and second.thread_id == first.thread_id
        release.set()
        await task
        await host.close()
    asyncio.run(check())


def test_immediate_cancel_leaves_no_accepted_work_running(tmp_path):
    async def check():
        host = ConversationHost(tmp_path, Session)
        job = await host.submit('alice', request('one', 'first'))
        task = host.tasks[job.job_id]
        await host.cancel(job.job_id, 'alice')
        await task
        assert host.store.get(job.job_id).status == 'uncertain'
        assert not host.active
    asyncio.run(check())


def test_person_and_conversation_history_paths_never_collide(monkeypatch, tmp_path):
    from flow import session_dirs
    monkeypatch.setattr(session_dirs, 'IF_WORKSPACE_BASE', str(tmp_path))
    from config import IF_USER_PK
    paths = [session_dirs.resolve_session_dir({'_owner': owner, 'conversation_id': conversation}, None, conversation)
             for owner in (IF_USER_PK, 'alice') for conversation in ('a:b', 'a_b', '../a', 'a')]
    assert len(set(paths)) == len(paths)
    first = session_dirs.resolve_session_dir({'_owner': IF_USER_PK, 'conversation_id': 'a:b', 'channel_id': 'channel-a'}, None, 'a:b')
    assert first == paths[0]


def test_history_keeps_concurrent_inputs_and_edits(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from flow.history import write_history, _load_events
    def record(index):
        write_history(tmp_path, [{'id': str(index), 'role': 'user', 'content': str(index)}])
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(record, range(20)))
    write_history(tmp_path, [{'id': '7', 'role': 'user', 'content': 'edited'}])
    history = _load_events(tmp_path / 'history.json')
    assert len(history) == 20 and history['7']['content'] == 'edited'
