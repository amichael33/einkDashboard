#!/usr/bin/env python3
"""
E-Ink Multi-Screen Dashboard — Waveshare 7.5" B&W V2 (800x480)
Screens:
  1. Homework + Tasks (default)
  2. Temperature
  3. Reserved
  4. Reserved
  5. Quotes (from Notion)

GPIO:
  Big buttons   : 16, 20, 21, 12, 25  → switch screens
  Small buttons : 24 (reset), 23 (next/ctx), 22 (filter/ctx), 27 (prev/ctx)
  Switches      : 5 (on/off), 6 (auto-refresh), 13 (sleep/wake)
"""

import os
import sys
import time
import threading
import requests
import textwrap
from datetime import datetime, timedelta, date

from PIL import Image, ImageDraw, ImageFont

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
NOTION_TOKEN      = "REDACTED_NOTION_TOKEN"
HOMEWORK_DB_ID    = "REDACTED_DB_ID"
TASKS_DB_ID       = "REDACTED_DB_ID"
QUOTES_DB_ID      = "REDACTED_DB_ID"
COUNTDOWNS_DB_ID  = "REDACTED_DB_ID"

CENTRAL = ZoneInfo("America/Chicago")
WIDTH, HEIGHT = 800, 480

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

STATUS_SYMBOLS = {
    "Not started": "○",
    "In progress": "◑",
    "Done":        "●",
}

# ─────────────────────────────────────────────
#  GPIO PINS
# ─────────────────────────────────────────────
PIN_BIG     = [16, 20, 21, 12, 25]   # screens 1-5
PIN_RESET   = 24
PIN_NEXT    = 23
PIN_FILTER  = 22
PIN_PREV    = 27
PIN_ONOFF   = 5
PIN_AUTOREF = 6
PIN_SLEEP   = 13

# ─────────────────────────────────────────────
#  STATE
# ─────────────────────────────────────────────
current_screen  = 1
auto_refresh    = True
sleeping        = False
quote_index     = 0
quote_filter    = None
all_quotes      = []
filtered_quotes = []

# ─────────────────────────────────────────────
#  FONTS
# ─────────────────────────────────────────────
def load_font(size, bold=False):
    paths = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans{'-Bold' if bold else '-Regular'}.ttf",
        f"/usr/share/fonts/truetype/freefont/FreeSans{'Bold' if bold else ''}.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

# ─────────────────────────────────────────────
#  NOTION HELPERS
# ─────────────────────────────────────────────
def fetch_notion_db(db_id, payload):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    all_results = []
    cursor = None
    while True:
        body = {**payload}
        if cursor:
            body["start_cursor"] = cursor
        resp = requests.post(url, headers=NOTION_HEADERS, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        all_results.extend(data.get("results", []))
        if data.get("has_more"):
            cursor = data.get("next_cursor")
        else:
            break
    return all_results

def parse_notion_date(date_str):
    if not date_str:
        return None
    return date.fromisoformat(date_str[:10])

def get_week_bounds():
    today  = datetime.now(CENTRAL).date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday

# ─────────────────────────────────────────────
#  DATA FETCHERS
# ─────────────────────────────────────────────
def fetch_homework():
    monday, sunday = get_week_bounds()
    payload = {"sorts": [{"property": "Due date", "direction": "ascending"}]}
    pages   = fetch_notion_db(HOMEWORK_DB_ID, payload)
    items   = []
    for page in pages:
        props  = page.get("properties", {})
        name   = "".join(t.get("plain_text", "") for t in props.get("Name", {}).get("title", [])).strip() or "Untitled"
        status = props.get("Status", {}).get("status", {}).get("name", "Not started")
        due_str = props.get("Due date", {}).get("date", {})
        if due_str and due_str.get("start"):
            due = parse_notion_date(due_str["start"])
            if due and monday <= due <= sunday:
                items.append({"name": name, "status": status, "due": due})
    return items, monday

def fetch_tasks():
    today  = datetime.now(CENTRAL).date()
    cutoff = today + timedelta(days=30)
    payload = {
        "filter": {"and": [
            {"property": "Status", "status": {"does_not_equal": "Completed"}},
            {"or": [
                {"property": "Due Date", "date": {"is_empty": True}},
                {"property": "Due Date", "date": {"on_or_before": cutoff.isoformat()}},
            ]}
        ]},
        "sorts": [{"property": "Due Date", "direction": "ascending"}]
    }
    pages = fetch_notion_db(TASKS_DB_ID, payload)
    items = []
    for page in pages:
        props      = page.get("properties", {})
        eisen_text = props.get("Eisenhower Status", {}).get("formula", {}).get("string", "") or ""
        if "1. Do" not in eisen_text:
            continue
        name    = "".join(t.get("plain_text", "") for t in props.get("Name", {}).get("title", [])).strip() or "Untitled"
        status  = props.get("Status", {}).get("status", {}).get("name", "Inbox")
        due_str = props.get("Due Date", {}).get("date", {})
        due     = parse_notion_date(due_str.get("start")) if due_str else None
        items.append({"name": name, "status": status, "due": due})
    return items

def fetch_quotes():
    payload = {"sorts": [{"property": "Author", "direction": "ascending"}]}
    pages   = fetch_notion_db(QUOTES_DB_ID, payload)
    items   = []
    for page in pages:
        props  = page.get("properties", {})
        quote  = "".join(t.get("plain_text", "") for t in props.get("Quote", {}).get("title", [])).strip()
        author = "".join(t.get("plain_text", "") for t in props.get("Author", {}).get("rich_text", [])).strip()
        cat_prop = props.get("Category", {})
        if cat_prop.get("select"):
            category = cat_prop["select"].get("name", "")
        elif cat_prop.get("multi_select"):
            category = ", ".join(o["name"] for o in cat_prop["multi_select"])
        else:
            category = ""
        if quote:
            items.append({"quote": quote, "author": author, "category": category})
    return items

def fetch_temperature():
    try:
        import glob
        base   = "/sys/bus/w1/devices/"
        device = glob.glob(base + "28*")[0]
        with open(device + "/w1_slave") as f:
            lines = f.readlines()
        if lines[0].strip().endswith("YES"):
            temp_c = float(lines[1].split("=")[1]) / 1000.0
            temp_f = temp_c * 9 / 5 + 32
            return round(temp_c, 1), round(temp_f, 1)
    except Exception:
        pass
    return None, None

def fetch_countdowns():
    """Fetch next 5 upcoming Days Until countdowns that aren't done."""
    today   = datetime.now(CENTRAL).date()
    payload = {
        "filter": {"and": [
            {"property": "Mode",  "select":   {"equals": "Days Until"}},
            {"property": "done",  "checkbox": {"equals": False}},
            {"property": "Date",  "date":     {"on_or_after": today.isoformat()}},
        ]},
        "sorts": [{"property": "Date", "direction": "ascending"}],
        "page_size": 5,
    }
    pages = fetch_notion_db(COUNTDOWNS_DB_ID, payload)
    items = []
    for page in pages:
        props = page.get("properties", {})
        name  = "".join(t.get("plain_text", "") for t in props.get("Countdown", {}).get("title", [])).strip() or "Untitled"
        due_str = props.get("Date", {}).get("date", {})
        due     = parse_notion_date(due_str.get("start")) if due_str else None
        if due:
            days_left = (due - today).days
            items.append({"name": name, "due": due, "days_left": days_left})
    return items[:5]

# ─────────────────────────────────────────────
#  DRAW HELPERS
# ─────────────────────────────────────────────
def draw_half_filled_square(draw, x, y, size):
    """Square with bottom-right triangle filled (top-left empty) = in progress."""
    # White background
    draw.rectangle([x, y, x+size, y+size], fill=1)
    # Fill bottom-right triangle
    draw.polygon([(x+size, y), (x+size, y+size), (x, y+size)], fill=0)
    # Border on top of everything
    draw.rectangle([x, y, x+size, y+size], outline=0, fill=None)

def draw_empty_square(draw, x, y, size):
    draw.rectangle([x, y, x+size, y+size], outline=0, fill=1)

def draw_screen_indicator(draw, screen_num, f_tiny):
    DOT_R  = 4
    GAP    = 14
    base_x = WIDTH - (5 * GAP) - 8
    base_y = HEIGHT - DOT_R - 4
    for i in range(5):
        cx = base_x + i * GAP + DOT_R
        if i + 1 == screen_num:
            draw.ellipse([cx-DOT_R, base_y-DOT_R, cx+DOT_R, base_y+DOT_R], fill=0)
        else:
            draw.ellipse([cx-DOT_R, base_y-DOT_R, cx+DOT_R, base_y+DOT_R], outline=0, fill=1)

# ─────────────────────────────────────────────
#  SCREEN RENDERERS
# ─────────────────────────────────────────────
def render_homework_screen():
    hw_items, monday = fetch_homework()
    tasks            = fetch_tasks()

    homework_by_day = {}
    for item in hw_items:
        homework_by_day.setdefault(item["due"], []).append(item)

    img  = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    today   = datetime.now(CENTRAL).date()
    f_large = load_font(20, bold=True)
    f_med   = load_font(15, bold=True)
    f_small = load_font(13)
    f_tiny  = load_font(12)

    HEADER_H   = 28
    PROGRESS_H = 22
    TOP_H      = HEADER_H + PROGRESS_H
    TASK_PANEL = 170
    HW_WIDTH   = WIDTH - TASK_PANEL
    COL_COUNT  = 6
    COL_W      = HW_WIDTH // COL_COUNT
    DAY_HDR_H  = 26
    TASK_H     = 38
    COL_TOP    = TOP_H
    COL_BOTTOM = HEIGHT - 1

    # Header
    date_str = today.strftime("%A, %B %-d %Y")
    draw.text((4, 3), date_str, font=f_large, fill=0)
    draw.line([0, HEADER_H, WIDTH, HEADER_H], fill=0, width=1)

    # Progress row
    py         = HEADER_H + 2
    week_day   = today.weekday()
    CIRCLE_R   = 5
    CIRCLE_GAP = 14
    wx = 4
    draw.text((wx, py), "Week", font=f_tiny, fill=0)
    wx += int(draw.textlength("Week", font=f_tiny)) + 6
    for i in range(7):
        cx, cy = wx + i * CIRCLE_GAP + CIRCLE_R, py + CIRCLE_R + 1
        if i < week_day:
            draw.ellipse([cx-CIRCLE_R, cy-CIRCLE_R, cx+CIRCLE_R, cy+CIRCLE_R], fill=0)
        elif i == week_day:
            draw.ellipse([cx-CIRCLE_R, cy-CIRCLE_R, cx+CIRCLE_R, cy+CIRCLE_R], outline=0, fill=1)
            draw.ellipse([cx-CIRCLE_R+2, cy-CIRCLE_R+2, cx+CIRCLE_R-2, cy+CIRCLE_R-2], fill=0)
        else:
            draw.ellipse([cx-CIRCLE_R, cy-CIRCLE_R, cx+CIRCLE_R, cy+CIRCLE_R], outline=0, fill=1)

    days_in_month = (date(today.year, today.month % 12 + 1, 1) - timedelta(days=1)).day if today.month < 12 else 31
    month_pct = today.day / days_in_month
    mx = wx + 7 * CIRCLE_GAP + 12
    draw.text((mx, py), "Month", font=f_tiny, fill=0)
    mx += int(draw.textlength("Month", font=f_tiny)) + 6
    BAR_W, BAR_H = 80, 10
    draw.rectangle([mx, py+2, mx+BAR_W, py+BAR_H+2], outline=0, fill=1)
    draw.rectangle([mx, py+2, mx+int(BAR_W*month_pct), py+BAR_H+2], fill=0)

    yx = mx + BAR_W + 12
    draw.text((yx, py), "Year", font=f_tiny, fill=0)
    yx += int(draw.textlength("Year", font=f_tiny)) + 6
    year_pct = today.timetuple().tm_yday / (366 if today.year % 4 == 0 else 365)
    draw.rectangle([yx, py+2, yx+BAR_W, py+BAR_H+2], outline=0, fill=1)
    draw.rectangle([yx, py+2, yx+int(BAR_W*year_pct), py+BAR_H+2], fill=0)

    draw.line([0, TOP_H, WIDTH, TOP_H], fill=0, width=1)

    # Homework columns
    DAY_DATES = [monday + timedelta(days=i) for i in range(5)] + [monday + timedelta(days=5)]
    for col in range(COL_COUNT):
        x0       = col * COL_W
        x1       = x0 + COL_W - 1
        day_date = DAY_DATES[col]
        is_today = (day_date == today) or (col == 5 and today in [monday+timedelta(days=5), monday+timedelta(days=6)])

        draw.rectangle([x0, COL_TOP, x1, COL_BOTTOM], outline=0, fill=1)
        hdr_fill      = 0 if is_today else 1
        hdr_text_fill = 1 if is_today else 0
        draw.rectangle([x0, COL_TOP, x1, COL_TOP+DAY_HDR_H], fill=hdr_fill)

        if col < 5:
            day_label = ["Mon","Tue","Wed","Thu","Fri"][col] + f" {day_date.strftime('%-d')}"
        else:
            sat = monday + timedelta(days=5)
            sun = monday + timedelta(days=6)
            day_label = f"Sa {sat.strftime('%-d')}/Su {sun.strftime('%-d')}"
        draw.text((x0+3, COL_TOP+4), day_label, font=f_tiny, fill=hdr_text_fill)

        tasks_day = (homework_by_day.get(monday+timedelta(days=5), []) +
                     homework_by_day.get(monday+timedelta(days=6), [])) if col == 5 \
                    else homework_by_day.get(day_date, [])

        task_y = COL_TOP + DAY_HDR_H + 2
        for i, task in enumerate(tasks_day):
            if task_y + TASK_H > COL_BOTTOM - 2:
                draw.text((x0+3, task_y), f"+{len(tasks_day)-i} more", font=f_tiny, fill=0)
                break
            draw.rectangle([x0+2, task_y, x1-2, task_y+TASK_H-2], outline=0, fill=1)
            max_chars = max(1, (COL_W-8) // 7)
            lines     = textwrap.wrap(task["name"], width=max_chars)
            # Draw up to 2 lines of task name
            draw.text((x0+4, task_y+1), lines[0] if lines else task["name"], font=f_small, fill=0)
            if len(lines) > 1:
                draw.text((x0+4, task_y+14), lines[1], font=f_small, fill=0)
            sym = STATUS_SYMBOLS.get(task["status"], "○")
            draw.text((x0+4, task_y+27), f"{sym} {task['status']}", font=f_tiny, fill=0)
            task_y += TASK_H + 1

    for col in range(1, COL_COUNT):
        draw.line([col*COL_W, COL_TOP, col*COL_W, COL_BOTTOM], fill=0, width=1)

    # ── RIGHT PANEL ──────────────────────────────
    px         = HW_WIDTH
    PANEL_MID  = COL_TOP + (COL_BOTTOM - COL_TOP) // 2
    SQ         = 11
    PANEL_TASK_H = 38

    draw.line([px, COL_TOP, px, COL_BOTTOM], fill=0, width=1)

    # ── TOP HALF: Do First tasks ─────────────────
    draw.rectangle([px, COL_TOP, WIDTH, COL_TOP+DAY_HDR_H], fill=0)
    draw.text((px+4, COL_TOP+4), "★ Do First", font=f_med, fill=1)

    task_y = COL_TOP + DAY_HDR_H + 3
    for task in tasks:
        if task_y + PANEL_TASK_H > PANEL_MID - 2:
            draw.text((px+4, task_y), f"+{len(tasks)-tasks.index(task)} more", font=f_tiny, fill=0)
            break
        in_progress = task["status"] in ("Next Action", "In progress")
        if in_progress:
            draw_half_filled_square(draw, px+3, task_y+3, SQ)
        else:
            draw_empty_square(draw, px+3, task_y+3, SQ)
        text_x      = px + SQ + 7
        avail_chars = max(1, (TASK_PANEL - SQ - 14) // 7)
        lines       = textwrap.wrap(task["name"], width=avail_chars)
        draw.text((text_x, task_y+1), lines[0] if lines else task["name"], font=f_small, fill=0)
        if len(lines) > 1:
            draw.text((text_x, task_y+14), lines[1], font=f_small, fill=0)
        if task["due"]:
            days_left = (task["due"] - today).days
            due_label = "overdue" if days_left < 0 else "today" if days_left == 0 else "tmrw" if days_left == 1 else task["due"].strftime("%-m/%-d")
            draw.text((text_x, task_y+27), due_label, font=f_tiny, fill=0)
        task_y += PANEL_TASK_H + 1

    # Divider between halves
    draw.line([px, PANEL_MID, WIDTH, PANEL_MID], fill=0, width=1)

    # ── BOTTOM HALF: Countdowns ──────────────────
    draw.rectangle([px, PANEL_MID, WIDTH, PANEL_MID+DAY_HDR_H], fill=0)
    draw.text((px+4, PANEL_MID+4), "⏳ Countdowns", font=f_med, fill=1)

    try:
        countdowns = fetch_countdowns()
    except Exception as e:
        print(f"  ⚠ Countdowns fetch failed: {e}")
        countdowns = []

    CDN_TASK_H = 32
    cdn_y = PANEL_MID + DAY_HDR_H + 3
    for cdn in countdowns:
        if cdn_y + CDN_TASK_H > COL_BOTTOM - 2:
            break
        days = cdn["days_left"]
        if days == 0:
            days_label = "Today!"
        elif days == 1:
            days_label = "Tmrw"
        else:
            days_label = f"{days}d"

        # Days badge (left-aligned)
        badge_str = days_label
        badge_w   = int(draw.textlength(badge_str, font=f_tiny)) + 6
        badge_x   = px + 3
        draw.rectangle([badge_x, cdn_y+3, badge_x+badge_w, cdn_y+CDN_TASK_H-4], fill=0)
        draw.text((badge_x+3, cdn_y+6), badge_str, font=f_tiny, fill=1)

        # Name to the right of badge
        text_x      = badge_x + badge_w + 5
        avail_chars = max(1, (WIDTH - text_x - 4) // 7)
        lines       = textwrap.wrap(cdn["name"], width=avail_chars)
        draw.text((text_x, cdn_y+3),  lines[0] if lines else cdn["name"], font=f_small, fill=0)
        if len(lines) > 1:
            draw.text((text_x, cdn_y+17), lines[1], font=f_tiny, fill=0)

        cdn_y += CDN_TASK_H + 1

    draw_screen_indicator(draw, 1, f_tiny)
    return img


def render_temperature_screen():
    img  = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    today   = datetime.now(CENTRAL)
    f_large = load_font(19, bold=True)
    f_huge  = load_font(80, bold=True)
    f_med   = load_font(24)
    f_tiny  = load_font(11)

    date_str = today.strftime("%A, %B %-d %Y  %-I:%M %p")
    draw.text((4, 3), date_str, font=f_large, fill=0)
    draw.line([0, 26, WIDTH, 26], fill=0, width=1)

    temp_c, temp_f = fetch_temperature()
    if temp_c is not None:
        temp_str = f"{temp_f}°F"
        tw = draw.textlength(temp_str, font=f_huge)
        draw.text(((WIDTH - tw) // 2, 80), temp_str, font=f_huge, fill=0)
        c_str = f"{temp_c}°C"
        draw.text(((WIDTH - draw.textlength(c_str, font=f_med)) // 2, 190), c_str, font=f_med, fill=0)
        if temp_f < 60:
            feel = "Cold"
        elif temp_f < 72:
            feel = "Comfortable"
        elif temp_f < 82:
            feel = "Warm"
        else:
            feel = "Hot"
        draw.text(((WIDTH - draw.textlength(feel, font=f_med)) // 2, 230), feel, font=f_med, fill=0)
    else:
        msg = "No temperature sensor detected"
        draw.text(((WIDTH - draw.textlength(msg, font=f_med)) // 2, 200), msg, font=f_med, fill=0)
        draw.text((20, 240), "Connect a DS18B20 sensor and enable 1-Wire in raspi-config", font=f_tiny, fill=0)

    draw_screen_indicator(draw, 2, f_tiny)
    return img


def render_quotes_screen():
    global all_quotes, filtered_quotes, quote_index, quote_filter

    img  = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    f_large  = load_font(19, bold=True)
    f_quote  = load_font(22)
    f_author = load_font(16, bold=True)
    f_tiny   = load_font(11)
    f_small  = load_font(13)

    today    = datetime.now(CENTRAL).date()
    date_str = today.strftime("%A, %B %-d %Y")
    draw.text((4, 3), date_str, font=f_large, fill=0)

    cat_label = f"Category: {quote_filter or 'All'}"
    draw.text((WIDTH - int(draw.textlength(cat_label, font=f_tiny)) - 6, 6), cat_label, font=f_tiny, fill=0)
    draw.line([0, 26, WIDTH, 26], fill=0, width=1)

    if not filtered_quotes:
        draw.text((20, 200), "No quotes found. Add some to your Notion database!", font=f_small, fill=0)
        draw_screen_indicator(draw, 5, f_tiny)
        return img

    q = filtered_quotes[quote_index % len(filtered_quotes)]

    # Index indicator
    idx_str = f"{(quote_index % len(filtered_quotes)) + 1} / {len(filtered_quotes)}"
    draw.text((WIDTH - int(draw.textlength(idx_str, font=f_tiny)) - 6, HEIGHT - 20), idx_str, font=f_tiny, fill=0)

    # Opening quote mark
    MARGIN = 40
    draw.text((MARGIN - 20, 40), "\u201c", font=load_font(60, bold=True), fill=0)

    # Quote text
    MAX_W     = WIDTH - MARGIN * 2
    char_w    = 12
    max_chars = MAX_W // char_w
    lines     = textwrap.wrap(q["quote"], width=max_chars)
    y         = 80
    LINE_H    = 32
    for line in lines:
        draw.text((MARGIN, y), line, font=f_quote, fill=0)
        y += LINE_H

    # Author
    y += 10
    draw.text((MARGIN, y), f"\u201d  \u2014 {q['author']}", font=f_author, fill=0)

    # Category tag
    if q["category"]:
        y += 34
        draw.text((MARGIN, y), f"[ {q['category']} ]", font=f_tiny, fill=0)

    # Button hints
    hints = "Small 4: Prev  |  Small 2: Next  |  Small 3: Filter category  |  Small 1: Refresh"
    draw.text((10, HEIGHT - 20), hints, font=f_tiny, fill=0)

    draw_screen_indicator(draw, 5, f_tiny)
    return img


def render_reserved_screen(screen_num):
    img  = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)
    f_large = load_font(24, bold=True)
    f_small = load_font(16)
    draw.text((40, 180), f"Screen {screen_num}", font=f_large, fill=0)
    draw.text((40, 220), "Coming soon...", font=f_small, fill=0)
    draw_screen_indicator(draw, screen_num, load_font(11))
    return img


def render_sleep_screen():
    img  = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)
    t    = datetime.now(CENTRAL).strftime("%-I:%M %p")
    f    = load_font(14)
    draw.text((10, 10), t, font=f, fill=0)
    return img

# ─────────────────────────────────────────────
#  DISPLAY
# ─────────────────────────────────────────────
def push_to_display(img):
    try:
        sys.path.insert(0, "/home/amichael/e-Paper/lib")
        from waveshare_epd import epd7in5_V2
        epd = epd7in5_V2.EPD()
        epd.init()
        epd.Clear()
        epd.display(epd.getbuffer(img))
        epd.sleep()
        print("✓ Display updated.")
    except ImportError:
        out = "/home/amichael/Desktop/eink/dashboard_preview.png"
        img.save(out)
        print(f"⚠ Waveshare lib not found — saved preview to {out}")
    except Exception as e:
        print(f"✗ Display error: {e}")
        img.save("/home/amichael/Desktop/eink/dashboard_error_preview.png")
        raise

def refresh_current_screen():
    if sleeping:
        push_to_display(render_sleep_screen())
        return
    print(f"→ Rendering screen {current_screen}…")
    if current_screen == 1:
        img = render_homework_screen()
    elif current_screen == 2:
        img = render_temperature_screen()
    elif current_screen == 5:
        img = render_quotes_screen()
    else:
        img = render_reserved_screen(current_screen)
    push_to_display(img)

# ─────────────────────────────────────────────
#  GPIO
# ─────────────────────────────────────────────
def setup_gpio():
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        for pin in PIN_BIG + [PIN_RESET, PIN_NEXT, PIN_FILTER, PIN_PREV,
                               PIN_ONOFF, PIN_AUTOREF, PIN_SLEEP]:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        for i, pin in enumerate(PIN_BIG):
            s = i + 1
            GPIO.add_event_detect(pin, GPIO.RISING,
                callback=lambda ch, s=s: on_screen_button(s), bouncetime=300)

        GPIO.add_event_detect(PIN_RESET,   GPIO.RISING, callback=on_reset,   bouncetime=300)
        GPIO.add_event_detect(PIN_NEXT,    GPIO.RISING, callback=on_next,    bouncetime=300)
        GPIO.add_event_detect(PIN_FILTER,  GPIO.RISING, callback=on_filter,  bouncetime=300)
        GPIO.add_event_detect(PIN_PREV,    GPIO.RISING, callback=on_prev,    bouncetime=300)
        GPIO.add_event_detect(PIN_ONOFF,   GPIO.BOTH,   callback=on_onoff,   bouncetime=500)
        GPIO.add_event_detect(PIN_AUTOREF, GPIO.BOTH,   callback=on_autoref, bouncetime=500)
        GPIO.add_event_detect(PIN_SLEEP,   GPIO.BOTH,   callback=on_sleep,   bouncetime=500)

        print("✓ GPIO ready.")
        return GPIO
    except ImportError:
        print("⚠ RPi.GPIO not available — running without button support.")
        return None

def on_screen_button(screen):
    global current_screen, all_quotes, filtered_quotes, quote_index
    print(f"  → Screen {screen}")
    current_screen = screen
    if screen == 5:
        all_quotes      = fetch_quotes()
        filtered_quotes = all_quotes[:]
        quote_index     = 0
    refresh_current_screen()

def on_reset(channel):
    global all_quotes, filtered_quotes, quote_index
    print("  → Force reset")
    if current_screen == 5:
        all_quotes      = fetch_quotes()
        filtered_quotes = [q for q in all_quotes if quote_filter is None or q["category"] == quote_filter]
        quote_index     = 0
    refresh_current_screen()

def on_next(channel):
    global quote_index
    if current_screen == 5 and filtered_quotes:
        quote_index = (quote_index + 1) % len(filtered_quotes)
        refresh_current_screen()

def on_prev(channel):
    global quote_index
    if current_screen == 5 and filtered_quotes:
        quote_index = (quote_index - 1) % len(filtered_quotes)
        refresh_current_screen()

def on_filter(channel):
    global quote_filter, filtered_quotes, quote_index
    if current_screen == 5 and all_quotes:
        categories   = [None] + sorted(set(q["category"] for q in all_quotes if q["category"]))
        idx          = categories.index(quote_filter) if quote_filter in categories else 0
        quote_filter = categories[(idx + 1) % len(categories)]
        filtered_quotes = [q for q in all_quotes if quote_filter is None or q["category"] == quote_filter]
        quote_index  = 0
        print(f"  Filter: {quote_filter or 'All'} ({len(filtered_quotes)} quotes)")
        refresh_current_screen()

def on_onoff(channel):
    import RPi.GPIO as GPIO
    if not GPIO.input(PIN_ONOFF):
        print("  → Off switch triggered, exiting.")
        cleanup()
        os._exit(0)

def on_autoref(channel):
    global auto_refresh
    import RPi.GPIO as GPIO
    auto_refresh = bool(GPIO.input(PIN_AUTOREF))
    print(f"  → Auto-refresh: {'ON' if auto_refresh else 'OFF'}")

def on_sleep(channel):
    global sleeping
    import RPi.GPIO as GPIO
    sleeping = bool(GPIO.input(PIN_SLEEP))
    print(f"  → Sleep: {'ON' if sleeping else 'OFF'}")
    refresh_current_screen()

def cleanup():
    try:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
    except Exception:
        pass

# ─────────────────────────────────────────────
#  AUTO-REFRESH THREAD
# ─────────────────────────────────────────────
def auto_refresh_loop():
    while True:
        time.sleep(1800)  # every 30 minutes
        if auto_refresh and not sleeping:
            print("→ Auto-refresh.")
            refresh_current_screen()

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    global all_quotes, filtered_quotes

    print("→ Starting dashboard…")

    print("→ Loading quotes…")
    try:
        all_quotes      = fetch_quotes()
        filtered_quotes = all_quotes[:]
        print(f"  Loaded {len(all_quotes)} quotes.")
    except Exception as e:
        print(f"  ⚠ Quotes fetch failed: {e}")

    refresh_current_screen()

    gpio = setup_gpio()

    threading.Thread(target=auto_refresh_loop, daemon=True).start()

    if gpio:
        print("✓ Listening for buttons. Ctrl+C to quit.")
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n  Exiting…")
            cleanup()
    else:
        print("✓ Single render complete.")

if __name__ == "__main__":
    main()
