import asyncio
import os
import contextlib
import time
import math
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait, RPCError, PeerIdInvalid, UserIsBlocked, UserDeactivated, AuthKeyUnregistered, MessageNotModified

from SHIVMUSIC import app
from SHIVMUSIC.misc import SUDOERS
from SHIVMUSIC.utils.database.clonedb import (
    get_all_clones, 
    get_served_chats_clone, 
    get_served_users_clone,
    get_clonebot_owner
)
from config import API_ID, API_HASH
from SHIVMUSIC.error_logger import ErrorLoggingClient

# Global Flag
IS_CBROADCASTING = False

# Stylish Progress Bar Generator
def get_progress_bar(current, total, length=15):
    if total == 0:
        return "▱" * length + " 0%"
    percentage = current / total
    filled_len = int(length * percentage)
    bar = '▰' * filled_len + '▱' * (length - filled_len)
    return f"{bar} {percentage * 100:.1f}%"

@app.on_message(filters.command("stopcbroadcast") & SUDOERS)
async def stop_clone_broadcast(client, message):
    global IS_CBROADCASTING
    if not IS_CBROADCASTING:
        return await message.reply_text("❌ **No Clone Broadcast is currently running.**")
    
    IS_CBROADCASTING = False
    await message.reply_text("🛑 **Stopping Broadcast...**\nProcess will halt after the current bot finishes its queue.")


@app.on_message(filters.command("cbroadcast") & SUDOERS)
async def clone_broadcast_handler(client, message):
    global IS_CBROADCASTING
    
    if IS_CBROADCASTING:
        return await message.reply_text("⚠️ **Broadcast already running!** Stop it first baby.")

    # --- COMMAND PARSING ---
    content = message.text or message.caption

    if message.reply_to_message:
        query = message.reply_to_message.text or message.reply_to_message.caption
    else:
        if not content or len(message.command) < 2:
            return await message.reply_text(
                "<b>📣 Clone Broadcast Manager</b>\n\n"
                "<b>Usage:</b> `/cbroadcast [Message] [Flags]`\n"
                "<b>Flags:</b> `-owner`, `-user`, `-group`, `-all`, `-pin`"
            )
        query = content.split(None, 1)[1]

    pin = "-pin" in content if content else False
    send_owners = "-owner" in content or "-all" in content if content else False
    send_users = "-user" in content or "-all" in content if content else False
    send_groups = "-group" in content or "-all" in content if content else False

    if not send_users and not send_groups and not send_owners:
        send_groups = True

    if query:
        for flag in ["-pin", "-owner", "-user", "-group", "-all"]:
            query = query.replace(flag, "")
        query = query.strip()

    if not query and not message.reply_to_message:
        return await message.reply_text("❌ **Message is empty!**")

    IS_CBROADCASTING = True
    status_msg = await message.reply_text("🔄 **Analyzing Clones Baby...**")

    # --- FETCH CLONES ---
    all_clones_data = []
    try:
        async for c in get_all_clones():
            all_clones_data.append(c)
    except Exception as e:
        IS_CBROADCASTING = False
        return await status_msg.edit_text(f"❌ **DB Error:** {e}")

    total_clones = len(all_clones_data)
    if total_clones == 0:
        IS_CBROADCASTING = False
        return await status_msg.edit_text("❌ **No Clones Found.**")

    # Tracking Variables
    processed_clones = 0
    success_clones = 0
    failed_clones = 0
    total_sent = 0
    
    total_targetted_groups = 0
    total_targetted_users = 0
    
    last_edit_time = time.time()
    edit_interval = 8  # Update the message every 8 seconds to avoid FloodWait

    # Download replied media ONCE: file_id of main bot is not valid for clone bots
    media_path = None
    rep = message.reply_to_message
    if rep and (rep.photo or rep.video or rep.audio or rep.document or rep.animation):
        try:
            media_path = await rep.download()
        except Exception:
            media_path = None

    try:
        from SHIVMUSIC.plugins.tools.clone import ACTIVE_CLONES
    except Exception:
        ACTIVE_CLONES = {}

    @contextlib.asynccontextmanager
    async def _clone_client(bot_id, token):
        running = ACTIVE_CLONES.get(int(bot_id)) if str(bot_id).isdigit() else None
        if running is not None and getattr(running, "is_connected", False):
            yield running
            return
        temp = ErrorLoggingClient(
            f"cb_{bot_id}",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=token,
            in_memory=True,
            no_updates=True,
            error_logger_name=f"Clone {bot_id} broadcast",
        )
        await temp.start()
        try:
            yield temp
        finally:
            try:
                await temp.stop()
            except Exception:
                pass

    # --- MAIN LOOP ---
    for clone in all_clones_data:
        if not IS_CBROADCASTING: break

        token = clone.get('token')
        bot_id = clone.get('bot_id')
        username = clone.get('username', 'Unknown')

        if not token or not bot_id:
            failed_clones += 1
            processed_clones += 1
            continue

        # --- A. COLLECT TARGETS ---
        target_ids = set()

        if send_owners:
            try:
                owner = await get_clonebot_owner(bot_id)
                if owner:
                    target_ids.add(int(owner))
                    total_targetted_users += 1
            except: pass

        if send_users:
            try:
                users_list = await get_served_users_clone(bot_id)
                total_targetted_users += len(users_list)
                for u in users_list:
                    target_ids.add(int(u['user_id']))
            except: pass

        if send_groups:
            try:
                chats_list = await get_served_chats_clone(bot_id)
                total_targetted_groups += len(chats_list)
                for c in chats_list:
                    target_ids.add(int(c['chat_id']))
            except: pass

        if not target_ids:
            processed_clones += 1
            continue

        # --- B. SEND MESSAGES ---
        try:
            async with _clone_client(bot_id, token) as clone_app:
                
                clone_sent_count = 0
                
                try:
                    await clone_app.get_me()
                except (AuthKeyUnregistered, UserDeactivated):
                    failed_clones += 1
                    processed_clones += 1
                    continue

                for chat_id in target_ids:
                    if not IS_CBROADCASTING: break
                    
                    try:
                        # Force Clone App to send natively
                        if message.reply_to_message:
                            rep = message.reply_to_message
                            if rep.photo:
                                sent = await clone_app.send_photo(chat_id, photo=media_path or rep.photo.file_id, caption=query)
                            elif rep.video:
                                sent = await clone_app.send_video(chat_id, video=media_path or rep.video.file_id, caption=query)
                            elif rep.audio:
                                sent = await clone_app.send_audio(chat_id, audio=media_path or rep.audio.file_id, caption=query)
                            elif rep.document:
                                sent = await clone_app.send_document(chat_id, document=media_path or rep.document.file_id, caption=query)
                            elif rep.animation:
                                sent = await clone_app.send_animation(chat_id, animation=media_path or rep.animation.file_id, caption=query)
                            elif rep.sticker:  # stickers: file_id works across bots
                                sent = await clone_app.send_sticker(chat_id, sticker=rep.sticker.file_id)
                            else:
                                sent = await clone_app.send_message(chat_id, text=query)
                        else:
                            sent = await clone_app.send_message(chat_id, text=query)
                        
                        if pin and sent and str(chat_id).startswith("-100"):
                            try:
                                await sent.pin(disable_notification=True)
                            except: pass
                        
                        clone_sent_count += 1
                        total_sent += 1
                        await asyncio.sleep(0.2)
                    
                    except FloodWait as e:
                        if int(e.value) > 60:
                            continue  # skip this chat instead of freezing the whole broadcast
                        await asyncio.sleep(int(e.value))
                    except (RPCError, PeerIdInvalid, UserIsBlocked):
                        continue
                    except Exception:
                        continue
                    
                    # 🚀 LIVE PROGRESS BAR UPDATE CHECK
                    if time.time() - last_edit_time > edit_interval:
                        progress_bar = get_progress_bar(processed_clones, total_clones)
                        live_text = (
                            f"📡 **Live Clone Broadcast**\n\n"
                            f"**Progress:**\n`[{progress_bar}]`\n\n"
                            f"🤖 **Clones Processed:** `{processed_clones}/{total_clones}`\n"
                            f"📨 **Messages Sent Live:** `{total_sent}`\n"
                            f"🔄 **Currently Sending via:** `@{username}`\n\n"
                            f"⚠️ **Failed Tokens:** `{failed_clones}`"
                        )
                        try:
                            await status_msg.edit_text(live_text)
                            last_edit_time = time.time()
                        except MessageNotModified:
                            pass
                        except FloodWait as fw:
                            last_edit_time = time.time() + int(fw.value)
                        except Exception:
                            pass
                
                if clone_sent_count > 0:
                    success_clones += 1
                
        except Exception:
            failed_clones += 1
            
        processed_clones += 1

    # --- FINAL REPORT ---
    IS_CBROADCASTING = False
    if media_path and os.path.exists(media_path):
        try:
            os.remove(media_path)
        except Exception:
            pass

    final_bar = get_progress_bar(total_clones, total_clones)
    with contextlib.suppress(Exception):
      await status_msg.edit_text(
        f"✅ **Clone Broadcast Completed!**\n\n"
        f"**Final Status:**\n`[{final_bar}]`\n\n"
        f"🤖 **Total Clones:** `{total_clones}`\n"
        f"📢 **Active Sending Clones:** `{success_clones}`\n"
        f"⚠️ **Failed/Revoked Tokens:** `{failed_clones}`\n"
        f"📨 **Total Messages Sent:** `{total_sent}`\n\n"
        f"👥 **Total Target Users:** `{total_targetted_users}`\n"
        f"👥 **Total Target Groups:** `{total_targetted_groups}`"
    )
