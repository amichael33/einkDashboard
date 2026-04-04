#!/usr/bin/env python3
"""
Screen 4 — Weather

Layout:
  ┌─────────────────────────────────────┐
  │     Location Name  /  Date          │  ← HEADER
  ├──────────────┬──────────────────────┤
  │  LEFT HALF   │     RIGHT HALF       │
  │  ┌────┬────┐ │  ┌──────┬──────┐    │
  │  │icon│temp│ │  │col A │col B │    │  ← MIDDLE
  │  │    │feels│ │  │      │      │    │
  │  └────┴────┘ │  └──────┴──────┘    │
  ├──────────────┴──────────────────────┤
  │  Mon  Tue  Wed  Thu  Fri  Sat  Sun  │  ← FORECAST
  └─────────────────────────────────────┘

Left half  → split left/right: icon | temp + feels like
Right half → split left/right:
  Col A: Sunrise, Wind, Pressure, Visibility
  Col B: Sunset, Humidity, UV Index, Air Quality
Each data point: icon left, label small above value, value bold
"""

import os
import requests
from datetime import datetime

from PIL import Image, ImageDraw

from config import WIDTH, HEIGHT, CENTRAL
from display import load_font, draw_screen_indicator

# ─────────────────────────────────────────────
#  LOCATION
# ─────────────────────────────────────────────
LATITUDE  = 29.7604
LONGITUDE = -95.3698
LOCATION  = "Houston, Texas"
ICONS_DIR = "/home/amichael/Desktop/eink/icons"

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def wmo_to_icon(code, is_day=1):
    s = "d" if is_day else "n"
    if code == 0:                            return f"01{s}"
    if code in (1, 2):                       return f"02{s}"
    if code == 3:                            return "04d"
    if code in (45, 48):                     return "50d"
    if code in (51, 53, 61, 63, 80, 81):     return f"10{s}"
    if code in (55, 65, 82):                 return "09d"
    if code in (56,57,66,67,71,73,75,77,85,86): return "13d"
    if code in (95, 96, 99):                 return "11d"
    return f"01{s}"

def wind_arrow(deg):
    return ["↑","↗","→","↘","↓","↙","←","↖"][round(deg/45)%8]

def aqi_label(val):
    if val is None: return "N/A"
    if val <= 20:   return "Good"
    if val <= 40:   return "Fair"
    if val <= 60:   return "Moderate"
    if val <= 80:   return "Poor"
    if val <= 100:  return "V.Poor"
    return "Ext.Poor"

def load_icon(name, size):
    name = name.replace(".png","")
    path = os.path.join(ICONS_DIR, f"{name}.png")
    if not os.path.exists(path):
        ph = Image.new("1", size, 1)
        ImageDraw.Draw(ph).rectangle([0,0,size[0]-1,size[1]-1], outline=0)
        return ph
    src = Image.open(path).convert("RGBA")
    bg  = Image.new("RGBA", src.size, (255,255,255,255))
    bg.paste(src, mask=src.split()[3])
    bw  = bg.convert("L").point(lambda p: 255 if p > 180 else 0, "1")
    return bw.resize(size, Image.LANCZOS)

def get_hourly_value(hourly, key, now):
    for i, t in enumerate(hourly.get("time",[])):
        try:
            dt = datetime.fromisoformat(t).astimezone(CENTRAL)
            if dt.date() == now.date() and dt.hour == now.hour:
                vals = hourly.get(key, [])
                return vals[i] if i < len(vals) else None
        except Exception:
            pass
    return None

# ─────────────────────────────────────────────
#  FETCH
# ─────────────────────────────────────────────
def fetch_weather():
    r = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": LATITUDE, "longitude": LONGITUDE,
        "current":  "temperature_2m,apparent_temperature,weathercode,"
                    "windspeed_10m,winddirection_10m,relativehumidity_2m,"
                    "surface_pressure,visibility,is_day",
        "daily":    "weathercode,temperature_2m_max,temperature_2m_min,"
                    "sunrise,sunset",
        "temperature_unit": "fahrenheit",
        "windspeed_unit":   "mph",
        "timezone":         "America/Chicago",
        "forecast_days":    8,
    }, timeout=10)
    r.raise_for_status()
    return r.json()

def fetch_aqi():
    r = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
        "latitude": LATITUDE, "longitude": LONGITUDE,
        "hourly":   "european_aqi,uv_index",
        "timezone": "America/Chicago",
    }, timeout=10)
    r.raise_for_status()
    return r.json()

# ─────────────────────────────────────────────
#  DRAW DATA POINT
# ─────────────────────────────────────────────
def draw_data_point(img, draw, x, y, w, h, icon_name, label, value, f_label, f_value):
    """
    Draw a single data point cell:
    [icon] label (small)
           value (bold)
    """
    ICO = 24
    icon = load_icon(icon_name, (ICO, ICO))
    # Center icon vertically in cell
    ico_y = y + (h - ICO) // 2
    img.paste(icon, (x + 2, ico_y))

    tx = x + ICO + 6
    # Center text block vertically
    block_h = 12 + 16  # label + value
    ty = y + (h - block_h) // 2
    draw.text((tx, ty),      label, font=f_label, fill=0)
    draw.text((tx, ty + 13), value, font=f_value, fill=0)

# ─────────────────────────────────────────────
#  RENDER
# ─────────────────────────────────────────────
def render():
    img  = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)
    now  = datetime.now(CENTRAL)

    f_title  = load_font(19, bold=True)
    f_date   = load_font(13)
    f_huge   = load_font(42, bold=True)
    f_feels  = load_font(12)
    f_label  = load_font(10)
    f_value  = load_font(13, bold=True)
    f_tiny   = load_font(10)
    f_med    = load_font(12, bold=True)

    # ── HEADER ───────────────────────────────────
    HEADER_H = 42

    loc_w = int(draw.textlength(LOCATION, font=f_title))
    draw.text(((WIDTH - loc_w) // 2, 2), LOCATION, font=f_title, fill=0)

    date_str = now.strftime("%A, %B %-d")
    date_w   = int(draw.textlength(date_str, font=f_date))
    draw.text(((WIDTH - date_w) // 2, 23), date_str, font=f_date, fill=0)

    draw.line([0, HEADER_H, WIDTH, HEADER_H], fill=0, width=1)

    # ── FETCH ─────────────────────────────────────
    try:
        weather = fetch_weather()
        aqi_raw = fetch_aqi()
    except Exception as e:
        print(f"  ⚠ Weather fetch failed: {e}")
        draw.text((20, 180), "Weather unavailable", font=f_value, fill=0)
        draw_screen_indicator(draw, 4, f_tiny, WIDTH, HEIGHT)
        return img

    cur    = weather.get("current", {})
    daily  = weather.get("daily",   {})
    hourly = aqi_raw.get("hourly",  {})

    cur_temp  = round(cur.get("temperature_2m", 0))
    feels     = round(cur.get("apparent_temperature", 0))
    wmo       = cur.get("weathercode", 0)
    wind_spd  = round(cur.get("windspeed_10m", 0), 1)
    wind_deg  = cur.get("winddirection_10m", 0)
    humidity  = round(cur.get("relativehumidity_2m", 0))
    pressure  = round(cur.get("surface_pressure", 0))
    vis_raw   = cur.get("visibility", 0)
    is_day    = cur.get("is_day", 1)

    vis_mi  = round(vis_raw / 1609.34, 1)
    vis_str = f"≥{vis_mi}" if vis_mi >= 6.2 else str(vis_mi)

    uv_val  = get_hourly_value(hourly, "uv_index", now)
    aqi_val = get_hourly_value(hourly, "european_aqi", now)
    uv_str  = str(round(uv_val, 2)) if uv_val  is not None else "N/A"
    aqi_str = f"{round(aqi_val)} {aqi_label(aqi_val)}" if aqi_val is not None else "N/A"

    sunrise_str = sunset_str = "N/A"
    if daily.get("sunrise"):
        sunrise_str = datetime.fromisoformat(daily["sunrise"][0]).astimezone(CENTRAL).strftime("%-I:%M %p")
    if daily.get("sunset"):
        sunset_str  = datetime.fromisoformat(daily["sunset"][0]).astimezone(CENTRAL).strftime("%-I:%M %p")

    # ── LAYOUT ───────────────────────────────────
    FORECAST_H = 95
    MID_TOP    = HEADER_H + 1
    MID_BOT    = HEIGHT - FORECAST_H - 1
    MID_H      = MID_BOT - MID_TOP

    HALF_W     = WIDTH // 2          # left half / right half split

    # ── LEFT HALF ────────────────────────────────
    # Split into icon section and temp section
    LEFT_ICO_W  = HALF_W // 2
    LEFT_TEMP_W = HALF_W - LEFT_ICO_W

    # Big weather icon — centered in icon section
    ICO_SZ = 72
    icon   = load_icon(wmo_to_icon(wmo, is_day), (ICO_SZ, ICO_SZ))
    ico_x  = (LEFT_ICO_W - ICO_SZ) // 2
    ico_y  = MID_TOP + (MID_H - ICO_SZ) // 2
    img.paste(icon, (ico_x, ico_y))

    # Temperature — centered in temp section
    temp_str = f"{cur_temp}°F"
    tw = int(draw.textlength(temp_str, font=f_huge))
    tx = LEFT_ICO_W + (LEFT_TEMP_W - tw) // 2
    ty = MID_TOP + MID_H // 2 - 30
    draw.text((tx, ty), temp_str, font=f_huge, fill=0)

    feels_str = f"Feels Like {feels}°"
    fw = int(draw.textlength(feels_str, font=f_feels))
    fx = LEFT_ICO_W + (LEFT_TEMP_W - fw) // 2
    draw.text((fx, ty + 48), feels_str, font=f_feels, fill=0)

    # Vertical divider: left half / right half
    draw.line([HALF_W, MID_TOP, HALF_W, MID_BOT], fill=0, width=1)

    # ── RIGHT HALF ───────────────────────────────
    # Split into col A and col B
    RIGHT_X  = HALF_W + 1
    RIGHT_W  = WIDTH - HALF_W - 1
    COL_W    = RIGHT_W // 2
    COL_A_X  = RIGHT_X
    COL_B_X  = RIGHT_X + COL_W

    # 4 data points per column, evenly spaced vertically
    DP_H = MID_H // 4

    COL_A = [
        ("sunrise",    "Sunrise",     sunrise_str),
        ("wind",       "Wind",        f"{wind_spd} mph {wind_arrow(wind_deg)}"),
        ("pressure",   "Pressure",    f"{pressure} hPa"),
        ("visibility", "Visibility",  f"{vis_str} mi"),
    ]
    COL_B = [
        ("sunset",     "Sunset",      sunset_str),
        ("humidity",   "Humidity",    f"{humidity}%"),
        ("uvi",        "UV Index",    uv_str),
        ("aqi",        "Air Quality", aqi_str),
    ]

    for i, (icon_name, label, value) in enumerate(COL_A):
        y0 = MID_TOP + i * DP_H
        draw_data_point(img, draw, COL_A_X, y0, COL_W, DP_H,
                        icon_name, label, value, f_label, f_value)
        # Horizontal divider between rows (not after last)
        if i < 3:
            draw.line([COL_A_X, y0+DP_H, COL_A_X+COL_W-1, y0+DP_H], fill=0, width=1)

    # Vertical divider between col A and col B
    draw.line([COL_B_X, MID_TOP, COL_B_X, MID_BOT], fill=0, width=1)

    for i, (icon_name, label, value) in enumerate(COL_B):
        y0 = MID_TOP + i * DP_H
        draw_data_point(img, draw, COL_B_X, y0, COL_W, DP_H,
                        icon_name, label, value, f_label, f_value)
        if i < 3:
            draw.line([COL_B_X, y0+DP_H, COL_B_X+COL_W-1, y0+DP_H], fill=0, width=1)

    # ── FORECAST ─────────────────────────────────
    draw.line([0, MID_BOT, WIDTH, MID_BOT], fill=0, width=1)

    FC_COUNT = 7
    FC_W     = WIDTH // FC_COUNT
    FC_TOP   = MID_BOT + 2
    FC_ICO   = 30

    dates    = daily.get("time", [])
    hi_list  = daily.get("temperature_2m_max", [])
    lo_list  = daily.get("temperature_2m_min", [])
    wmo_list = daily.get("weathercode", [])

    for i in range(FC_COUNT):
        di = i + 1
        if di >= len(dates):
            break

        x0 = i * FC_W
        x1 = x0 + FC_W - 1

        day_dt   = datetime.strptime(dates[di], "%Y-%m-%d")
        day_name = day_dt.strftime("%a")
        is_tmrw  = (i == 0)

        # Box border
        draw.rectangle([x0+1, FC_TOP, x1-1, HEIGHT-2], outline=0, fill=1)

        # Day name header
        hdr_fill = 0 if is_tmrw else 1
        txt_fill = 1 if is_tmrw else 0
        draw.rectangle([x0+1, FC_TOP, x1-1, FC_TOP+15], fill=hdr_fill)
        dn_w = int(draw.textlength(day_name, font=f_med))
        draw.text((x0+(FC_W-dn_w)//2, FC_TOP+1), day_name, font=f_med, fill=txt_fill)

        # Icon
        fc_icon = load_icon(wmo_to_icon(wmo_list[di] if di < len(wmo_list) else 0), (FC_ICO, FC_ICO))
        img.paste(fc_icon, (x0+(FC_W-FC_ICO)//2, FC_TOP+17))

        # High / Low
        hi = round(hi_list[di]) if di < len(hi_list) else "--"
        lo = round(lo_list[di]) if di < len(lo_list) else "--"
        hl_str = f"{hi}°/{lo}°"
        hl_w   = int(draw.textlength(hl_str, font=f_tiny))
        draw.text((x0+(FC_W-hl_w)//2, FC_TOP+49), hl_str, font=f_tiny, fill=0)

    draw_screen_indicator(draw, 4, f_tiny, WIDTH, HEIGHT)
    return img


if __name__ == "__main__":
    img = render()
    img.save("/home/amichael/Desktop/eink/weather_preview.png")
    print("Saved weather_preview.png")
