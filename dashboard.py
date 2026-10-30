#!/usr/bin/env python3
"""
E-Ink Dashboard — main entry point
Controls via USB keypad. No GPIO required.

Key mapping (see buttons.txt):
  1-5       → switch to screen 1-5
  6         → display on/off (sleep screen)
  7         → refresh: re-fetch data and redraw without clearing the panel first
  8 / Enter → force reset: clear the panel, then re-render
  9         → next (screen's own on_next if it has one, otherwise next screen)
  0         → previous (screen's own on_prev if it has one, otherwise previous screen)
  a         → (blank)
  b         → photos
"""

import os
import sys
import time
import threading

import display
from config import CENTRAL, WIDTH, HEIGHT
from screens import homework, calendar, photos, weather, goals

#  SCREEN REGISTRY
SCREENS = {
    1: homework,
    2: calendar,
    3: goals,
    4: weather,
    5: photos,
}

#  STATE
current_screen = 1
auto_refresh   = True
sleeping       = False

#  RENDER

def refresh_current_screen(clear=True):
    if sleeping:
        display.push(display.render_sleep_screen(CENTRAL, WIDTH, HEIGHT), "sleep", clear=clear)
        return
    print(f"→ Rendering screen {current_screen}…")
    try:
        screen = SCREENS[current_screen]
        img    = screen.render()
        display.push(img, f"{current_screen}_{screen.__name__.split('.')[-1]}", clear=clear)
    except Exception as e:
        print(f"✗ Screen {current_screen} render failed: {e}")


#  KEYBOARD HANDLER

def step(direction):
    """9 / 0: let the screen handle next/previous, else move between screens."""
    global current_screen
    hook = getattr(SCREENS[current_screen], "on_next" if direction > 0 else "on_prev", None)
    if hook:
        hook()
        print(f"  → {'Next' if direction > 0 else 'Previous'} (screen {current_screen})")
    else:
        current_screen = (current_screen - 1 + direction) % len(SCREENS) + 1
        print(f"  → {'Next' if direction > 0 else 'Previous'} screen ({current_screen})")
    refresh_current_screen()

def handle_key(key):
    global current_screen, sleeping

    if key in ("1", "2", "3", "4", "5"):
        current_screen = int(key)
        print(f"  → Screen {current_screen}")
        refresh_current_screen()

    elif key == "6":
        sleeping = not sleeping
        print(f"  → Display {'OFF' if sleeping else 'ON'}")
        refresh_current_screen()

    elif key == "7":
        print("  → Refresh")
        refresh_current_screen(clear=False)

    elif key in ("8", "enter"):
        print("  → Force reset")
        refresh_current_screen()

    elif key == "9":
        step(+1)

    elif key == "0":
        step(-1)

    elif key == "b":
        # Dedicated key to jump straight to the photos screen.
        current_screen = 5
        print("  → Photos (key b)")
        refresh_current_screen()

def setup_keyboard():
    """Listen for USB keypad input using the 'keyboard' library."""
    try:
        import keyboard as kb

        def bind(key_name):
            try:
                kb.on_press_key(key_name, lambda _: handle_key(key_name))
            except Exception as e:
                print(f"⚠ Skipping key bind {key_name!r}: {e}")

        # Bind only keys your 2x6 keypad actually emits (per evtest): 0-9, a, b, enter.
        for k in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "a", "b", "enter"]:
            bind(k)

        print("✓ Keyboard listener ready.")
        return kb
    except ImportError:
        print("⚠ 'keyboard' library not installed — running without keypad support.")
        print("  Install with: pip3 install keyboard --break-system-packages")
        return None
    except Exception as e:
        print(f"⚠ Keyboard setup failed ({e}) — running without keypad support.")
        return None


#  AUTO-REFRESH THREAD

def auto_refresh_loop():
    while True:
        time.sleep(1800)
        if auto_refresh and not sleeping:
            print("→ Auto-refresh.")
            refresh_current_screen()


#  MAIN

def main():
    print("→ Starting dashboard…")
    refresh_current_screen()

    kb = setup_keyboard()
    threading.Thread(target=auto_refresh_loop, daemon=True).start()

    if kb:
        print("✓ Listening for keypad input. Ctrl+C to quit.")
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n  Exiting…")
    else:
        print("✓ Single render complete.")

if __name__ == "__main__":
    main()
