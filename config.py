# config.py - constants for the e-ink dashboard
#
# Secrets and personal settings are NOT stored here. They are loaded from
# config_local.py (see config_local.example.py), looked up in this repo folder
# first and then in EINK_HOME. Environment variables override both.

#  SAMPLE IMAGES
# True  -> also save a PNG of every screen shown to sample_images/ (gitignored)
# False -> don't save PNGs
SAVE_SAMPLE_IMAGES = True

import os
import importlib.util
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

#  PATHS
REPO_DIR  = os.path.dirname(os.path.abspath(__file__))
# Home of the real user, even under sudo (where "~" would be /root)
HOME_DIR  = os.path.expanduser("~" + os.environ.get("SUDO_USER", ""))
# Folder on the Pi holding credentials.json, token.json, config_local.py and previews
BASE_DIR  = os.environ.get("EINK_HOME", os.path.join(HOME_DIR, "Desktop", "eink"))
ICONS_DIR = os.path.join(REPO_DIR, "icons")
SAMPLE_IMAGES_DIR = os.path.join(REPO_DIR, "sample_images")


def _load_local():
    for folder in (REPO_DIR, BASE_DIR):
        path = os.path.join(folder, "config_local.py")
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("config_local", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return vars(module)
    return {}


_local = _load_local()


def _setting(name, default=None):
    return os.environ.get(name) or _local.get(name, default)


#  DISPLAY
WIDTH  = 800
HEIGHT = 480

#  TIMEZONE
CENTRAL = ZoneInfo("America/Chicago")

#  NOTION
NOTION_TOKEN     = _setting("NOTION_TOKEN")
HOMEWORK_DB_ID   = _setting("HOMEWORK_DB_ID")
TASKS_DB_ID      = _setting("TASKS_DB_ID")
COUNTDOWNS_DB_ID = _setting("COUNTDOWNS_DB_ID")

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

#  GOOGLE CALENDAR
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE       = os.path.join(BASE_DIR, "token.json")
CALENDAR_SCOPES  = ["https://www.googleapis.com/auth/calendar.readonly"]

CALENDARS_TO_SHOW = _local.get("CALENDARS_TO_SHOW", [])

#  WEATHER
LATITUDE  = float(_setting("LATITUDE", 29.7604))
LONGITUDE = float(_setting("LONGITUDE", -95.3698))
LOCATION  = _setting("LOCATION", "Houston, Texas")

#  WAVESHARE LIB PATH
WAVESHARE_LIB = _setting("WAVESHARE_LIB", os.path.join(HOME_DIR, "e-Paper", "lib"))
PREVIEW_PATH  = os.path.join(BASE_DIR, "dashboard_preview.png")
ERROR_PATH    = os.path.join(BASE_DIR, "dashboard_error_preview.png")
