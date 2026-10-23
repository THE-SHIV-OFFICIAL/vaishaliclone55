"""
24-hour auto delete for "Started Streaming" player cards (main + clone bots).

Every card sent through utils/playerui.send_player is saved in MongoDB with
the id of the bot that sent it. A background worker checks every 10 minutes
and deletes cards older than 24 hours using the SAME bot that sent them
(so no permission errors). Works after restarts too.
Messages that were already deleted / bots that were removed are just cleared.
"""
import asyncio
import logging
import time

from SHIVMUSIC.core.mongo import mongodb

PLAY_MSG_TTL = 24 * 60 * 60   # 24 hours
CHECK_EVERY = 600             # 10 minutes
play_msgs_db = mongodb.all_play_messages
_worker_started = False
log = logging.getLogger("PlayCleaner")


def _bot_id(client):
    me = getattr(client, "me", None)
    return getattr(me, "id", None) or getattr(client, "id", None) or 0


async def track_play_message(client, chat_id, message_id):
    try:
        await play_msgs_db.insert_one({
            "chat_id": int(chat_id),
            "message_id": int(message_id),
            "bot_id": int(_bot_id(client) or 0),
            "timestamp": int(time.time()),
        })
    except Exception as e:
        log.warning("Could not save play message for auto delete: %s", e)
    start_play_cleaner()


def _client_for(bot_id):
    from SHIVMUSIC import app
    if not bot_id or bot_id == getattr(app, "id", None):
        return app
    try:
        from SHIVMUSIC.plugins.tools.clone import ACTIVE_CLONES
        return ACTIVE_CLONES.get(int(bot_id))
    except Exception:
        return None


async def clean_once(now=None):
    """Delete every expired card once. Returns number of records processed."""
    cutoff = int(now or time.time()) - PLAY_MSG_TTL
    docs = await play_msgs_db.find({"timestamp": {"$lt": cutoff}}).to_list(length=500)
    for doc in docs:
        client = _client_for(doc.get("bot_id"))
        if client is not None:
            try:
                await client.delete_messages(
                    chat_id=int(doc["chat_id"]), message_ids=[int(doc["message_id"])]
                )
            except Exception:
                pass  # already deleted / no rights / chat gone → just forget it
        await play_msgs_db.delete_one({"_id": doc["_id"]})
        await asyncio.sleep(0.3)
    return len(docs)


async def _worker():
    while True:
        try:
            while await clean_once() >= 500:
                pass
        except Exception as e:
            log.warning("Play message cleaner error: %s", e)
        await asyncio.sleep(CHECK_EVERY)


def start_play_cleaner():
    global _worker_started
    if _worker_started:
        return
    try:
        asyncio.get_running_loop().create_task(_worker())
        _worker_started = True
    except RuntimeError:
        pass
