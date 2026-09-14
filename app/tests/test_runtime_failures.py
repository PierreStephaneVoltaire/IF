import asyncio
import sys
import types
from types import SimpleNamespace

import pytest

from flow import codex_llm


def test_preflight_maps_authentication_failure():
    class Codex:
        async def account(self):
            raise RuntimeError("not logged in")

    with pytest.raises(codex_llm.CodexInferenceError) as raised:
        asyncio.run(codex_llm._preflight(Codex(), "gpt-5.6-sol"))

    assert raised.value.code == "auth_unavailable"
    assert raised.value.retryable is False


def test_preflight_rejects_non_subscription_authentication():
    account = SimpleNamespace(account=SimpleNamespace(root=SimpleNamespace(type="api")))

    class Codex:
        async def account(self):
            return account

    with pytest.raises(codex_llm.CodexInferenceError) as raised:
        asyncio.run(codex_llm._preflight(Codex(), "gpt-5.6-sol"))

    assert raised.value.code == "subscription_required"
    assert raised.value.retryable is False


def test_background_callers_use_background_priority(monkeypatch):
    calls = []

    async def fake_call(**kwargs):
        calls.append(kwargs)
        return "summary"

    import heartbeat.runner as heartbeat
    import memory.summarizer as summarizer
    from agent.reflection.opinion_formation import OpinionFormer

    monkeypatch.setattr(codex_llm, "call_codex_chat", fake_call)
    monkeypatch.setattr(summarizer, "call_codex_chat", fake_call)

    asyncio.run(heartbeat.call_llm("ignored", [], "system", 1, None))

    class Store:
        def add(self, **_):
            pass

    monkeypatch.setattr(summarizer, "get_user_fact_store", lambda: Store())
    asyncio.run(summarizer.summarize_and_store("cache", [{"role": "user", "content": "x"}] * 4, "operator", None))
    asyncio.run(OpinionFormer(Store(), None, llm_model="gpt-5.6-sol")._form_single_opinion("topic", "position"))

    assert len(calls) == 3
    assert [call["priority"] for call in calls] == [10, 10, 10]


def test_native_quota_errors_do_not_request_automatic_retry():
    from execution.native import failure

    error = failure(RuntimeError('usage limit reached'))
    assert error['code'] == 'usage_limit' and error['retryable'] is False
