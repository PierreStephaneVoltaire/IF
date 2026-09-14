import threading
import time
from types import SimpleNamespace

from channels.listeners import discord_listener as listener


class FakeClient:
    created = []
    fail_once = False

    def __init__(self, *, intents):
        if self.fail_once:
            type(self).fail_once = False
            raise RuntimeError("constructor failed")
        self.closed = threading.Event()
        self.user = SimpleNamespace(id=1)
        type(self).created.append(self)

    def event(self, callback):
        return callback

    async def start(self, token):
        while not self.closed.is_set():
            await __import__("asyncio").sleep(0.01)

    async def close(self):
        self.closed.set()

    def get_channel(self, channel_id):
        return None


class FakeIntents:
    @staticmethod
    def default():
        return SimpleNamespace(message_content=False)


class FakeTree:
    def __init__(self, client):
        self.client = client


class Record:
    def __init__(self, webhook_id, channel_id, token):
        self.webhook_id = webhook_id
        self.conversation_id = f"conversation-{webhook_id}"
        self.label = webhook_id
        self.platform = "discord"
        self._config = {"channel_id": str(channel_id), "bot_token": token}

    def get_config(self):
        return self._config


def _wait(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


def test_discord_gateway_token_scoped_lifecycle(monkeypatch):
    listener._active_clients.clear()
    listener._runtime_records.clear()
    listener._runtimes.clear()
    listener._runtime_starting.clear()
    listener._runtime_ready.clear()
    listener._record_runtime_keys.clear()
    FakeClient.created = []
    FakeClient.fail_once = False
    monkeypatch.setattr(listener.discord, "Client", FakeClient)
    monkeypatch.setattr(listener.discord, "Intents", FakeIntents)
    monkeypatch.setattr(listener.app_commands, "CommandTree", FakeTree)
    import channels.slash_commands as slash
    monkeypatch.setattr(slash, "setup_command_tree", lambda *args: None)
    monkeypatch.setattr(slash, "should_sync", lambda *args: False)

    a_stop, b_stop, c_stop = threading.Event(), threading.Event(), threading.Event()
    a = Record("a", 101, "token-a")
    b = Record("b", 102, "token-a")
    c = Record("c", 103, "token-b")
    threads = [
        threading.Thread(target=listener.create_discord_listener(a, a_stop)),
        threading.Thread(target=listener.create_discord_listener(b, b_stop)),
        threading.Thread(target=listener.create_discord_listener(c, c_stop)),
    ]
    for thread in threads:
        thread.start()
    try:
        _wait(lambda: len(FakeClient.created) == 2)
        a_client = listener._active_clients["a"]
        b_client = listener._active_clients["b"]
        c_client = listener._active_clients["c"]
        assert a_client is b_client
        assert a_client is not c_client

        a_stop.set()
        threads[0].join(2)
        assert threads[0].is_alive() is False
        assert "b" in listener._active_clients
        assert b_client.closed.is_set() is False

        b_client.closed.set()
        _wait(lambda: listener._active_clients.get("b") not in (None, b_client), timeout=8)
        assert listener._active_clients["b"] is not c_client
    finally:
        a_stop.set()
        b_stop.set()
        c_stop.set()
        for thread in threads:
            thread.join(2)
        assert all(not thread.is_alive() for thread in threads)
        _wait(lambda: all(client.closed.is_set() for client in FakeClient.created))


def test_discord_gateway_restarts_after_constructor_failure(monkeypatch):
    listener._active_clients.clear()
    listener._runtime_records.clear()
    listener._runtimes.clear()
    listener._runtime_starting.clear()
    listener._runtime_ready.clear()
    listener._record_runtime_keys.clear()
    FakeClient.created = []
    FakeClient.fail_once = True
    monkeypatch.setattr(listener.discord, "Client", FakeClient)
    monkeypatch.setattr(listener.discord, "Intents", FakeIntents)
    monkeypatch.setattr(listener.app_commands, "CommandTree", FakeTree)
    import channels.slash_commands as slash
    monkeypatch.setattr(slash, "setup_command_tree", lambda *args: None)
    record = Record("retry", 104, "token-retry")
    stop = threading.Event()
    thread = threading.Thread(target=listener.create_discord_listener(record, stop))
    thread.start()
    try:
        _wait(lambda: len(FakeClient.created) == 1, timeout=8)
        assert not listener._runtime_starting
    finally:
        stop.set()
        thread.join(2)
        assert not thread.is_alive()
