# notion.py — shared Notion API helpers

import requests
from datetime import datetime, timedelta, date
from config import (
    NOTION_HEADERS, HOMEWORK_DB_ID, TASKS_DB_ID,
    COUNTDOWNS_DB_ID, CENTRAL
)

#  CORE
def fetch_notion_db(db_id, payload):
    """Fetch all pages from a Notion database, handling pagination."""
    url         = f"https://api.notion.com/v1/databases/{db_id}/query"
    all_results = []
    cursor      = None
    while True:
        body = {**payload}
        if cursor:
            body["start_cursor"] = cursor
        resp = requests.post(url, headers=NOTION_HEADERS, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        all_results.extend(data.get("results", []))
        if data.get("has_more"):
            cursor = data.get("next_cursor")
        else:
            break
    return all_results

def parse_notion_date(date_str):
    """Parse a Notion date string (date or datetime with timezone) to a date object."""
    if not date_str:
        return None
    return date.fromisoformat(date_str[:10])

def get_week_bounds():
    today  = datetime.now(CENTRAL).date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday

def get_text(props, key):
    """Extract plain text from a Notion title or rich_text property."""
    prop = props.get(key, {})
    blocks = prop.get("title") or prop.get("rich_text") or []
    return "".join(t.get("plain_text", "") for t in blocks).strip()

#  HOMEWORK
def fetch_homework():
    monday, sunday = get_week_bounds()
    payload = {"sorts": [{"property": "Due date", "direction": "ascending"}]}
    pages   = fetch_notion_db(HOMEWORK_DB_ID, payload)
    items   = []
    for page in pages:
        props  = page.get("properties", {})
        name   = get_text(props, "Name") or "Untitled"
        status = props.get("Status", {}).get("status", {}).get("name", "Not started")
        due_str = props.get("Due date", {}).get("date", {})
        if due_str and due_str.get("start"):
            start = parse_notion_date(due_str["start"])
            end   = parse_notion_date(due_str.get("end")) if due_str.get("end") else start
            if start and end and not (end < monday or start > sunday):
                clamped_start = max(start, monday)
                clamped_end   = min(end, sunday)
                items.append({
                    "name":     name,
                    "status":   status,
                    "due":      start,
                    "start":    clamped_start,
                    "end":      clamped_end,
                    "multiday": end > start,
                })
    items = [i for i in items if i["status"] != "Done"]
    return items, monday

#  TASKS
def fetch_tasks():
    today  = datetime.now(CENTRAL).date()
    cutoff = today + timedelta(days=30)
    payload = {"sorts": [{"property": "Due Date", "direction": "ascending"}]}
    pages   = fetch_notion_db(TASKS_DB_ID, payload)
    items   = []
    for page in pages:
        props      = page.get("properties", {})
        eisen_text = props.get("Eisenhower Status", {}).get("formula", {}).get("string", "") or ""
        if "1. Do" not in eisen_text:
            continue
        status = props.get("Status", {}).get("status", {}).get("name", "Inbox")
        if status == "Completed":
            continue
        name    = get_text(props, "Name") or "Untitled"
        due_str = props.get("Due Date", {}).get("date", {})
        due     = parse_notion_date(due_str.get("start")) if due_str else None
        if due and (due - today).days > 30:
            continue
        items.append({"name": name, "status": status, "due": due})
    return items

#  COUNTDOWNS
def fetch_countdowns():
    today   = datetime.now(CENTRAL).date()
    payload = {"sorts": [{"property": "Date", "direction": "ascending"}]}
    pages   = fetch_notion_db(COUNTDOWNS_DB_ID, payload)
    items   = []
    for page in pages:
        props = page.get("properties", {})
        mode  = props.get("Mode", {}).get("select", {})
        if not mode or mode.get("name") != "Days Until":
            continue
        if props.get("done", {}).get("checkbox", False):
            continue
        name    = get_text(props, "Countdown") or "Untitled"
        due_str = props.get("Date", {}).get("date", {})
        due     = parse_notion_date(due_str.get("start")) if due_str else None
        if due and due >= today:
            items.append({
                "name":      name,
                "due":       due,
                "days_left": (due - today).days,
            })
    return items[:5]
