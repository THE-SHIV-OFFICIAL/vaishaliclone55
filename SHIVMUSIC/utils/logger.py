import html
import logging
from datetime import datetime

from pyrogram import Client, filters, enums
from pyrogram.enums import ParseMode, ButtonStyle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated
import random

# Make sure config se LOGGER_2_ID import ho raha hai
from SHIVMUSIC import app
from SHIVMUSIC.core.mongo import mongodb
from SHIVMUSIC.utils.database import (
    add_served_chat,
    delete_served_chat,
    is_on_off,
)
from config import LOGGER_ID, LOGGER_2_ID

# 🔥 PREMIUM EMOJIS LIST 🔥
PREMIUM_EMOJIS = [
    "5422831825178206894", 
    "5368324170673489600",
    "5206607081334906820",
    "5206380668048496464"
]

daily_statsdb = mongodb["daily_stats"]
LOGGER = logging.getLogger(__name__)

# ====================================================
# HELPER FUNCTION: To Fetch Group Owner
# ====================================================
async def get_owner(client, chat_id):
    try:
        async for member in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            if member.status == enums.ChatMemberStatus.OWNER:
                return member.user.mention
    except:
        pass
    return "Unknown"


# ====================================================
# PLAY LOGS
# ====================================================
async def play_logs(message, streamtype):
    if await is_on_off(2):
        try:
            query = message.text.split(None, 1)[1]
        except:
            query = "Link/File or Reply"

        try:
            members_count = await app.get_chat_members_count(message.chat.id)
        except:
            members_count = "Unknown"
            
        owner = await get_owner(app, message.chat.id)

        chat_link = None
        if message.chat.username:
            chat_link = f"https://t.me/{message.chat.username}"
        else:
            try:
                chat_link = await app.export_chat_invite_link(message.chat.id)
            except:
                pass

        logger_text = f"""
<blockquote><b>{app.mention} ᴘʟᴀʏ ʟᴏɢ</b>

<b>• ʀᴇǫᴜᴇsᴛ ʙʏ : {message.from_user.mention}</b>
<b>• ǫᴜᴇʀʏ : {query}</b>
<b>• ᴄʜᴀᴛ : {message.chat.title} [<code>{message.chat.id}</code>]</b>
<b>• ᴏᴡɴᴇʀ : {owner}</b>
<b>• ᴍᴇᴍʙᴇʀs : {members_count}</b></blockquote>
"""
        buttons = []
        if chat_link:
            buttons.append([InlineKeyboardButton("ɢʀᴏᴜᴘ ʟɪɴᴋ", url=chat_link, style=ButtonStyle.PRIMARY, icon_custom_emoji_id=random.choice(PREMIUM_EMOJIS))])
        buttons.append([InlineKeyboardButton("sᴜᴘᴘᴏʀᴛ", url="https://t.me/betabot_support")])
        
        reply_markup = InlineKeyboardMarkup(buttons)

        if message.chat.id != LOGGER_ID:
            try:
                await app.send_message(
                    chat_id=LOGGER_ID,
                    text=logger_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup
                )
            except:
                pass
        return


# ====================================================
# AUTOPLAY LOGS (main logger group)
# ====================================================
async def autoplay_logs(client, chat_id, title):
    """Send autoplay log to the main LOGGER_ID group (main bot + clones)."""
    if not LOGGER_ID or int(chat_id) == int(LOGGER_ID):
        return
    try:
        if not await is_on_off(2):
            return
    except Exception:
        pass
    sender = client or app
    try:
        chat = await sender.get_chat(chat_id)
        chat_title = html.escape(chat.title or str(chat_id))
        chat_link = f"https://t.me/{chat.username}" if getattr(chat, "username", None) else None
    except Exception:
        chat_title, chat_link = str(chat_id), None
    try:
        me = getattr(sender, "me", None) or await sender.get_me()
        bot_label = f"@{me.username}" if me and me.username else app.mention
    except Exception:
        bot_label = app.mention
    is_clone = sender is not app
    text = (
        f"<blockquote><b>{'🤖 ᴄʟᴏɴᴇ ʙᴏᴛ ' if is_clone else ''}ᴀᴜᴛᴏᴘʟᴀʏ ʟᴏɢ : {bot_label}</b>\n\n"
        f"<b>• ʀᴇǫᴜᴇsᴛ ʙʏ :</b> ᴀᴜᴛᴏᴘʟᴀʏ 🎧\n"
        f"<b>• ǫᴜᴇʀʏ :</b> {html.escape(str(title))}\n"
        f"<b>• ᴄʜᴀᴛ :</b> {chat_title} [<code>{chat_id}</code>]</blockquote>"
    )
    buttons = []
    if chat_link:
        buttons.append([InlineKeyboardButton("ɢʀᴏᴜᴘ ʟɪɴᴋ", url=chat_link)])
    try:
        await app.send_message(
            chat_id=LOGGER_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
        )
    except Exception as e:
        LOGGER.warning(f"Autoplay main log failed: {e}")


# ====================================================
# CLONE BOT PLAY LOGS
# ====================================================
async def clone_bot_logs(client, message, bot_mention, clone_logger_id, streamtype):
    bot = await client.get_me()
    try:
        query = message.text.split(None, 1)[1]
    except:
        query = "Link/File or Reply"

    if clone_logger_id:
        owner_log_text = f"""
<b><a href="https://t.me/{bot.username}">{bot.first_name}</a> ᴘʟᴀʏ ʟᴏɢ</b>

<b>• ʀᴇǫᴜᴇsᴛ ʙʏ :</b> {message.from_user.mention}
<b>• ǫᴜᴇʀʏ :</b> {query}
<b>• ᴄʜᴀᴛ :</b> {message.chat.title} [<code>{message.chat.id}</code>]
"""     
        owner_reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("sᴜᴘᴘᴏʀᴛ", url="https://t.me/betabot_support")]]
        )

        if message.chat.id != int(clone_logger_id):
            try:
                await client.send_message(
                    chat_id=int(clone_logger_id),
                    text=owner_log_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=owner_reply_markup
                )
            except Exception as e:
                print(f"[ERROR] Sending to Clone Owner Log Failed: {e}")

    if LOGGER_ID:
        try:
            members_count = await client.get_chat_members_count(message.chat.id)
        except:
            members_count = "Unknown"
            
        owner = await get_owner(client, message.chat.id)

        chat_link = None
        if message.chat.username:
            chat_link = f"https://t.me/{message.chat.username}"
        else:
            try:
                chat_link = await client.export_chat_invite_link(message.chat.id)
            except:
                pass

        admin_log_text = f"""
<blockquote><b>🤖 ᴄʟᴏɴᴇ ʙᴏᴛ ʟᴏɢ : @{bot.username}</b>

<b>• ʀᴇǫᴜᴇsᴛ ʙʏ : {message.from_user.mention}</b>
<b>• ǫᴜᴇʀʏ : {query}</b>
<b>• ᴄʜᴀᴛ : {message.chat.title} [<code>{message.chat.id}</code>]</b>
<b>• ᴏᴡɴᴇʀ : {owner}</b>
<b>• ᴍᴇᴍʙᴇʀs : {members_count}</b></blockquote>
"""
        buttons = []
        if chat_link:
            buttons.append([InlineKeyboardButton("ɢʀᴏᴜᴘ ʟɪɴᴋ", url=chat_link, style=ButtonStyle.PRIMARY, icon_custom_emoji_id=random.choice(PREMIUM_EMOJIS))])
        buttons.append([InlineKeyboardButton("sᴜᴘᴘᴏʀᴛ", url="https://t.me/betabot_support")])
        
        reply_markup = InlineKeyboardMarkup(buttons)

        try:
            await app.send_message(
                chat_id=LOGGER_ID,
                text=admin_log_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"[ERROR] Sending to Main Admin Log Failed: {e}")


# ====================================================
# AUTO GROUP ADD/REMOVE EVENT LOGGER
# ====================================================
def _member_status(member):
    """Return a stable lowercase status for Pyrogram/Kurigram versions."""
    status = getattr(member, "status", None)
    value = getattr(status, "value", status)
    return str(value or "").lower().split(".")[-1]


def _member_user_id(member):
    user = getattr(member, "user", None)
    return getattr(user, "id", None)


def _is_join_status(status):
    return status in {"member", "administrator", "owner"}


def _is_leave_status(status):
    # Kurigram/Pyrogram have used both ``kicked`` and ``banned`` names.
    return status in {"left", "kicked", "banned"}


async def _record_daily_activity(action: str, chat_id: int) -> None:
    """Record one unique chat action per day."""
    if action not in {"added", "removed"}:
        raise ValueError("Invalid daily activity action")

    today = datetime.now().strftime("%Y-%m-%d")
    field = f"{action}_chat_ids"

    try:
        old_stats = await daily_statsdb.find_one({"date": today}) or {}

        # 🟢 FIX: Removed conflicting fields from $setOnInsert
        # $addToSet will automatically create the array if it doesn't exist!
        update = {
            "$setOnInsert": {
                "date": today,
            },
            "$addToSet": {
                field: int(chat_id),
            },
        }

        # Preserve old $inc-based counters that may already exist today.
        if action not in old_stats and isinstance(old_stats.get(action), int):
            update["$set"] = {
                f"legacy_{action}": old_stats[action]
            }

        await daily_statsdb.update_one(
            {"date": today},
            update,
            upsert=True,
        )
    except Exception:
        # Stats failure must not stop group add/remove logging.
        LOGGER.warning(
            "Could not update daily group statistics",
            exc_info=True,
        )

@app.on_chat_member_updated(filters.group, group=1)
async def auto_group_logger(client: Client, message: ChatMemberUpdated):
    try:
        bot = await client.get_me()

        old_member = getattr(message, "old_chat_member", None)
        new_member = getattr(message, "new_chat_member", None)
        # On a leave/kick Telegram reports the bot in old_chat_member. On an
        # add it reports it in new_chat_member. Checking both fixes the old
        # implementation which could never log removals reliably.
        member = new_member if _member_user_id(new_member) == bot.id else old_member
        if _member_user_id(member) != bot.id:
            return

        old_status = _member_status(old_member)
        new_status = _member_status(new_member)
        was_added = _is_join_status(new_status) and not _is_join_status(old_status)
        was_removed = _is_leave_status(new_status) and not _is_leave_status(old_status)
        if not (was_added or was_removed):
            return
        
        chat = message.chat
        action_by = message.from_user

        if was_added:
            await _record_daily_activity("added", chat.id)
            # The welcome handler also performs this operation, but the
            # database helper is idempotent and this keeps BData correct even
            # if the welcome handler was skipped.
            try:
                await add_served_chat(chat.id)
            except Exception:
                LOGGER.warning("Could not save newly joined chat", exc_info=True)
        else:
            await _record_daily_activity("removed", chat.id)
            try:
                await delete_served_chat(chat.id)
            except Exception:
                LOGGER.warning("Could not remove departed chat", exc_info=True)

        # This handler belongs to the main app. Clone handlers use their own
        # plugin instance and their own logger below.
        target_logger = LOGGER_ID
        if not target_logger:
            return
        
        try:
            members_count = await client.get_chat_members_count(chat.id)
        except:
            members_count = "Unknown"

        owner = await get_owner(client, chat.id)
        action_by_mention = action_by.mention if action_by else "<b>Unknown User</b>"
        bot_details = app.mention
        chat_title = html.escape(chat.title or "Unknown", quote=True)
        
        # Image URL
        log_image = "https://files.catbox.moe/10zwqs.jpg"

        # Group Link Fetching Logic for Button
        chat_link = None
        if chat.username:
            chat_link = f"https://t.me/{chat.username}"
        elif new_status in {"administrator", "owner"}:
            try:
                chat_link = await client.export_chat_invite_link(chat.id)
            except:
                pass

        # Button Setup
        reply_markup = None
        if chat_link:
            buttons = [
                [InlineKeyboardButton("🔗 ɢʀᴏᴜᴘ ʟɪɴᴋ", url=chat_link)]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)

        # 🟢 CONDITION 1: Added to Group
        if was_added:
            log_caption = f"""
#Added
<blockquote><b>✅ ʙᴏᴛ ᴀᴅᴅᴇᴅ ᴛᴏ ɢʀᴏᴜᴘ</b>

<b>• ʙᴏᴛ : {bot_details}</b>
<b>• ᴀᴅᴅᴇᴅ ʙʏ : {action_by_mention}</b>
<b>• ᴄʜᴀᴛ : {chat_title} [<code>{chat.id}</code>]</b>
<b>• ᴏᴡɴᴇʀ : {owner}</b>
<b>• ᴍᴇᴍʙᴇʀs : {members_count}</b></blockquote>
"""
            await client.send_photo(
                chat_id=target_logger,
                photo=log_image,
                caption=log_caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        # 🔴 CONDITION 2: Removed from Group
        elif was_removed:
            log_caption = f"""
#Removed
<blockquote><b>❌ ʙᴏᴛ ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ ɢʀᴏᴜᴘ</b>

<b>• ʙᴏᴛ : {bot_details}</b>
<b>• ʀᴇᴍᴏᴠᴇᴅ ʙʏ : {action_by_mention}</b>
<b>• ᴄʜᴀᴛ : {chat_title} [<code>{chat.id}</code>]</b>
<b>• ᴏᴡɴᴇʀ : {owner}</b>
<b>• ᴍᴇᴍʙᴇʀs : {members_count}</b></blockquote>
"""
            await client.send_photo(
                chat_id=target_logger,
                photo=log_image,
                caption=log_caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

    except Exception as e:
        LOGGER.error("Auto Group Logger Failed", exc_info=True)


# ====================================================
# AUTOPLAY LOGS 
# ====================================================
async def autoplay_log(client, chat_id, query, vibe="Unknown", is_clone=False, clone_logger_id=None):
    if not await is_on_off(2):
        return
        
    try:
        bot = await client.get_me()
        bot_mention = bot.mention
    except:
        return

    try:
        chat = await client.get_chat(chat_id)
        chat_title = chat.title
        chat_username = chat.username
    except:
        chat_title = "Unknown Chat"
        chat_username = None

    try:
        members_count = await client.get_chat_members_count(chat_id)
    except:
        members_count = "Unknown"
        
    owner = await get_owner(client, chat_id)

    chat_link = None
    if chat_username:
        chat_link = f"https://t.me/{chat_username}"
    else:
        try:
            chat_link = await client.export_chat_invite_link(chat_id)
        except:
            pass

    if is_clone and clone_logger_id:
        owner_autoplay_text = f"""
<b><a href="https://t.me/{bot.username}">{bot.first_name}</a> ᴀᴜᴛᴏᴘʟᴀʏ ʟᴏɢ</b>

<b>• ᴀᴄᴛɪᴏɴ : ᴀᴜᴛᴏᴘʟᴀʏ ᴛʀɪɢɢᴇʀᴇᴅ 🔄</b>
<b>• ᴛʀᴀᴄᴋ :</b> {query}
<b>• ᴠɪʙᴇ :</b> {vibe}
<b>• ᴄʜᴀᴛ :</b> {chat_title} [<code>{chat_id}</code>]
"""
        owner_reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("sᴜᴘᴘᴏʀᴛ", url="https://t.me/betabot_support")]]
        )

        if chat_id != int(clone_logger_id):
            try:
                await client.send_message(
                    chat_id=int(clone_logger_id),
                    text=owner_autoplay_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=owner_reply_markup
                )
            except Exception as e:
                print(f"[ERROR] Sending to Clone Owner Autoplay Log Failed: {e}")

    if is_clone:
        header_text = f"🤖 <b>ᴄʟᴏɴᴇ ᴀᴜᴛᴏᴘʟᴀʏ ʟᴏɢ : @{bot.username}</b>"
    else:
        header_text = f"<b>{bot_mention} ᴀᴜᴛᴏᴘʟᴀʏ ʟᴏɢ</b>"

    logger_text = f"""
<blockquote>{header_text}

<b>• ᴀᴄᴛɪᴏɴ : ᴀᴜᴛᴏᴘʟᴀʏ ᴛʀɪɢɢᴇʀᴇᴅ 🔄</b>
<b>• ᴛʀᴀᴄᴋ : {query}</b>
<b>• ᴠɪʙᴇ : {vibe}</b>
<b>• ᴄʜᴀᴛ : {chat_title} [<code>{chat_id}</code>]</b>
<b>• ᴏᴡɴᴇʀ : {owner}</b>
<b>• ᴍᴇᴍʙᴇʀs : {members_count}</b></blockquote>
"""
    buttons = []
    if chat_link:
        buttons.append([InlineKeyboardButton("ɢʀᴏᴜᴘ ʟɪɴᴋ", url=chat_link, style=ButtonStyle.SUCCESS, icon_custom_emoji_id=random.choice(PREMIUM_EMOJIS))])
    buttons.append([InlineKeyboardButton("sᴜᴘᴘᴏʀᴛ", url="https://t.me/betabot_support")])
    
    reply_markup = InlineKeyboardMarkup(buttons)

    if chat_id != LOGGER_ID:
        try:
            await app.send_message(
                chat_id=LOGGER_ID,
                text=logger_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"[ERROR] Sending Autoplay Log Failed: {e}")
