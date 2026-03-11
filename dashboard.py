#!/usr/bin/env python3
"""
E-Ink Dashboard for Waveshare 7.5" B&W V2 (800x480)
- Header: current date (Central time) + quote of the day
- Progress row: week circles, month bar, year bar
- 6 homework columns (Mon-Fri separate, Sat+Sun merged)
- Right panel: Tasks with Eisenhower "Do" status, due within 30 days or no due date
"""

import os
import sys
import requests
from datetime import datetime, timedelta, date
from PIL import Image, ImageDraw, ImageFont
import textwrap
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
NOTION_TOKEN   = "REDACTED_NOTION_TOKEN"
HOMEWORK_DB_ID = "REDACTED_DB_ID"
TASKS_DB_ID    = "REDACTED_DB_ID"

CENTRAL = ZoneInfo("America/Chicago")

WIDTH  = 800
HEIGHT = 480

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
#  NOTION FETCH
# ─────────────────────────────────────────────
def get_week_bounds():
    today = datetime.now(CENTRAL).date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday

def fetch_notion_db(db_id, payload):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    resp = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json().get("results", [])

def parse_notion_date(date_str):
    """Parse a Notion date string (date or datetime with timezone) to a date object."""
    if not date_str:
        return None
    # Always just take the first 10 chars (YYYY-MM-DD) regardless of time/tz
    return date.fromisoformat(date_str[:10])

def fetch_homework(monday, sunday):
    # Fetch without date filter since Notion chokes on datetime vs date comparisons
    # We'll filter manually after parsing
    payload = {
        "sorts": [{"property": "Due date", "direction": "ascending"}]
    }
    pages = fetch_notion_db(HOMEWORK_DB_ID, payload)
    items = []
    for page in pages:
        props = page.get("properties", {})
        name = "".join(t.get("plain_text", "") for t in props.get("Name", {}).get("title", [])).strip() or "Untitled"
        status = props.get("Status", {}).get("status", {}).get("name", "Not started")
        due_str = props.get("Due date", {}).get("date", {})
        if due_str and due_str.get("start"):
            due = parse_notion_date(due_str["start"])
            if due and monday <= due <= sunday:
                items.append({"name": name, "status": status, "due": due})
    return items

def fetch_tasks():
    today = datetime.now(CENTRAL).date()
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
        props = page.get("properties", {})

        # Eisenhower status — formula property returns string
        eisen_prop = props.get("Eisenhower Status", {})
        formula = eisen_prop.get("formula", {})
        eisen_text = formula.get("string", "") or ""
        name_debug = "".join(t.get("plain_text", "") for t in props.get("Name", {}).get("title", [])).strip()
        print(f"  DEBUG task: '{name_debug}' | eisen='{eisen_text}'")

        # Only include "1. Do" items
        if "1. Do" not in eisen_text:
            continue

        name = "".join(t.get("plain_text", "") for t in props.get("Name", {}).get("title", [])).strip() or "Untitled"
        status = props.get("Status", {}).get("status", {}).get("name", "Inbox")

        due_str = props.get("Due Date", {}).get("date", {})
        due = parse_notion_date(due_str.get("start")) if due_str else None

        items.append({"name": name, "status": status, "due": due})
    return items

def fetch_quote():
    try:
        resp = requests.get("https://zenquotes.io/api/today", timeout=5)
        data = resp.json()
        if data:
            q = data[0]
            return f'"{q["q"]}" — {q["a"]}'
    except Exception:
        pass
    return '"Do the work." — Unknown'

# ─────────────────────────────────────────────
#  DRAW HELPERS
# ─────────────────────────────────────────────
def draw_half_filled_square(draw, x, y, size):
    """Draw a square with diagonal half-fill (top-left triangle = filled)."""
    draw.rectangle([x, y, x + size, y + size], outline=0, fill=1)
    draw.polygon([
        (x, y),
        (x + size, y),
        (x, y + size),
    ], fill=0)

def draw_empty_square(draw, x, y, size):
    draw.rectangle([x, y, x + size, y + size], outline=0, fill=1)

def draw_filled_square(draw, x, y, size):
    draw.rectangle([x, y, x + size, y + size], outline=0, fill=0)

# ─────────────────────────────────────────────
#  RENDER
# ─────────────────────────────────────────────
def render(homework_by_day, tasks, monday, quote_text):
    img  = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    today    = datetime.now(CENTRAL).date()
    f_large  = load_font(16, bold=True)
    f_med    = load_font(12, bold=True)
    f_small  = load_font(10)
    f_tiny   = load_font(9)

    # ── LAYOUT CONSTANTS ────────────────────────
    HEADER_H   = 22   # date + quote row
    PROGRESS_H = 18   # progress bars row
    TOP_H      = HEADER_H + PROGRESS_H
    TASK_PANEL = 160  # right panel width for Tasks
    HW_WIDTH   = WIDTH - TASK_PANEL
    COL_COUNT  = 6    # Mon Tue Wed Thu Fri Sat+Sun
    COL_W      = HW_WIDTH // COL_COUNT
    DAY_HDR_H  = 22
    TASK_H     = 26
    COL_TOP    = TOP_H
    COL_BOTTOM = HEIGHT - 1

    # ── HEADER: date left, quote right ──────────
    date_str = today.strftime("%A, %B %-d %Y")
    draw.text((4, 3), date_str, font=f_large, fill=0)

    # Quote — truncate to fit remaining space
    date_w = draw.textlength(date_str, font=f_large) + 12
    avail  = WIDTH - int(date_w) - 8
    q      = quote_text
    while draw.textlength(q, font=f_tiny) > avail and len(q) > 10:
        q = q[:-2] + "…"
    draw.text((int(date_w), 5), q, font=f_tiny, fill=0)

    # Thin divider under header
    draw.line([0, HEADER_H, WIDTH, HEADER_H], fill=0, width=1)

    # ── PROGRESS ROW ────────────────────────────
    py = HEADER_H + 2

    # Week progress — 7 circles
    week_day = today.weekday()  # 0=Mon, 6=Sun
    CIRCLE_R = 5
    CIRCLE_GAP = 14
    wx = 6
    draw.text((wx, py), "W", font=f_tiny, fill=0)
    wx += 14
    for i in range(7):
        cx, cy = wx + i * CIRCLE_GAP + CIRCLE_R, py + CIRCLE_R + 1
        if i < week_day:
            draw.ellipse([cx - CIRCLE_R, cy - CIRCLE_R, cx + CIRCLE_R, cy + CIRCLE_R], fill=0)
        elif i == week_day:
            draw.ellipse([cx - CIRCLE_R, cy - CIRCLE_R, cx + CIRCLE_R, cy + CIRCLE_R], outline=0, fill=1)
            draw.ellipse([cx - CIRCLE_R + 2, cy - CIRCLE_R + 2, cx + CIRCLE_R - 2, cy + CIRCLE_R - 2], fill=0)
        else:
            draw.ellipse([cx - CIRCLE_R, cy - CIRCLE_R, cx + CIRCLE_R, cy + CIRCLE_R], outline=0, fill=1)

    # Month progress bar
    days_in_month = (date(today.year, today.month % 12 + 1, 1) - timedelta(days=1)).day if today.month < 12 else 31
    month_pct = today.day / days_in_month
    mx = wx + 7 * CIRCLE_GAP + 10
    draw.text((mx, py), "M", font=f_tiny, fill=0)
    mx += 14
    BAR_W, BAR_H = 80, 10
    draw.rectangle([mx, py + 1, mx + BAR_W, py + BAR_H], outline=0, fill=1)
    draw.rectangle([mx, py + 1, mx + int(BAR_W * month_pct), py + BAR_H], fill=0)

    # Year progress bar
    yx = mx + BAR_W + 10
    draw.text((yx, py), "Y", font=f_tiny, fill=0)
    yx += 14
    year_pct = today.timetuple().tm_yday / (366 if today.year % 4 == 0 else 365)
    draw.rectangle([yx, py + 1, yx + BAR_W, py + BAR_H], outline=0, fill=1)
    draw.rectangle([yx, py + 1, yx + int(BAR_W * year_pct), py + BAR_H], fill=0)

    draw.line([0, TOP_H, WIDTH, TOP_H], fill=0, width=1)

    # ── 6 HOMEWORK COLUMNS ──────────────────────
    DAY_NAMES  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat/Sun"]
    DAY_DATES  = [monday + timedelta(days=i) for i in range(5)] + [monday + timedelta(days=5)]

    for col in range(COL_COUNT):
        x0 = col * COL_W
        x1 = x0 + COL_W - 1
        day_date = DAY_DATES[col]
        is_today = (day_date == today) or (col == 5 and today in [monday + timedelta(days=5), monday + timedelta(days=6)])

        draw.rectangle([x0, COL_TOP, x1, COL_BOTTOM], outline=0, fill=1)

        hdr_fill      = 0 if is_today else 1
        hdr_text_fill = 1 if is_today else 0
        draw.rectangle([x0, COL_TOP, x1, COL_TOP + DAY_HDR_H], fill=hdr_fill)

        day_label = DAY_NAMES[col]
        if col < 5:
            day_label += f" {day_date.strftime('%-d')}"
        else:
            sat = monday + timedelta(days=5)
            sun = monday + timedelta(days=6)
            day_label = f"Sa {sat.strftime('%-d')} / Su {sun.strftime('%-d')}"

        draw.text((x0 + 3, COL_TOP + 4), day_label, font=f_tiny, fill=hdr_text_fill)

        # Tasks — for Sat/Sun col, combine both days
        if col == 5:
            tasks_day = homework_by_day.get(monday + timedelta(days=5), []) + \
                        homework_by_day.get(monday + timedelta(days=6), [])
        else:
            tasks_day = homework_by_day.get(day_date, [])

        task_y = COL_TOP + DAY_HDR_H + 2
        for i, task in enumerate(tasks_day):
            if task_y + TASK_H > COL_BOTTOM - 2:
                remaining = len(tasks_day) - i
                draw.text((x0 + 3, task_y), f"+{remaining} more", font=f_tiny, fill=0)
                break

            draw.rectangle([x0 + 2, task_y, x1 - 2, task_y + TASK_H - 2], outline=0, fill=1)

            max_chars = max(1, (COL_W - 8) // 6)
            lines = textwrap.wrap(task["name"], width=max_chars)
            name_line = lines[0] if lines else task["name"]
            if len(lines) > 1:
                name_line = name_line[:max_chars - 1] + "…"
            draw.text((x0 + 4, task_y + 1), name_line, font=f_small, fill=0)

            sym   = STATUS_SYMBOLS.get(task["status"], "○")
            label = task["status"]
            draw.text((x0 + 4, task_y + 13), f"{sym} {label}", font=f_tiny, fill=0)

            task_y += TASK_H + 1

    # Vertical dividers
    for col in range(1, COL_COUNT):
        draw.line([col * COL_W, COL_TOP, col * COL_W, COL_BOTTOM], fill=0, width=1)

    # ── RIGHT PANEL: TASKS ───────────────────────
    px = HW_WIDTH
    draw.line([px, COL_TOP, px, COL_BOTTOM], fill=0, width=1)

    # Panel header
    draw.rectangle([px, COL_TOP, WIDTH, COL_TOP + DAY_HDR_H], fill=0)
    draw.text((px + 4, COL_TOP + 4), "★ Do First", font=f_med, fill=1)

    task_y = COL_TOP + DAY_HDR_H + 3
    SQ = 9  # checkbox size

    for task in tasks:
        if task_y + TASK_H > COL_BOTTOM - 2:
            remaining = len(tasks) - tasks.index(task)
            draw.text((px + 4, task_y), f"+{remaining} more", font=f_tiny, fill=0)
            break

        status = task["status"]
        in_progress = status in ("Next Action", "In progress")

        # Checkbox
        sq_x, sq_y = px + 3, task_y + 3
        if in_progress:
            draw_half_filled_square(draw, sq_x, sq_y, SQ)
        else:
            draw_empty_square(draw, sq_x, sq_y, SQ)

        # Task name
        text_x = px + SQ + 7
        avail_chars = max(1, (TASK_PANEL - SQ - 12) // 6)
        lines = textwrap.wrap(task["name"], width=avail_chars)
        name_line = lines[0] if lines else task["name"]
        if len(lines) > 1:
            name_line = name_line[:avail_chars - 1] + "…"
        draw.text((text_x, task_y + 1), name_line, font=f_small, fill=0)

        # Due date (if exists)
        if task["due"]:
            days_left = (task["due"] - today).days
            if days_left < 0:
                due_label = f"overdue"
            elif days_left == 0:
                due_label = "today"
            elif days_left == 1:
                due_label = "tmrw"
            else:
                due_label = task["due"].strftime("%-m/%-d")
            draw.text((text_x, task_y + 14), due_label, font=f_tiny, fill=0)

        task_y += TASK_H + 1

    return img

# ─────────────────────────────────────────────
#  PUSH TO DISPLAY
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

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    print("→ Fetching week bounds…")
    monday, sunday = get_week_bounds()
    print(f"  Week: {monday} – {sunday}")

    print("→ Querying Notion homework…")
    hw_items = fetch_homework(monday, sunday)
    print(f"  Found {len(hw_items)} homework items.")

    homework_by_day = {}
    for item in hw_items:
        homework_by_day.setdefault(item["due"], []).append(item)

    print("→ Querying Notion tasks…")
    try:
        tasks = fetch_tasks()
        print(f"  Found {len(tasks)} 'Do First' tasks.")
    except Exception as e:
        print(f"  ⚠ Tasks fetch failed: {e}")
        tasks = []

    print("→ Fetching quote…")
    quote = fetch_quote()
    print(f"  Quote: {quote[:60]}…")

    print("→ Rendering…")
    img = render(homework_by_day, tasks, monday, quote)

    print("→ Pushing to display…")
    push_to_display(img)

if __name__ == "__main__":
    main()
