# -*- coding: utf-8 -*-
"""海克斯大乱斗卡片渲染（二次元风格）。

设计：浅粉渐变底 + 小々路立绘（右上，出血）+ 白色圆角卡片 + 玫瑰金点缀。
Pillow 本地生成，不依赖在线 T2I。
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except Exception:  # pragma: no cover
    Image = None

BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "fonts"
CHARA_PATH = BASE_DIR / "assets" / "chara.png"

_FONT_REG = FONT_DIR / "AlibabaPuHuiTi-3-55-Regular.ttf"
_FONT_BOLD = FONT_DIR / "AlibabaPuHuiTi-3-75-SemiBold.ttf"

# ---- 二次元浅色配色 ----
BG_TOP = (255, 250, 253)
BG_BOT = (253, 232, 243)
CARD = (255, 255, 255)
CARD_ALT = (255, 246, 251)
TEXT = (72, 45, 62)
MUTED = (156, 124, 145)
ROSE = (230, 88, 146)
ROSE_SOFT = (255, 160, 198)
GOLD = (232, 160, 74)
GREEN = (98, 190, 142)
BLUE = (104, 168, 224)
LINE = (243, 220, 232)
SHADOW = (214, 180, 200)

W = 760
PAD = 26

_fonts: dict = {}
_chara = None
_chara_loaded = False


def available() -> bool:
    return Image is not None and _FONT_REG.exists()


def _f(size: int, bold: bool = False):
    key = (size, bold)
    if key in _fonts:
        return _fonts[key]
    path = _FONT_BOLD if bold else _FONT_REG
    try:
        f = ImageFont.truetype(str(path), size)
    except Exception:
        f = ImageFont.load_default()
    _fonts[key] = f
    return f


def _load_chara():
    global _chara, _chara_loaded
    if not _chara_loaded:
        _chara_loaded = True
        try:
            if CHARA_PATH.exists():
                _chara = Image.open(str(CHARA_PATH)).convert("RGBA")
        except Exception:
            _chara = None
    return _chara


def _tier_color(tier: str):
    return {"S": GOLD, "A": GREEN, "B": BLUE}.get(str(tier).upper(), MUTED)


def _pct(x, nd=1):
    try:
        return f"{float(x) * 100:.{nd}f}%"
    except Exception:
        return "-"


def _num(x):
    try:
        x = int(x)
    except Exception:
        return "-"
    if x >= 1e8:
        return f"{x / 1e8:.1f}亿"
    if x >= 1e4:
        return f"{x / 1e4:.0f}万"
    return str(x)


def _gradient(w, h):
    """竖向渐变背景。"""
    img = Image.new("RGB", (1, h))
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3))
    return img.resize((w, h), Image.BILINEAR).convert("RGBA")


def _soft_shadow(img, box, radius, blur=6, offset=3, alpha=70):
    """给一个圆角矩形画柔和阴影。"""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0, y0 + offset, x1, y1 + offset], radius=radius,
                        fill=SHADOW + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer)


def _paste_chara(img, top, height):
    """把立绘贴到右上角，右边缘出血。返回实际占用高度。"""
    ch = _load_chara()
    if not ch:
        return 0
    ratio = height / ch.height
    cw = max(1, int(ch.width * ratio))
    c = ch.resize((cw, height), Image.LANCZOS)
    x = img.width - cw + 62          # 右侧出血
    img.alpha_composite(c, (x, top))
    return height


def _glow(img, cx, cy, r, color=ROSE_SOFT, alpha=90):
    """角色身后的柔光圆。"""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(r // 2))
    img.alpha_composite(layer)


def _wrap(d, text, font, max_w):
    """按像素宽度折行（逐字符，适配中文）。"""
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        for ch in para:
            if cur and d.textlength(cur + ch, font=font) > max_w:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
    return lines


def render(title: str, subtitle: str = "", hero: dict | None = None,
           rows: list | None = None, footer: str = "", kind_label: str = "",
           section: str = "", desc: str = "") -> str | None:
    """渲染一张卡片，返回 PNG 路径；失败返回 None。"""
    if not available():
        return None
    rows = rows or []
    has_chara = _load_chara() is not None

    # 效果描述：先测宽算行数
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    desc_text = str(desc or "").strip()
    if len(desc_text) > 230:
        desc_text = desc_text[:230] + "…"
    desc_lines = _wrap(probe, desc_text, _f(17), W - 2 * PAD - 44) if desc_text else []
    # 34(分区标题) + 上下各 14 内边距 + 行数*行高 + 底部间距
    desc_box_h = (len(desc_lines) * 27 + 28) if desc_lines else 0
    desc_h = (34 + desc_box_h + 10) if desc_lines else 0

    head_h = 214 if has_chara else 100
    hero_h = 152 if hero else 0
    row_h = 60
    sec_h = 34 if rows else 0
    body_h = len(rows) * row_h + (12 if rows else 0)
    footer_h = 44
    bottom_pad = 34 if has_chara else 18
    H = head_h + hero_h + desc_h + sec_h + body_h + footer_h + bottom_pad

    img = _gradient(W, H)

    # 角色柔光 + 立绘
    if has_chara:
        _glow(img, W - 210, 108, 190)
        _paste_chara(img, 4, head_h + 18)

    d = ImageDraw.Draw(img)

    # ---- 顶部标题 ----
    d.rectangle([0, 0, W, 5], fill=ROSE)
    ty = 30
    tf = _f(29, True)
    d.text((PAD, ty), title, font=tf, fill=TEXT)
    if subtitle:
        d.text((PAD, ty + 40), subtitle, font=_f(16), fill=MUTED)
    if kind_label:
        kw = d.textlength(kind_label, font=_f(15, True))
        d.rounded_rectangle([PAD, ty + 68, PAD + kw + 22, ty + 96], radius=14,
                            fill=(255, 236, 245, 255))
        d.text((PAD + 11, ty + 73), kind_label, font=_f(15, True), fill=ROSE)

    y = head_h

    # ---- 主卡 ----
    if hero:
        box = [PAD, y, W - PAD, y + hero_h - 14]
        _soft_shadow(img, box, 20)
        d.rounded_rectangle(box, radius=20, fill=CARD + (255,))
        tx, tyy = PAD + 22, y + 16

        tier = str(hero.get("tier") or "").upper()
        if tier:
            tc = _tier_color(tier)
            d.rounded_rectangle([tx, tyy, tx + 46, tyy + 28], radius=8, fill=tc + (255,))
            tw = d.textlength(tier, font=_f(18, True))
            d.text((tx + (46 - tw) / 2, tyy + 2), tier, font=_f(18, True), fill=(255, 255, 255))
            tx += 60

        d.text((tx, tyy), str(hero.get("name", "")), font=_f(26, True), fill=TEXT)

        big = str(hero.get("big", ""))
        bf = _f(40, True)
        d.text((PAD + 22, tyy + 46), big, font=bf, fill=ROSE)
        bw_big = d.textlength(big, font=bf)
        d.text((PAD + 26 + bw_big, tyy + 62), "胜率", font=_f(15), fill=MUTED)

        sub = str(hero.get("sub") or "")
        if sub:
            sx = PAD + 30 + bw_big + 56
            d.multiline_text((sx, tyy + 50), sub, font=_f(16), fill=TEXT, spacing=7)
        y += hero_h

    # ---- 效果描述 ----
    if desc_lines:
        d.rounded_rectangle([PAD + 2, y + 10, PAD + 6, y + 28], radius=2, fill=ROSE)
        d.text((PAD + 14, y + 8), "效果", font=_f(17, True), fill=ROSE)

        box = [PAD, y + 34, W - PAD, y + 34 + desc_box_h]
        _soft_shadow(img, box, 16, blur=5, offset=2, alpha=55)
        d.rounded_rectangle(box, radius=16, fill=(255, 249, 253, 255))

        ly = y + 34 + 14
        for ln in desc_lines:
            d.text((PAD + 22, ly), ln, font=_f(17), fill=TEXT)
            ly += 27
        y += desc_h

    # ---- 分区标题 ----
    if rows and section:
        d.rounded_rectangle([PAD + 2, y + 10, PAD + 6, y + 28], radius=2, fill=ROSE)
        d.text((PAD + 14, y + 8), section, font=_f(17, True), fill=ROSE)
        y += sec_h
    elif rows:
        y += 8

    # ---- 列表 ----
    for i, r in enumerate(rows):
        ry = y + i * row_h
        box = [PAD, ry, W - PAD, ry + row_h - 8]
        _soft_shadow(img, box, 14, blur=5, offset=2, alpha=55)
        d.rounded_rectangle(box, radius=14,
                            fill=(CARD if i % 2 == 0 else CARD_ALT) + (255,))

        rk = str(r.get("rank", i + 1))
        rkf = _f(19, True)
        rkw = d.textlength(rk, font=rkf)
        d.rounded_rectangle([PAD + 14, ry + 12, PAD + 14 + max(30, rkw + 18), ry + 40],
                            radius=9, fill=LINE + (255,))
        d.text((PAD + 14 + (max(30, rkw + 18) - rkw) / 2, ry + 14), rk, font=rkf, fill=ROSE)

        nm = str(r.get("name", ""))
        f22 = _f(21, True)
        maxw = 348
        if d.textlength(nm, font=f22) > maxw:
            while nm and d.textlength(nm + "…", font=f22) > maxw:
                nm = nm[:-1]
            nm += "…"
        d.text((PAD + 62, ry + 9), nm, font=f22, fill=TEXT)

        ratio = r.get("ratio")
        if ratio is not None:
            bx, by, bw2, bh = PAD + 62, ry + 37, 320, 7
            ratio = max(0.0, min(1.0, float(ratio)))
            d.rounded_rectangle([bx, by, bx + bw2, by + bh], radius=4, fill=LINE + (255,))
            if ratio > 0:
                d.rounded_rectangle([bx, by, bx + max(bh, int(bw2 * ratio)), by + bh],
                                    radius=4, fill=ROSE_SOFT + (255,))

        val = str(r.get("value", ""))
        fv = _f(23, True)
        vw = d.textlength(val, font=fv)
        d.text((W - PAD - 20 - vw, ry + 7), val, font=fv, fill=ROSE)
        if r.get("extra"):
            ex = str(r["extra"])
            fe = _f(14)
            ew = d.textlength(ex, font=fe)
            d.text((W - PAD - 20 - ew, ry + 36), ex, font=fe, fill=MUTED)

    # ---- 页脚 ----
    fy = H - footer_h + 4
    d.line([PAD, fy - 8, W - PAD, fy - 8], fill=LINE + (255,), width=1)
    if footer:
        d.text((PAD, fy), footer, font=_f(14), fill=MUTED)
    ts = time.strftime("%Y-%m-%d %H:%M")
    tw = d.textlength(ts, font=_f(14))
    d.text((W - PAD - tw, fy), ts, font=_f(14), fill=MUTED)

    out_dir = Path(_temp_dir())
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"aram_{uuid.uuid4().hex[:10]}.png"
    img.convert("RGB").save(str(p), "PNG", optimize=True)
    return str(p)


def render_help(items, title: str = "海克斯大乱斗 · 指令帮助",
                subtitle: str = "用「/海克斯」开头，支持俗称与缩写",
                footer: str = "数据源 ARAMKit") -> str | None:
    """渲染指令帮助卡。items = [(指令, 说明), ...]"""
    if not available():
        return None
    items = list(items or [])
    has_chara = _load_chara() is not None

    head_h = 214 if has_chara else 100
    row_h = 58
    footer_h = 44
    bottom_pad = 34 if has_chara else 18
    H = head_h + len(items) * row_h + 16 + footer_h + bottom_pad

    img = _gradient(W, H)
    if has_chara:
        _glow(img, W - 210, 108, 190)
        _paste_chara(img, 4, head_h + 18)

    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 5], fill=ROSE)
    d.text((PAD, 30), title, font=_f(29, True), fill=TEXT)
    if subtitle:
        d.text((PAD, 70), subtitle, font=_f(16), fill=MUTED)

    y = head_h
    for i, (cmd, desc) in enumerate(items):
        ry = y + i * row_h
        box = [PAD, ry, W - PAD, ry + row_h - 8]
        _soft_shadow(img, box, 14, blur=5, offset=2, alpha=55)
        d.rounded_rectangle(box, radius=14,
                            fill=(CARD if i % 2 == 0 else CARD_ALT) + (255,))

        # 左侧指令
        cf = _f(19, True)
        cmd_txt = str(cmd)
        maxcw = 330
        if d.textlength(cmd_txt, font=cf) > maxcw:
            while cmd_txt and d.textlength(cmd_txt + "…", font=cf) > maxcw:
                cmd_txt = cmd_txt[:-1]
            cmd_txt += "…"
        d.text((PAD + 20, ry + 13), cmd_txt, font=cf, fill=ROSE)

        # 右侧说明
        if desc:
            df = _f(16)
            dtxt = str(desc)
            maxdw = 300
            if d.textlength(dtxt, font=df) > maxdw:
                while dtxt and d.textlength(dtxt + "…", font=df) > maxdw:
                    dtxt = dtxt[:-1]
                dtxt += "…"
            dw = d.textlength(dtxt, font=df)
            d.text((W - PAD - 20 - dw, ry + 16), dtxt, font=df, fill=MUTED)

    fy = H - footer_h + 4
    d.line([PAD, fy - 8, W - PAD, fy - 8], fill=LINE + (255,), width=1)
    if footer:
        d.text((PAD, fy), footer, font=_f(14), fill=MUTED)
    ts = time.strftime("%Y-%m-%d %H:%M")
    tw = d.textlength(ts, font=_f(14))
    d.text((W - PAD - tw, fy), ts, font=_f(14), fill=MUTED)

    out_dir = Path(_temp_dir())
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"aram_help_{uuid.uuid4().hex[:10]}.png"
    img.convert("RGB").save(str(p), "PNG", optimize=True)
    return str(p)


def _temp_dir() -> str:
    try:
        from astrbot.core.utils.astrbot_path import get_astrbot_temp_path
        return str(get_astrbot_temp_path())
    except Exception:
        import tempfile
        return tempfile.gettempdir()
