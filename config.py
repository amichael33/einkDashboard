# config.py - all credentials and constants for the e-ink dashboard

import os
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

#  DISPLAY
WIDTH  = 800
HEIGHT = 480

#  TIMEZONE
CENTRAL = ZoneInfo("America/Chicago")

#  NOTION
NOTION_TOKEN     = "REDACTED_NOTION_TOKEN"
HOMEWORK_DB_ID   = "REDACTED_DB_ID"
TASKS_DB_ID      = "REDACTED_DB_ID"
COUNTDOWNS_DB_ID = "REDACTED_DB_ID"

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
BASE_DIR         = "/home/amichael/Desktop/eink"
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE       = os.path.join(BASE_DIR, "token.json")
CALENDAR_SCOPES  = ["https://www.googleapis.com/auth/calendar.readonly"]

CALENDARS_TO_SHOW = [
    "Aliki Michael",
    "Academics",
    "you@example.com",
    "Clubs",
    "Sports",
    "M2 Family",
]

#  WAVESHARE LIB PATH
WAVESHARE_LIB = "/home/amichael/e-Paper/lib"
PREVIEW_PATH  = os.path.join(BASE_DIR, "dashboard_preview.png")
ERROR_PATH    = os.path.join(BASE_DIR, "dashboard_error_preview.png")
