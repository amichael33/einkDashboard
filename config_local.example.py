# config_local.example.py - copy to config_local.py and fill in your values.
#
# config_local.py is gitignored. Put it in the repo folder, or in EINK_HOME
# (default ~/Desktop/eink) so the GitHub Actions runner's checkout can find it.

#  NOTION
NOTION_TOKEN     = "your_integration_token"
HOMEWORK_DB_ID   = "your_homework_database_id"
TASKS_DB_ID      = "your_tasks_database_id"
COUNTDOWNS_DB_ID = "your_countdowns_database_id"

#  GOOGLE CALENDAR - calendar names as they appear in Google Calendar
CALENDARS_TO_SHOW = [
    "you@example.com",
    "Work",
]

#  WEATHER (optional - defaults to Houston)
# LATITUDE  = 29.7604
# LONGITUDE = -95.3698
# LOCATION  = "Houston, Texas"

#  WAVESHARE (optional - defaults to ~/e-Paper/lib)
# WAVESHARE_LIB = "/home/pi/e-Paper/lib"
