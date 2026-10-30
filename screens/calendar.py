#!/usr/bin/env python3
"""
Screen 2 — Calendar
Mon–Sun week grid of Google Calendar events.
"""

import textwrap
from datetime import datetime, timedelta

from PIL import Image, ImageDraw

from config import WIDTH, HEIGHT, CENTRAL
from display import load_font, draw_screen_indicator
from gcal import fetch_week_events, get_week_bounds, CalendarError


def render(fetch=fetch_week_events):
    img  = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    today   = datetime.now(CENTRAL).date()
    f_large = load_font(20, bold=True)
    f_small = load_font(13)
    f_tiny  = load_font(12)
    f_time  = load_font(12, bold=True)

    # ── LAYOUT ───────────────────────────────────
    HEADER_H   = 28
    DAY_HDR_H  = 22
    COL_COUNT  = 7
    COL_W      = WIDTH // COL_COUNT
    COL_TOP    = HEADER_H
    COL_BOTTOM = HEIGHT - 1
    EVENTS_BOTTOM = HEIGHT - 16          # keep clear of the screen indicator dots
    LINE_H     = 14
    ALLDAY_H   = 16

    # ── HEADER ───────────────────────────────────
    date_str = today.strftime("%A, %B") + f" {today.day} " + today.strftime("%Y")
    draw.text((4, 3), date_str, font=f_large, fill=0)
    draw.line([0, HEADER_H, WIDTH, HEADER_H], fill=0, width=1)

    # ── DATA ─────────────────────────────────────
    try:
        week, monday = fetch()
        error = None
    except CalendarError as e:
        week, error = {}, str(e)
        monday, _ = get_week_bounds()
    except Exception as e:
        print(f"✗ Calendar fetch failed: {e}")
        week, error = {}, "Couldn't reach Google Calendar"
        monday, _ = get_week_bounds()

    # ── COLUMNS ──────────────────────────────────
    for col in range(COL_COUNT):
        day_date = monday + timedelta(days=col)
        x0 = col * COL_W
        x1 = WIDTH - 1 if col == COL_COUNT - 1 else x0 + COL_W - 1
        is_today = day_date == today

        draw.rectangle([x0, COL_TOP, x1, COL_BOTTOM], outline=0, fill=1)
        draw.rectangle([x0, COL_TOP, x1, COL_TOP+DAY_HDR_H], fill=0 if is_today else 1, outline=0)
        day_label = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][col] + f" {day_date.day}"
        draw.text((x0+4, COL_TOP+4), day_label, font=f_tiny, fill=1 if is_today else 0)

        if error:
            continue

        events    = week.get(day_date, [])
        max_chars = max(1, (x1 - x0 - 8) // 7)
        y         = COL_TOP + DAY_HDR_H + 4

        for i, ev in enumerate(events):
            if ev["all_day"]:
                needed = ALLDAY_H + 3
            else:
                lines  = textwrap.wrap(ev["title"], width=max_chars)[:2] or [""]
                needed = LINE_H + len(lines) * LINE_H + 6

            # leave room for a "+N more" line unless this is the last event
            limit = EVENTS_BOTTOM if i == len(events) - 1 else EVENTS_BOTTOM - LINE_H
            if y + needed > limit:
                draw.text((x0+4, y), f"+{len(events) - i} more", font=f_tiny, fill=0)
                break

            if ev["all_day"]:
                draw.rectangle([x0+2, y, x1-2, y+ALLDAY_H], fill=0)
                draw.text((x0+5, y+1), ev["title"][:max_chars], font=f_tiny, fill=1)
            else:
                start_str = ev["start"].strftime("%I:%M %p").lstrip("0")
                draw.text((x0+4, y), start_str, font=f_time, fill=0)
                for j, line in enumerate(lines):
                    draw.text((x0+4, y + LINE_H*(j+1)), line, font=f_small, fill=0)
            y += needed

    if error:
        msg_w = int(draw.textlength(error, font=f_small))
        mx, my = (WIDTH - msg_w) // 2, HEIGHT // 2 - 10
        draw.rectangle([mx-10, my-8, mx+msg_w+10, my+24], fill=1, outline=0)
        draw.text((mx, my), error, font=f_small, fill=0)

    draw_screen_indicator(draw, 2, f_tiny, WIDTH, HEIGHT)
    return img
