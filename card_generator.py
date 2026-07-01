"""Generate HLTV-style CS player cards from GitHub data."""

import io
import math
import os
import textwrap
import urllib.request
from datetime import datetime
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter


# Card dimensions — 800x900 to fit all sections without excessive whitespace
CARD_WIDTH = 800
CARD_HEIGHT = 900
BG_COLOR = (17, 17, 17, 255)
PANEL_BG = (28, 28, 28, 220)
ACCENT_GOLD = (212, 175, 55, 255)
ACCENT_GOLD_DIM = (170, 140, 40, 255)
TEXT_WHITE = (245, 245, 245, 255)
TEXT_GRAY = (165, 165, 165, 255)
TEXT_DIM = (115, 115, 115, 255)
BAR_BG = (50, 50, 50, 255)
BAR_FILL = (160, 160, 160, 255)       # default stat bar fill
BAR_GREEN = (76, 175, 80, 255)          # RATING bar fill
BORDER_COLOR = (212, 175, 55, 255)

# Stat descriptions for tooltips (served to web UI)
STAT_DESCRIPTIONS = {
    "FIREPOWER": "Raw code output & productivity — based on repo count, push frequency, and creation events",
    "STARPOWER": "Star impact & project popularity — based on total stars, max stars, and average stars per repo",
    "LONGEVITY": "Account & project staying power — based on account age and repo maintenance consistency",
    "IMPACT": "Community reach & influence — based on followers, forks, watch events, and PR activity",
    "COLLAB": "Open-source collaboration — based on language diversity, PRs, issues, and forks",
    "VERSATILE": "Technology range & breadth — based on language count, topics, and repo diversity",
    "RATING": "Overall GitHub rating — weighted composite of all six stat dimensions above",
}


def _load_font(size: int, bold: bool = False, title: bool = False) -> ImageFont.FreeTypeFont:
    """Load a font preferring clean bold sans-serif faces.

    For titles/handles, prefers Impact (condensed, CS-card look).
    For body text, uses Segoe UI Bold or Arial Bold for clean readability.
    """
    if title:
        candidates = [
            (r"C:\Windows\Fonts\impact.ttf", True),
            (r"C:\Windows\Fonts\segoeuib.ttf", True),
            (r"C:\Windows\Fonts\arialbd.ttf", True),
        ]
    else:
        candidates = [
            (r"C:\Windows\Fonts\segoeuib.ttf", True),
            (r"C:\Windows\Fonts\arialbd.ttf", True),
            (r"C:\Windows\Fonts\segoeui.ttf", False),
            (r"C:\Windows\Fonts\arial.ttf", False),
            ("/System/Library/Fonts/Helvetica.ttc", False),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", True),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", False),
        ]

    for path, is_bold in candidates:
        if os.path.exists(path):
            if bold and not is_bold:
                continue
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    # Ultimate fallback
    for path, _ in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _text_width(text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.Draw) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _download_avatar(url: str) -> Image.Image | None:
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "gitcstv-card-generator"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def _create_placeholder_avatar(size: int, name: str = "") -> Image.Image:
    img = Image.new("RGBA", (size, size), (50, 50, 50, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, size, size], fill=(70, 70, 70, 255))
    initials = "".join(part[0].upper() for part in name.split()[:2] if part) or "?"
    font = _load_font(size // 3, bold=True, title=True)
    bbox = draw.textbbox((0, 0), initials, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((size - tw) // 2, (size - th) // 2 - bbox[1] // 2), initials, font=font, fill=TEXT_WHITE)
    return img


def _round_avatar_with_fade(img: Image.Image, target_size: int) -> Image.Image:
    """Crop to square, resize, apply circular mask with radial edge fade."""
    src_w, src_h = img.size
    size = min(src_w, src_h)
    left = (src_w - size) // 2
    top = (src_h - size) // 2
    cropped = img.crop((left, top, left + size, top + size))
    cropped = cropped.resize((target_size, target_size), Image.Resampling.LANCZOS)

    mask = Image.new("L", (target_size, target_size), 0)
    cx = cy = target_size // 2
    for y in range(target_size):
        for x in range(target_size):
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx * dx + dy * dy)
            r = target_size // 2
            if dist < r * 0.70:
                mask.putpixel((x, y), 255)
            elif dist < r:
                t = (dist - r * 0.70) / (r * 0.30)
                mask.putpixel((x, y), int(255 * (1 - t * t)))
            else:
                mask.putpixel((x, y), 0)

    out = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
    out.paste(cropped, (0, 0), mask)
    return out


def _draw_stylized_handle(draw, handle: str, x: int, y: int,
                          font, fill: Tuple[int, ...]) -> None:
    """Render handle in gold, replacing '0' with a crosshair circle."""
    cx = x
    for ch in handle:
        if ch == "0":
            bbox = draw.textbbox((0, 0), "0", font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            cx += w // 2
            cy = y + h // 2 - bbox[1]
            r = min(w, h) // 2 - 2
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=fill, width=3)
            draw.line([cx - r, cy, cx + r, cy], fill=fill, width=2)
            draw.line([cx, cy - r, cx, cy + r], fill=fill, width=2)
            cx += w // 2 + 4
        else:
            draw.text((cx, y), ch, font=font, fill=fill)
            bbox = draw.textbbox((cx, y), ch, font=font)
            cx += bbox[2] - bbox[0]


def _draw_panel(draw, x: int, y: int, w: int, h: int) -> None:
    draw.rectangle([x, y, x + w, y + h], fill=PANEL_BG)
    draw.rectangle([x, y, x + w, y + h], outline=(75, 75, 75, 255), width=1)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


# ===========================================================================
# Public API
# ===========================================================================

def generate_card(data: dict, stats: dict, rank: int, output_path: str) -> None:
    card = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(card)
    _render(draw, card, data, stats, rank)
    card.convert("RGB").save(output_path, "PNG")


def generate_card_to_bytes(data: dict, stats: dict, rank: int) -> bytes:
    card = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(card)
    _render(draw, card, data, stats, rank)
    buf = io.BytesIO()
    card.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _render(draw: ImageDraw.Draw, card: Image.Image, data: dict, stats: dict, rank: int) -> None:
    # ------- Fonts ----------------------------------------------------------
    f_handle   = _load_font(58, bold=True, title=True)
    f_subtitle = _load_font(17)
    f_section  = _load_font(16, bold=True, title=True)
    f_label    = _load_font(14, bold=True, title=True)
    f_value    = _load_font(15)
    f_small    = _load_font(11)
    f_rank     = _load_font(130, bold=True, title=True)
    f_brand    = _load_font(14, bold=True, title=True)
    f_award    = _load_font(14)
    f_event    = _load_font(13)
    f_badge    = _load_font(13, bold=True, title=True)

    # ------- Background -----------------------------------------------------
    # Gold thick bar on the LEFT edge (matching HLTV card style)
    draw.rectangle([0, 0, 5, CARD_HEIGHT], fill=ACCENT_GOLD)

    # Subtle vignette
    for i in range(CARD_HEIGHT):
        draw.line([(0, i), (CARD_WIDTH, i)], fill=(22, 22, 22, int(10 + 18 * i / CARD_HEIGHT)))

    # Gold top accent
    draw.rectangle([0, 0, CARD_WIDTH, 3], fill=ACCENT_GOLD)

    # ------- Right: Avatar --------------------------------------------------
    avatar_size = 290
    avatar_x = CARD_WIDTH - avatar_size - 55
    avatar_y = 50

    avatar = _download_avatar(data.get("avatar_url", ""))
    if avatar is None:
        avatar = _create_placeholder_avatar(avatar_size, data.get("name", ""))
    avatar = _round_avatar_with_fade(avatar, avatar_size)

    # Gold glow
    gs = avatar_size + 100
    glow = Image.new("RGBA", (gs, gs), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([0, 0, gs, gs], fill=(212, 175, 55, 35))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=45))
    card.paste(glow, (avatar_x + avatar_size // 2 - gs // 2, avatar_y + avatar_size // 2 - gs // 2), glow)
    card.paste(avatar, (avatar_x, avatar_y), avatar)

    # ------- Left layout constants ------------------------------------------
    lx = 20
    rx = avatar_x - 15  # right edge of left content

    # ------- Header ---------------------------------------------------------
    handle = data["login"].upper()
    _draw_stylized_handle(draw, handle, lx, 25, f_handle, ACCENT_GOLD)

    name = data.get("name", data["login"])
    age_y = data["account_age_days"] / 365.25
    parts = [name]
    if data.get("company"):
        parts.append(data["company"])
    if data.get("location"):
        parts.append(data["location"])
    parts.append(f"{age_y:.1f}y on GitHub")
    draw.text((lx, 90), "  \u2022  ".join(parts), font=f_subtitle, fill=TEXT_GRAY)

    # ------- MVP / EVP panel ------------------------------------------------
    ay = 120
    ah = 85
    _draw_panel(draw, lx, ay, rx - lx, ah)

    draw.text((lx + 8, ay + 6), "MVP AWARDS", font=f_section, fill=TEXT_WHITE)
    draw.text(((lx + rx) // 2 + 5, ay + 6), "EVP AWARDS", font=f_section, fill=TEXT_WHITE)

    mvp_list = stats["awards"].get("mvp", [])
    evp_list = stats["awards"].get("evp", [])
    col_mid = (lx + rx) // 2

    ln_y = ay + 30
    for i in range(min(3, max(len(mvp_list), len(evp_list), 1))):
        mvp_t = f"\u2022 {_truncate(mvp_list[i], 14)}" if i < len(mvp_list) else "\u2022 \u2014"
        evp_t = f"\u2022 {_truncate(evp_list[i], 14)}" if i < len(evp_list) else "\u2022 \u2014"
        c = ACCENT_GOLD if i < len(mvp_list) else TEXT_DIM
        e_c = ACCENT_GOLD_DIM if i < len(evp_list) else TEXT_DIM
        draw.text((lx + 10, ln_y + i * 20), mvp_t, font=f_award, fill=c)
        draw.text((col_mid + 5, ln_y + i * 20), evp_t, font=f_award, fill=e_c)

    # ------- Event placings -------------------------------------------------
    ey = ay + ah + 12
    draw.text((lx, ey), "EVENT PLACINGS", font=f_section, fill=TEXT_WHITE)
    ey += 26

    events_list = stats.get("events", [])
    col_w = (rx - lx) // 3
    for i, ev in enumerate(events_list[:3]):
        cx = lx + i * col_w
        place = ["1ST", "2ND", "3RD"][i]
        draw.rounded_rectangle([cx, ey, cx + 30, ey + 18], radius=3, fill=ACCENT_GOLD)
        bw = _text_width(place, f_badge, draw)
        draw.text((cx + (30 - bw) // 2, ey), place, font=f_badge, fill=BG_COLOR)

        # Repo name — truncate long names
        parts_ev = ev.split(" ")
        repo_name = _truncate(parts_ev[1], 14)
        repo_details = " ".join(parts_ev[2:])
        draw.text((cx, ey + 22), repo_name, font=f_event, fill=TEXT_WHITE)
        draw.text((cx, ey + 38), repo_details, font=f_small, fill=TEXT_GRAY)

    # ------- Personal stats panel -------------------------------------------
    sy = ey + 68
    sh = 270
    _draw_panel(draw, lx, sy, rx - lx, sh)

    draw.text((lx + 8, sy + 8), "PERSONAL STATS", font=f_section, fill=TEXT_WHITE)

    lbl_w = 95
    bar_w = (rx - lx) - lbl_w - 55
    bar_x = lx + lbl_w + 8
    avg_x = bar_x + int(bar_w * 0.5)
    bar_top = sy + 42

    draw.text((avg_x - _text_width("AVERAGE", f_small, draw) // 2, bar_top - 14),
              "AVERAGE", font=f_small, fill=TEXT_DIM)

    stat_items = [
        ("FIREPOWER",  stats["firepower"]),
        ("STARPOWER",  stats["starpower"]),
        ("LONGEVITY",  stats["longevity"]),
        ("IMPACT",     stats["impact_score"]),
        ("COLLAB",     stats["collaboration"]),
        ("VERSATILE",  stats["versatility"]),
        ("RATING",     int(stats["rating"] * 100)),
    ]

    for j, (label, val) in enumerate(stat_items):
        row_y = bar_top + j * 33
        # RATING is last, highlighted in green and gold
        is_rating = (label == "RATING")
        label_color = ACCENT_GOLD if is_rating else TEXT_GRAY

        draw.text((lx + 8, row_y), label, font=f_label, fill=label_color)

        bar_y = row_y + 7
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 12], radius=6, fill=BAR_BG)

        max_val = 150 if is_rating else 100
        ratio = min(val / max_val, 1.0)
        fill_color = BAR_GREEN if is_rating else BAR_FILL
        fw = int(bar_w * ratio)
        if fw > 0:
            draw.rounded_rectangle([bar_x, bar_y, bar_x + fw, bar_y + 12], radius=6, fill=fill_color)

        draw.line([avg_x, bar_y - 2, avg_x, bar_y + 14], fill=TEXT_WHITE, width=1)
        val_text = f"{stats['rating']:.2f}" if is_rating else str(val)
        draw.text((bar_x + bar_w + 10, row_y), val_text, font=f_value, fill=TEXT_WHITE)

    # ------- Notable stats --------------------------------------------------
    ny = sy + sh + 14
    draw.text((lx, ny), "NOTABLE STATS", font=f_section, fill=TEXT_WHITE)
    ny += 26

    repos = data["repos"]
    notables = [
        f"{stats['rating']:.2f} rating (#{rank})",
        f"{repos['total_stars']:,} total stars",
        f"{repos['max_stars']:,} max repo stars",
        f"{repos['total']:,} public repos",
        f"{age_y:.1f} years on GitHub",
        f"{data['followers']:,} followers",
        f"{repos['language_count']} languages",
        f"{repos['total_forks']:,} forks",
    ]
    c1, c2 = notables[:4], notables[4:]
    cm = (lx + rx) // 2
    for i, line in enumerate(c1):
        draw.text((lx, ny + i * 22), f"\u2022 {line}", font=f_event, fill=TEXT_GRAY)
    for i, line in enumerate(c2):
        draw.text((cm, ny + i * 22), f"\u2022 {line}", font=f_event, fill=TEXT_GRAY)

    # ------- Rank & Branding ------------------------------------------------
    rank_y = 700
    rank_x = CARD_WIDTH - 275
    draw.text((rank_x, rank_y), f"#{rank}", font=f_rank, fill=ACCENT_GOLD)

    # Brand text centered below the rank number, moved down to avoid overlap
    brand_text = "HLTV-STYLE"
    brand_text2 = "TOP 20  //  2026"
    brand_y = rank_y + 135
    b1_w = _text_width(brand_text, f_brand, draw)
    b2_w = _text_width(brand_text2, f_brand, draw)
    rank_w = _text_width(f"#{rank}", f_rank, draw)
    rank_cx = rank_x + rank_w // 2
    draw.text((rank_cx - b1_w // 2, brand_y), brand_text, font=f_brand, fill=TEXT_GRAY)
    draw.text((rank_cx - b2_w // 2, brand_y + 21), brand_text2, font=f_brand, fill=TEXT_DIM)
