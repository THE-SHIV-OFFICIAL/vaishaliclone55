import html
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime

import urllib3
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
from SHIVMUSIC import app

try:
    from SHIVMUSIC.core.bot import clones
except ImportError:
    clones = []

from SHIVMUSIC.misc import HAPP, SUDOERS, XCB
from SHIVMUSIC.utils.database import (
    get_active_chats,
    remove_active_chat,
    remove_active_video_chat,
)
from SHIVMUSIC.utils.decorators.language import language
from SHIVMUSIC.utils.pastebin import ANJALIBin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def is_heroku():
    return "heroku" in socket.getfqdn().lower()


def restart_current_process():
    """Current process ko replace kare, doosra bot process start na kare."""
    os.execv(sys.executable, [sys.executable, "-m", "SHIVMUSIC"])


def clear_runtime_files():
    for directory in ("downloads", "raw_files", "cache"):
        shutil.rmtree(directory, ignore_errors=True)


async def notify_active_chats(text_template):
    """Har active chat ko ek notice bheje, phir stale call records clear kare."""
    try:
        active_chats = await get_active_chats()
    except Exception:
        return

    clients = [app] + list(clones or [])

    for chat_id in active_chats:
        try:
            chat_id = int(chat_id)
        except (TypeError, ValueError):
            continue

        for client in clients:
            try:
                await client.send_message(
                    chat_id=chat_id,
                    text=text_template.format(client.mention),
                )
                try:
                    await remove_active_chat(chat_id)
                    await remove_active_video_chat(chat_id)
                except Exception:
                    pass
                break
            except Exception:
                continue


@app.on_message(
    filters.command(
        ["getlog", "logs", "getlogs"],
        prefixes=["/", "!", "%", ",", "", ".", "@", "#"],
    )
    & SUDOERS
)
@language
async def log_(client, message, _):
    try:
        await message.reply_document(document="log.txt")
    except Exception:
        await message.reply_text(_["server_1"])


@app.on_message(
    filters.command(
        ["update", "gitpull"],
        prefixes=["/", "!", "%", ",", "", ".", "@", "#"],
    )
    & SUDOERS
)
@language
async def update_(client, message, _):
    if is_heroku() and HAPP is None:
        return await message.reply_text(_["server_2"])

    response = await message.reply_text(_["server_3"])

    try:
        repo = Repo(search_parent_directories=True)
        origin = repo.remotes.origin
    except (GitCommandError, InvalidGitRepositoryError, IndexError, AttributeError):
        return await response.edit(_["server_5"])

    branch = getattr(config, "UPSTREAM_BRANCH", None)
    if not branch:
        return await response.edit(
            "❌ config.py mein UPSTREAM_BRANCH set nahi hai."
        )

    try:
        repo.git.fetch("origin", branch)
        commits = list(repo.iter_commits(f"HEAD..origin/{branch}"))
    except Exception as exc:
        return await response.edit(
            f"❌ Git fetch/check fail hua: "
            f"<code>{html.escape(str(exc))}</code>"
        )

    if not commits:
        return await response.edit(_["server_6"])

    repo_url = origin.url.removesuffix(".git").rstrip("/")
    updates = []

    for info in commits:
        committed = datetime.fromtimestamp(info.committed_date)
        summary = html.escape(info.summary)
        author = html.escape(str(info.author))
        commit_url = html.escape(
            f"{repo_url}/commit/{info.hexsha}",
            quote=True,
        )
        updates.append(
            f'<b>➣ <a href="{commit_url}">{summary}</a> by {author}</b>\n'
            f"<b>➥ Committed:</b> {committed.strftime('%d %b %Y')}\n"
        )

    header = "<b>Update available. Applying fast-forward update...</b>\n\n"
    update_text = header + "\n".join(updates)

    if len(update_text) > 3900:
        try:
            url = await ANJALIBin("\n".join(updates))
            nrs = await response.edit(
                f'{header}<a href="{html.escape(str(url), quote=True)}">'
                "View commit details</a>",
                disable_web_page_preview=True,
            )
        except Exception:
            nrs = await response.edit(
                header + "Update details are too long to display."
            )
    else:
        nrs = await response.edit(
            update_text,
            disable_web_page_preview=True,
        )

    # Local tracked changes hon to unhe silently stash/discard na kare.
    if repo.is_dirty(untracked_files=False):
        return await response.edit(
            "❌ Update roka gaya: tracked files mein local changes hain. "
            "Pehle unhe commit ya restore karein, phir /update chalayein."
        )

    try:
        repo.git.merge("--ff-only", f"origin/{branch}")
    except GitCommandError as exc:
        return await response.edit(
            "❌ Update apply nahi hua; fast-forward possible nahi. "
            "Git status check karein.\n"
            f"<code>{html.escape(str(exc))[:700]}</code>"
        )

    await notify_active_chats(
        _["server_8"]
        + "\nRestarting now; please start playback again shortly."
    )
    await response.edit(
        "✅ Update apply ho gaya. Bot ab isi process mein restart ho raha hai."
    )

    if is_heroku():
        restart_command = (
            f"{XCB[5]} {XCB[7]} {XCB[9]}{XCB[4]}"
            f"{XCB[0] * 2}{XCB[6]}{XCB[4]}{XCB[8]}{XCB[1]}"
            f"{XCB[5]}{XCB[2]}{XCB[6]}{XCB[2]}{XCB[3]}"
            f"{XCB[0]}{XCB[10]}{XCB[2]}{XCB[5]} "
            f"{XCB[11]}{XCB[4]}{XCB[12]}"
        )
        try:
            subprocess.run(restart_command, shell=True, check=True)
        except Exception as err:
            await app.send_message(
                chat_id=config.LOGGER_ID,
                text=_["server_10"].format(err),
            )
        return

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                "requirements.txt",
            ],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        await app.send_message(
            chat_id=config.LOGGER_ID,
            text=(
                "Dependency install failed "
                f"(exit {exc.returncode}); current environment se restart kar raha hoon."
            ),
        )

    restart_current_process()


@app.on_message(filters.command(["restart"]) & SUDOERS)
async def restart_(_, message):
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🤖 ᴍᴀɪɴ ʙᴏᴛ",
                    callback_data="restart_main",
                ),
                InlineKeyboardButton(
                    "👥 ᴄʟᴏɴᴇs ʙᴏᴛ",
                    callback_data="restart_clones",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔄 ʙᴏᴛʜ (ᴍᴀɪɴ + ᴄʟᴏɴᴇs)",
                    callback_data="restart_both",
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ ᴄᴀɴᴄᴇʟ",
                    callback_data="cancel_restart",
                )
            ],
        ]
    )
    await message.reply_text(
        "**⚠️ ᴋɪsᴇ ʀᴇsᴛᴀʀᴛ ᴋᴀʀɴᴀ ᴄʜᴀʜᴛᴇ ʜᴀɪɴ?**\n\n"
        "*(Neeche diye gaye options me se select karein)*",
        reply_markup=markup,
    )


@app.on_callback_query(filters.regex(r"^cancel_restart$") & SUDOERS)
async def cancel_restart(_, query):
    await query.answer()
    await query.message.edit_text(
        "**❌ ʀᴇsᴛᴀʀᴛ ᴘʀᴏᴄᴇss ᴄᴀɴᴄᴇʟʟᴇᴅ.**"
    )


@app.on_callback_query(filters.regex(r"^restart_main$") & SUDOERS)
async def restart_main(_, query):
    await query.answer()
    await query.message.edit_text(
        "🔄 **ᴍᴀɪɴ ʙᴏᴛ ʀᴇsᴛᴀʀᴛ ʜᴏ ʀᴀʜᴀ ʜᴀɪ...**"
    )
    await notify_active_chats(
        "{} is restarting. Please start playback again in a few seconds."
    )
    clear_runtime_files()
    restart_current_process()


@app.on_callback_query(filters.regex(r"^restart_clones$") & SUDOERS)
async def restart_clones(_, query):
    await query.answer()

    if not clones:
        return await query.message.edit_text(
            "❌ Koi clone bot available nahi hai."
        )

    await query.message.edit_text(
        "🔄 **Clone bots restart ho rahe hain...**"
    )
    await notify_active_chats(
        "{} is restarting. Please start playback again in a few seconds."
    )

    succeeded = 0
    failed = 0

    for clone in list(clones):
        try:
            await clone.stop()
            await clone.start()
            succeeded += 1
        except Exception:
            failed += 1

    await query.message.edit_text(
        f"Clone restart complete: {succeeded} successful, {failed} failed."
    )


@app.on_callback_query(filters.regex(r"^restart_both$") & SUDOERS)
async def restart_both(_, query):
    await query.answer()
    await query.message.edit_text(
        "🔄 **Main bot aur clones restart ho rahe hain...**"
    )
    await notify_active_chats(
        "{} is restarting. Please start playback again in a few seconds."
    )
    clear_runtime_files()
    restart_current_process()
