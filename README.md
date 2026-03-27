# 🕐 TrackMe Buddy
A dark-themed desktop time tracker for Windows, built with Python and Tkinter.  
Designed for use with the **NovaTime** web-based time tracking system, but works fully standalone without it.

<img width="559" height="508" alt="Screenshot 2026-03-27 122830" src="https://github.com/user-attachments/assets/ddc1826d-43ee-4f2a-90ce-286d77f68d87" /> <img width="555" height="505" alt="Screenshot 2026-03-26 160015" src="https://github.com/user-attachments/assets/efadead5-15c7-450e-9e2c-eb2ebcfa9c44" />


---

## ✨ Features

- **Live clock** with weekday, date and time display
- **Tile-based dashboard** — resizable window with four info tiles (Worked, Core Hours, Break, Leave)
- **Work progress bar** — fills as you work towards your daily goal, turns green on overtime
- **Pause progress bar** — tracks your mandatory break time
- **Live balance** — fetched from NovaTime and ticked every second in real time
- **Leave at** — calculates your target leave time based on goal, pause and daily credit
- **Overtime indicator** — shows current OT with correct ±sign in the Leave tile, colour-coded green/red
- **AutoOvertime Planner** — plan how to work down your balance over N days with arrive/leave times per day
- **User Journal** — fetch and display your full monthly time-tracking journal in a scrollable table, with a refresh button (NovaTime-only feature)
- **Business Trip** tracking
- **System tray** integration with context menu
- **Desktop notifications** for goal reached, pause complete and upcoming mandatory break — can be disabled per session
- **NovaTime API integration** — automatically books via browser automation (Playwright + Edge/Chrome)
- **Encrypted credentials (DPAPI-backed encryption)
- **Theme switcher** — choose between Dark Mode, Dracula and Blue Theme; applies instantly without restart
- Save files stored in a dedicated `save/` folder — works both as script and compiled exe

---

## 🚀 Getting Started

### Requirements

- Python 3.11+
- Windows (tray integration uses `pystray` Win32 backend)

### Install dependencies

```bash
pip install tkinter pystray pillow playwright plyer pywin32
playwright install chromium
```

### Run

```bash
python main.py
```

---

## ⚙️ Settings

<img width="616" height="489" alt="Screenshot 2026-03-26 155959" src="https://github.com/user-attachments/assets/d93aded1-58b9-42b5-a6da-8091b96ca83a" />


Open the **⚙ Settings** window to configure. Settings are arranged in a 2×2 card grid:

### 💼 Work
| Setting | Default | Description |
|---|---|---|
| Daily Goal | 8:00 h | Target work hours per day (HH:MM with spinboxes) |
| Daily Credit | 0 min | Minutes credited per day (reduces effective goal) |

### ☕ Break
| Setting | Default | Description |
|---|---|---|
| Target Break | 30 min | Required break duration |
| Break Warning | 15 min | How many minutes before the mandatory break threshold to warn |

### ⚡ Extras
| Setting | Default | Description |
|---|---|---|
| Break Required After | 6.0 h | Hours of work after which a break becomes mandatory |
| Disable Notifications | off | Toggle to silence all desktop notifications for the current session |

### 🔧 Correction
Buttons for retroactively fixing the current session — no API calls are made:

- **⏱ Already Checked In** — set a past clock-in time for today's session
- **☕ Correct Break** — add a missed break to the current session
- **🗑 Hard Reset** — clears balance and current session completely

---

## 🎨 Theme Switcher

<img width="229" height="262" alt="Screenshot 2026-03-26 155947" src="https://github.com/user-attachments/assets/112dca52-1a90-4aab-87bc-453efb27454b" />


Click **🎨 Theme** in the header bar to open the theme picker. Three built-in themes are available, each applied instantly across the entire UI without a restart:

| Theme | Description |
|---|---|
| **Dark Mode** | Default dark grey with blue accents |
| **Dracula** | Purple/pink accents on a deep dark background |
| **Blue Theme** | Navy base with cyan and teal highlights |

The active theme is saved to `save/theme.json` and restored automatically on next launch.

---

## 📋 User Journal (NovaTime specific)

<img width="999" height="857" alt="Screenshot 2026-03-26 155918" src="https://github.com/user-attachments/assets/0f49f8af-1021-4665-a14e-9406d28e4efd" />


Click **📋 Journal** in the header bar to open your monthly time-tracking journal fetched directly from NovaTime.

- Displays the full journal table for the current month in a **scrollable grid** (horizontal and vertical)
- Columns shown: weekday, date, clock-in/out times, booking type, actual/target hours, break, daily saldo, total saldo, comments
- **Positive/negative saldo** values are colour-coded green and red automatically
- **Today's row** is highlighted
- Summary rows (e.g. Nachtzuschlag totals) are shown at the bottom
- Use the **🔄 Refresh** button to re-fetch the latest data without closing the window

> Requires the **NovaTime User Journal URL** to be configured in the **🔌 API** settings.

---

## 🔌 NovaTime API Integration

<img width="603" height="646" alt="Screenshot 2026-03-26 155938" src="https://github.com/user-attachments/assets/60229ee0-9055-4a30-a348-db51d4a4fae0" />


Open the **🔌 API** window and enter:

| Field | Description |
|---|---|
| NovaTime URL | Your company's main NovaTime web address (used for clock-in/out bookings) |
| NovaTime User Journal URL | Separate URL for the User Journal page (required for the Journal feature) |
| Username / Password | Your NovaTime login credentials |
| Proxy Auth | HTTP basic auth credentials if behind a corporate proxy |
| Show NovaTime Window | Uncheck for headless (invisible) browser automation |

> NovaTime integration requires Microsoft Edge or Google Chrome to be installed.
> Credentials are saved encrypted and dependant on the current users os, which means no one else can access the data even if he has the .lock file.

---

## 📊 AutoOvertime Planner

<img width="800" height="567" alt="Screenshot 2026-03-26 155927" src="https://github.com/user-attachments/assets/eff2bd20-078e-4111-b772-345ecf8bd30e" />



Click **◑ AutoOvertime** to open the planner. Use the sliders to:

1. Set your **balance to clear** (−12h to +12h in 10-minute steps, pre-filled from Nova)
2. Choose how many **days** to spread it over (1–31)
3. Pin either your **Arrive** or **Leave** time
4. Optionally **skip Saturdays** (Sundays are always skipped)

The right panel shows a card for each day with exact arrive, leave, work and pause times.

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `tkinter` | UI framework (stdlib) |
| `pystray` | System tray icon |
| `Pillow` | Image handling for tray icon |
| `playwright` | Browser automation for NovaTime |
| `plyer` | Desktop notifications |
| `pywin32` | DPAPI-backed encryption |

---

## 📄 License

MIT — feel free to use and adapt.
