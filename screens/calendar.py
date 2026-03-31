#!/usr/bin/env python3
"""
Screen 2 — Calendar

Placeholder until calendar rendering is implemented.
"""

from datetime import datetime

from PIL import Image, ImageDraw

from config import WIDTH, HEIGHT, CENTRAL
from display import load_font, draw_screen_indicator


def render():
    img = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    now = datetime.now(CENTRAL)
    f_large = load_font(18, bold=True)
    f_med = load_font(13, bold=True)
    f_tiny = load_font(10)

    # Use a Windows-safe day formatting (Python on Windows doesn't support "%-d").
    date_str = now.strftime("%A, %B") + f" {now.day} " + now.strftime("%Y")
    draw.text((4, 3), date_str, font=f_large, fill=0)
    draw.line([0, 26, WIDTH, 26], fill=0, width=1)

    draw.text((40, 150), "Calendar", font=f_med, fill=0)
    draw.text((40, 178), "Coming soon...", font=f_med, fill=0)

    draw_screen_indicator(draw, 2, f_tiny, WIDTH, HEIGHT)
    return img
