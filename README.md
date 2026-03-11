# E-Ink Dashboard

A Raspberry Pi-powered e-ink display dashboard that syncs with Notion to show a weekly homework view, priority tasks, and daily progress — refreshed automatically throughout the day.

[Waveshare 7.5" E-Ink Display](https://www.waveshare.com/img/devkit/general/7.5inch-e-paper-hat.jpg)
(https://www.waveshare.com/pico-epaper-7.5.htm?srsltid=AfmBOorl9QlHSdyojZRyrNhvVcEIUEvpxjp2KjBB5vPhDY1RfWTBE6L6)
https://www.waveshare.com/wiki/7.5inch_e-Paper_HAT 
---

## What it shows

- **Header** — current date (Central time) and a quote of the day
- **Progress bars** — Week (circles), Month (bar), and Year (bar)
- **Homework columns** — 6-column week view (Mon–Fri + Sat/Sun merged) pulled from a Notion database, each item showing its name and status
- **Tasks panel** — right-side panel showing high-priority "Do First" tasks from a separate Notion database, with checkbox states indicating progress

---

## Hardware

| Component | Details |
|---|---|
| Display | Waveshare 7.5" E-Ink HAT (B&W, V2, 800×480) |
| Computer | Raspberry Pi 4 |
| Connection | SPI |

---

## How it works

1. A Python script (`dashboard.py`) queries two Notion databases via the Notion API
2. It fetches a quote of the day from [ZenQuotes](https://zenquotes.io)
3. It renders everything to an 800×480 1-bit bitmap using Pillow
4. The image is pushed to the e-ink display via the Waveshare Python library
5. A GitHub Actions self-hosted runner on the Pi triggers the script on a schedule and on every push to `main`

---

## Notion databases

### Homework
- **Name** — task name
- **Status** — Not started / In progress / Done
- **Due date** — used to place the item in the correct day column

### Tasks
- **Name** — task name
- **Status** — Inbox / Next Action / In progress / Completed
- **Due Date** — optional
- **Eisenhower Status** — formula-based priority label; only "1. Do" items are shown

---

## Refresh schedule

| Time (Central) | Trigger |
|---|---|
| 12:00 AM | Scheduled |
| 8:30 AM | Scheduled |
| 12:00 PM | Scheduled |
| 4:00 PM | Scheduled |
| 6:30 PM | Scheduled |
| Any push to `main` | On commit |

---

## Setup

### 1. Enable SPI on the Pi
```bash
sudo raspi-config
# Interface Options → SPI → Enable
sudo reboot
```

### 2. Clone the Waveshare library
```bash
cd ~
git clone https://github.com/waveshare/e-Paper.git
```

### 3. Install Python dependencies
```bash
pip3 install requests pillow RPi.GPIO spidev --break-system-packages
```

### 4. Configure Notion credentials
In `dashboard.py`, set:
```python
NOTION_TOKEN   = "your_integration_token"
HOMEWORK_DB_ID = "your_homework_database_id"
TASKS_DB_ID    = "your_tasks_database_id"
```

To get these:
- Create an integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
- Share both databases with the integration
- Copy the DB ID from each database's URL (the 32-char string before `?v=`)

### 5. Set up the GitHub Actions self-hosted runner
```bash
mkdir ~/actions-runner && cd ~/actions-runner
curl -o actions-runner-linux-arm64-2.332.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.332.0/actions-runner-linux-arm64-2.332.0.tar.gz
tar xzf ./actions-runner-linux-arm64-2.332.0.tar.gz
./config.sh --url https://github.com/YOUR_USERNAME/YOUR_REPO --token YOUR_TOKEN
sudo ./svc.sh install
sudo ./svc.sh start
```

---

## File structure
```
.
├── dashboard.py                        # main script
├── .github/
│   └── workflows/
│       └── update-display.yml          # GitHub Actions schedule
└── README.md
```

---

## Dependencies

- [Pillow](https://python-pillow.org/) — image rendering
- [Requests](https://requests.readthedocs.io/) — Notion + ZenQuotes API calls
- [Waveshare e-Paper library](https://github.com/waveshare/e-Paper) — display driver
- [ZenQuotes API](https://zenquotes.io) — daily quote
- [Notion API](https://developers.notion.com) — homework and task data
