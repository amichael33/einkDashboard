#!/usr/bin/env python3
"""
Screen 4 — Weather
Matches the reference project layout, rendered in B&W with Pillow.
Icons live in /home/amichael/Desktop/eink/icons/
Uses Open-Meteo (no API key needed).

Layout:
  Header  : title + date
  Middle  : current temp + icon (left) | data points grid (right)
  Bottom  : forecast day cards
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
LOCATION  = "Houston, TX"
ICONS_DIR = "/home/amichael/Desktop/eink/icons"

# ─────────────────────────────────────────────
#  WEATHER CODE HELPERS
# ─────────────────────────────────────────────
def wmo_to_icon(code, is_day=1):
    suffix = "d" if is_day else "n"
    if code == 0:                    return f"01{suffix}"
    if code in (1, 2):               return f"02{suffix}"
    if code == 3:                    return "04d"
    if code in (45, 48):             return "50d"
    if code in (51, 53, 61, 63, 80, 81): return f"10{suffix}"
    if code in (55, 65, 82):         return "09d"
    if code in (56, 57, 66, 67, 71, 73, 75, 77, 85, 86): return "13d"
    if code in (95, 96, 99):         return "11d"
    return f"01{suffix}"

def wmo_to_desc(code):
    MAP = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Icy fog",
        51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
        61: "Light rain", 63: "Rain", 65: "Heavy rain",
        71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
        80: "Showers", 81: "Showers", 82: "Heavy showers",
        95: "Thunderstorm", 96: "T-storm/hail", 99: "T-storm/hail",
    }
    return MAP.get(code, "Unknown")

def wind_arrow(deg):
    dirs = ["↑","↗","→","↘","↓","↙","←","↖"]
    return dirs[round(deg / 45) % 8]

def aqi_label(val):
    if val is None:   return "N/A"
    if val <= 20:     return "Good"
    if val <= 40:     return "Fair"
    if val <= 60:     return "Moderate"
    if val <= 80:     return "Poor"
    if val <= 100:    return "V.Poor"
    return "Ext.Poor"

def load_icon(name, size):
    """Load PNG icon from icons dir, convert to B&W, resize."""
    # Strip extension if passed with it
    name = name.replace(".png", "")
    path = os.path.join(ICONS_DIR, f"{name}.png")
    if not os.path.exists(path):
        placeholder = Image.new("1", size, 1)
        d = ImageDraw.Draw(placeholder)
        d.rectangle([0, 0, size[0]-1, size[1]-1], outline=0)
        return placeholder
    src  = Image.open(path).convert("RGBA")
    bg   = Image.new("RGBA", src.size, (255, 255, 255, 255))
    bg.paste(src, mask=src.split()[3])
    gray = bg.convert("L")
    bw   = gray.point(lambda p: 255 if p > 180 else 0, "1")
    return bw.resize(size, Image.LANCZOS)

# ─────────────────────────────────────────────
#  FETCH
# ─────────────────────────────────────────────
def fetch_weather():
    params = {
        "latitude":           LATITUDE,
        "longitude":          LONGITUDE,
        "current":            "temperature_2m,apparent_temperature,weathercode,windspeed_10m,winddirection_10m,relativehumidity_2m,surface_pressure,visibility,is_day",
        "daily":              "weathercode,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max",
        "temperature_unit":   "fahrenheit",
        "windspeed_unit":     "mph",
        "precipitation_unit": "inch",
        "timezone":           "America/Chicago",
        "forecast_days":      6,
    }
    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def fetch_air_quality():
    params = {
        "latitude":  LATITUDE,
        "longitude": LONGITUDE,
        "hourly":    "european_aqi,uv_index",
        "timezone":  "America/Chicago",
    }
    r = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def get_hourly_value(hourly, key, now):
    times  = hourly.get("time", [])
    values = hourly.get(key, [])
    for i, t in enumerate(times):
        try:
            dt = datetime.fromisoformat(t).astimezone(CENTRAL)
            if dt.date() == now.date() and dt.hour == now.hour:
                return values[i] if i < len(values) else None
        except Exception:
            continue
    return None

# ─────────────────────────────────────────────
#  RENDER
# ─────────────────────────────────────────────
def render():
    img  = Image.new("1", (WIDTH, HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    now     = datetime.now(CENTRAL)
    f_large = load_font(18, bold=True)
    f_med   = load_font(13, bold=True)
    f_small = load_font(11)
    f_tiny  = load_font(10)
    f_huge  = load_font(46, bold=True)

    # ── HEADER ───────────────────────────────────
    HEADER_H = 24
    draw.text((4, 3), now.strftime("%A, %B %-d %Y"), font=f_large, fill=0)
    loc_w = int(draw.textlength(LOCATION, font=f_tiny))
    draw.text((WIDTH - loc_w - 4, 6), LOCATION, font=f_tiny, fill=0)
    draw.line([0, HEADER_H, WIDTH, HEADER_H], fill=0, width=1)

    # ── FETCH ─────────────────────────────────────
    try:
        weather = fetch_weather()
        aqi_raw = fetch_air_quality()
    except Exception as e:
        print(f"  ⚠ Weather fetch failed: {e}")
        draw.text((20, 180), "Weather unavailable", font=f_med, fill=0)
        draw_screen_indicator(draw, 4, f_tiny, WIDTH, HEIGHT)
        return img

    cur    = weather.get("current", {})
    daily  = weather.get("daily", {})
    hourly = aqi_raw.get("hourly", {})

    cur_temp   = round(cur.get("temperature_2m", 0))
    feels      = round(cur.get("apparent_temperature", 0))
    wmo        = cur.get("weathercode", 0)
    wind_spd   = round(cur.get("windspeed_10m", 0))
    wind_deg   = cur.get("winddirection_10m", 0)
    humidity   = round(cur.get("relativehumidity_2m", 0))
    pressure   = round(cur.get("surface_pressure", 0))
    vis_raw    = cur.get("visibility", 0)
    is_day     = cur.get("is_day", 1)

    vis_mi  = round(vis_raw / 1609.34, 1)
    vis_str = f"≥{vis_mi}" if vis_mi >= 6.2 else str(vis_mi)

    uv_val  = get_hourly_value(hourly, "uv_index", now)
    aqi_val = get_hourly_value(hourly, "european_aqi", now)

    sunrise_str, sunset_str = "", ""
    if daily.get("sunrise"):
        sr = datetime.fromisoformat(daily["sunrise"][0]).astimezone(CENTRAL)
        sunrise_str = sr.strftime("%-I:%M %p")
    if daily.get("sunset"):
        ss = datetime.fromisoformat(daily["sunset"][0]).astimezone(CENTRAL)
        sunset_str  = ss.strftime("%-I:%M %p")

    # ── ZONES ─────────────────────────────────────
    FORECAST_H = 100
    MID_TOP    = HEADER_H + 1
    MID_BOT    = HEIGHT - FORECAST_H - 1
    MID_H      = MID_BOT - MID_TOP
    CURRENT_W  = 190
    DATA_X     = CURRENT_W + 1
    DATA_W     = WIDTH - CURRENT_W

    # ── CURRENT: icon + temp ──────────────────────
    ICO_SZ  = 68
    icon    = load_icon(wmo_to_icon(wmo, is_day), (ICO_SZ, ICO_SZ))
    ico_x   = (CURRENT_W - ICO_SZ) // 2
    ico_y   = MID_TOP + 8
    img.paste(icon, (ico_x, ico_y))

    temp_str = f"{cur_temp}°F"
    tw = int(draw.textlength(temp_str, font=f_huge))
    draw.text(((CURRENT_W - tw) // 2, ico_y + ICO_SZ + 4), temp_str, font=f_huge, fill=0)

    feels_str = f"Feels {feels}°F"
    fw = int(draw.textlength(feels_str, font=f_tiny))
    draw.text(((CURRENT_W - fw) // 2, ico_y + ICO_SZ + 52), feels_str, font=f_tiny, fill=0)

    cond_str = wmo_to_desc(wmo)
    cw = int(draw.textlength(cond_str, font=f_small))
    draw.text(((CURRENT_W - cw) // 2, ico_y + ICO_SZ + 64), cond_str, font=f_small, fill=0)

    draw.line([CURRENT_W, MID_TOP, CURRENT_W, MID_BOT], fill=0, width=1)

    # ── DATA POINTS GRID (4×2) ────────────────────
    DP_COLS = 4
    DP_ROWS = 2
    DP_W    = DATA_W // DP_COLS
    DP_H    = MID_H  // DP_ROWS
    DP_ICO  = 20

    uv_str  = str(round(uv_val, 1))  if uv_val  is not None else "N/A"
    aqi_str = str(round(aqi_val))    if aqi_val is not None else "N/A"

    DATA_POINTS = [
        ("sunrise",    "Sunrise",     sunrise_str),
        ("sunset",     "Sunset",      sunset_str),
        ("wind",       "Wind",        f"{wind_spd} mph  {wind_arrow(wind_deg)}"),
        ("humidity",   "Humidity",    f"{humidity}%"),
        ("pressure",   "Pressure",    f"{pressure} hPa"),
        ("uvi",        "UV Index",    uv_str),
        ("visibility", "Visibility",  f"{vis_str} mi"),
        ("aqi",        "Air Quality", f"{aqi_str} {aqi_label(aqi_val)}"),
    ]

    for idx, (icon_name, label, value) in enumerate(DATA_POINTS):
        col = idx % DP_COLS
        row = idx // DP_COLS
        x0  = DATA_X + col * DP_W
        y0  = MID_TOP + row * DP_H

        # Cell border
        draw.rectangle([x0, y0, x0+DP_W-1, y0+DP_H-1], outline=0, fill=None)

        # Icon
        dp_icon = load_icon(icon_name, (DP_ICO, DP_ICO))
        img.paste(dp_icon, (x0+4, y0+4))

        # Label
        draw.text((x0+DP_ICO+8, y0+2), label, font=f_tiny, fill=0)

        # Value
        draw.text((x0+DP_ICO+8, y0+14), value, font=f_med, fill=0)

    # ── FORECAST (5 days) ─────────────────────────
    draw.line([0, MID_BOT, WIDTH, MID_BOT], fill=0, width=1)

    FC_COUNT = 5
    FC_W     = WIDTH // FC_COUNT
    FC_TOP   = MID_BOT + 2
    FC_ICO   = 34

    dates    = daily.get("time", [])
    hi_list  = daily.get("temperature_2m_max", [])
    lo_list  = daily.get("temperature_2m_min", [])
    wmo_list = daily.get("weathercode", [])
    pct_list = daily.get("precipitation_probability_max", [])

    for i in range(FC_COUNT):
        di = i + 1
        if di >= len(dates):
            break

        x0 = i * FC_W
        x1 = x0 + FC_W - 1

        day_dt   = datetime.strptime(dates[di], "%Y-%m-%d")
        day_name = day_dt.strftime("%a")
        is_tmrw  = (i == 0)

        # Day header
        hdr_fill = 0 if is_tmrw else 1
        txt_fill = 1 if is_tmrw else 0
        draw.rectangle([x0, FC_TOP, x1, FC_TOP+16], fill=hdr_fill)
        dn_w = int(draw.textlength(day_name, font=f_med))
        draw.text((x0+(FC_W-dn_w)//2, FC_TOP+1), day_name, font=f_med, fill=txt_fill)

        # Icon
        fc_icon = load_icon(wmo_to_icon(wmo_list[di] if di < len(wmo_list) else 0), (FC_ICO, FC_ICO))
        img.paste(fc_icon, (x0+(FC_W-FC_ICO)//2, FC_TOP+18))

        # High / Low
        hi  = round(hi_list[di])  if di < len(hi_list)  else "--"
        lo  = round(lo_list[di])  if di < len(lo_list)  else "--"
        pct = pct_list[di]        if di < len(pct_list) else "--"

        hl_str = f"{hi}°/{lo}°"
        hl_w   = int(draw.textlength(hl_str, font=f_small))
        draw.text((x0+(FC_W-hl_w)//2, FC_TOP+54), hl_str, font=f_small, fill=0)

        pc_str = f"R:{pct}%"
        pc_w   = int(draw.textlength(pc_str, font=f_tiny))
        draw.text((x0+(FC_W-pc_w)//2, FC_TOP+68), pc_str, font=f_tiny, fill=0)

        if i > 0:
            draw.line([x0, FC_TOP, x0, HEIGHT-1], fill=0, width=1)

    draw_screen_indicator(draw, 4, f_tiny, WIDTH, HEIGHT)
    return img


if __name__ == "__main__":
    img = render()
    img.save("/home/amichael/Desktop/eink/weather_preview.png")
    print("Saved weather_preview.png")
