# ❄️ Equalizer + Volume panel for the MAIN bot (/eq and the ❄️ player button)
from pyrogram import filters

from SHIVMUSIC import app
from SHIVMUSIC.utils.equalizer import (
    EQ_CALLBACK_REGEX,
    EQ_COMMANDS,
    handle_eq_callback,
    handle_eq_command,
)
from config import BANNED_USERS


@app.on_message(filters.command(EQ_COMMANDS, prefixes=["/", "!", "."]) & filters.group & ~BANNED_USERS)
async def main_eq_command(client, message):
    await handle_eq_command(client, message)


@app.on_callback_query(filters.regex(EQ_CALLBACK_REGEX) & ~BANNED_USERS)
async def main_eq_callback(client, callback_query):
    await handle_eq_callback(client, callback_query)
