# 🎛 Player UI helpers: Thumbnail ON/OFF sender + live button label refresh
import asyncio

from SHIVMUSIC.utils.database import is_thumb_on, autoplay_label, thumb_label

# Invisible marker placed at the end of `stream_1` in strings/langs/*.yml.
# It is replaced with the Volume + By lines (so the card reads
# Title → Time → RQ → Volume → By) without changing every caller.
CAPTION_MARKER = "\u2063"


def _bot_mention(client):
    mention = getattr(client, "mention", None)
    if isinstance(mention, str) and mention:
        return mention
    me = getattr(client, "me", None)
    if me is not None:
        try:
            return me.mention
        except Exception:
            name = getattr(me, "first_name", None) or "Bot"
            return f"<a href=\"tg://user?id={me.id}\">{name}</a>"
    return "ᴍᴜsɪᴄ ʙᴏᴛ"


def finalize_caption(caption, chat_id=None, client=None):
    if not caption or CAPTION_MARKER not in caption:
        return caption
    try:
        from SHIVMUSIC.utils.equalizer import get_chat_volume, get_chat_eq, get_eq_name
        volume = get_chat_volume(chat_id) if chat_id is not None else 50
        mood = get_eq_name(get_chat_eq(chat_id)) if chat_id is not None else get_eq_name("off")
    except Exception:
        volume, mood = 50, "ɴᴏʀᴍᴀʟ"
    extra = (
        f"\n❍ <tg-emoji emoji-id=\"6100384213649855022\">❄️</tg-emoji> <b>єǫ ➥</b> {mood}"
        f"\n❍ <tg-emoji emoji-id=\"5258389041006518073\">🔊</tg-emoji> <b>ᴠσʟυϻє ➥</b> {volume}%"
        f"\n❍ <tg-emoji emoji-id=\"5409025823388741707\">🤖</tg-emoji> <b>ʙʏ ➥</b> {_bot_mention(client)}"
    )
    return caption.replace(CAPTION_MARKER, extra, 1).replace(CAPTION_MARKER, "")


async def send_player(client, chat_id=None, photo=None, caption=None, reply_markup=None, **kwargs):
    """Thumbnail ON -> photo card, OFF -> sirf text + buttons. Card auto-deletes after 24h."""
    caption = finalize_caption(caption, chat_id, client)
    msg = None
    if await is_thumb_on(chat_id):
        try:
            msg = await client.send_photo(chat_id=chat_id, photo=photo, caption=caption, reply_markup=reply_markup, **kwargs)
        except Exception:
            msg = None  # photo fail -> text fallback
    if msg is None:
        msg = await client.send_message(
            chat_id=chat_id, text=caption or "\u200b", reply_markup=reply_markup, disable_web_page_preview=True
        )
    if msg is not None:
        try:
            from SHIVMUSIC.utils.playmsg_cleaner import track_play_message
            asyncio.create_task(track_play_message(client, msg.chat.id, msg.id))
        except Exception:
            pass
    return msg


async def refresh_player_buttons(CallbackQuery, chat_id):
    """Message ke existing keyboard me Autoplay / Thumbnail labels update karo."""
    try:
        markup = CallbackQuery.message.reply_markup
        if not markup or not getattr(markup, "inline_keyboard", None):
            return
        changed = False
        for row in markup.inline_keyboard:
            for btn in row:
                cb = getattr(btn, "callback_data", None) or ""
                if isinstance(cb, bytes):
                    cb = cb.decode(errors="ignore")
                if cb.startswith("ADMIN Autoplay|"):
                    btn.text = autoplay_label(chat_id); changed = True
                elif cb.startswith("ADMIN Thumbnail|"):
                    btn.text = thumb_label(chat_id); changed = True
        if changed:
            await CallbackQuery.edit_message_reply_markup(reply_markup=markup)
    except Exception:
        pass
