# ❄️ Equalizer + Volume panel for every CLONE bot (/eq and the ❄️ player button)
from pyrogram import Client, filters

from SHIVMUSIC.utils.equalizer import (
    EQ_CALLBACK_REGEX,
    EQ_COMMANDS,
    handle_eq_callback,
    handle_eq_command,
)
from config import BANNED_USERS


@Client.on_message(filters.command(EQ_COMMANDS, prefixes=["/", "!", "."]) & filters.group & ~BANNED_USERS)
async def clone_eq_command(client: Client, message):
    await handle_eq_command(client, message)


@Client.on_callback_query(filters.regex(EQ_CALLBACK_REGEX) & ~BANNED_USERS)
async def clone_eq_callback(client: Client, callback_query):
    await handle_eq_callback(client, callback_query)
