"""Clone group membership tracking for CData and clone event logs."""

import html
import logging

from pyrogram import Client, enums, filters
from pyrogram.enums import ParseMode
from pyrogram.types import ChatMemberUpdated

import config
from SHIVMUSIC.utils.database import (
    add_served_chat_clone,
    delete_served_chat_clone,
)

LOGGER = logging.getLogger(__name__)


def _status(member):
    value = getattr(getattr(member, "status", None), "value", None)
    return str(value or getattr(member, "status", "")).lower().split(".")[-1]


def _user_id(member):
    return getattr(getattr(member, "user", None), "id", None)


def _joined(value):
    return value in {"member", "administrator", "owner"}


def _removed(value):
    return value in {"left", "kicked", "banned"}


@Client.on_chat_member_updated(filters.group, group=1)
async def clone_group_membership(client: Client, update: ChatMemberUpdated):
    try:
        bot = await client.get_me()
        old_member = getattr(update, "old_chat_member", None)
        new_member = getattr(update, "new_chat_member", None)
        member = (
            new_member if _user_id(new_member) == bot.id else old_member
        )
        if _user_id(member) != bot.id:
            return

        old_status = _status(old_member)
        new_status = _status(new_member)
        added = _joined(new_status) and not _joined(old_status)
        removed = _removed(new_status) and not _removed(old_status)
        if not (added or removed):
            return

        if added:
            await add_served_chat_clone(update.chat.id, bot.id)
            action = "Added"
            icon = "✅"
        else:
            await delete_served_chat_clone(update.chat.id, bot.id)
            action = "Removed"
            icon = "❌"

        logger_id = getattr(config, "CLONE_LOGGER_2", 0) or getattr(
            config, "LOGGER_ID", 0
        )
        if not logger_id:
            return

        actor = getattr(update, "from_user", None)
        actor_text = actor.mention if actor else "Unknown user"
        title = html.escape(update.chat.title or "Unknown", quote=True)
        text = (
            f"<b>#{action}_Clone_Bot</b>\n\n"
            f"<b>🤖 Bot:</b> @{html.escape(bot.username or str(bot.id))}\n"
            f"<b>📌 Group:</b> {title} "
            f"[<code>{update.chat.id}</code>]\n"
            f"<b>👤 By:</b> {actor_text}\n"
            f"<b>Action:</b> {icon} {action}"
        )
        try:
            await client.send_message(
                logger_id,
                text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            try:
                from SHIVMUSIC import app as _main_app
                await _main_app.send_message(
                    logger_id, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True
                )
            except Exception as e:
                LOGGER.warning(f"Could not send clone membership log: {e}")
    except Exception:
        LOGGER.warning("Clone membership handler failed", exc_info=True)