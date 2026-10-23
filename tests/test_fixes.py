"""Offline tests for the equalizer, captions, 24h cleaner, broadcast and dead-clone guard.
Run:  pip install pytest kurigram motor && python -m pytest tests -q
They use small fakes, so no Telegram / MongoDB connection is needed."""
import ast, asyncio, importlib.util, os, sys, time, types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pkg(name):
    mod = sys.modules.get(name) or types.ModuleType(name)
    mod.__path__ = []
    sys.modules[name] = mod
    return mod


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------- fakes ----------------
class FakeCursor:
    def __init__(self, docs): self.docs = docs
    async def to_list(self, length=None): return list(self.docs)[:length]


class FakeCollection:
    def __init__(self): self.docs = []; self._id = 0
    async def insert_one(self, d):
        self._id += 1; d = dict(d, _id=self._id); self.docs.append(d)
    def find(self, q=None):
        q = q or {}
        def ok(d):
            for k, v in q.items():
                if isinstance(v, dict) and "$lt" in v:
                    if not d.get(k, 0) < v["$lt"]: return False
                elif d.get(k) != v: return False
            return True
        return FakeCursor([d for d in self.docs if ok(d)])
    async def find_one(self, q):
        r = await self.find(q).to_list(1); return r[0] if r else None
    async def delete_one(self, q):
        for d in list(self.docs):
            if all(d.get(k) == v for k, v in q.items()):
                self.docs.remove(d); return


class FakeBot:
    def __init__(self, bot_id, username="bot", dead_exc=None):
        self.me = types.SimpleNamespace(id=bot_id, username=username, mention=f"@{username}")
        self.id = bot_id; self.is_connected = True; self.deleted = []; self.sent = []
        self.dead_exc = dead_exc; self.stopped = False
    async def get_me(self):
        if self.dead_exc: raise self.dead_exc
        return self.me
    async def stop(self): self.stopped = True; self.is_connected = False
    async def delete_messages(self, chat_id, message_ids):
        if self.dead_exc: raise self.dead_exc
        self.deleted.append((chat_id, tuple(message_ids)))
    async def send_message(self, chat_id, text, **k): self.sent.append((chat_id, text))


MAIN = FakeBot(1, "mainbot")
CLONEDB = FakeCollection()
PLAYDB = FakeCollection()
ACTIVE_CLONES, CLONES = {}, set()

_pkg("SHIVMUSIC").app = MAIN
_pkg("SHIVMUSIC.core"); _pkg("SHIVMUSIC.utils"); _pkg("SHIVMUSIC.plugins"); _pkg("SHIVMUSIC.plugins.tools")
sys.modules["SHIVMUSIC.core.mongo"] = types.SimpleNamespace(mongodb=types.SimpleNamespace(all_play_messages=PLAYDB))
async def _thumb_on(chat_id): return True
sys.modules["SHIVMUSIC.utils.database"] = types.SimpleNamespace(
    clonebotdb=CLONEDB, is_thumb_on=_thumb_on, autoplay_label=lambda c: "", thumb_label=lambda c: "")
sys.modules["SHIVMUSIC.plugins.tools.clone"] = types.SimpleNamespace(ACTIVE_CLONES=ACTIVE_CLONES, CLONES=CLONES)
sys.modules["config"] = types.SimpleNamespace(LOGGER_ID=-100, ERROR_LOGGER_ID=0, CLONE_LOGGER=0)

eq = _load("SHIVMUSIC.utils.equalizer", "SHIVMUSIC/utils/equalizer.py")
ui = _load("SHIVMUSIC.utils.playerui", "SHIVMUSIC/utils/playerui.py")
cleaner = _load("SHIVMUSIC.utils.playmsg_cleaner", "SHIVMUSIC/utils/playmsg_cleaner.py")
guard = _load("SHIVMUSIC.utils.clone_guard", "SHIVMUSIC/utils/clone_guard.py")


def run(c): return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(c)


# ---------------- equalizer ----------------
def test_volume_steps_and_limits():
    assert eq.next_volume(50, "up") == 100
    assert eq.next_volume(50, "down") == 25
    assert eq.next_volume(600, "boost") == 1000      # max 1000%
    assert eq.next_volume(10, "down") == 0           # min 0%
    assert eq.next_volume(700, "reset") == 50


def test_eq_state_and_filter_chain():
    eq.reset_chat_audio(-5)
    assert eq.build_audio_filter(-5) == ""            # normal + 50% = untouched audio
    eq.set_chat_eq(-5, "bass"); eq.set_chat_volume(-5, 100)
    assert eq.build_audio_filter(-5) == "bass=g=9:f=90:w=0.5,volume=2.00"
    eq.set_chat_eq(-5, "not-a-preset")
    assert eq.get_chat_eq(-5) == "off"


def test_eq_markup_has_all_presets_volume_and_close():
    m = eq.equalizer_markup({"CLOSE_BUTTON": "close"}, -7)
    cbs = [b.callback_data for r in m.inline_keyboard for b in r]
    assert sum(cb.startswith("EqSet -7|") for cb in cbs) == len(eq.EQ_PRESETS)
    assert "VolumePanel -7" in cbs and "close" in cbs


def _pytgcalls_parser():
    """Copy of py-tgcalls 2.3.3 ffmpeg argument splitter (pure python)."""
    try:
        from pytgcalls.ffmpeg import _get_stream_params
        return _get_stream_params
    except Exception:
        pass
    src = open(os.environ.get("PYTGCALLS_FFMPEG", "/tmp/pt/pytgcalls/ffmpeg.py")).read()
    tree = ast.parse(src)
    keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_get_stream_params", "_extract_stream_params")]
    import shlex
    from typing import Dict, List, Optional
    ns = {"shlex": shlex, "Dict": Dict, "List": List, "Optional": Optional}
    exec(compile(ast.Module(keep, []), "ffmpeg", "exec"), ns)
    return ns["_get_stream_params"]


def _with_eq_func():
    src = open(os.path.join(ROOT, "SHIVMUSIC/core/call.py")).read()
    node = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_with_eq")
    ns = {}; exec(compile(ast.Module([node], []), "call", "exec"), ns); return ns["_with_eq"]


def test_ffmpeg_args_reach_audio_only_after_input():
    _get_stream_params = _pytgcalls_parser()
    with_eq = _with_eq_func()
    eq.set_chat_eq(-9, "dj"); eq.set_chat_volume(-9, 50)
    args = with_eq(None, -9, "-ss 01:10")
    p = _get_stream_params(args)
    assert p["audio"]["start"] == ["-ss", "01:10"]          # seek stays before input
    assert p["audio"]["mid"][0] == "-af"                      # filter after input
    assert p["video"]["mid"] == []                            # video untouched
    eq.reset_chat_audio(-9)
    assert with_eq(None, -9, "") == ""


def test_play_buttons_replay_replaced_with_eq():
    main = open(os.path.join(ROOT, "SHIVMUSIC/utils/inline/play.py")).read()
    clone = open(os.path.join(ROOT, "SHIVMUSIC/cplugin/buttons.py")).read()
    assert "ADMIN Replay|{chat_id}\", style=s_map[3], emoji_id=REPLAY_EMOJI" not in main
    assert "6100384213649855022" in main and "6100384213649855022" in clone
    assert clone.count("eq_button(chat_id, s_map[3])") >= 5


# ---------------- caption order ----------------
def test_caption_title_time_rq_volume_by():
    import yaml
    s = yaml.safe_load(open(os.path.join(ROOT, "strings/langs/en.yml")))["stream_1"]
    eq.set_chat_volume(-3, 150); eq.set_chat_eq(-3, "lofi")
    out = ui.finalize_caption(s.format("link", "Song", "3:20", "Aman"), -3, MAIN)
    assert "ʀǫ" not in out and "Aman" not in out
    order = [out.index(x) for x in ("ᴛɪᴛʟє", "ᴛɪϻє", "єǫ ➥</b> ʟᴏ-ғɪ", "ᴠσʟυϻє ➥</b> 150%", "ʙʏ ➥</b> @mainbot")]
    assert order == sorted(order)
    assert ui.CAPTION_MARKER not in out


# ---------------- 24h auto delete ----------------
def test_play_cards_deleted_after_24h_by_the_bot_that_sent_them():
    clone = FakeBot(77, "clone77"); ACTIVE_CLONES[77] = clone
    PLAYDB.docs.clear()
    old = int(time.time()) - 25 * 3600
    PLAYDB.docs += [
        {"_id": 1, "chat_id": -1, "message_id": 10, "bot_id": 1, "timestamp": old},
        {"_id": 2, "chat_id": -2, "message_id": 20, "bot_id": 77, "timestamp": old},
        {"_id": 3, "chat_id": -3, "message_id": 30, "bot_id": 1, "timestamp": int(time.time())},
    ]
    assert run(cleaner.clean_once()) == 2
    assert (-1, (10,)) in MAIN.deleted and (-2, (20,)) in clone.deleted
    assert [d["_id"] for d in PLAYDB.docs] == [3]             # fresh card kept
    ACTIVE_CLONES.clear()


# ---------------- dead clone guard ----------------
def test_dead_error_detection():
    from pyrogram import errors
    assert guard.is_dead_bot_error(errors.AccessTokenInvalid())
    assert guard.is_dead_bot_error(errors.AuthKeyUnregistered())
    assert guard.is_dead_bot_error(RuntimeError("[401 USER_DEACTIVATED]"))
    assert not guard.is_dead_bot_error(asyncio.TimeoutError())
    assert not guard.is_dead_bot_error(errors.FloodWait(value=5))


def test_deleted_clone_is_cleared_without_crash_and_logged_once():
    from pyrogram import errors
    MAIN.sent.clear(); CLONEDB.docs.clear(); ACTIVE_CLONES.clear(); CLONES.clear()
    dead = FakeBot(55, "gone_bot", dead_exc=errors.AccessTokenInvalid())
    alive = FakeBot(66, "ok_bot")
    ACTIVE_CLONES.update({55: dead, 66: alive}); CLONES.update({55, 66})
    CLONEDB.docs += [{"_id": 1, "bot_id": 55, "user_id": 999, "username": "gone_bot"},
                     {"_id": 2, "bot_id": 66, "user_id": 111, "username": "ok_bot"}]
    run(guard.sweep_clones())
    assert 55 not in ACTIVE_CLONES and 55 not in CLONES and dead.stopped
    assert 66 in ACTIVE_CLONES and not alive.stopped          # other bots keep running
    assert [d["bot_id"] for d in CLONEDB.docs] == [66]
    assert len(MAIN.sent) == 1
    chat, text = MAIN.sent[0]
    assert chat == -100 and "AccessTokenInvalid" in text and "gone_bot" in text and "ᴄʟᴇᴀʀᴇᴅ" in text


def test_handler_error_from_dead_clone_is_handled_not_reported():
    from pyrogram import errors
    MAIN.sent.clear(); ACTIVE_CLONES.clear()
    dead = FakeBot(88, "closed", dead_exc=errors.AuthKeyUnregistered()); ACTIVE_CLONES[88] = dead
    assert run(guard.handle_client_error(dead, errors.AuthKeyUnregistered())) is True
    assert 88 not in ACTIVE_CLONES and len(MAIN.sent) == 1
    # main bot errors are never swallowed
    assert run(guard.handle_client_error(MAIN, errors.AuthKeyUnregistered())) is False
    # normal errors are reported like before
    assert run(guard.handle_client_error(dead, ValueError("x"))) is False


def test_network_glitch_does_not_remove_clone():
    ACTIVE_CLONES.clear(); MAIN.sent.clear()
    flaky = FakeBot(99, "flaky", dead_exc=ConnectionError("timeout")); ACTIVE_CLONES[99] = flaky
    run(guard.sweep_clones())
    assert 99 in ACTIVE_CLONES and MAIN.sent == []
