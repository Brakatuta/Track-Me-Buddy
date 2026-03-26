# 🕐 TrackMe Buddy
A dark-themed desktop time tracker for Windows, built with Python and Tkinter.  
Designed for use with the **NovaTime** web-based time tracking system, but works fully standalone without it.


---

## ✨ Features

- **Live clock** with weekday, date and time display
- **Work progress bar** — fills as you work towards your daily goal, turns green on overtime
- **Pause progress bar** — tracks your mandatory break time
- **Live balance** — fetched from NovaTime and ticked every second in real time
- **Leave at** — calculates your target leave time based on goal, pause and daily credit
- **AutoOvertime Planner** — plan how to work down your balance over N days with arrive/leave times per day
- **Business Trip** tracking (Dienstgang)
- **System tray** integration with context menu
- **Desktop notifications** for goal reached, pause complete and upcoming mandatory break
- **NovaTime API integration** — automatically books via browser automation (Playwright + Edge/Chrome)
- **Bored?** — launches a game executable from the same directory
- **Theme switcher** — choose between Dark Mode, Dracula and Blue Theme; applies instantly
- Save files stored in a dedicated `save/` folder — works both as script and compiled exe

---

## 🚀 Getting Started

### Requirements

- Python 3.11+
- Windows (tray integration uses `pystray` Win32 backend)

### Install dependencies

```bash
pip install pystray pillow playwright plyer
playwright install chromium
```

### Run

```bash
python main.py
```

---

## ⚙️ Settings

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

### 🔧 Correction
Buttons for retroactively fixing the current session — no API calls are made:

- **⏱ Already Checked In** — set a past clock-in time for today's session
- **☕ Correct Break** — add a missed break to the current session
- **🗑 Hard Reset** — clears balance and current session completely

---

## 🔌 NovaTime API Integration

Open the **🔌 API** window and enter:

- **NovaTime URL** — your company's NovaTime web address
- **Username / Password** — your NovaTime login
- **Proxy Auth** — HTTP basic auth credentials if behind a corporate proxy
- **Show NovaTime Window** — uncheck for headless (invisible) browser automation

> NovaTime integration requires Microsoft Edge or Google Chrome to be installed.

---

## 📊 AutoOvertime Planner

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
| `plyer` | Desktop notifications |
| `playwright` | Browser automation for NovaTime |

---

## 📄 License

MIT — feel free to use and adapt.
