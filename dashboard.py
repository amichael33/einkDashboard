#!/usr/bin/env python3

import os
import sys
import json
import requests
from datetime import datetime, timedelta, date
from PIL import Image, ImageDraw, ImageFont
import textwrap

#  CONFIG
NOTION_TOKEN       = "REDACTED_NOTION_TOKEN"
HOMEWORK_DB_ID     = "REDACTED_DB_ID" 

# Status display config
STATUS_SYMBOLS = {
    "Not started": "○",
    "In progress": "◑",
    "Done":        "●",
}
STATUS_LABELS = {
    "Not started": "Not started",
    "In progress": "In progress",
    "Done":        "Done",
}

#  DISPLAY SIZE  (Waveshare 7.5" V2 = 800×480)
WIDTH  = 800
HEIGHT = 480

#  NOTION API
NOTION_VERSION = "2022-06-28"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

def get_week_bounds():
    """Return Monday and Sunday of the current week."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday

def fetch_homework(monday, sunday):
    """Query Notion for homework due this week."""
    url = f"https://api.notion.com/v1/databases/{HOMEWORK_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                {
                    "property": "Due date",
                    "date": {"on_or_after": monday.isoformat()}
                },
                {
                    "property": "Due date",
                    "date": {"on_or_before": sunday.isoformat()}
                }
            ]
        },
        "sorts": [{"property": "Due date", "direction": "ascending"}]
    }
    resp = requests.post(url, headers=NOTION_HEADERS, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json().get("results", [])

def parse_homework(pages):
    """Extract name, status, due_date from Notion pages."""
    items = []
    for page in pages:
        props = page.get("properties", {})

        # Name
        name_prop = props.get("Name", {})
        title_list = name_prop.get("title", [])
        name = "".join(t.get("plain_text", "") for t in title_list).strip() or "Untitled"

        # Status
        status_prop = props.get("Status", {})
        status = status_prop.get("status", {}).get("name", "Not started")

        # Due date
        due_prop = props.get("Due date", {})
        due_str = due_prop.get("date", {})
        if due_str and due_str.get("start"):
            due = date.fromisoformat(due_str["start"][:10])
        else:
            continue  # skip items with no due date

        items.append({"name": name, "status": status, "due": due})
    return items

def fetch_quote():
    """Fetch a quote from ZenQuotes API."""
    try:
        resp = requests.get("https://zenquotes.io/api/today", timeout=5)
        data = resp.json()
        if data:
            q = data[0]
            return f'"{q["q"]}" — {q["a"]}'
    except Exception:
        pass
    return '"Do the work." — Unknown'


#  FONT HELPERS  (DejaVu bundled w/ PIL)
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


#  RENDER
def render(homework_by_day, monday, quote_text):
    img  = Image.new("1", (WIDTH, HEIGHT), 1)   # "1" = 1-bit B&W, 1=white
    draw = ImageDraw.Draw(img)

    # Fonts
    f_title  = load_font(18, bold=True)
    f_day    = load_font(13, bold=True)
    f_task   = load_font(11)
    f_status = load_font(10)
    f_quote  = load_font(9)

    DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    #  Header bar 
    HEADER_H = 30
    draw.rectangle([0, 0, WIDTH, HEADER_H], fill=0)   # black bar

    week_str = monday.strftime("%B %d") + " – " + (monday + timedelta(days=6)).strftime("%B %d, %Y")
    draw.text((8, 6), f"Homework Week  •  {week_str}", font=f_title, fill=1)  # white text

    # 7 columns
    COL_COUNT  = 7
    COL_W      = WIDTH // COL_COUNT          # ~114px each
    COL_TOP    = HEADER_H + 1
    QUOTE_H    = 20
    COL_BOTTOM = HEIGHT - QUOTE_H - 2
    COL_H      = COL_BOTTOM - COL_TOP
    DAY_HDR_H  = 28
    TASK_H     = 28                          # height per task slot

    today = date.today()

    for col, day_name in enumerate(DAY_NAMES):
        x0 = col * COL_W
        x1 = x0 + COL_W - 1
        day_date = monday + timedelta(days=col)
        is_today = (day_date == today)

        # Column border
        draw.rectangle([x0, COL_TOP, x1, COL_BOTTOM], outline=0, fill=1)

        # Day header background (filled black if today)
        hdr_fill = 0 if is_today else 1
        hdr_text_fill = 1 if is_today else 0
        draw.rectangle([x0, COL_TOP, x1, COL_TOP + DAY_HDR_H], fill=hdr_fill)

        # Day name + date number
        date_num = day_date.strftime("%-d")
        draw.text((x0 + 5, COL_TOP + 3),  day_name, font=f_day, fill=hdr_text_fill)
        draw.text((x0 + 5, COL_TOP + 15), date_num,  font=f_status, fill=hdr_text_fill)

        # Tasks for this day
        tasks = homework_by_day.get(day_date, [])
        task_y = COL_TOP + DAY_HDR_H + 3

        for task in tasks:
            if task_y + TASK_H > COL_BOTTOM - 2:
                # Draw "+N more" if overflow
                remaining = len(tasks) - tasks.index(task)
                draw.text((x0 + 4, task_y), f"+{remaining} more", font=f_status, fill=0)
                break

            # Task box
            draw.rectangle([x0 + 2, task_y, x1 - 2, task_y + TASK_H - 2], outline=0, fill=1)

            # Task name — wrap to fit column width
            max_chars = max(1, (COL_W - 10) // 6)
            name_lines = textwrap.wrap(task["name"], width=max_chars)
            name_line  = name_lines[0] if name_lines else task["name"]
            if len(name_lines) > 1:
                name_line = name_line[:max_chars - 1] + "…"
            draw.text((x0 + 5, task_y + 1), name_line, font=f_task, fill=0)

            # Status
            symbol = STATUS_SYMBOLS.get(task["status"], "○")
            label  = STATUS_LABELS.get(task["status"], task["status"])
            draw.text((x0 + 5, task_y + 14), f"{symbol} {label}", font=f_status, fill=0)

            task_y += TASK_H + 1

    # Vertical dividers between columns
    for col in range(1, COL_COUNT):
        x = col * COL_W
        draw.line([x, COL_TOP, x, COL_BOTTOM], fill=0, width=1)

    # Quote bar at bottom
    draw.rectangle([0, COL_BOTTOM + 1, WIDTH, HEIGHT], fill=0)
    # Truncate quote to fit one line
    max_q_chars = WIDTH // 5
    q_display = quote_text if len(quote_text) <= max_q_chars else quote_text[:max_q_chars - 1] + "…"
    draw.text((6, COL_BOTTOM + 4), q_display, font=f_quote, fill=1)

    return img


#  PUSH TO DISPLAY
def push_to_display(img):
    """Send image to Waveshare 7.5" V2 e-ink display."""
    try:
        # Waveshare library path (adjust if yours differs)
        sys.path.insert(0, "/home/amichael/e-Paper/lib")
        from waveshare_epd import epd7in5_V2
        epd = epd7in5_V2.EPD()
        epd.init()
        epd.Clear()
        epd.display(epd.getbuffer(img))
        epd.sleep()
        print("✓ Display updated.")
    except ImportError:
        # Save image locally if display lib not available (for testing)
        out = "/home/amichael/Desktop/eink/dashboard_preview.png"
        img.save(out)
        print(f"⚠ Waveshare lib not found — saved preview to {out}")
    except Exception as e:
        print(f"✗ Display error: {e}")
        img.save("/home/amichael/Desktop/eink/dashboard_error_preview.png")
        raise

#  MAIN
def main():
    print("→ Fetching week bounds…")
    monday, sunday = get_week_bounds()
    print(f"  Week: {monday} – {sunday}")

    print("→ Querying Notion…")
    pages = fetch_homework(monday, sunday)
    items = parse_homework(pages)
    print(f"  Found {len(items)} homework items.")

    # Group by due date
    homework_by_day = {}
    for item in items:
        homework_by_day.setdefault(item["due"], []).append(item)

    print("→ Fetching quote…")
    quote = fetch_quote()
    print(f"  Quote: {quote[:60]}…")

    print("→ Rendering image…")
    img = render(homework_by_day, monday, quote)

    print("→ Pushing to display…")
    push_to_display(img)

if __name__ == "__main__":
    main()
