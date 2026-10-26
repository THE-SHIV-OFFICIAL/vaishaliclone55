import time
import random
import asyncio
import logging

from pyrogram import filters
from pyrogram.enums import ChatType, ChatAction, ButtonStyle
from pyrogram.types import InlineKeyboardMarkup, Message, InlineKeyboardButton
from youtubesearchpython.__future__ import VideosSearch

import config
from SHIVMUSIC import app
from SHIVMUSIC.misc import _boot_
from SHIVMUSIC.plugins.sudo.sudoers import sudoers_list
from SHIVMUSIC.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_lang,
    is_banned_user,
    is_on_off,
)
from SHIVMUSIC.utils.decorators.language import LanguageStart
from SHIVMUSIC.utils.formatters import get_readable_time
from SHIVMUSIC.utils.inline import help_pannel, private_panel, start_panel
from config import BANNED_USERS, START_IMG_URL, CMBOT
from strings import get_string


LOGGER = logging.getLogger(__name__)

PREMIUM_EMOJIS = [
    "5258362837411045098", "6102938383456146362",
    "5463274047771000031", "6100397162976252509",
    "5373310679241466020", "5408916593780470262",
    "5776182936638329359", "5258389041006518073",
    "6280269890821558384", "5936143551854285132",
    "6172332822892647766", "5891211339170326418",
    "5409368076447657845", "6172312314423808834",
    "6082387600599944892", "6271537028307881531",
]

EFFECT_ID = [
    5046509860389126442,
    5107584321108051014,
    5104841245755180586,
    5159385139981059251,
]


def get_style_map():
    styles = [ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER]
    random.shuffle(styles)
    return {1: styles[0], 2: styles[1], 3: styles[2]}


def create_btn(
    text,
    cb=None,
    url=None,
    user_id=None,
    style=ButtonStyle.PRIMARY,
    no_emoji=False,
):
    kwargs = {"text": text, "style": style}

    if cb:
        kwargs["callback_data"] = cb
    if url:
        kwargs["url"] = url
    if user_id:
        kwargs["user_id"] = user_id
    if not no_emoji:
        kwargs["icon_custom_emoji_id"] = int(random.choice(PREMIUM_EMOJIS))

    return InlineKeyboardButton(**kwargs)


def _as_list(value):
    """Config value ko safely list me badalta hai."""
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split() if item.strip()]
    try:
        return [item for item in value if item]
    except TypeError:
        return [value]


async def _reply_photo_with_fallback(message, photos, caption, reply_markup=None):
    """Photo URL fail ho to agla photo, phir plain text bhejta hai."""
    for photo in photos:
        try:
            return await message.reply_photo(
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
            )
        except Exception as exc:
            LOGGER.warning("Start photo send failed: %s", exc)

    return await message.reply_text(
        caption,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )


async def _send_start_media(
    message,
    caption,
    reply_markup=None,
    prefer_video=False,
):
    """Pehle configured video, phir photo, aur aakhir me text fallback."""
    if prefer_video:
        video_url = getattr(config, "START_VIDEO_URL", "")
        video_urls = _as_list(video_url)

        if video_urls:
            try:
                return await message.reply_video(
                    video=random.choice(video_urls),
                    caption=caption,
                    reply_markup=reply_markup,
                )
            except Exception as exc:
                LOGGER.warning("Start video send failed; trying photo fallback: %s", exc)

    images = _as_list(START_IMG_URL)
    if images:
        random.shuffle(images)

    return await _reply_photo_with_fallback(
        message=message,
        photos=images,
        caption=caption,
        reply_markup=reply_markup,
    )


@app.on_message(filters.command(["start"]) & filters.private & ~BANNED_USERS)
@LanguageStart
async def start_pm(client, message: Message, _):
    try:
        loading_1 = await message.reply_text(random.choice(CMBOT))
        await add_served_user(message.from_user.id)

        loading_messages = [
            "<b><tg-emoji emoji-id='5373310679241466020'>🌀</tg-emoji> ᴌᴏᴀᴅɪɴɢ....</b>",
            "<b><tg-emoji emoji-id='5891211339170326418'>⌛️</tg-emoji> ꜱᴛᴀʀᴛɪɴɢ..ʙᴀʙʏ.❤️❤️</b>",
            "<b><tg-emoji emoji-id='5355051922862653659'>🤖</tg-emoji> ɪ ᴀᴍ ᴀʟɪᴠᴇ ʙᴀʙʏ❤️😌🫣🫣</b>",
            "<b><tg-emoji emoji-id='6172312314423808834'>✨</tg-emoji> BETA ʙᴏᴛs🫣🫣.</b>",
        ]

        for loading_text in loading_messages:
            try:
                await loading_1.edit_text(loading_text)
            except Exception as exc:
                LOGGER.warning("Start loading animation failed: %s", exc)
                break
            await asyncio.sleep(0.3)

        try:
            await loading_1.delete()
        except Exception:
            pass

    except Exception as exc:
        LOGGER.warning("Could not show start loading animation: %s", exc)

    command_text = message.text or ""
    parts = command_text.split(maxsplit=1)

    if len(parts) > 1:
        name = parts[1]

        if name.startswith("help"):
            keyboard = help_pannel(_)
            await app.send_chat_action(message.chat.id, ChatAction.TYPING)

            try:
                await message.reply_sticker(
                    "CAACAgUAAxkBAAFJgZ1qBGwx9Z9vW5BhG3dw0l1A5j4CyQACXRYAAuc-wVWs4--9DGlDKzsE"
                )
            except Exception as exc:
                LOGGER.warning("Help sticker send failed: %s", exc)

            return await _send_start_media(
                message=message,
                caption=_["help_1"].format(config.SUPPORT_CHAT),
                reply_markup=keyboard,
                prefer_video=False,
            )

        if name.startswith("sud"):
            await sudoers_list(client=client, message=message, _=_)

            if await is_on_off(2):
                return await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=(
                        f"<tg-emoji emoji-id='6172312314423808834'>✨</tg-emoji> "
                        f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ "
                        f"ᴛᴏ ᴄʜᴇᴄᴋ <b>sᴜᴅᴏʟɪsᴛ</b>.\n\n"
                        f"<tg-emoji emoji-id='5258362837411045098'>👤</tg-emoji> "
                        f"<b>ᴜsᴇʀ ɪᴅ ➠</b> <code>{message.from_user.id}</code>\n\n"
                        f"<tg-emoji emoji-id='6235576525563895420'>📍</tg-emoji> "
                        f"<b>ᴜsᴇʀɴᴀᴍᴇ ➠</b> @{message.from_user.username}"
                    ),
                )
            return

        if name.startswith("inf"):
            info_message = await message.reply_text(
                "<tg-emoji emoji-id='5429571366384842791'>🔎</tg-emoji>"
            )

            query_id = name.replace("info_", "", 1)
            query = f"https://www.youtube.com/watch?v={query_id}"

            try:
                results = VideosSearch(query, limit=1)
                search_data = await results.next()

                if not search_data or not search_data.get("result"):
                    return await info_message.edit_text(
                        "<tg-emoji emoji-id='6271611232457855630'>❌</tg-emoji> "
                        "Track details not found. The video might be restricted or deleted."
                    )

                result = search_data["result"][0]
                title = result.get("title") or "Unknown Title"
                duration = result.get("duration") or "Unknown Duration"

                view_data = result.get("viewCount") or {}
                views = view_data.get("short", "0") if isinstance(view_data, dict) else "0"

                thumbnails = result.get("thumbnails") or []
                thumbnail = None
                if thumbnails and isinstance(thumbnails[0], dict):
                    thumbnail = thumbnails[0].get("url")
                    if thumbnail:
                        thumbnail = thumbnail.split("?")[0]

                channel_data = result.get("channel") or {}
                channellink = channel_data.get("link", "")
                channel = channel_data.get("name") or "Unknown Channel"
                link = result.get("link") or query
                published = result.get("publishedTime") or "Unknown Date"

                searched_text = _["start_6"].format(
                    title,
                    duration,
                    views,
                    published,
                    channellink,
                    channel,
                    app.mention,
                )

                style_map = get_style_map()
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            create_btn(
                                text=_["S_B_8"],
                                url=link,
                                style=style_map[2],
                            ),
                            create_btn(
                                text=_["S_B_9"],
                                url=config.SUPPORT_CHAT,
                                style=style_map[2],
                            ),
                        ],
                    ]
                )

                try:
                    await info_message.delete()
                except Exception:
                    pass

                photo_candidates = []
                if thumbnail:
                    photo_candidates.append(thumbnail)
                photo_candidates.extend(_as_list(START_IMG_URL))

                await _reply_photo_with_fallback(
                    message=message,
                    photos=photo_candidates,
                    caption=searched_text,
                    reply_markup=keyboard,
                )

                if await is_on_off(2):
                    return await app.send_message(
                        chat_id=config.LOGGER_ID,
                        text=(
                            f"<tg-emoji emoji-id='6172312314423808834'>✨</tg-emoji> "
                            f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ "
                            f"ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>ᴛʀᴀᴄᴋ ɪɴғᴏʀᴍᴀᴛɪᴏɴ</b>.\n\n"
                            f"<tg-emoji emoji-id='5258362837411045098'>👤</tg-emoji> "
                            f"<b>ᴜsᴇʀ ɪᴅ ➠</b> <code>{message.from_user.id}</code>\n\n"
                            f"<tg-emoji emoji-id='6235576525563895420'>📍</tg-emoji> "
                            f"<b>ᴜsᴇʀɴᴀᴍᴇ ➠</b> @{message.from_user.username}"
                        ),
                    )

            except Exception as exc:
                LOGGER.exception("Track info handler failed")
                try:
                    return await info_message.edit_text(
                        f"❌ Track info fetch nahi ho payi: `{exc}`"
                    )
                except Exception:
                    return await message.reply_text(
                        "❌ Track info fetch nahi ho payi. Dobara try karein."
                    )

    keyboard = private_panel(_)
    await app.send_chat_action(message.chat.id, ChatAction.TYPING)

    try:
        await message.reply_sticker(
            "CAACAgUAAxkBAAFJgZ1qBGwx9Z9vW5BhG3dw0l1A5j4CyQACXRYAAuc-wVWs4--9DGlDKzsE"
        )
    except Exception as exc:
        LOGGER.warning("Start sticker send failed: %s", exc)

    await _send_start_media(
        message=message,
        caption=_["start_2"].format(message.from_user.mention, app.mention),
        reply_markup=InlineKeyboardMarkup(keyboard),
        prefer_video=True,
    )

    if await is_on_off(2):
        return await app.send_message(
            chat_id=config.LOGGER_ID,
            text=(
                f"<tg-emoji emoji-id='6172312314423808834'>✨</tg-emoji> "
                f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ.\n\n"
                f"<tg-emoji emoji-id='5258362837411045098'>👤</tg-emoji> "
                f"<b>ᴜsᴇʀ ɪᴅ ➠</b> <code>{message.from_user.id}</code>\n\n"
                f"<tg-emoji emoji-id='6235576525563895420'>📍</tg-emoji> "
                f"<b>ᴜsᴇʀɴᴀᴍᴇ ➠</b> @{message.from_user.username}"
            ),
        )


@app.on_message(filters.command(["start"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def start_gp(client, message: Message, _):
    keyboard = start_panel(_)
    uptime = int(time.time() - _boot_)

    await _send_start_media(
        message=message,
        caption=_["start_1"].format(
            app.mention,
            get_readable_time(uptime),
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        prefer_video=True,
    )

    return await add_served_chat(message.chat.id)


@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    for member in message.new_chat_members:
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)

            if await is_banned_user(member.id):
                try:
                    await message.chat.ban_member(member.id)
                except Exception:
                    pass

            if member.id == app.id:
                if message.chat.type != ChatType.SUPERGROUP:
                    await message.reply_text(_["start_4"])
                    return await app.leave_chat(message.chat.id)

                if message.chat.id in await blacklisted_chats():
                    await message.reply_text(
                        _["start_5"].format(
                            app.mention,
                            f"https://t.me/{app.username}?start=sudolist",
                            config.SUPPORT_CHAT,
                        ),
                        disable_web_page_preview=True,
                    )
                    return await app.leave_chat(message.chat.id)

                keyboard = start_panel(_)
                await message.reply_text(
                    text=_["start_3"].format(
                        message.from_user.mention,
                        app.mention,
                        message.chat.title,
                        app.mention,
                    ),
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
                await add_served_chat(message.chat.id)
                await message.stop_propagation()

        except Exception:
            LOGGER.exception("Welcome handler failed")
