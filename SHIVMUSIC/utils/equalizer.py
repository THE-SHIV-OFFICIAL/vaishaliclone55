"""
Equalizer + Volume engine shared by the MAIN bot and every CLONE bot.

- Presets are plain ffmpeg audio filters, applied through py-tgcalls
  ``ffmpeg_parameters`` (see Call._with_eq in core/call.py).
- State is per chat (in memory). Changing a preset restarts the stream
  from the same time-stamp, so the song does not start again.
- The handlers at the bottom are client-agnostic: the main bot registers
  them in plugins/admins/equalizer.py and clones in cplugin/equalizer.py.
"""
import asyncio

from pyrogram.enums import ChatMemberStatus
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

try:  # kurigram exposes coloured buttons
    from pyrogram.enums import ButtonStyle
except Exception:  # pragma: no cover - older pyrogram
    ButtonStyle = None

EQ_EMOJI = 6100384213649855022  # ❄️ premium emoji (player button + panel title)

EQ_PRESETS = {
    "off":       ("ɴᴏʀᴍᴀʟ",        ""),
    "clear":     ("ᴄʟᴇᴀʀ ᴀᴜᴅɪᴏ",   "highpass=f=60,equalizer=f=1000:t=q:w=1:g=3,equalizer=f=3500:t=q:w=1:g=4,dynaudnorm=f=200"),
    "dj":        ("ᴅᴊ ʙᴀss",       "bass=g=12:f=70:w=0.6,treble=g=4,acompressor=ratio=3,dynaudnorm=f=150"),
    "bass":      ("ʙᴀss ʙᴏᴏsᴛ",    "bass=g=9:f=90:w=0.5"),
    "deep":      ("ᴅᴇᴇᴘ ʙᴀss",     "bass=g=15:f=55:w=0.7,lowpass=f=12000"),
    "8d":        ("8ᴅ ᴀᴜᴅɪᴏ",      "apulsator=hz=0.09,stereotools=mlev=0.05,bass=g=4"),
    "lofi":      ("ʟᴏ-ғɪ",         "highpass=f=200,lowpass=f=3500,acompressor=ratio=4,aecho=0.8:0.85:60:0.25"),
    "vocal":     ("ᴠᴏᴄᴀʟ",         "highpass=f=120,equalizer=f=2500:t=q:w=2:g=6,dynaudnorm=f=200"),
    "treble":    ("ᴛʀᴇʙʟᴇ",        "treble=g=10:f=4000"),
    "soft":      ("sᴏғᴛ",          "volume=0.8,lowpass=f=8000"),
    "party":     ("ᴘᴀʀᴛʏ",         "bass=g=8,treble=g=6,extrastereo=m=2.0,dynaudnorm=f=150"),
    "nightcore": ("ɴɪɢʜᴛᴄᴏʀᴇ",     "asetrate=48000*1.25,aresample=48000,atempo=1.0"),
    "slowed":    ("sʟᴏᴡᴇᴅ+ʀᴇᴠᴇʀʙ", "asetrate=48000*0.85,aresample=48000,aecho=0.8:0.88:60:0.4"),
}

EQ_STATE = {}
VOLUME_STATE = {}
MIN_VOLUME = 0
DEFAULT_VOLUME = 50
MAX_VOLUME = 1000
_BUSY = set()


def _cid(chat_id):
    try:
        return int(chat_id)
    except Exception:
        return chat_id


def get_eq_filter(preset) -> str:
    data = EQ_PRESETS.get(str(preset))
    return data[1] if data else ""


def get_eq_name(preset) -> str:
    data = EQ_PRESETS.get(str(preset))
    return data[0] if data else EQ_PRESETS["off"][0]


def get_chat_eq(chat_id) -> str:
    return EQ_STATE.get(_cid(chat_id), "off")


def get_chat_eq_filter(chat_id) -> str:
    return get_eq_filter(get_chat_eq(chat_id))


def set_chat_eq(chat_id, preset):
    chat_id = _cid(chat_id)
    preset = str(preset)
    if preset not in EQ_PRESETS or preset == "off":
        EQ_STATE.pop(chat_id, None)
    else:
        EQ_STATE[chat_id] = preset


def get_chat_volume(chat_id) -> int:
    try:
        value = int(VOLUME_STATE.get(_cid(chat_id), DEFAULT_VOLUME))
    except Exception:
        value = DEFAULT_VOLUME
    return max(MIN_VOLUME, min(MAX_VOLUME, value))


def set_chat_volume(chat_id, volume):
    VOLUME_STATE[_cid(chat_id)] = max(MIN_VOLUME, min(MAX_VOLUME, int(volume)))


def reset_chat_audio(chat_id):
    set_chat_eq(chat_id, "off")
    set_chat_volume(chat_id, DEFAULT_VOLUME)


def get_chat_volume_filter(chat_id) -> str:
    volume = get_chat_volume(chat_id)
    if volume == DEFAULT_VOLUME:
        return ""
    return f"volume={volume / DEFAULT_VOLUME:.2f}"


def next_volume(current: int, action: str) -> int:
    if action == "up":
        new = current + 50
    elif action == "down":
        new = current - 25
    elif action == "boost":
        new = current + 500
    else:
        new = DEFAULT_VOLUME
    return max(MIN_VOLUME, min(MAX_VOLUME, new))


def build_audio_filter(chat_id) -> str:
    """Return the full ffmpeg -af chain for a chat ('' when nothing to apply)."""
    parts = []
    eq = get_chat_eq_filter(chat_id)
    if eq:
        parts.append(eq)
    vol = get_chat_volume_filter(chat_id)
    if vol:
        parts.append(vol)
    return ",".join(parts)


# ----------------------------------------------------------------- buttons
def _btn(text, cb, style=None, emoji=None):
    kwargs = {"text": text, "callback_data": cb}
    if ButtonStyle is not None and style is not None:
        kwargs["style"] = getattr(ButtonStyle, style, None) or ButtonStyle.PRIMARY
    if emoji:
        kwargs["icon_custom_emoji_id"] = int(emoji)
    try:
        return InlineKeyboardButton(**kwargs)
    except TypeError:  # library without style/emoji support
        return InlineKeyboardButton(text=text, callback_data=cb)


def _close_text(_):
    try:
        return _["CLOSE_BUTTON"]
    except Exception:
        return "ᴄʟᴏsᴇ"


def equalizer_markup(_, chat_id):
    current = get_chat_eq(chat_id)
    rows, row = [], []
    for key, (name, _f) in EQ_PRESETS.items():
        on = key == current
        row.append(_btn(f"{name} · ᴏɴ" if on else name, f"EqSet {chat_id}|{key}",
                        "SUCCESS" if on else "PRIMARY", 5217933090483098080))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([_btn(f"ᴠᴏʟᴜᴍᴇ · {get_chat_volume(chat_id)}%", f"VolumePanel {chat_id}", "PRIMARY", 5258389041006518073)])
    rows.append([_btn(_close_text(_), "close", "DANGER", 6271611232457855630)])
    return InlineKeyboardMarkup(rows)


def volume_markup(_, chat_id):
    volume = get_chat_volume(chat_id)
    return InlineKeyboardMarkup([
        [
            _btn("ᴠᴏʟ +50", f"VolumeSet {chat_id}|up", "SUCCESS", 5258389041006518073),
            _btn("ᴠᴏʟ -25", f"VolumeSet {chat_id}|down", "DANGER", 5891211339170326418),
        ],
        [_btn(f"ʙᴏᴏsᴛ +500 · {volume}%", f"VolumeSet {chat_id}|boost", "PRIMARY", 6100220081474639964)],
        [_btn("ʀᴇsᴇᴛ · ɴᴏʀᴍᴀʟ ᴇǫ · 50%", f"AudioReset {chat_id}", "SUCCESS", 6280269890821558384)],
        [_btn("ʙᴀᴄᴋ ᴛᴏ ᴇǫ", f"VolumeBack {chat_id}", "PRIMARY", 5352759161945867747)],
        [_btn(_close_text(_), "close", "DANGER", 6271611232457855630)],
    ])


def panel_text(chat_id) -> str:
    return (
        f"<blockquote><b><tg-emoji emoji-id=\"{EQ_EMOJI}\">❄️</tg-emoji> "
        "єǫυᴧʟɪᴢєʀ ᴘᴧηєʟ</b>\n│\n"
        f"├ <b>ᴄυʀʀєηᴛ :</b> <code>{get_eq_name(get_chat_eq(chat_id))}</code>\n"
        f"├ <b>ᴠσʟυϻє :</b> <code>{get_chat_volume(chat_id)}%</code>\n"
        "└ <b>ᴘɪᴄᴋ ᴧη єғғєᴄᴛ — ᴛʀᴧᴄᴋ ᴋєєᴘs ᴘʟᴧʏɪηɢ ғʀσϻ ᴛʜє sᴧϻє ᴛɪϻє, ησ ʀєsᴛᴧʀᴛ.</b></blockquote>"
    )


def volume_panel_text(chat_id) -> str:
    return (
        "<blockquote><b><tg-emoji emoji-id=\"5258389041006518073\">🔊</tg-emoji> "
        "ᴠσʟυϻє ᴄσηᴛʀσʟ</b>\n│\n"
        f"├ <b>ᴄυʀʀєηᴛ ʟєᴠєʟ :</b> <code>{get_chat_volume(chat_id)}%</code>\n"
        "└ <b>+50 / -25 · ʙσσsᴛ +500 · ϻᴧx 1000%</b></blockquote>"
    )


# ---------------------------------------------------------------- handlers
async def _lang(chat_id):
    try:
        from SHIVMUSIC.utils.database import get_lang
        from strings import get_string
        return get_string(await get_lang(chat_id))
    except Exception:
        return {"CLOSE_BUTTON": "ᴄʟᴏsᴇ"}


async def can_control(client, chat_id, user_id) -> bool:
    """Sudo / non-admin mode / auth user / admin of the chat."""
    try:
        from SHIVMUSIC.misc import SUDOERS
        if user_id in SUDOERS:
            return True
    except Exception:
        pass
    try:
        from SHIVMUSIC.utils.database import is_nonadmin_chat
        if await is_nonadmin_chat(chat_id):
            return True
    except Exception:
        pass
    try:
        from config import adminlist
        if user_id in (adminlist.get(chat_id) or []):
            return True
    except Exception:
        pass
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


def _is_playing(chat_id) -> bool:
    from SHIVMUSIC.misc import db
    return bool(db.get(_cid(chat_id)))


async def _restart_audio(chat_id, preset=None):
    """Re-apply filters to the running stream (same time-stamp)."""
    from SHIVMUSIC.core.call import ANJALI
    if preset is None:
        await ANJALI.volume_stream(chat_id)
    else:
        await ANJALI.equalizer_stream(chat_id, preset)


async def handle_eq_command(client, message):
    chat_id = message.chat.id
    _ = await _lang(chat_id)
    if not _is_playing(chat_id):
        return await message.reply_text("❌ ɴᴏᴛʜɪɴɢ ɪs ᴘʟᴀʏɪɴɢ ʀɪɢʜᴛ ɴᴏᴡ.")
    if message.from_user and not await can_control(client, chat_id, message.from_user.id):
        return await message.reply_text("❌ ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴜsᴇ ᴛʜᴇ ᴇǫᴜᴀʟɪᴢᴇʀ.")
    return await message.reply_text(panel_text(chat_id), reply_markup=equalizer_markup(_, chat_id))


async def _safe_edit(cq, text, markup):
    try:
        await cq.edit_message_text(text, reply_markup=markup)
    except Exception:
        pass


async def handle_eq_callback(client, cq):
    data = cq.data or ""
    try:
        action, rest = data.split(None, 1)
    except ValueError:
        return await cq.answer()
    arg = None
    if "|" in rest:
        rest, arg = rest.split("|", 1)
    try:
        chat_id = int(rest)
    except ValueError:
        return await cq.answer()

    if not await can_control(client, chat_id, cq.from_user.id):
        return await cq.answer("❌ ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴜsᴇ ᴛʜɪs.", show_alert=True)
    _ = await _lang(chat_id)

    if action == "EqPanel":
        if not _is_playing(chat_id):
            return await cq.answer("❌ ɴᴏᴛʜɪɴɢ ɪs ᴘʟᴀʏɪɴɢ.", show_alert=True)
        await cq.answer("❄️ ᴇǫᴜᴀʟɪᴢᴇʀ")
        # Panel opens as a new message so the player card stays untouched.
        return await cq.message.reply_text(panel_text(chat_id), reply_markup=equalizer_markup(_, chat_id))

    if action in ("VolumePanel",):
        await cq.answer("🔊 ᴠᴏʟᴜᴍᴇ")
        return await _safe_edit(cq, volume_panel_text(chat_id), volume_markup(_, chat_id))

    if action == "VolumeBack":
        await cq.answer()
        return await _safe_edit(cq, panel_text(chat_id), equalizer_markup(_, chat_id))

    if chat_id in _BUSY:
        return await cq.answer("⏳ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ, ᴀᴘᴘʟʏɪɴɢ...", show_alert=False)

    if action == "EqSet":
        preset = arg if arg in EQ_PRESETS else "off"
        if not _is_playing(chat_id):
            set_chat_eq(chat_id, preset)
            await cq.answer(f"❄️ {get_eq_name(preset)} sᴀᴠᴇᴅ")
            return await _safe_edit(cq, panel_text(chat_id), equalizer_markup(_, chat_id))
        _BUSY.add(chat_id)
        try:
            await _restart_audio(chat_id, preset)
        except Exception as exc:
            return await cq.answer(f"❌ ғᴀɪʟᴇᴅ: {str(exc)[:150]}", show_alert=True)
        finally:
            _BUSY.discard(chat_id)
        await cq.answer(f"❄️ {get_eq_name(preset)} ᴀᴘᴘʟɪᴇᴅ")
        return await _safe_edit(cq, panel_text(chat_id), equalizer_markup(_, chat_id))

    if action in ("VolumeSet", "AudioReset"):
        if action == "AudioReset":
            reset_chat_audio(chat_id)
            note = "🔄 ɴᴏʀᴍᴀʟ · 50%"
        else:
            set_chat_volume(chat_id, next_volume(get_chat_volume(chat_id), arg or ""))
            note = f"🔊 ᴠᴏʟᴜᴍᴇ: {get_chat_volume(chat_id)}%"
        if _is_playing(chat_id):
            _BUSY.add(chat_id)
            try:
                await _restart_audio(chat_id, None)
            except Exception as exc:
                return await cq.answer(f"❌ ғᴀɪʟᴇᴅ: {str(exc)[:150]}", show_alert=True)
            finally:
                _BUSY.discard(chat_id)
        await cq.answer(note)
        if action == "AudioReset":
            return await _safe_edit(cq, panel_text(chat_id), equalizer_markup(_, chat_id))
        return await _safe_edit(cq, volume_panel_text(chat_id), volume_markup(_, chat_id))

    return await cq.answer()


EQ_CALLBACK_REGEX = r"^(EqPanel|EqSet|VolumePanel|VolumeSet|VolumeBack|AudioReset) "
EQ_COMMANDS = ["eq", "equalizer", "ceq", "cequalizer"]
