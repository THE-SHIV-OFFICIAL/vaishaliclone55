"""Private health check for bot and assistants."""

import asyncio
from datetime import datetime, timezone

from pyrogram import filters
from pyrogram.types import Message

import config
from SHIVMUSIC import app, userbot
from SHIVMUSIC.core.call import ANJALI
from SHIVMUSIC.misc import SUDOERS, db
from SHIVMUSIC.utils.database import get_active_chats


async def _check_client(label, client):
    """Telegram client ka status check karta hai."""
    if client is None:
        return f"❌ {label}: not configured"

    if not client.is_connected:
        return f"❌ {label}: disconnected"

    try:
        me = await asyncio.wait_for(
            client.get_me(),
            timeout=config.HEALTHCHECK_TIMEOUT,
        )

        username = (
            f"@{me.username}"
            if me.username
            else str(me.id)
        )

        return f"✅ {label}: {username}"

    except Exception as error:
        return (
            f"⚠️ {label}: RPC failed "
            f"({type(error).__name__})"
        )


@app.on_message(
    filters.command("health") & SUDOERS
)
async def health_command(_, message: Message):
    """Main bot aur music system ka health status."""
    status = [
        "<b>🩺 SHIVMUSIC HEALTH</b>",
        "",
    ]

    status.append(
        await _check_client("Main bot", app)
    )

    assistants = (
        ("Assistant 1", config.STRING1, userbot.one),
        ("Assistant 2", config.STRING2, userbot.two),
        ("Assistant 3", config.STRING3, userbot.three),
        ("Assistant 4", config.STRING4, userbot.four),
    )

    for label, session, client in assistants:
        if session:
            status.append(
                await _check_client(label, client)
            )

    started_calls = len(
        getattr(ANJALI, "_started_calls", [])
    )

    watchdog = getattr(
        ANJALI,
        "_watchdog_task",
        None,
    )

    watchdog_ok = bool(
        watchdog and not watchdog.done()
    )

    try:
        active_chats = await get_active_chats()
        active_count = len(active_chats)
    except Exception:
        active_count = "unknown"

    status.extend(
        [
            "",
            (
                "🎙️ PyTgCalls clients: "
                f"<code>{started_calls}</code>"
            ),
            (
                "🐕 Stream watchdog: "
                f"<code>{'running' if watchdog_ok else 'stopped'}</code>"
            ),
            (
                "🎵 Active music chats: "
                f"<code>{active_count}</code>"
            ),
            (
                "💾 In-memory queues: "
                f"<code>{len(db)}</code>"
            ),
            (
                "⏱️ Checked: "
                f"<code>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</code>"
            ),
        ]
    )

    await message.reply_text(
        "\n".join(status)
    )
