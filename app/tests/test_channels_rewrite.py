import asyncio
import json
from pathlib import Path

import jsonschema
import pytest

from api import completions


def test_completion_stream_forwards_worker_deltas(monkeypatch):
    async def fake_process(*, request_data, **_kwargs):
        await request_data["_emit"]("started", {"model": "model-1"})
        await request_data["_emit"]("delta", {"delta": "hello"})
        await request_data["_emit"]("completed", {})
        return "hello", []

    monkeypatch.setattr(completions, "process_chat_completion_internal", fake_process)

    async def collect():
        return [
            chunk
            async for chunk in completions._stream_completion(
                {"messages": [{"role": "user", "content": "hi"}]},
                None,
                "chatcmpl-test",
                False,
            )
        ]

    chunks = asyncio.run(collect())
    assert any('"content":"hello"' in chunk for chunk in chunks)
    assert chunks[-1] == "data: [DONE]\n\n"


def test_outbox_conflicts_are_not_acknowledged_as_duplicate_delivery(monkeypatch):
    from botocore.exceptions import ClientError
    from channels.execution_models import DiscordOutboundMessage
    from channels.execution_store import ExecutionStore

    store = ExecutionStore()
    message = DiscordOutboundMessage("outbound", "channel", "conversation", idempotency_key="turn")
    response = {"Error": {"Code": "TransactionCanceledException"}, "CancellationReasons": []}

    def fail(_items):
        raise ClientError(response, "TransactWriteItems")

    monkeypatch.setattr(store, "_transact_put_items", fail)
    for reasons in ([], ["TransactionConflict"], ["ConditionalCheckFailed", "ThrottlingError"]):
        response["CancellationReasons"] = [{"Code": reason} for reason in reasons]
        with pytest.raises(ClientError):
            store._put_outbound_message_sync(message)
    response["CancellationReasons"] = [{"Code": "None"}, {"Code": "ConditionalCheckFailed"}]
    assert store._put_outbound_message_sync(message) is False
