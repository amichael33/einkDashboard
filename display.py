# display.py — shared display helpers

import os
import sys
import time
from PIL import ImageFont
from config import (
    WAVESHARE_LIB, PREVIEW_PATH, ERROR_PATH,
    SAVE_SAMPLE_IMAGES, SAMPLE_IMAGES_DIR,
)


#  FONTS

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


#  DRAW HELPERS

def draw_half_filled_square(draw, x, y, size):
    """Square with bottom-right triangle filled = in progress."""
    draw.rectangle([x, y, x+size, y+size], fill=1)
    draw.polygon([(x+size, y), (x+size, y+size), (x, y+size)], fill=0)
    draw.rectangle([x, y, x+size, y+size], outline=0, fill=None)

def draw_empty_square(draw, x, y, size):
    draw.rectangle([x, y, x+size, y+size], outline=0, fill=1)

def draw_screen_indicator(draw, screen_num, f_tiny, width, height):
    """Draw 5 dots at the bottom right indicating which screen is active."""
    DOT_R  = 4
    GAP    = 14
    base_x = width - (5 * GAP) - 8
    base_y = height - DOT_R - 4
    for i in range(5):
        cx = base_x + i * GAP + DOT_R
        if i + 1 == screen_num:
            draw.ellipse([cx-DOT_R, base_y-DOT_R, cx+DOT_R, base_y+DOT_R], fill=0)
        else:
            draw.ellipse([cx-DOT_R, base_y-DOT_R, cx+DOT_R, base_y+DOT_R], outline=0, fill=1)


#  SAMPLE IMAGES

def save_sample(img, name):
    """Save a PNG of the screen to sample_images/ when SAVE_SAMPLE_IMAGES is on."""
    if not SAVE_SAMPLE_IMAGES:
        return
    try:
        os.makedirs(SAMPLE_IMAGES_DIR, exist_ok=True)
        path = os.path.join(SAMPLE_IMAGES_DIR, f"{name}.png")
        img.save(path)
        print(f"  saved sample → {path}")
    except Exception as e:
        print(f"⚠ Could not save sample image: {e}")


#  PUSH TO DISPLAY

def push(img, name="screen"):
    """Send a Pillow image to the Waveshare 7.5" V2 display."""
    save_sample(img, name)

    def _try_push():
        sys.path.insert(0, WAVESHARE_LIB)
        from waveshare_epd import epd7in5_V2
        epd = epd7in5_V2.EPD()
        epd.init()
        epd.Clear()
        epd.display(epd.getbuffer(img))
        epd.sleep()

    try:
        _try_push()
        print("✓ Display updated.")
    except ImportError:
        os.makedirs(os.path.dirname(PREVIEW_PATH), exist_ok=True)
        img.save(PREVIEW_PATH)
        print(f"⚠ Waveshare lib not found — saved preview to {PREVIEW_PATH}")
    except Exception as e:
        # Common when another process is using the Waveshare HAT, or a prior crash
        # left GPIO in a bad state. Try a single GPIO cleanup + retry.
        if "GPIO busy" in str(e):
            try:
                import RPi.GPIO as GPIO
                GPIO.cleanup()
                time.sleep(0.2)
                _try_push()
                print("✓ Display updated. (after GPIO cleanup)")
                return
            except Exception:
                pass

        print(f"✗ Display error: {e}")
        os.makedirs(os.path.dirname(ERROR_PATH), exist_ok=True)
        img.save(ERROR_PATH)
        raise


#  SLEEP SCREEN

def render_sleep_screen(central, width, height):
    from PIL import Image, ImageDraw
    from datetime import datetime
    img  = Image.new("1", (width, height), 1)
    draw = ImageDraw.Draw(img)
    t    = datetime.now(central).strftime("%I:%M %p").lstrip("0")
    f    = load_font(14)
    draw.text((10, 10), t, font=f, fill=0)
    return img
