import asyncio
import importlib
import os
import glob
import shutil

# Raise open-file limit (fixes "[Errno 24] Too many open files")
try:
    import resource
    _soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    _target = 65535 if _hard == resource.RLIM_INFINITY else min(65535, _hard)
    if _soft < _target:
        resource.setrlimit(resource.RLIMIT_NOFILE, (_target, _hard))
except Exception:
    pass

from pyrogram import idle
import config
from SHIVMUSIC import LOGGER, app, userbot
from SHIVMUSIC.core.call import ANJALI
from SHIVMUSIC.error_logger import report_exception
from SHIVMUSIC.misc import sudo
from SHIVMUSIC.plugins import ALL_MODULES
from SHIVMUSIC.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS
from SHIVMUSIC.plugins.tools.clone import restart_bots


# ==========================================
# 🧹 CACHE SWEEPER: Start hone se pehle kachra saaf karega
# ==========================================
def clear_all_caches():
    LOGGER(__name__).info("🧹 Sweeping old files for Main Bot and Clones...")

    directories_to_clean = [
        "downloads", 
        "cache",
        "playback"
    ]

    file_patterns = ["vid_*.mp4", "vid_*.m4a", "vid_*.webm", "*.webm", "*.mp4"]

    cleaned_count = 0

    for pattern in file_patterns:
        for file in glob.glob(pattern):
            try:
                os.remove(file)
                cleaned_count += 1
            except:
                pass

    for directory in directories_to_clean:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                try:
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        cleaned_count += 1
                    elif os.path.isdir(filepath):
                        shutil.rmtree(filepath)
                except Exception as e:
                    LOGGER(__name__).warning(f"Could not remove {filepath}: {e}")

    if cleaned_count > 0:
        LOGGER(__name__).info(f"✅ Successfully swept {cleaned_count} leftover temporary files from all bots.")
    else:
        LOGGER(__name__).info("✅ Server storage is already clean.")

clear_all_caches()
# ==========================================


async def _run_application():
    if not config.STRING1:
        LOGGER(__name__).error("String Session not filled, please Provide a valid session.")
        exit()
    await sudo()
    try:
        from SHIVMUSIC.utils.database import load_player_settings
        await load_player_settings()
    except Exception as e:
        print(f"Player settings load failed: {e}")
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("SHIVMUSIC.plugins" + all_module)
    LOGGER("SHIVMUSIC.plugins").info("𝐀𝐥𝐥 𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬 𝐋𝐨𝐚𝐝𝐞𝐝 𝐁𝐚𝐛𝐲🥳...")
    
    # 🟢 Assistant Telegram clients always start before PyTgCalls
    await userbot.start()
    await ANJALI.start()
    
    try:
        # Do not require a live voice chat in the logger group during boot.
        pass
    except Exception:
        LOGGER("SHIVMUSIC").error(
            "𝗣𝗹𝗭 𝗦𝗧𝗔𝗥𝗧 𝗬𝗢𝗨𝗥 𝗟𝗢𝗚 𝗚𝗥𝗢𝗨𝗣 𝗩𝗢𝗜𝗖𝗘𝗖𝗛𝗔𝗧\𝗖𝗛𝗔𝗡𝗡𝗘𝗟\n\n𝗠𝗨𝗦𝗜𝗖 𝗕𝗢𝗧 𝗦𝗧𝗢𝗣........"
        )
        exit()
    except:
        pass
    
    # 🟢 ERROR FIXED: Removed 'await ANJALI.decorators()' because handlers are now auto-initialized inside call.py
    
    await restart_bots()
    try:
        # 24h auto delete of player cards (main + clones) — also cleans after restart
        from SHIVMUSIC.utils.playmsg_cleaner import start_play_cleaner
        start_play_cleaner()
    except Exception as e:
        LOGGER("SHIVMUSIC").warning(f"Play message cleaner not started: {e}")
    LOGGER("SHIVMUSIC").info(
        "╔═════ஜ۩۞۩ஜ════╗\n  ☠︎︎𝗠𝗔𝗗𝗘 𝗕𝗬 THE SHIV𝘀☠︎︎\n╚═════ஜ۩۞۩ஜ════╝"
    )
    
    # ==========================================
    # 🟢 HEALTH MONITOR SETUP (Replaced idle())
    # ==========================================
    async def health_monitor():
        failures = 0

        while True:
            await asyncio.sleep(
                config.HEALTHCHECK_INTERVAL
            )

            try:
                if not app.is_connected:
                    raise RuntimeError(
                        "Main Telegram client is disconnected"
                    )

                await asyncio.wait_for(
                    app.get_me(),
                    timeout=config.HEALTHCHECK_TIMEOUT,
                )

                assistants = (
                    (config.STRING1, userbot.one),
                    (config.STRING2, userbot.two),
                    (config.STRING3, userbot.three),
                    (config.STRING4, userbot.four),
                )

                for session, assistant in assistants:
                    if not session:
                        continue

                    if not assistant.is_connected:
                        raise RuntimeError(
                            "Enabled assistant is disconnected"
                        )

                    await asyncio.wait_for(
                        assistant.get_me(),
                        timeout=config.HEALTHCHECK_TIMEOUT,
                    )

                failures = 0

            except asyncio.CancelledError:
                raise

            except Exception as error:
                failures += 1

                LOGGER("SHIVMUSIC.health").warning(
                    "Health check failed (%s/%s): %s",
                    failures,
                    config.HEALTHCHECK_FAILURES,
                    error,
                )

                if failures >= config.HEALTHCHECK_FAILURES:
                    raise RuntimeError(
                        "Telegram connection failed repeatedly; "
                        "restarting process"
                    ) from error

    idle_task = asyncio.create_task(
        idle(),
        name="shivmusic-pyrogram-idle",
    )

    health_task = asyncio.create_task(
        health_monitor(),
        name="shivmusic-health-monitor",
    )

    done, pending = await asyncio.wait(
        {idle_task, health_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    try:
        for task in done:
            if not task.cancelled():
                error = task.exception()

                if error:
                    raise error

    finally:
        for task in pending:
            task.cancel()

        if pending:
            await asyncio.gather(
                *pending,
                return_exceptions=True,
            )
    # ==========================================

    await app.stop()
    await ANJALI.stop()
    await userbot.stop()
    LOGGER("SHIVMUSIC").info("𝗦𝗧𝗢𝗣 𝗠𝗨𝗦𝗜𝗖🎻 𝗕𝗢𝗧..")


async def init():
    """Run the application and report fatal startup/runtime failures."""
    try:
        await _run_application()
    except asyncio.CancelledError:
        raise
    except BaseException as exception:
        await report_exception(
            app,
            exception,
            context="Application startup/runtime",
        )
        raise


if __name__ == "__main__":
    # Keep the event loop used by Pyrogram clients created during import.
    # asyncio.run() creates a second loop and causes:
    # "got Future attached to a different loop".
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(init())
