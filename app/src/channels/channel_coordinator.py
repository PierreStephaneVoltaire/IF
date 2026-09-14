import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from execution.service import get_execution_service
from execution.store import TERMINAL

logger = logging.getLogger(__name__)
_main_loop = None
_delivery_task = None
_channel_locks = {}


def discord_owner(author_id):
    from config import IF_USER_PK
    return IF_USER_PK if str(author_id) == os.getenv("IF_OPERATOR_DISCORD_ID") else "discord:" + str(author_id)


def discord_conversation(channel_id):
    from storage.factory import get_webhook_store
    records = get_webhook_store().list_active()
    return next((record.conversation_id for record in records if record.platform == "discord" and str(record.get_config().get("channel_id")) == str(channel_id)), str(channel_id))


def init_channel_coordinator(loop):
    global _main_loop, _delivery_task
    _main_loop = loop
    _delivery_task = loop.create_task(recover_deliveries())


def push_discord_event(conversation_id, message):
    if _main_loop:
        future = asyncio.run_coroutine_threadsafe(handle_discord_event(conversation_id, message), _main_loop)
        future.add_done_callback(log_failure)


def log_failure(future):
    try:
        future.result()
    except Exception:
        logger.exception("Discord Conversation input failed")


async def enqueue_response(channel_id, conversation_id, reference, content, attachments=None, reply_to=None):
    from channels.execution_models import DiscordOutboundMessage
    from channels.execution_store import get_execution_store
    from channels.outbound_queue import schedule_drain
    now = datetime.now(timezone.utc).isoformat()
    message = DiscordOutboundMessage(outbound_id=uuid.uuid4().hex, channel_id=channel_id, conversation_id=conversation_id,
        content=content, attachments=attachments or [], reply_to_message_id=reply_to, created_at=now, updated_at=now,
        idempotency_key="native:" + reference)
    await get_execution_store().put_outbound_message(message)
    schedule_drain(channel_id)


async def handle_discord_event(conversation_id, message):
    from channels.translators.discord_translator import translate_discord_batch
    from channels.attachments import download_discord_attachments
    from flow.runner import prepare_conversation
    from flow.session_dirs import resolve_session_dir
    owner = discord_owner(message["author_id"])
    key = (owner, conversation_id)
    async with _channel_locks.setdefault(key, asyncio.Lock()):
        request_data = translate_discord_batch([message], conversation_id)
        request_data["_owner"] = owner
        from routing.cache import get_cache
        from flow.runner import conversation_scope
        state = get_cache().get_or_create(conversation_scope(owner, conversation_id))
        request_data["_thinking_mode_requested"] = bool(state.pondering or (state.pinned and state.pinned_tier == 2))
        reference = "discord:" + message["channel_id"] + ":" + message["message_id"] + ":" + (message.get("edited_at") or "created")
        request_data["_idempotency_key"] = reference
        if message.get("is_edit") or message.get("event_type") == "message_edit":
            request_data["messages"][-1]["content"] = "The Operator edited message " + message["message_id"] + ". Use this corrected text for the current request:\n" + request_data["messages"][-1]["content"]
        request_data["_delivery"] = {"channel_id": message["channel_id"], "conversation_id": conversation_id, "reply_to": message["message_id"]}
        session_dir = resolve_session_dir(request_data, None, conversation_id)
        if not (session_dir / "history.json").exists() and message.get("channel_ref"):
            async def fetch_history():
                import discord
                return [item async for item in message["channel_ref"].history(limit=100, before=discord.Object(id=int(message["message_id"])))]
            discord_loop = message.get("discord_loop")
            history = await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(fetch_history(), discord_loop)) if discord_loop and discord_loop != asyncio.get_running_loop() else await fetch_history()
            translated = translate_discord_batch([message], conversation_id, history)
            request_data["messages"] = translated["messages"]
            request_data["_history_events"] = translated["_history_events"]
        pending = request_data.pop("_pending_uploads", [])
        request_data["_uploaded_files"] = await download_discord_attachments(pending, conversation_id, session_dir / "uploads")
        try:
            _, request, _ = await asyncio.to_thread(prepare_conversation, request_data, conversation_id, conversation_id)
            await get_execution_service().submit(owner, request)
        except Exception as exc:
            await enqueue_response(message["channel_id"], conversation_id, reference + ":error", str(exc), reply_to=message["message_id"])
            return
        try:
            from heartbeat.activity import ActivityTracker
            from storage.factory import get_webhook_store
            store = get_webhook_store()
            ActivityTracker(store._backend).record_activity(conversation_id, webhook_id=message.get("webhook_id"))
        except Exception:
            logger.exception("Activity recording failed after accepting the Discord turn")


async def deliver_completed(job):
    from flow.runner import materialize_result, materialize_file_ref
    from flow.history import write_history
    delivery = job.request.payload["delivery"]
    history = job.request.payload.get("history_path")
    session_dir = Path(history).parent if history else Path(os.getenv("IF_WORKSPACE_BASE", "/tmp/if-workspaces")) / job.job_id
    if job.status == "succeeded":
        result = materialize_result({**(job.result or {}), "job_id": job.job_id}, session_dir)
        content = result.content
        attachments = [value for ref in result.file_refs if (value := materialize_file_ref(ref, job.job_id))]
        write_history(session_dir, [{"id": job.job_id, "role": "assistant", "content": content}])
    else:
        content, attachments = (job.error.message if job.error else "The turn did not complete."), []
    await enqueue_response(delivery["channel_id"], delivery["conversation_id"], job.job_id, content, attachments, delivery.get("reply_to"))
    await get_execution_service().request("POST", f"/turns/{job.job_id}/delivered", params={"owner": job.owner})


async def recover_deliveries():
    while True:
        try:
            for job in await get_execution_service().list(undelivered=True):
                if job.status in TERMINAL:
                    await deliver_completed(job)
            from channels.outbound_queue import schedule_drain
            from storage.factory import get_webhook_store
            for record in await asyncio.to_thread(get_webhook_store().list_active):
                if record.platform == "discord":
                    schedule_drain(str(record.get_config()["channel_id"]))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Conversation delivery reconciliation will retry")
        await asyncio.sleep(2)

async def shutdown_channel_coordinator():
    if _delivery_task:
        _delivery_task.cancel()
        await asyncio.gather(_delivery_task, return_exceptions=True)
