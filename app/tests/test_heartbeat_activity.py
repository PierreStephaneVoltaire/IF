from datetime import datetime, timedelta, timezone

from heartbeat.activity import ActivityTracker
from storage.dynamodb_backend import DynamoDBWebhookStore
from storage.models import WebhookRecord


class FakeDynamoTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[(Item["pk"], Item["sk"])] = dict(Item)

    def get_item(self, Key):
        item = self.items.get((Key["pk"], Key["sk"]))
        return {"Item": dict(item)} if item else {}

    def query(self, **kwargs):
        return {"Items": [dict(item) for item in self.items.values()]}


def test_dynamodb_store_supports_heartbeat_startup_and_activity():
    store = DynamoDBWebhookStore("test")
    store._table = FakeDynamoTable()
    webhook = WebhookRecord(platform="discord", label="test")
    webhook.set_config({"channel_id": "channel-1"})
    store.create(webhook)

    tracker = ActivityTracker(store._backend)
    tracker.record_activity("conversation-1", webhook.webhook_id)
    entry = store.get_activity("channel-1")
    assert entry["webhook_id"] == webhook.webhook_id
    assert store.get_activity("conversation-1") is None
    assert store.get("activity#channel-1") is None
    assert store.deactivate("activity#channel-1") is False
    assert tracker.get_idle_webhooks([webhook], 1, 1) == []

    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    entry["last_message_at"] = old
    store.table.put_item(Item=entry)
    assert tracker.get_idle_webhooks([webhook], 1, 1) == [webhook]

    tracker.record_heartbeat("channel-1")
    assert tracker.get_idle_webhooks([webhook], 1, 1) == []
