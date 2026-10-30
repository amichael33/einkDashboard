# gcal.py — Google Calendar helpers
#
# One-time sign-in (opens a browser, saves token.json):
#   python gcal.py --login

import os
import sys
from datetime import datetime, timedelta, date, time

from config import (
    CREDENTIALS_FILE, TOKEN_FILE, CALENDAR_SCOPES,
    CALENDARS_TO_SHOW, CENTRAL,
)


class CalendarError(Exception):
    """A calendar problem that should be shown on screen instead of crashing."""


#  AUTH
def login():
    """Run the browser sign-in and save token.json."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    if not os.path.exists(CREDENTIALS_FILE):
        sys.exit(f"credentials.json not found at {CREDENTIALS_FILE}")
    flow  = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, CALENDAR_SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    print(f"✓ Signed in — saved {TOKEN_FILE}")

def _save_token(creds):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

def get_credentials():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google.auth.exceptions import RefreshError
    except ImportError:
        raise CalendarError("Google libraries not installed")

    if not os.path.exists(TOKEN_FILE):
        raise CalendarError("Not signed in. Run: python gcal.py --login")
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, CALENDAR_SCOPES)
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            raise CalendarError("Sign-in expired. Run: python gcal.py --login")
        _save_token(creds)
        return creds
    raise CalendarError("Sign-in invalid. Run: python gcal.py --login")


#  FETCH
def get_week_bounds():
    today  = datetime.now(CENTRAL).date()
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=6)

def fetch_week_events():
    """Return ({date: [event, ...]} for Mon–Sun of this week, monday)."""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        raise CalendarError("Google libraries not installed")

    monday, sunday = get_week_bounds()
    service = build("calendar", "v3", credentials=get_credentials(), cache_discovery=False)

    wanted    = set(CALENDARS_TO_SHOW)
    found     = set()
    calendars = []
    for cal in service.calendarList().list().execute().get("items", []):
        names = {cal.get("summaryOverride"), cal.get("summary"), cal.get("id")} & wanted
        if names:
            calendars.append(cal["id"])
            found |= names
    for name in wanted - found:
        print(f"⚠ Calendar not found: {name}")

    time_min = datetime.combine(monday, time.min, CENTRAL).isoformat()
    time_max = datetime.combine(sunday + timedelta(days=1), time.min, CENTRAL).isoformat()
    raw = []
    for cal_id in calendars:
        page_token = None
        while True:
            resp = service.events().list(
                calendarId=cal_id, timeMin=time_min, timeMax=time_max,
                singleEvents=True, orderBy="startTime", pageToken=page_token,
            ).execute()
            raw.extend(resp.get("items", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    return group_by_day(raw, monday), monday

def _declined(event):
    return any(a.get("self") and a.get("responseStatus") == "declined"
               for a in event.get("attendees", []))

def group_by_day(raw_events, monday):
    """Group Google event dicts into {date: [event]} for the 7 days from monday.

    Each event is {"title", "start" (datetime or None), "all_day"}. All-day and
    multi-day events appear on every day they cover; timed events that run past
    midnight show as all-day bars on the following days.
    """
    days = {monday + timedelta(days=i): [] for i in range(7)}
    seen = set()

    for ev in raw_events:
        if ev.get("status") == "cancelled" or _declined(ev):
            continue
        key = (ev.get("iCalUID") or ev.get("id"), str(ev.get("start")))
        if key in seen:
            continue
        seen.add(key)

        title = (ev.get("summary") or "(no title)").strip()
        start, end = ev.get("start", {}), ev.get("end", {})

        if "date" in start:
            first = date.fromisoformat(start["date"])
            last  = date.fromisoformat(end["date"]) - timedelta(days=1)
            for d in _days_between(first, last, days):
                days[d].append({"title": title, "start": None, "all_day": True})
            continue

        start_dt = datetime.fromisoformat(start["dateTime"]).astimezone(CENTRAL)
        end_dt   = datetime.fromisoformat(end["dateTime"]).astimezone(CENTRAL)
        last     = (end_dt - timedelta(microseconds=1)).date()
        if start_dt.date() in days:
            days[start_dt.date()].append({"title": title, "start": start_dt, "all_day": False})
        for d in _days_between(start_dt.date() + timedelta(days=1), last, days):
            days[d].append({"title": title, "start": None, "all_day": True})

    for events in days.values():
        events.sort(key=lambda e: (not e["all_day"], e["start"] or datetime.min.replace(tzinfo=CENTRAL)))
    return days

def _days_between(first, last, days):
    d = first
    while d <= last:
        if d in days:
            yield d
        d += timedelta(days=1)


if __name__ == "__main__":
    if "--login" in sys.argv:
        login()
    else:
        week, _ = fetch_week_events()
        for d, events in week.items():
            print(d.strftime("%a %m/%d"))
            for e in events:
                when = "all day" if e["all_day"] else e["start"].strftime("%I:%M %p").lstrip("0")
                print(f"   {when:>8}  {e['title']}")
