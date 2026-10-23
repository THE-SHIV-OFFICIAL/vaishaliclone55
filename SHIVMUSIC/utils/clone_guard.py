"""
Dead clone guard.

When a clone owner deletes the bot in @BotFather, revokes the token, or the
bot gets deactivated, Telegram starts answering with errors such as
ACCESS_TOKEN_INVALID / AUTH_KEY_UNREGISTERED / USER_DEACTIVATED.

Instead of crashing or flooding the error group with tracebacks, this module:
  1. stops that clone quietly,
  2. removes it from ACTIVE_CLONES / CLONES and from the clone database,
  3. posts ONE short notice in the logger group:
       "🧹 Clone bot cleared ... Reason: <ErrorType>"
and every other bot keeps running normally.
"""
import asyncio
import html
import logging

from pyrogram import errors as _e

log = logging.getLogger("CloneGuard")

# Error classes that mean "this bot token / account will never work again".
_DEAD_NAMES = (
    "AccessTokenExpired",
    "AccessTokenInvalid",
    "AuthKeyUnregistered",
    "AuthKeyInvalid",
    "AuthKeyPermEmpty",
    "SessionRevoked",
    "SessionExpired",
    "UserDeactivated",
    "UserDeactivatedBan",
    "BotMethodInvalid",
)
DEAD_ERRORS = tuple(getattr(_e, n) for n in _DEAD_NAMES if hasattr(_e, n))

_DEAD_TEXT = (
    "ACCESS_TOKEN_EXPIRED",
    "ACCESS_TOKEN_INVALID",
    "AUTH_KEY_UNREGISTERED",
    "AUTH_KEY_INVALID",
    "SESSION_REVOKED",
    "SESSION_EXPIRED",
    "USER_DEACTIVATED",
    "BOT_TOKEN_INVALID",
)

HEALTH_INTERVAL = 300  # seconds between automatic clone checks
HEALTH_TIMEOUT = 20

_cleaning = set()
_worker_started = False
_sweep_pending = False


def is_dead_bot_error(exc) -> bool:
    if exc is None:
        return False
    if DEAD_ERRORS and isinstance(exc, DEAD_ERRORS):
        return True
    text = f"{type(exc).__name__} {exc}".upper()
    return any(t in text for t in _DEAD_TEXT)


def _main_app():
    try:
        from SHIVMUSIC import app
        return app
    except Exception:
        return None


def is_clone_client(client) -> bool:
    if client is None:
        return False
    app = _main_app()
    if client is app:
        return False
    try:
        from SHIVMUSIC.plugins.tools.clone import ACTIVE_CLONES
        return any(c is client for c in ACTIVE_CLONES.values())
    except Exception:
        return False


async def _notify(text):
    app = _main_app()
    if app is None:
        return
    try:
        import config
        chat = getattr(config, "ERROR_LOGGER_ID", 0) or getattr(config, "CLONE_LOGGER", 0) or getattr(config, "LOGGER_ID", 0)
        if chat:
            await app.send_message(chat, text, disable_web_page_preview=True)
    except Exception:
        pass  # never let the notice itself raise


async def _stop_quietly(client):
    if client is None:
        return
    try:
        assistant = getattr(client, "assistant", None)
        if assistant is not None and getattr(assistant, "is_connected", False):
            await asyncio.wait_for(assistant.stop(), timeout=10)
    except Exception:
        pass
    try:
        if getattr(client, "is_connected", False):
            await asyncio.wait_for(client.stop(), timeout=10)
    except Exception:
        pass


async def clear_dead_clone(*, bot_id=None, token=None, client=None, exc=None, bot_number=None, remove_from_db=True):
    """Stop + forget a dead clone and log one clean line. Never raises."""
    try:
        from SHIVMUSIC.plugins.tools.clone import ACTIVE_CLONES, CLONES
        from SHIVMUSIC.utils.database import clonebotdb
    except Exception:
        ACTIVE_CLONES, CLONES, clonebotdb = {}, set(), None

    if client is not None and bot_id is None:
        me = getattr(client, "me", None)
        bot_id = getattr(me, "id", None)
        if bot_id is None:
            for k, v in list(ACTIVE_CLONES.items()):
                if v is client:
                    bot_id = k
                    break
    if bot_id is None and token:
        try:
            bot_id = int(str(token).split(":")[0])
        except Exception:
            pass

    key = bot_id or token
    if key in _cleaning:
        return False
    _cleaning.add(key)
    try:
        if client is None and bot_id is not None:
            client = ACTIVE_CLONES.get(bot_id)
        username = getattr(getattr(client, "me", None), "username", None)

        if bot_id is not None:
            ACTIVE_CLONES.pop(bot_id, None)
            CLONES.discard(bot_id)
        await _stop_quietly(client)

        doc = None
        if clonebotdb is not None:
            query = {"bot_id": bot_id} if bot_id is not None else {"token": token}
            try:
                doc = await clonebotdb.find_one(query)
                if doc is None and token:
                    doc = await clonebotdb.find_one({"token": token})
                if remove_from_db and doc is not None:
                    await clonebotdb.delete_one({"_id": doc["_id"]})
            except Exception:
                pass
        username = username or (doc or {}).get("username")
        owner = (doc or {}).get("user_id")
        err_type = type(exc).__name__ if exc is not None else "Unknown"
        err_text = html.escape(str(exc))[:200] if exc is not None else "-"

        log.warning("Clone %s (@%s) cleared: %s", bot_id, username, err_type)
        await _notify(
            "🧹 <b>ᴄʟᴏɴᴇ ʙᴏᴛ ᴄʟᴇᴀʀᴇᴅ</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            + (f"<b>Clone No:</b> <code>{bot_number}</code>\n" if bot_number else "")
            + f"<b>Bot:</b> {('@' + html.escape(str(username))) if username else '-'} (<code>{bot_id}</code>)\n"
            + f"<b>Owner ID:</b> <code>{owner or '-'}</code>\n"
            + f"<b>Error type:</b> <code>{err_type}</code>\n"
            + f"<b>Detail:</b> <code>{err_text}</code>\n"
            + "<b>Action:</b> bot was deleted/closed by its owner, so it was stopped"
            + (" and removed from the database." if remove_from_db else ".")
            + "\n<i>All other bots keep running normally.</i>"
        )
        return True
    except Exception as e:  # absolutely never crash the main bot
        log.warning("clear_dead_clone failed: %s", e)
        return False
    finally:
        _cleaning.discard(key)


async def check_clone(bot_id, client):
    """Ping one clone; clears it when Telegram says it is dead."""
    try:
        await asyncio.wait_for(client.get_me(), timeout=HEALTH_TIMEOUT)
        return True
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if is_dead_bot_error(exc):
            await clear_dead_clone(bot_id=bot_id, client=client, exc=exc)
            return False
        return True  # temporary network problem — keep the clone


async def sweep_clones():
    try:
        from SHIVMUSIC.plugins.tools.clone import ACTIVE_CLONES
    except Exception:
        return
    for bot_id, client in list(ACTIVE_CLONES.items()):
        await check_clone(bot_id, client)
        await asyncio.sleep(0.2)


async def _health_worker():
    while True:
        await asyncio.sleep(HEALTH_INTERVAL)
        try:
            await sweep_clones()
        except Exception as e:
            log.warning("Clone health sweep error: %s", e)


def start_clone_guard():
    global _worker_started
    if _worker_started:
        return
    try:
        asyncio.get_running_loop().create_task(_health_worker())
        _worker_started = True
    except RuntimeError:
        pass


def schedule_sweep():
    """Called from the error logger when a dead-token error shows up anywhere."""
    global _sweep_pending
    if _sweep_pending:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _sweep_pending = True

    async def _run():
        global _sweep_pending
        try:
            await asyncio.sleep(2)
            await sweep_clones()
        finally:
            _sweep_pending = False

    loop.create_task(_run())


async def handle_client_error(client, exc) -> bool:
    """Return True when the error was a dead clone and has been handled."""
    if not is_dead_bot_error(exc):
        return False
    if client is not None and client is _main_app():
        return False  # main bot problem — must be reported normally
    if is_clone_client(client):
        await clear_dead_clone(client=client, exc=exc)
    else:
        schedule_sweep()
    return True
