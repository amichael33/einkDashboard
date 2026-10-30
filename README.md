# E-Ink Dashboard

A Raspberry Pi–powered 7.5" e-ink dashboard for college life: this week's assignments, priority tasks, countdowns, Google Calendar and the weather — switched between with a small USB keypad.

---

## Screens

| Key | Screen | What it shows | Data source |
|---|---|---|---|
| 1 | **Homework** | Week progress (week / month / year), a Mon–Fri + weekend column view of this week's unfinished assignments with their class and status, a "Do First" task panel, and up to 5 countdowns | Notion |
| 2 | **Calendar** | Mon–Sun week grid of events: all-day bars on top, then timed events with start times; `+N more` when a day overflows | Google Calendar |
| 3 | Goals | *Placeholder — coming soon* | — |
| 4 | **Weather** | Current temperature and "feels like", sunrise/sunset, wind, humidity, pressure, UV, visibility, air quality, and a 7-day forecast | [Open-Meteo](https://open-meteo.com) (no API key) |
| 5 | Photos | *Placeholder — coming soon* | — |

If a data source can't be reached (not signed in, offline, missing library), the screen still draws and shows a short message instead of crashing.

---

## Hardware

| Component | Details |
|---|---|
| Display | [Waveshare 7.5" e-Paper HAT](https://www.waveshare.com/7.5inch-e-Paper-HAT.htm) (B&W, V2, 800×480) |
| Computer | Raspberry Pi 4 |
| Connection | SPI |
| Controls | USB keypad (sends `0`–`9`, `a`, `b`, `Enter`) |

Waveshare docs: [wiki](https://www.waveshare.com/wiki/7.5inch_e-Paper_HAT) · [Raspberry Pi guide](https://www.waveshare.com/wiki/7.5inch_e-Paper_HAT_Manual#Working_With_Raspberry_Pi)

---

## Controls

| Key | Action |
|---|---|
| `1`–`5` | Switch to that screen |
| `Enter` | Re-render the current screen |
| `b` | Jump to the photos screen |

While running, the dashboard also re-renders the current screen every 30 minutes. Without the `keyboard` library it renders once and exits.

---

## How it works

1. `dashboard.py` renders the current screen to an 800×480 1-bit image with Pillow.
2. Each screen pulls its own data: `notion.py` (homework, tasks, countdowns), `gcal.py` (calendar), Open-Meteo (weather).
3. `display.py` pushes the image to the e-ink panel with the Waveshare library. On a computer without the panel, it saves a preview PNG instead.
4. A GitHub Actions self-hosted runner on the Pi runs the dashboard on every push to `main`, so pushing code deploys it. (A scheduled refresh is included in the workflow but commented out.)

---

## Notion databases

Share each database with your Notion integration (database **⋯ → Connections**), including any database it links to.

**Homework** — e.g. a college "Assignments" database
- **Assignment Name** (or **Name**) — title
- **Status** — Not started / In progress / Done (Done is hidden)
- **Due date** — places the assignment in its day column; date ranges span columns
- **Class** *(optional)* — relation to a Courses database; shows that course's short `class` code (e.g. "CS 311"), or its `Course Name`

**Tasks**
- **Name**, **Status** (Inbox / Next Action / In progress / Completed), **Due Date** *(optional)*
- **Eisenhower Status** — formula; only "1. Do" tasks due within 30 days are shown

**Countdowns**
- **Countdown** (title), **Date**, **Mode** (select; only "Days Until" is shown), **done** (checkbox)

---

## Setup

### 1. Enable SPI on the Pi
```bash
sudo raspi-config
# Interface Options → SPI → Enable
sudo reboot
```

### 2. Clone the Waveshare library and this repo
```bash
cd ~
git clone https://github.com/waveshare/e-Paper.git
git clone https://github.com/amichael33/einkDashboard.git ~/Desktop/eink
```

### 3. Install Python dependencies
```bash
pip3 install requests pillow RPi.GPIO spidev keyboard google-api-python-client google-auth-oauthlib --break-system-packages
```
The `keyboard` library reads the keypad and usually needs the dashboard to run with `sudo`. If so, install the packages with `sudo pip3 …` too, since root uses its own packages.

### 4. Add your private settings
Secrets never go in the repo. Copy the template into the data folder (`~/Desktop/eink` by default, or set `EINK_HOME`) and fill it in:
```bash
cp config_local.example.py ~/Desktop/eink/config_local.py
nano ~/Desktop/eink/config_local.py
```
It holds your Notion token and database IDs, the Google calendars to show, and optionally your weather location (default: Houston). `config_local.py`, `credentials.json` and `token.json` are gitignored, and environment variables with the same names (e.g. `NOTION_TOKEN`) override the file.

To get the Notion values:
- Create an integration at [notion.so/my-integrations](https://www.notion.so/my-integrations) and copy its secret
- Connect the integration to each database (see above)
- Copy each database ID from its URL (the 32-character string before `?v=`)

### 5. Sign in to Google Calendar
1. In Google Cloud, enable the Calendar API, create an OAuth client of type **Desktop app**, download it as `credentials.json`, and put it in `~/Desktop/eink/`.
2. Under **Google Auth Platform → Audience**, set the publishing status to **In production**. While it's in *Testing*, the sign-in expires every 7 days.
3. Sign in once. This opens a browser and saves `~/Desktop/eink/token.json`:
   ```bash
   python3 gcal.py --login
   ```
   No browser on the Pi? Run it on another computer and copy `token.json` over.
4. List the calendars to show by name in `CALENDARS_TO_SHOW`. Check it works with:
   ```bash
   python3 gcal.py
   ```

### 6. Run it
```bash
cd ~/Desktop/eink
sudo python3 dashboard.py
```

### 7. (Optional) Deploy on push with a self-hosted runner
In your repo: **Settings → Actions → Runners → New self-hosted runner**, choose Linux / ARM64, and follow the commands it shows. Then install it as a service:
```bash
cd ~/actions-runner
sudo ./svc.sh install
sudo ./svc.sh start
```

> **Public repo?** The workflow only runs on pushes to `main`, never on pull requests. Still, under **Settings → Actions → General**, set fork pull request workflows to **Require approval for all external contributors**, so nobody else's code can run on your Pi.

---

## Previewing screens without the Pi

Set `SAVE_SAMPLE_IMAGES = True` at the top of `config.py` to also save a PNG of every screen to `sample_images/` (gitignored), e.g. `1_homework.png`, `2_calendar.png`. Screens render on any computer; fonts fall back to a basic one when the Pi's DejaVu fonts aren't installed.

---

## File structure
```
.
├── dashboard.py              # entry point: keypad, screen switching, auto-refresh
├── config.py                 # constants + SAVE_SAMPLE_IMAGES; loads config_local.py
├── config_local.example.py   # template for your private settings
├── display.py                # fonts, drawing helpers, push to e-ink / preview PNG
├── notion.py                 # Notion: homework, tasks, countdowns
├── gcal.py                   # Google Calendar: sign-in + this week's events
├── screens/                  # one module per screen (homework, calendar, goals, weather, photos)
├── icons/                    # weather and moon icons
└── .github/workflows/
    └── update-display.yml    # runs the dashboard on the Pi on push
```

---

## Dependencies

- [Pillow](https://python-pillow.org/) — image rendering
- [Requests](https://requests.readthedocs.io/) — Notion and Open-Meteo API calls
- [Google API Python client](https://github.com/googleapis/google-api-python-client) + [google-auth-oauthlib](https://github.com/googleapis/google-auth-library-python-oauthlib) — Google Calendar
- [keyboard](https://github.com/boppreh/keyboard) — USB keypad input
- [Waveshare e-Paper library](https://github.com/waveshare/e-Paper) — display driver
