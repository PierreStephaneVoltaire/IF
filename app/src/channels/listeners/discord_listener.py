from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
from typing import TYPE_CHECKING, Callable

import discord
from discord import app_commands

if TYPE_CHECKING:
    from storage.models import WebhookRecord

logger = logging.getLogger(__name__)
_active_clients: dict[str, discord.Client] = {}
_runtime_lock = threading.RLock()
_runtime_records: dict[str, tuple["WebhookRecord", threading.Event]] = {}
_runtimes: dict[str, tuple[discord.Client, asyncio.AbstractEventLoop, threading.Thread]] = {}
_runtime_starting: set[str] = set()
_runtime_ready: dict[str, threading.Event] = {}
_record_runtime_keys: dict[str, str] = {}

def get_discord_client() -> discord.Client | None:
    with _runtime_lock:
        if _runtimes:
            return next(iter(_runtimes.values()))[0]
        return next(iter(_active_clients.values()), None)

def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def _records_for(channel_id: int, runtime_key: str) -> list["WebhookRecord"]:
    with _runtime_lock:
        return [
            r for webhook_id, (r, _) in _runtime_records.items()
            if _record_runtime_keys.get(webhook_id) == runtime_key
            and int(r.get_config()["channel_id"]) == channel_id
        ]

def _message_data(message, record, loop, event_type, before=None):
    return {
        "platform": "discord", "webhook_id": record.webhook_id,
        "conversation_id": record.conversation_id, "message_id": str(message.id),
        "guild_id": str(message.guild.id) if message.guild else "",
        "channel_id": str(message.channel.id), "author": message.author.display_name,
        "author_id": str(message.author.id), "content": message.clean_content,
        "attachments": [{"filename": a.filename, "url": a.url, "content_type": a.content_type or "application/octet-stream"} for a in message.attachments],
        "channel_ref": message.channel, "discord_loop": loop,
        "timestamp": message.created_at.isoformat(),
        "edited_at": message.edited_at.isoformat() if message.edited_at else "",
        "reply_to_message_id": str(message.reference.message_id) if message.reference and getattr(message.reference, "message_id", None) else None,
        "event_type": event_type,
        **({"is_edit": True, "previous_content": before.clean_content} if before else {}),
    }

def _start_runtime(record, runtime_key):
    token = record.get_config()["bot_token"]

    def gateway():
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            intents = discord.Intents.default()
            intents.message_content = True
            client = discord.Client(intents=intents)
            tree = app_commands.CommandTree(client)
        except Exception:
            with _runtime_lock:
                _runtime_starting.discard(runtime_key)
                ready = _runtime_ready.pop(runtime_key, None)
                if ready:
                    ready.set()
            if loop:
                loop.close()
            logger.exception("Discord gateway initialization failed")
            return
        with _runtime_lock:
            _runtimes[runtime_key] = (client, loop, threading.current_thread())
            _runtime_starting.discard(runtime_key)
            _runtime_ready[runtime_key].set()
            for webhook_id, key in _record_runtime_keys.items():
                if key != runtime_key:
                    continue
                _active_clients[webhook_id] = client
        from channels.slash_commands import setup_command_tree, should_sync
        try:
            setup_command_tree(tree, int(record.get_config()["channel_id"]), record.conversation_id, record.webhook_id)
        except Exception as exc:
            logger.error("Slash command setup failed (messages will still be received): %s", exc, exc_info=True)

        @client.event
        async def on_ready():
            logger.info("Discord gateway connected as %s", client.user)
            with _runtime_lock:
                records = [
                    r for webhook_id, (r, _) in _runtime_records.items()
                    if _record_runtime_keys.get(webhook_id) == runtime_key
                ]
            seen_guilds = set()
            for current in records or [record]:
                channel = client.get_channel(int(current.get_config()["channel_id"]))
                guild = getattr(channel, "guild", None)
                if not guild or guild.id in seen_guilds or not should_sync(client.user.id, guild.id):
                    continue
                seen_guilds.add(guild.id)
                try:
                    tree.copy_global_to(guild=guild)
                    existing = {cmd.name for cmd in await tree.fetch_commands(guild=guild)}
                    local = {cmd.name for cmd in tree.get_commands(guild=guild)}
                    if existing != local:
                        await tree.sync(guild=guild)
                        logger.info("Synced slash commands to guild %s (%s)", guild.name, guild.id)
                except discord.HTTPException as exc:
                    logger.error("Failed to sync slash commands to %s: %s", guild.name, exc)

        @client.event
        async def on_message(message):
            if message.author == client.user or message.author.bot:
                return
            from channels.channel_coordinator import push_discord_event
            for target in _records_for(message.channel.id, runtime_key):
                push_discord_event(target.conversation_id, _message_data(message, target, loop, "message_create"))

        @client.event
        async def on_message_edit(before, after):
            if after.author == client.user or after.author.bot:
                return
            from channels.channel_coordinator import push_discord_event
            for target in _records_for(after.channel.id, runtime_key):
                push_discord_event(target.conversation_id, _message_data(after, target, loop, "message_edit", before))

        async def run_client():
            try:
                await client.start(token)
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.error("Discord client error: %s", exc)
            finally:
                await client.close()

        try:
            loop.run_until_complete(run_client())
        finally:
            with _runtime_lock:
                for webhook_id, active in list(_active_clients.items()):
                    if active is client:
                        _active_clients.pop(webhook_id, None)
                _runtimes.pop(runtime_key, None)
                _runtime_ready.pop(runtime_key, None)
            loop.close()
            logger.info("Discord gateway stopped")

    threading.Thread(target=gateway, name="discord-gateway", daemon=True).start()

def create_discord_listener(record: "WebhookRecord", stop_event: threading.Event) -> Callable[[], None]:
    def run() -> None:
        webhook_id = record.webhook_id
        runtime_key = _token_key(record.get_config()["bot_token"])
        with _runtime_lock:
            _runtime_records[webhook_id] = (record, stop_event)
            _record_runtime_keys[webhook_id] = runtime_key
            runtime = _runtimes.get(runtime_key)
            active = runtime is not None and runtime[2].is_alive()
            starter = not active and runtime_key not in _runtime_starting
            ready = _runtime_ready.get(runtime_key)
            if starter:
                _runtime_starting.add(runtime_key)
                ready = _runtime_ready[runtime_key] = threading.Event()
        if not active:
            if starter:
                _start_runtime(record, runtime_key)
            else:
                ready.wait(timeout=5)
        with _runtime_lock:
            runtime = _runtimes.get(runtime_key)
            if runtime:
                _active_clients[webhook_id] = runtime[0]
        while not stop_event.wait(1):
            with _runtime_lock:
                runtime = _runtimes.get(runtime_key)
                restart = runtime is None and runtime_key not in _runtime_starting
                if restart:
                    _runtime_starting.add(runtime_key)
                    _runtime_ready[runtime_key] = threading.Event()
            if restart:
                logger.warning("Discord gateway stopped unexpectedly; restarting")
                _start_runtime(record, runtime_key)
                if stop_event.wait(5):
                    break
                continue
        with _runtime_lock:
            _runtime_records.pop(webhook_id, None)
            _record_runtime_keys.pop(webhook_id, None)
            _active_clients.pop(webhook_id, None)
            runtime = _runtimes.get(runtime_key)
            last = not any(key == runtime_key for key in _record_runtime_keys.values())
        if last and runtime:
            asyncio.run_coroutine_threadsafe(runtime[0].close(), runtime[1])
        logger.info("Discord listener stopped for %s", webhook_id)
    return run
