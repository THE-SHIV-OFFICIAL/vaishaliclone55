"""Clone bot player card: custom /setthumb photo is used full-size; otherwise a clean card
(no bot-name / owner-name banner)."""
import os
import re
import math
import random
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from youtubesearchpython.__future__ import VideosSearch
from SHIVMUSIC import app
from SHIVMUSIC.utils.database import clonebotdb

W, H = 1920, 1080

# Luxury Red Wine & Royal Gold palette
WINE_BG = (12, 2, 7)
WINE_DARK = (40, 4, 16)
WINE_RICH = (155, 14, 48)
ROSE_NEON = (255, 45, 100)
GOLD_LIGHT = (255, 225, 135)
GOLD_WARM = (245, 175, 55)
CREAM = (255, 248, 244)
MUTED = (215, 185, 195)


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def glow_text(base, pos, text, font, fill, glow, radius=12, strength=3, anchor="la"):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(pos, text, font=font, fill=glow, anchor=anchor)
    blurred = layer.filter(ImageFilter.GaussianBlur(radius))
    for _ in range(strength):
        base.alpha_composite(blurred)
    ImageDraw.Draw(base).text(pos, text, font=font, fill=fill, anchor=anchor)


def draw_lens_flare(draw_layer, cx, cy, size=24, color=GOLD_LIGHT):
    r, g, b = color[:3]
    draw_layer.ellipse((cx - size // 3, cy - size // 3, cx + size // 3, cy + size // 3), fill=(255, 255, 255, 255))
    draw_layer.ellipse((cx - size, cy - size, cx + size, cy + size), fill=(r, g, b, 70))
    draw_layer.line((cx - size * 4, cy, cx + size * 4, cy), fill=(255, 255, 255, 210), width=2)
    draw_layer.line((cx - size * 7, cy, cx + size * 7, cy), fill=(r, g, b, 110), width=1)
    draw_layer.line((cx, cy - size * 3, cx, cy + size * 3), fill=(255, 255, 255, 190), width=2)
    draw_layer.line((cx, cy - size * 5, cx, cy + size * 5), fill=(r, g, b, 100), width=1)
    dsz = int(size * 1.6)
    draw_layer.line((cx - dsz, cy - dsz, cx + dsz, cy + dsz), fill=(r, g, b, 120), width=1)
    draw_layer.line((cx - dsz, cy + dsz, cx + dsz, cy - dsz), fill=(r, g, b, 120), width=1)


def draw_flowing_ribbon(canvas, p0, p1, p2, p3, base_width=40, color_start=ROSE_NEON, color_end=GOLD_LIGHT, steps=120):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = (u**3) * p0[0] + 3 * (u**2) * t * p1[0] + 3 * u * (t**2) * p2[0] + (t**3) * p3[0]
        y = (u**3) * p0[1] + 3 * (u**2) * t * p1[1] + 3 * u * (t**2) * p2[1] + (t**3) * p3[1]
        pts.append((x, y))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for i in range(len(pts) - 1):
        t = i / len(pts)
        r = int(color_start[0] + (color_end[0] - color_start[0]) * t)
        g = int(color_start[1] + (color_end[1] - color_start[1]) * t)
        b = int(color_start[2] + (color_end[2] - color_start[2]) * t)
        w = max(4, int(base_width * math.sin(math.pi * (0.04 + 0.92 * t))))
        alpha = int((120 + 80 * math.sin(math.pi * t)))
        ld.line([pts[i], pts[i + 1]], fill=(r, g, b, alpha), width=w)
    spine = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spine)
    for i in range(len(pts) - 1):
        t = i / len(pts)
        sd.line([pts[i], pts[i + 1]], fill=(255, 255, 255, int(190 * math.sin(math.pi * t))), width=3)
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(30)))
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(12)))
    canvas.alpha_composite(layer)
    canvas.alpha_composite(spine.filter(ImageFilter.GaussianBlur(5)))
    canvas.alpha_composite(spine)


async def download_user_photo(user_id, client=None):
    cli = client or app
    try:
        async for photo in cli.get_chat_photos(user_id, limit=1):
            return await cli.download_media(photo.file_id, file_name=f"cache/{user_id}.jpg")
    except Exception:
        return None
    return None


def build_thumb(bg, avatar_img, title, channel, views, duration, seed):
    # 1. Base Canvas with Deep Rich Wine & Ambient Vignette
    canvas = ImageOps.fit(bg.convert("RGB"), (W, H)).convert("RGBA")
    canvas = canvas.filter(ImageFilter.GaussianBlur(34))
    tint = Image.new("RGBA", (W, H), (*WINE_BG, 185))
    canvas.alpha_composite(tint)
    vign = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vign).ellipse((-160, -160, W + 160, H + 160), fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(160))
    vign_layer = Image.new("RGBA", (W, H), (3, 0, 2, 230))
    vign_layer.putalpha(Image.eval(vign, lambda v: 255 - v))
    canvas.alpha_composite(vign_layer)

    # Ambient Light Pools & Soft Warm Bokeh Orbs
    bokeh_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bokeh_layer)
    bd.ellipse((-100, 50, 750, 850), fill=(*WINE_RICH, 100))
    bd.ellipse((1100, -50, 2050, 750), fill=(*GOLD_WARM, 60))
    bd.ellipse((650, 100, 1350, 650), fill=(*WINE_DARK, 110))
    rng_bokeh = random.Random(777)
    for _ in range(45):
        bx = rng_bokeh.randint(40, W - 40)
        by = rng_bokeh.randint(30, H - 240)
        bsz = rng_bokeh.randint(22, 115)
        if rng_bokeh.random() > 0.45:
            col = (*GOLD_LIGHT, rng_bokeh.randint(30, 85))
        else:
            col = (*ROSE_NEON, rng_bokeh.randint(35, 95))
        bd.ellipse((bx - bsz, by - bsz, bx + bsz, by + bsz), fill=col)
    canvas.alpha_composite(bokeh_layer.filter(ImageFilter.GaussianBlur(36)))

    # 2. Flowing Silk Waves
    draw_flowing_ribbon(canvas, (380, 510), (740, 580), (1140, 540), (1530, 370), base_width=40, color_start=ROSE_NEON, color_end=GOLD_LIGHT)
    draw_flowing_ribbon(canvas, (390, 240), (780, 290), (1180, 310), (1450, 260), base_width=20, color_start=GOLD_LIGHT, color_end=ROSE_NEON)
    draw_flowing_ribbon(canvas, (280, 580), (660, 640), (1040, 610), (1380, 580), base_width=14, color_start=WINE_RICH, color_end=GOLD_WARM)
    flares_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(flares_layer)
    draw_lens_flare(fd, 740, 575, size=24, color=GOLD_LIGHT)
    draw_lens_flare(fd, 1140, 535, size=28, color=CREAM)
    draw_lens_flare(fd, 1400, 395, size=22, color=GOLD_LIGHT)
    draw_lens_flare(fd, 820, 295, size=20, color=ROSE_NEON)
    draw_lens_flare(fd, 1450, 260, size=18, color=CREAM)
    canvas.alpha_composite(flares_layer.filter(ImageFilter.GaussianBlur(4)))
    canvas.alpha_composite(flares_layer)

    # Fonts
    f_vibe = _font("SHIVMUSIC/assets/font.ttf", 80)
    f_title = _font("SHIVMUSIC/assets/font.ttf", 52)
    f_meta = _font("SHIVMUSIC/assets/font2.ttf", 30)
    f_small = _font("SHIVMUSIC/assets/font2.ttf", 26)

    # 3. Top Clean Branding ("VIBE" only - RED WINE, THE SHIV, BOT/OWNER removed)
    glow_text(canvas, (110, 60), "VIBE", f_vibe, GOLD_LIGHT, (*ROSE_NEON, 255), radius=18, strength=4)

    # 4. Left: Tilted YouTube Cover Card
    cw, ch = 470, 370
    cover = ImageOps.fit(bg.convert("RGB"), (cw, ch), centering=(0.5, 0.5)).convert("RGBA")
    pad = 65
    card_w, card_h = cw + pad * 2, ch + pad * 2
    card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    c_glow = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    cgd = ImageDraw.Draw(c_glow)
    cgd.rounded_rectangle((pad - 18, pad - 18, pad + cw + 18, pad + ch + 18), 52, fill=(*ROSE_NEON, 240))
    card.alpha_composite(c_glow.filter(ImageFilter.GaussianBlur(24)))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((pad - 10, pad - 10, pad + cw + 10, pad + ch + 10), 46, outline=(*GOLD_LIGHT, 255), width=6)
    cd.rounded_rectangle((pad - 4, pad - 4, pad + cw + 4, pad + ch + 4), 42, fill=(*WINE_RICH, 255))
    c_mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(c_mask).rounded_rectangle((0, 0, cw - 1, ch - 1), 38, fill=255)
    card.paste(cover, (pad, pad), c_mask)
    glass_sweep = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    ImageDraw.Draw(glass_sweep).polygon(
        [(pad, pad), (pad + 170, pad), (pad + 50, pad + ch), (pad - 120, pad + ch)],
        fill=(255, 255, 255, 40),
    )
    sm = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(sm).rounded_rectangle((pad, pad, pad + cw, pad + ch), 38, fill=255)
    card.paste(Image.alpha_composite(card, glass_sweep), (0, 0), sm)
    cd_flare = ImageDraw.Draw(card)
    draw_lens_flare(cd_flare, pad - 5, pad - 5, size=22, color=GOLD_LIGHT)
    draw_lens_flare(cd_flare, pad + cw + 5, pad + ch + 5, size=18, color=ROSE_NEON)
    tilted_card = card.rotate(18, resample=Image.BICUBIC, expand=True)
    canvas.alpha_composite(tilted_card, (40, 75))

    # 5. Right: User Avatar Circle (260px) + Orbital Rings
    av_size = 260
    cx, cy = 1540, 335
    orbit = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orbit)
    od.ellipse((cx - av_size // 2 - 46, cy - av_size // 2 - 24, cx + av_size // 2 + 46, cy + av_size // 2 + 24), outline=(*GOLD_LIGHT, 180), width=3)
    od.ellipse((cx - av_size // 2 - 48, cy - 6, cx - av_size // 2 - 36, cy + 6), fill=(*GOLD_LIGHT, 255))
    od.ellipse((cx + av_size // 2 + 36, cy - 6, cx + av_size // 2 + 48, cy + 6), fill=(*CREAM, 255))
    canvas.alpha_composite(orbit.filter(ImageFilter.GaussianBlur(10)))
    canvas.alpha_composite(orbit)
    av_glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(av_glow).ellipse((cx - av_size // 2 - 20, cy - av_size // 2 - 20, cx + av_size // 2 + 20, cy + av_size // 2 + 20), fill=(*ROSE_NEON, 230))
    canvas.alpha_composite(av_glow.filter(ImageFilter.GaussianBlur(24)))
    ad = ImageDraw.Draw(canvas)
    ad.ellipse((cx - av_size // 2 - 8, cy - av_size // 2 - 8, cx + av_size // 2 + 8, cy + av_size // 2 + 8), outline=(*GOLD_LIGHT, 255), width=6)
    if avatar_img is not None:
        a_cropped = ImageOps.fit(avatar_img.convert("RGB"), (av_size, av_size)).convert("RGBA")
    else:
        a_cropped = ImageOps.fit(bg.convert("RGB"), (av_size, av_size)).convert("RGBA").filter(ImageFilter.GaussianBlur(8))
    a_mask = Image.new("L", (av_size, av_size), 0)
    ImageDraw.Draw(a_mask).ellipse((0, 0, av_size - 1, av_size - 1), fill=255)
    canvas.paste(a_cropped, (cx - av_size // 2, cy - av_size // 2), a_mask)

    # Golden Music Note Badge
    bx, by = cx + int(av_size * 0.38), cy + int(av_size * 0.36)
    b_glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(b_glow).ellipse((bx - 42, by - 42, bx + 42, by + 42), fill=(*GOLD_WARM, 220))
    canvas.alpha_composite(b_glow.filter(ImageFilter.GaussianBlur(16)))
    bd_badge = ImageDraw.Draw(canvas)
    bd_badge.ellipse((bx - 36, by - 36, bx + 36, by + 36), fill=(35, 6, 16), outline=GOLD_LIGHT, width=4)
    bd_badge.ellipse((bx - 16, by + 4, bx - 2, by + 18), fill=CREAM)
    bd_badge.line((bx - 3, by + 10, bx - 3, by - 16), fill=CREAM, width=4)
    bd_badge.line((bx - 3, by - 16, bx + 15, by - 8), fill=CREAM, width=4)

    # 6. Bottom Glass Player Card
    x0, y0, x1, y1 = 90, 660, 1830, 960
    radius = 50
    glow_text(canvas, (x0 + 15, y0 - 45), "NOW PLAYING", f_small, MUTED, (*ROSE_NEON, 180), radius=10, strength=2)
    np_line = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    npd = ImageDraw.Draw(np_line)
    npd.line((x0 + 195, y0 - 32, x1 - 20, y0 - 32), fill=(*ROSE_NEON, 110), width=2)
    canvas.alpha_composite(np_line.filter(ImageFilter.GaussianBlur(6)))
    canvas.alpha_composite(np_line)

    card_glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cgd = ImageDraw.Draw(card_glow)
    cgd.rounded_rectangle((x0 - 8, y0 - 8, x1 + 8, y1 + 8), radius + 6, outline=(*ROSE_NEON, 220), width=8)
    canvas.alpha_composite(card_glow.filter(ImageFilter.GaussianBlur(20)))

    glass = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glass).rounded_rectangle((x0, y0, x1, y1), radius, fill=(18, 3, 11, 225))
    canvas.alpha_composite(glass)

    cd_player = ImageDraw.Draw(canvas)
    cd_player.rounded_rectangle((x0, y0, x1, y1), radius, outline=(*GOLD_LIGHT, 175), width=3)
    beam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(beam).line((x0 + 70, y0 + 1, x1 - 70, y0 + 1), fill=(255, 255, 255, 220), width=3)
    canvas.alpha_composite(beam.filter(ImageFilter.GaussianBlur(3)))
    canvas.alpha_composite(beam)

    ix, iy = x0 + 45, y0 + 45
    cd_player.rounded_rectangle((ix, iy, ix + 120, iy + 120), 28, fill=(45, 8, 22), outline=(*ROSE_NEON, 220), width=3)
    cd_player.rounded_rectangle((ix + 46, iy + 25, ix + 74, iy + 71), 14, outline=CREAM, width=4)
    cd_player.arc((ix + 34, iy + 45, ix + 86, iy + 89), 0, 180, fill=CREAM, width=4)
    cd_player.line((ix + 60, iy + 89, ix + 60, iy + 101), fill=CREAM, width=4)

    tx = ix + 155
    cd_player.text((tx, y0 + 32), f"{channel[:28]}  |  {views} views", font=f_meta, fill=MUTED)

    max_title_w = 780
    words = title.split()
    lines, curr = [], ""
    for w in words:
        test = f"{curr} {w}".strip()
        if cd_player.textlength(test, font=f_title) <= max_title_w:
            curr = test
        else:
            if curr:
                lines.append(curr)
            curr = w
        if len(lines) == 2:
            break
    if curr and len(lines) < 2:
        lines.append(curr)
    if len(lines) == 1:
        cd_player.text((tx, y0 + 74), lines[0], font=f_title, fill=CREAM)
        badge_y = y0 + 155
    else:
        l2 = lines[1]
        while cd_player.textlength(l2 + "...", font=f_title) > max_title_w and len(l2) > 3:
            l2 = l2[:-3].rstrip()
        if l2 != lines[1]:
            l2 += "..."
        cd_player.text((tx, y0 + 68), lines[0], font=f_title, fill=CREAM)
        cd_player.text((tx, y0 + 122), l2, font=f_title, fill=CREAM)
        badge_y = y0 + 175

    cd_player.rounded_rectangle((tx, badge_y, tx + 205, badge_y + 40), 20, fill=(185, 18, 50))
    cd_player.text((tx + 102, badge_y + 20), "YouTube Music", font=f_small, fill=CREAM, anchor="mm")

    rng_wave = random.Random(str(seed))
    wx = 1320
    wy = y0 + 115
    bars = 36
    h_vals = [rng_wave.randint(20, 82) for _ in range(bars)]
    wave_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wave_layer)
    for i in range(bars):
        env = math.sin(math.pi * i / (bars - 1)) ** 0.72
        h = max(8, int(h_vals[i] * env))
        x = wx + i * 13
        wd.rounded_rectangle((x, wy - h, x + 6, wy + h), 3, fill=GOLD_LIGHT)
    wave_glow = wave_layer.filter(ImageFilter.GaussianBlur(10))
    canvas.alpha_composite(wave_glow)
    canvas.alpha_composite(wave_layer)

    py = y1 - 48
    px0, px1 = x0 + 60, x1 - 60
    cd_prog = ImageDraw.Draw(canvas)
    cd_prog.line((px0, py, px1, py), fill=(105, 55, 70), width=5)
    prog = px0 + int((px1 - px0) * 0.12)
    prog_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(prog_layer)
    pd.line((px0, py, prog, py), fill=ROSE_NEON, width=6)
    canvas.alpha_composite(prog_layer.filter(ImageFilter.GaussianBlur(8)))
    canvas.alpha_composite(prog_layer)
    cd_prog.ellipse((prog - 12, py - 12, prog + 12, py + 12), fill=CREAM, outline=ROSE_NEON, width=4)
    cd_prog.text((px0, py + 12), "00:00", font=f_small, fill=MUTED)
    cd_prog.text((px1, py + 12), duration, font=f_small, fill=MUTED, anchor="ra")

    return canvas.convert("RGB")


async def get_thumb(videoid, user_id, client=None, *args, **kwargs):
    os.makedirs("cache", exist_ok=True)
    cli = client or app

    # 1. Custom Thumbnail Check: Agar user/clone ne custom thumb set kiya hai toh directly wahi use hoga
    try:
        me = await cli.get_me() if cli else None
        bot_id = me.id if me else None
        if bot_id:
            bot_data = await clonebotdb.find_one({"bot_id": bot_id})
            custom_thumb = bot_data.get("custom_thumb") if bot_data else None
            if custom_thumb:
                import hashlib
                tag = hashlib.md5(str(custom_thumb).encode()).hexdigest()[:10]
                custom_file = f"cache/custom_{bot_id}_{tag}.jpg"
                if not os.path.exists(custom_file):
                    dl = await cli.download_media(custom_thumb, file_name=custom_file)
                else:
                    dl = custom_file
                if dl and os.path.exists(dl):
                    return dl
    except Exception:
        pass

    # 2. Jo custom thumb set nahi karenge unke liye Luxury Red Wine card generate hoga
    safe_videoid = re.sub(r"[^a-zA-Z0-9_-]", "_", str(videoid))[:80] or "track"
    final_path = f"cache/{safe_videoid}_{user_id}_v6.png"
    if os.path.exists(final_path):
        return final_path

    temp_path = f"cache/temp_{safe_videoid}_{user_id}.jpg"
    u_photo = None
    try:
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        data = await results.next()
        lst = data.get("result", []) if isinstance(data, dict) else []
        result = lst[0] if lst else {}
        raw_title = result.get("title") or "Unknown Title"
        title = re.sub(r"\s+", " ", re.sub(r"[^\w\s|&'-]", " ", str(raw_title))).strip() or "Unknown Title"
        duration = str(result.get("duration") or "00:00")
        views = str((result.get("viewCount") or {}).get("short") or "Unknown").replace(" views", "")
        channel = str((result.get("channel") or {}).get("name") or "Unknown Artist")

        try:
            if result.get("thumbnails"):
                url = result["thumbnails"][0]["url"].split("?")[0]
                async with aiohttp.ClientSession() as s:
                    async with s.get(url) as r:
                        if r.status == 200:
                            async with aiofiles.open(temp_path, "wb") as f:
                                await f.write(await r.read())
        except Exception as e:
            print(f"Thumbnail download failed: {e}")

        try:
            bg = Image.open(temp_path).convert("RGBA") if os.path.exists(temp_path) and os.path.getsize(temp_path) else None
        except Exception:
            bg = None

        if bg is None:
            bg = Image.new("RGBA", (1280, 720), (60, 10, 25, 255))

        avatar = None
        u_photo = await download_user_photo(user_id, cli)
        if u_photo and os.path.exists(u_photo):
            try:
                avatar = Image.open(u_photo)
            except Exception:
                avatar = None

        build_thumb(bg, avatar, title, channel, views, duration, videoid).save(final_path, "PNG")
        return final_path
    except Exception as e:
        print(f"Thumbnail General Error: {e}")
        return None
    finally:
        for p in (temp_path, u_photo):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
