"""Storage abstraction layer.

All persistent document storage goes through this interface.
Current backend: SQLite + SQLModel.
Future backend: DynamoDB (write new class, flip STORE_BACKEND env var).
"""
from storage.models import WebhookRecord
from storage.factory import get_webhook_store, init_store, close_store

__all__ = ["WebhookRecord", "get_webhook_store", "init_store", "close_store"]
