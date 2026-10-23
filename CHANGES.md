# Anjali Music Clone — final setup (v4)

## Naya kya hai
1. **❄️ Equalizer (main + clone dono me)**
   - Player me replay wale button ki jagah ❄️ Equalizer button (premium emoji `6100384213649855022`).
   - Clone ke player me bhi ▷ II ❄️ ‣‣I.
   - `/eq` `/equalizer` command bhi chalti hai (sirf admin / sudo / auth user).
   - 13 preset (Normal, Clear, DJ Bass, Bass Boost, Deep Bass, 8D, Lo-Fi, Vocal, Treble, Soft, Party, Nightcore, Slowed+Reverb).
   - Volume panel: +50 / -25 / boost +500 (0–1000%), reset.
   - Song wahi se chalta rehta hai jahan tha, shuru se nahi. Agla gaana bhi same EQ/volume ke sath bajta hai.
2. **Caption order**: Title → Time → EQ (mood) → Volume → By (same font).
3. **Thumbnail button**: `ᴛʜᴜᴍʙɴɪʟ : ᴏɴ / ᴏғғ` (button + popup).
4. **Clone thumbnail**: bot name / owner name wala banner hata diya. `/setthumb` wali photo poori card me dikhti hai (thumb badalne par naya wala hi aata hai).
5. **Broadcast auto delete fix**: `/broadcast` aur promo dono ke messages save hote hain aur 48 ghante baad delete hote hain (har 10 min check).
6. **Play message 24 ghante me auto delete** — main + clone dono ke, jis bot ne bheja wahi delete karta hai, restart ke baad bhi.
7. **Delete/close kiya hua clone bot** — koi crash ya traceback spam nahi. Bot ko rok ke database se hata deta hai aur logger group me ek message:
   `🧹 ᴄʟᴏɴᴇ ʙᴏᴛ ᴄʟᴇᴀʀᴇᴅ … Error type: AccessTokenInvalid …` — baaki sab bots chalte rehte hain.
   Har 5 minute me sab clones check hote hain; internet ki chhoti dikkat par clone **nahi** hataya jata.

## Files
Nayi: `SHIVMUSIC/utils/equalizer.py`, `SHIVMUSIC/plugins/admins/equalizer.py`, `SHIVMUSIC/cplugin/equalizer.py`,
`SHIVMUSIC/utils/playmsg_cleaner.py`, `SHIVMUSIC/utils/clone_guard.py`, `tests/test_fixes.py`

Badli: `core/call.py`, `utils/inline/play.py`, `cplugin/buttons.py`, `utils/playerui.py`, `utils/database/database.py`,
`plugins/admins/callback.py`, `cplugin/callback.py`, `utils/stream/stream.py`, `cplugin/utils/cthumbnail.py`,
`plugins/misc/broadcast.py`, `plugins/tools/clone.py`, `error_logger.py`, `__main__.py`, `strings/langs/*.yml`

## Test
```
pip install pytest kurigram==2.2.24 pyyaml
python -m pytest tests -q
```
