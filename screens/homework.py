#!/usr/bin/env python3
"""
Screen 1 — Homework + Tasks + Countdowns
Matches the original dashboard layout exactly.
"""

import textwrap
from datetime import datetime, timedelta, date

from PIL import Image, ImageDraw

from config import WIDTH, HEIGHT, CENTRAL, STATUS_SYMBOLS
from display import (
    load_font, draw_half_filled_square, draw_empty_square,
    draw_screen_indicator
)
from notion import fetch_homework, fetch_tasks, fetch_countdowns


def render():
    hw_items, monday = fetch_homework()
    tasks            = fetch_tasks()

    img  = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    today   = datetime.now(CENTRAL).date()
    f_large = load_font(20, bold=True)
    f_med   = load_font(15, bold=True)
    f_small = load_font(13)
    f_tiny  = load_font(12)

    # ── LAYOUT ───────────────────────────────────
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

    # ── HEADER ───────────────────────────────────
    date_str = today.strftime("%A, %B %-d %Y")
    draw.text((4, 3), date_str, font=f_large, fill=0)
    draw.line([0, HEADER_H, WIDTH, HEADER_H], fill=0, width=1)

    # ── PROGRESS ROW ─────────────────────────────
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

    days_in_month = (date(today.year, today.month % 12 + 1, 1) - timedelta(days=1)).day \
                    if today.month < 12 else 31
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

    # ── COLUMN HEADERS ───────────────────────────
    DAY_DATES = [monday + timedelta(days=i) for i in range(5)] + [monday + timedelta(days=5)]
    for col in range(COL_COUNT):
        x0       = col * COL_W
        x1       = x0 + COL_W - 1
        day_date = DAY_DATES[col]
        is_today = (day_date == today) or (
            col == 5 and today in [monday+timedelta(days=5), monday+timedelta(days=6)]
        )
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

    # ── DATE → COLUMN HELPER ─────────────────────
    def date_to_col(d):
        delta = (d - monday).days
        if delta < 0 or delta > 6:
            return None
        return min(delta, 5)

    # ── HOMEWORK TASKS ───────────────────────────
    col_task_y = [COL_TOP + DAY_HDR_H + 2] * COL_COUNT
    sorted_items = sorted(hw_items, key=lambda t: (0 if not t["multiday"] else 1, t["start"]))
    drawn = set()

    for task in sorted_items:
        tid = id(task)
        if tid in drawn:
            continue
        drawn.add(tid)

        start_col = date_to_col(task["start"])
        end_col   = date_to_col(task["end"])
        if start_col is None:
            continue
        if end_col is None:
            end_col = 5

        x0_task = start_col * COL_W + 2
        x1_task = end_col * COL_W + COL_W - 2
        task_y  = col_task_y[start_col]
        if task_y + TASK_H > COL_BOTTOM - 2:
            continue

        # Box height based on content
        span_w    = x1_task - x0_task
        max_chars = max(1, (span_w - 8) // 7)
        lines     = textwrap.wrap(task["name"], width=max_chars)
        line_count = min(2, len(lines))
        box_h = max(14 + line_count * 13 + 14, TASK_H - 2)

        draw.rectangle([x0_task, task_y, x1_task, task_y+box_h], outline=0, fill=1)

        y_text = task_y + 3
        for line in lines[:2]:
            draw.text((x0_task+4, y_text), line, font=f_small, fill=0)
            y_text += 14
        sym = STATUS_SYMBOLS.get(task["status"], "○")
        draw.text((x0_task+4, y_text+1), f"{sym} {task['status']}", font=f_tiny, fill=0)

        actual_h = y_text + 14 - task_y
        for c in range(start_col, end_col+1):
            col_task_y[c] = task_y + actual_h + 6

    # ── VERTICAL DIVIDERS (skip multi-day spans) ──
    blocked = {}
    for task in hw_items:
        if not task["multiday"]:
            continue
        sc = date_to_col(task["start"])
        ec = date_to_col(task["end"])
        if sc is None or ec is None:
            continue
        for div_col in range(sc+1, ec+1):
            if div_col not in blocked:
                blocked[div_col] = []
            blocked[div_col].append((COL_TOP+DAY_HDR_H+2, col_task_y[sc]-3))

    for col in range(1, COL_COUNT):
        x = col * COL_W
        segs_to_skip = blocked.get(col, [])
        all_points   = [(COL_TOP+DAY_HDR_H, False), (COL_BOTTOM, False)]
        for (y0, y1) in segs_to_skip:
            all_points.append((y0, True))
            all_points.append((y1, False))
        all_points.sort(key=lambda p: p[0])

        y_draw   = COL_TOP + DAY_HDR_H
        skipping = False
        for (y_pt, is_skip_start) in all_points:
            if not skipping and y_pt > y_draw:
                draw.line([x, y_draw, x, y_pt], fill=0, width=1)
            skipping = is_skip_start
            if not skipping:
                y_draw = y_pt
        if not skipping and y_draw < COL_BOTTOM:
            draw.line([x, y_draw, x, COL_BOTTOM], fill=0, width=1)

    # ── RIGHT PANEL ───────────────────────────────
    px        = HW_WIDTH
    PANEL_MID = COL_TOP + (COL_BOTTOM - COL_TOP) // 2
    SQ        = 11
    PANEL_TASK_H = 38

    draw.line([px, COL_TOP, px, COL_BOTTOM], fill=0, width=1)

    # Top half: Do First tasks
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
            due_label = ("overdue" if days_left < 0 else
                         "today"   if days_left == 0 else
                         "tmrw"    if days_left == 1 else
                         task["due"].strftime("%-m/%-d"))
            draw.text((text_x, task_y+27), due_label, font=f_tiny, fill=0)
        task_y += PANEL_TASK_H + 1

    # Divider
    draw.line([px, PANEL_MID, WIDTH, PANEL_MID], fill=0, width=1)

    # Bottom half: Countdowns
    draw.rectangle([px, PANEL_MID, WIDTH, PANEL_MID+DAY_HDR_H], fill=0)

    # Hourglass
    hx, hy = px+5, PANEL_MID+4
    hw_w, hh = 10, 18
    draw.polygon([(hx, hy), (hx+hw_w, hy), (hx+hw_w//2, hy+hh//2)], fill=1)
    draw.polygon([(hx, hy+hh), (hx+hw_w, hy+hh), (hx+hw_w//2, hy+hh//2)], fill=1)
    draw.line([hx, hy, hx+hw_w, hy], fill=1, width=2)
    draw.line([hx, hy+hh, hx+hw_w, hy+hh], fill=1, width=2)
    draw.text((px+hw_w+9, PANEL_MID+4), "Countdowns", font=f_med, fill=1)

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
        days_label = ("Today!" if days == 0 else
                      "Tmrw"   if days == 1 else
                      f"{days}d")

        badge_str = days_label
        badge_w   = int(draw.textlength(badge_str, font=f_tiny)) + 6
        badge_x   = px + 3
        draw.rectangle([badge_x, cdn_y+3, badge_x+badge_w, cdn_y+CDN_TASK_H-4], fill=0)
        draw.text((badge_x+3, cdn_y+6), badge_str, font=f_tiny, fill=1)

        text_x      = badge_x + badge_w + 5
        avail_chars = max(1, (WIDTH - text_x - 4) // 7)
        lines       = textwrap.wrap(cdn["name"], width=avail_chars)
        draw.text((text_x, cdn_y+3),  lines[0] if lines else cdn["name"], font=f_small, fill=0)
        if len(lines) > 1:
            draw.text((text_x, cdn_y+17), lines[1], font=f_tiny, fill=0)

        cdn_y += CDN_TASK_H + 1

    draw_screen_indicator(draw, 1, f_tiny, WIDTH, HEIGHT)
    return img
