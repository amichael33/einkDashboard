#!/usr/bin/env python3
"""
E-Ink Dashboard — main entry point
Controls via USB keypad. No GPIO required.

Key mapping:
  1-5       → switch to screen 1-5
  Enter     → force reset / re-render current screen
  +         → next screen
  -         → previous screen
  *         → toggle sleep
  /         → toggle auto-refresh
  0         → filter (passed to current screen if supported)
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

def refresh_current_screen():
    if sleeping:
        display.push(display.render_sleep_screen(CENTRAL, WIDTH, HEIGHT))
        return
    print(f"→ Rendering screen {current_screen}…")
    try:
        img = SCREENS[current_screen].render()
        display.push(img)
    except Exception as e:
        print(f"✗ Screen {current_screen} render failed: {e}")


#  KEYBOARD HANDLER

def handle_key(key):
    global current_screen, auto_refresh, sleeping

    if key in ("1", "2", "3", "4", "5"):
        current_screen = int(key)
        print(f"  → Screen {current_screen}")
        refresh_current_screen()

    elif key == "enter":
        print("  → Force reset")
        refresh_current_screen()

    elif key == "+":
        current_screen = (current_screen % len(SCREENS)) + 1
        print(f"  → Next screen ({current_screen})")
        refresh_current_screen()

    elif key == "-":
        current_screen = ((current_screen - 2) % len(SCREENS)) + 1
        print(f"  → Prev screen ({current_screen})")
        refresh_current_screen()

    elif key == "*":
        sleeping = not sleeping
        print(f"  → Sleep: {'ON' if sleeping else 'OFF'}")
        refresh_current_screen()

    elif key == "/":
        auto_refresh = not auto_refresh
        print(f"  → Auto-refresh: {'ON' if auto_refresh else 'OFF'}")

    elif key == "0":
        screen = SCREENS.get(current_screen)
        if hasattr(screen, "on_filter"):
            screen.on_filter()
            refresh_current_screen()

    elif key == "b":
        # Dedicated key to jump straight to the photos screen.
        current_screen = 5
        print("  → Photos (key b)")
        refresh_current_screen()

def setup_keyboard():
    """Listen for USB keypad input using the 'keyboard' library."""
    try:
        import keyboard as kb

        kb.on_press_key("1",     lambda _: handle_key("1"))
        kb.on_press_key("2",     lambda _: handle_key("2"))
        kb.on_press_key("3",     lambda _: handle_key("3"))
        kb.on_press_key("4",     lambda _: handle_key("4"))
        kb.on_press_key("5",     lambda _: handle_key("5"))
        kb.on_press_key("b",     lambda _: handle_key("b"))
        kb.on_press_key("enter", lambda _: handle_key("enter"))
        kb.on_press_key("+",     lambda _: handle_key("+"))
        kb.on_press_key("-",     lambda _: handle_key("-"))
        kb.on_press_key("*",     lambda _: handle_key("*"))
        kb.on_press_key("/",     lambda _: handle_key("/"))
        kb.on_press_key("0",     lambda _: handle_key("0"))

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
