import tkinter as tk
from tkinter import messagebox
import time
import json
import os
import threading
import subprocess
from pathlib import Path
import math
from datetime import datetime, timedelta
from enum import Enum
import sys

# ── NovaTime integration ──────────────────────────────────────────────────────
from NovaTime import nova as nova

# ── extra deps ────────────────────────────────────────────────────────────────
import pystray
from PIL import Image as PilImage

from plyer import notification as plyer_notify

NOVA_AVAILABLE = True
TRAY_AVAILABLE = True
NOTIFY_AVAILABLE = True

# ── Themes (palette definitions) ─────────────────────────────────────────────
THEMES = {
    "Dark Mode": {
        "BACKGROUND":       "#1f1d1d",
        "FOREGROUND":       "#333131",
        "BUTTON":           "#555252",
        "TEXT":             "#ffffff",
        "PAUSE":            "#ff9800",
        "OVERTIME":         "#4caf50",
        "NEGATIVE":         "#f44336",
        "STOP":             "#9c1515",
        "ACCENT":           "#5b9bd5",
        "API":              "#2e86ab",
        "TEST":             "#9c1515",
        "BAR_EMPTY":        "#2a2a3e",
        "BAR_TEXT":         "#ffffff",
        "BTN_OVERTIME_BG":  "#5b9bd5",
        "BTN_OVERTIME_FG":  "#ffffff",
        "BTN_BORED_BG":     "#e6b800",
        "BTN_BORED_FG":     "#1a1a1a",
        "BTN_THEME_BG":     "#555252",
        "BTN_THEME_FG":     "#ffffff",
        "BTN_API_BG":       "#2e86ab",
        "BTN_API_FG":       "#ffffff",
        "BTN_SETTINGS_BG":  "#555252",
        "BTN_SETTINGS_FG":  "#ffffff",
        "BTN_CLOCKIN_BG":   "#555252",
        "BTN_CLOCKIN_FG":   "#ffffff",
        "BTN_CLOCKOUT_BG":  "#9c1515",
        "BTN_CLOCKOUT_FG":  "#ffffff",
        "BTN_PAUSE_BG":     "#ff9800",
        "BTN_PAUSE_FG":     "#ffffff",
        "BTN_ENDPAUSE_BG":  "#f44336",
        "BTN_ENDPAUSE_FG":  "#ffffff",
        "BTN_TRIP_BG":      "#0b7236",
        "BTN_TRIP_FG":      "#ffffff",
        "BTN_ENDTRIP_BG":   "#f44336",
        "BTN_ENDTRIP_FG":   "#ffffff",
    },
    "Dracula": {
        "BACKGROUND":       "#282a36",
        "FOREGROUND":       "#383a4a",
        "BUTTON":           "#44475a",
        "TEXT":             "#f8f8f2",
        "PAUSE":            "#ffb86c",
        "OVERTIME":         "#50fa7b",
        "NEGATIVE":         "#ff5555",
        "STOP":             "#ff5555",
        "ACCENT":           "#bd93f9",
        "API":              "#8be9fd",
        "TEST":             "#ff5555",
        "BAR_EMPTY":        "#21222c",
        "BAR_TEXT":         "#f8f8f2",
        "BTN_OVERTIME_BG":  "#bd93f9",
        "BTN_OVERTIME_FG":  "#282a36",
        "BTN_BORED_BG":     "#f1fa8c",
        "BTN_BORED_FG":     "#282a36",
        "BTN_THEME_BG":     "#44475a",
        "BTN_THEME_FG":     "#f8f8f2",
        "BTN_API_BG":       "#8be9fd",
        "BTN_API_FG":       "#282a36",
        "BTN_SETTINGS_BG":  "#44475a",
        "BTN_SETTINGS_FG":  "#f8f8f2",
        "BTN_CLOCKIN_BG":   "#44475a",
        "BTN_CLOCKIN_FG":   "#f8f8f2",
        "BTN_CLOCKOUT_BG":  "#ff5555",
        "BTN_CLOCKOUT_FG":  "#f8f8f2",
        "BTN_PAUSE_BG":     "#ffb86c",
        "BTN_PAUSE_FG":     "#f8f8f2",
        "BTN_ENDPAUSE_BG":  "#ff5555",
        "BTN_ENDPAUSE_FG":  "#282a36",
        "BTN_TRIP_BG":      "#50fa7b",
        "BTN_TRIP_FG":      "#282a36",
        "BTN_ENDTRIP_BG":   "#ff5555",
        "BTN_ENDTRIP_FG":   "#f8f8f2",
    },
    "Blue Theme": {
        "BACKGROUND":       "#0d1b2a",
        "FOREGROUND":       "#1b2d45",
        "BUTTON":           "#1e3a5f",
        "TEXT":             "#e0f0ff",
        "PAUSE":            "#f4a261",
        "OVERTIME":         "#52b788",
        "NEGATIVE":         "#e63946",
        "STOP":             "#c1121f",
        "ACCENT":           "#48cae4",
        "API":              "#0096c7",
        "TEST":             "#c1121f",
        "BAR_EMPTY":        "#0a1628",
        "BAR_TEXT":         "#e0f0ff",
        "BTN_OVERTIME_BG":  "#48cae4",
        "BTN_OVERTIME_FG":  "#0d1b2a",
        "BTN_BORED_BG":     "#f4a261",
        "BTN_BORED_FG":     "#0d1b2a",
        "BTN_THEME_BG":     "#1e3a5f",
        "BTN_THEME_FG":     "#e0f0ff",
        "BTN_API_BG":       "#0096c7",
        "BTN_API_FG":       "#e0f0ff",
        "BTN_SETTINGS_BG":  "#1e3a5f",
        "BTN_SETTINGS_FG":  "#e0f0ff",
        "BTN_CLOCKIN_BG":   "#1e3a5f",
        "BTN_CLOCKIN_FG":   "#e0f0ff",
        "BTN_CLOCKOUT_BG":  "#c1121f",
        "BTN_CLOCKOUT_FG":  "#e0f0ff",
        "BTN_PAUSE_BG":     "#f4a261",
        "BTN_PAUSE_FG":     "#e0f0ff",
        "BTN_ENDPAUSE_BG":  "#e63946",
        "BTN_ENDPAUSE_FG":  "#0d1b2a",
        "BTN_TRIP_BG":      "#2dc653",
        "BTN_TRIP_FG":      "#0d1b2a",
        "BTN_ENDTRIP_BG":   "#e63946",
        "BTN_ENDTRIP_FG":   "#e0f0ff",
    },
}

# ── Colours ───────────────────────────────────────────────────────────────────
class Color(Enum):
    TEST            = "#9c1515"
    BACKGROUND      = "#1f1d1d"
    FOREGROUND      = "#333131"
    BUTTON          = "#555252"
    TEXT            = "#ffffff"
    PAUSE           = "#ff9800"
    OVERTIME        = "#4caf50"
    NEGATIVE        = "#f44336"
    STOP            = "#9c1515"
    ACCENT          = "#5b9bd5"
    API             = "#2e86ab"
    # Progress bars
    BAR_EMPTY       = "#2a2a3e"
    BAR_TEXT        = "#ffffff"
    # Header buttons
    BTN_OVERTIME_BG = "#5b9bd5"
    BTN_OVERTIME_FG = "#200202"
    BTN_BORED_BG    = "#e6b800"
    BTN_BORED_FG    = "#1a1a1a"
    BTN_THEME_BG    = "#555252"
    BTN_THEME_FG    = "#ffffff"
    BTN_API_BG      = "#2e86ab"
    BTN_API_FG      = "#200202"
    BTN_SETTINGS_BG = "#555252"
    BTN_SETTINGS_FG = "#ffffff"
    # Main action buttons
    BTN_CLOCKIN_BG  = "#535552"
    BTN_CLOCKIN_FG  = "#ffffff"
    BTN_CLOCKOUT_BG = "#9c1515"
    BTN_CLOCKOUT_FG = "#ffffff"
    BTN_PAUSE_BG    = "#ff9800"
    BTN_PAUSE_FG    = "#ffffff"
    BTN_ENDPAUSE_BG = "#f44336"
    BTN_ENDPAUSE_FG = "#ffffff"
    BTN_TRIP_BG     = "#0b7236"
    BTN_TRIP_FG     = "#ffffff"
    BTN_ENDTRIP_BG  = "#f44336"
    BTN_ENDTRIP_FG  = "#ffffff"

# ── Base directory & save folder ─────────────────────────────────────────────
# Works correctly both as a plain .py script and when bundled with
# auto-py-to-exe / PyInstaller (which sets sys.frozen and puts the exe
# path in sys.executable).

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def _get_save_dir() -> Path:
    save_dir = _get_base_dir() / "save"
    save_dir.mkdir(exist_ok=True)
    return save_dir

# ── Theme helpers (need Color and _get_save_dir defined above) ────────────────
def _load_active_theme_name() -> str:
    try:
        path = _get_save_dir() / "theme.json"
        if path.exists():
            with open(path) as f:
                return json.load(f).get("theme", "Dark Mode")
    except Exception:
        pass
    return "Dark Mode"

def _save_active_theme_name(name: str):
    try:
        path = _get_save_dir() / "theme.json"
        with open(path, "w") as f:
            json.dump({"theme": name}, f)
    except Exception as e:
        print(f"[Theme] Save error: {e}")

def _apply_theme(name: str):
    """Patch Color enum values in-place from the named theme palette."""
    palette = THEMES.get(name, THEMES["Dark Mode"])
    for member in Color:
        if member.name in palette:
            member._value_ = palette[member.name]

# ── NovaTime API config (separate file) ───────────────────────────────────────
class NovaConfig:
    """Loads and saves NovaTime API settings to nova_config.json."""

    DEFAULTS = {
        "url":                "",
        "username":           "",
        "password":           "",
        "proxy_auth_username":"",
        "proxy_auth_password":"",
        "show_window":        True,
    }

    def __init__(self):
        self.file_path = str(_get_save_dir() / "nova_config.json")
        self.data = dict(self.DEFAULTS)
        self.load()

    def load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    saved = json.load(f)
                # Merge saved values over defaults so new keys always exist
                for k, v in self.DEFAULTS.items():
                    self.data[k] = saved.get(k, v)
            except Exception as e:
                print(f"[NovaConfig] Load error: {e}")

    def save(self):
        try:
            with open(self.file_path, "w") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"[NovaConfig] Save error: {e}")

    # Convenience property accessors
    def __getattr__(self, name):
        if name in ("file_path", "data"):
            raise AttributeError(name)
        try:
            return self.data[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        if name in ("file_path", "data"):
            super().__setattr__(name, value)
        else:
            self.data[name] = value


# ── Data model ────────────────────────────────────────────────────────────────
class Tracker:
    def __init__(self):
        self.file_path = str(_get_save_dir() / "data.json")
        self.reset_values()
        self.daily_goal                  = 8.0
        self.default_pause_mins          = 30.0
        self.total_balance_seconds       = 0.0
        self.daily_credit_mins           = 0.0
        self.pause_warn_before_mins      = 15.0
        self.break_required_after_hours  = 6.0
        self.load_data()

    def reset_values(self):
        self.start_time_stamp  = 0
        self.is_in_pause       = False
        self.pauses            = []
        self.is_on_dienstgang  = False
        self.last_reset_date   = datetime.now().strftime("%Y-%m-%d")

    def get_current_date(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def start_tracking(self):
        if self.start_time_stamp == 0:
            self.start_time_stamp = time.time()

    def stop_tracking(self):
        self.end_open_pause()
        self.reset_values()

    def toggle_pause(self):
        if not self.start_time_stamp:
            return
        now = time.time()
        if not self.is_in_pause:
            self.pauses.append([now, None])
            self.is_in_pause = True
        else:
            if self.pauses and self.pauses[-1][1] is None:
                self.pauses[-1][1] = now
            self.is_in_pause = False

    def toggle_dienstgang(self):
        self.is_on_dienstgang = not self.is_on_dienstgang
        state = "started" if self.is_on_dienstgang else "ended"
        print(f"[Dienstgang] {state} at {datetime.now().strftime('%H:%M:%S')}")

    def end_open_pause(self):
        if self.is_in_pause and self.pauses and self.pauses[-1][1] is None:
            self.pauses[-1][1] = time.time()
            self.is_in_pause   = False

    def get_total_pause_duration(self):
        total = 0
        for p_start, p_end in self.pauses:
            if p_end:
                total += p_end - p_start
            elif self.is_in_pause:
                total += time.time() - p_start
        return total

    def save_data(self):
        data = {
            "start_time_stamp":       self.start_time_stamp,
            "is_in_pause":            self.is_in_pause,
            "pauses":                 self.pauses,
            "daily_goal":             self.daily_goal,
            "default_pause_mins":     self.default_pause_mins,
            "total_balance_seconds":  self.total_balance_seconds,
            "last_reset_date":        self.last_reset_date,
            "daily_credit_mins":      self.daily_credit_mins,
            "pause_warn_before_mins": self.pause_warn_before_mins,
            "is_on_dienstgang":       self.is_on_dienstgang,
            "break_required_after_hours": self.break_required_after_hours,
        }
        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=4)

    def load_data(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    d = json.load(f)
                self.start_time_stamp       = d.get("start_time_stamp", 0)
                self.is_in_pause            = d.get("is_in_pause", False)
                self.pauses                 = d.get("pauses", [])
                self.daily_goal             = d.get("daily_goal", 8.0)
                self.default_pause_mins     = d.get("default_pause_mins", 30.0)
                self.total_balance_seconds  = d.get("total_balance_seconds",
                                              d.get("total_overtime_seconds", 0.0))
                self.last_reset_date        = d.get("last_reset_date",
                                              datetime.now().strftime("%Y-%m-%d"))
                self.daily_credit_mins      = d.get("daily_credit_mins", 0.0)
                self.pause_warn_before_mins = d.get("pause_warn_before_mins", 15.0)
                self.is_on_dienstgang       = d.get("is_on_dienstgang", False)
                self.break_required_after_hours = d.get("break_required_after_hours", 6.0)
            except Exception as e:
                print(f"Load error: {e}")


# ── Main application ──────────────────────────────────────────────────────────
class TrackMe:
    def __init__(self, master):
        self.master     = master
        self.tracker    = Tracker()
        self.nova_cfg   = NovaConfig()

        self._notified_work_done    = False
        self._notified_pause_done   = False
        self._notified_pause_warn   = False
        self._ot_compute            = None
        # Snapshot: (saldo_seconds, time.time() at fetch)
        self._nova_saldo_snapshot   = None
        self._saldo_syncing         = False   # True while Nova fetch is in progress

        base = os.path.dirname(os.path.abspath(__file__))
        self.icon_ico = os.path.join(base, "Icon.ico")
        self.icon_png = os.path.join(base, "Icon.png")

        self._setup_window()
        self._build_ui()
        self.__update()
        self._try_init_nova()
        self._sync_saldo_from_nova()

        self.master.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.master.withdraw()

        self.tray_icon = None
        if TRAY_AVAILABLE:
            threading.Thread(target=self._run_tray, daemon=True).start()
        else:
            self.master.deiconify()

    # ── Window setup ──────────────────────────────────────────────────────────
    def _setup_window(self):
        self.master.title("Track Me Buddy")
        self.master.config(bg=Color.BACKGROUND.value)
        self.master.geometry("500x445")
        self.master.resizable(False, False)
        if os.path.exists(self.icon_ico):
            try: self.master.iconbitmap(self.icon_ico)
            except Exception: pass
        elif os.path.exists(self.icon_png) and TRAY_AVAILABLE:
            try:
                from PIL import ImageTk
                img = PilImage.open(self.icon_png).resize((32, 32))
                self._tk_icon = ImageTk.PhotoImage(img)
                self.master.iconphoto(True, self._tk_icon)
            except Exception: pass

    # ── Tray ──────────────────────────────────────────────────────────────────
    def _load_tray_image(self):
        for path in (self.icon_png, self.icon_ico):
            if os.path.exists(path):
                try: return PilImage.open(path).resize((64, 64)).convert("RGBA")
                except Exception: pass
        return PilImage.new("RGBA", (64, 64), color=(76, 175, 80, 255))

    def _run_tray(self):
        img  = self._load_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("Open Track Me Buddy", self._tray_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Clock In / Clock Out",     self._tray_start_work),
            pystray.MenuItem("Break / Resume", self._tray_toggle_pause),
            pystray.MenuItem("Dienstgang",     self._tray_toggle_dienstgang),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._tray_quit),
        )
        self.tray_icon = pystray.Icon("TrackMeBuddy", img, "Track Me Buddy", menu)
        self.tray_icon.run()

    def _tray_open(self, *_):               self.master.after(0, self.show_window_near_tray)
    def _tray_start_work(self, *_):         self.master.after(0, self._tray_start_work_main)
    def _tray_toggle_pause(self, *_):       self.master.after(0, self._do_toggle_pause)
    def _tray_toggle_dienstgang(self, *_):  self.master.after(0, self._do_toggle_dienstgang)
    def _tray_quit(self, *_):               self.master.after(0, self._do_quit)

    def _tray_start_work_main(self):
        if self.tracker.start_time_stamp == 0:
            self.tracker.start_tracking()
            self._notified_work_done  = False
            self._notified_pause_done = False
            self._notified_pause_warn = False
            self.tracker.save_data()
            self._nova_work_async("start_work")
            self._nova_saldo_snapshot = None
            self._saldo_syncing = False
            self._sync_saldo_from_nova(delay_ms=5000)

    def _do_toggle_pause(self):
        self.tracker.toggle_pause()
        self.update_pause_button_text()
        self.tracker.save_data()
        self._nova_pause_async()

    def _do_toggle_dienstgang(self):
        self.tracker.toggle_dienstgang()
        self.update_dienstgang_button_text()
        self.tracker.save_data()
        self._nova_trip_async()

    def _do_quit(self):
        self.tracker.save_data()
        if self.tray_icon: self.tray_icon.stop()
        self.master.destroy()

    # ── Window positioning ────────────────────────────────────────────────────
    def _sync_on_restore(self):
        """Trigger a Nova saldo sync when the window is restored from tray."""
        self._sync_saldo_from_nova()

    def show_window_near_tray(self):
        self.master.deiconify()
        self.master.update_idletasks()
        win_w  = self.master.winfo_width()
        win_h  = self.master.winfo_height()
        scr_w  = self.master.winfo_screenwidth()
        scr_h  = self.master.winfo_screenheight()
        margin = 12
        x = scr_w - win_w - margin
        y = scr_h - win_h - 90 - margin
        self.master.geometry(f"+{max(0,x)}+{max(0,y)}")
        self.master.lift()
        self.master.focus_force()
        self._sync_on_restore()

    def show_window(self):
        self.master.deiconify()
        self.master.lift()
        self.master.focus_force()
        self._sync_on_restore()

    def hide_to_tray(self):
        self.tracker.save_data()
        self.master.withdraw()
        if not TRAY_AVAILABLE:
            self.master.destroy()

    # ── Notifications ─────────────────────────────────────────────────────────
    def _notify(self, title, message):
        if not NOTIFY_AVAILABLE: return
        ico = self.icon_ico if os.path.exists(self.icon_ico) else None
        try:
            plyer_notify.notify(title=title, message=message,
                                app_name="Track Me Buddy", app_icon=ico, timeout=8)
        except Exception as e:
            print(f"Notify error: {e}")

    def _fire_notify(self, title, message):
        threading.Thread(target=self._notify, args=(title, message), daemon=True).start()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.main_frame = tk.Frame(self.master, bg=Color.FOREGROUND.value)
        self.main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(self.main_frame, bg=Color.FOREGROUND.value)
        header.pack(fill=tk.X, padx=10, pady=5)

        # Right side of header: Settings | API (right-to-left order)
        self.hdr_settings_btn = tk.Button(header, text="⚙ Settings",
                  bg=Color.BTN_SETTINGS_BG.value, fg=Color.BTN_SETTINGS_FG.value,
                  activebackground=Color.BTN_SETTINGS_BG.value, activeforeground=Color.BTN_SETTINGS_FG.value,
                  command=self.open_settings, font=("Arial", 10), bd=0, padx=10, relief="flat")
        self.hdr_settings_btn.pack(side="right")

        self.hdr_api_btn = tk.Button(header, text="🔌 API",
                  bg=Color.BTN_API_BG.value, fg=Color.BTN_API_FG.value,
                  activebackground=Color.BTN_API_BG.value, activeforeground=Color.BTN_API_FG.value,
                  command=self.open_api_settings, font=("Arial", 10), bd=0, padx=10, relief="flat")
        self.hdr_api_btn.pack(side="right", padx=(0, 4))

        self.hdr_overtime_btn = tk.Button(header, text="◑ AutoOvertime",
                  bg=Color.BTN_OVERTIME_BG.value, fg=Color.BTN_OVERTIME_FG.value,
                  activebackground=Color.BTN_OVERTIME_BG.value, activeforeground=Color.BTN_OVERTIME_FG.value,
                  command=self.open_auto_overtime, font=("Arial", 10), bd=0, padx=10, relief="flat")
        self.hdr_overtime_btn.pack(side="right", padx=(0, 4))

        self.hdr_bored_btn = tk.Button(header, text="🎮 Bored?",
                  bg=Color.BTN_BORED_BG.value, fg=Color.BTN_BORED_FG.value,
                  activebackground=Color.BTN_BORED_BG.value, activeforeground=Color.BTN_BORED_FG.value,
                  command=self._launch_game, font=("Arial", 10, "bold"), bd=0, padx=10, relief="flat")
        self.hdr_bored_btn.pack(side="right", padx=(0, 4))

        self.hdr_theme_btn = tk.Button(header, text="🎨 Theme",
                  bg=Color.BTN_THEME_BG.value, fg=Color.BTN_THEME_FG.value,
                  activebackground=Color.BTN_THEME_BG.value, activeforeground=Color.BTN_THEME_FG.value,
                  command=self.open_theme_picker, font=("Arial", 10), bd=0, padx=10, relief="flat")
        self.hdr_theme_btn.pack(side="right", padx=(0, 4))

        # ── Info area ─────────────────────────────────────────────────────────
        self.info_frame = tk.Frame(self.main_frame, bg=Color.BACKGROUND.value, height=300)
        self.info_frame.pack_propagate(False)
        self.info_frame.pack(side="top", padx=10, pady=10, fill=tk.X)

        BG  = Color.BACKGROUND.value
        TXT = Color.TEXT.value

        # Row 1: Weekday + Date + Time
        self.time_display = tk.Label(self.info_frame, bg=BG,
                                     fg=TXT, font=("Arial", 22, "bold"))
        self.time_display.pack(anchor="nw", padx=10, pady=(10, 2))

        # Row 2: Balance
        self.balance_account_label = tk.Label(self.info_frame, text="",
            bg=BG, fg=Color.OVERTIME.value, font=("Arial", 20, "bold"))
        self.balance_account_label.pack(anchor="nw", padx=10, pady=(0, 6))

        tk.Frame(self.info_frame, bg=Color.BUTTON.value, height=1).pack(
            fill=tk.X, padx=10, pady=(0, 8))

        # Row 3: Worked label + progress bar
        self.worked_label = tk.Label(self.info_frame, bg=BG,
                                     fg=TXT, font=("Arial", 16, "bold"))
        self.worked_label.pack(anchor="nw", padx=10, pady=(0, 3))

        self._bar_h = 16
        self._bar_w = 340
        self.work_bar_canvas = tk.Canvas(self.info_frame, bg=BG,
                                         width=self._bar_w, height=self._bar_h,
                                         highlightthickness=0)
        self.work_bar_canvas.pack(anchor="nw", padx=10, pady=(0, 6))

        # Row 4: Work Left / Goal Reached label + progress bar
        self.work_hours_left = tk.Label(self.info_frame, bg=BG,
                                        fg=TXT, font=("Arial", 16, "bold"))
        self.work_hours_left.pack(anchor="nw", padx=10, pady=(0, 3))

        # Row 5: Pause info text
        self.pause_info = tk.Label(self.info_frame, bg=BG,
                                   fg=Color.PAUSE.value, font=("Arial", 13, "bold"))
        self.pause_info.pack(anchor="nw", padx=10, pady=(0, 4))

        self.pause_bar_canvas = tk.Canvas(self.info_frame, bg=BG,
                                          width=self._bar_w, height=self._bar_h,
                                          highlightthickness=0)
        self.pause_bar_canvas.pack(anchor="nw", padx=10, pady=(0, 6))     

        # Row 5: Target leave time
        self.you_can_go_in = tk.Label(self.info_frame, bg=BG,
                                      fg=Color.ACCENT.value, font=("Arial", 17, "bold"))
        self.you_can_go_in.pack(anchor="nw", padx=10, pady=(0, 2))   

        # ── Button row: Work | Business Trip | Pause ──────────────────────────
        self.btn_frame = tk.Frame(self.main_frame, bg=Color.FOREGROUND.value)
        self.btn_frame.pack(side="bottom", pady=(10, 20))

        BTN_W = 18

        self.start_button = tk.Button(self.btn_frame, text="Clock In",
                                      bg=Color.BTN_CLOCKIN_BG.value, fg=Color.BTN_CLOCKIN_FG.value,
                                      activebackground=Color.BTN_CLOCKIN_BG.value, activeforeground=Color.BTN_CLOCKIN_FG.value,
                                      command=self.handle_start_stop, relief="flat",
                                      font=("Arial", 11, "bold"), width=BTN_W, pady=10)
        self.start_button.pack(side="left", padx=6)

        self.dienstgang_button = tk.Button(
            self.btn_frame,
            text="🚗 Business Trip Start",
            bg=Color.BTN_TRIP_BG.value, fg=Color.BTN_TRIP_FG.value,
            activebackground=Color.BTN_TRIP_BG.value, activeforeground=Color.BTN_TRIP_FG.value,
            command=self.handle_dienstgang_click, relief="flat",
            font=("Arial", 11, "bold"), width=BTN_W, pady=10,
        )
        self.dienstgang_button.pack(side="left", padx=6)

        self.pause_button = tk.Button(self.btn_frame, text="Break",
                                      bg=Color.BTN_PAUSE_BG.value, fg=Color.BTN_PAUSE_FG.value,
                                      activebackground=Color.BTN_PAUSE_BG.value, activeforeground=Color.BTN_PAUSE_FG.value,
                                      command=self.handle_pause_click, relief="flat",
                                      font=("Arial", 11, "bold"), width=BTN_W, pady=10)
        self.pause_button.pack(side="left", padx=6)

        self.update_dienstgang_button_text()

    # ── Button handlers ───────────────────────────────────────────────────────
    def handle_start_stop(self):
        if self.tracker.start_time_stamp == 0:
            self.tracker.start_tracking()
            self._notified_work_done  = False
            self._notified_pause_done = False
            self._notified_pause_warn = False
            self.tracker.save_data()
            self._nova_work_async("start_work")
            self._nova_saldo_snapshot = None
            self._saldo_syncing = False
            self._sync_saldo_from_nova(delay_ms=5000)
        else:
            self.tracker.end_open_pause()
            now          = time.time()
            total_pause  = self.tracker.get_total_pause_duration()
            work_elapsed = (now - self.tracker.start_time_stamp) - total_pause
            goal_secs    = self.tracker.daily_goal * 3600
            diff         = work_elapsed - goal_secs

            if diff < 0:
                missing = self.format_seconds(abs(diff))
                if not messagebox.askyesno(
                    "⚠ Work not finished",
                    f"You still have {missing} of work remaining!\n\n"
                    f"Stop anyway?"
                ):
                    return

            self.tracker.reset_values()
            self.tracker.save_data()
            self._nova_work_async("end_work")
        self.update_start_button()

    def handle_pause_click(self):
        if self.tracker.is_on_dienstgang:
            return
        self.tracker.toggle_pause()
        self.update_pause_button_text()
        self.tracker.save_data()
        self._nova_pause_async()

    def _nova_work_async(self, action: str):
        """Fire start_work or end_work in a background thread."""
        if not NOVA_AVAILABLE or not self.nova_cfg.url:
            return
        def _run():
            try:
                nova.run_nova_action(action)
            except Exception as e:
                print(f"[Nova Work] {action} failed: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def _nova_trip_async(self):
        """Fire the correct Nova business trip action in a background thread."""
        if not NOVA_AVAILABLE or not self.nova_cfg.url:
            return
        # Read state AFTER toggle — is_on_dienstgang=True means trip just started
        action = "start_business_trip" if self.tracker.is_on_dienstgang else "end_business_trip"
        def _run():
            try:
                nova.run_nova_action(action)
            except Exception as e:
                print(f"[Nova Trip] {action} failed: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def _nova_pause_async(self):
        """Fire the correct Nova pause action in a background thread."""
        if not NOVA_AVAILABLE or not self.nova_cfg.url:
            return
        # Read state AFTER toggle — is_in_pause=True means we just started a pause
        action = "start_pause" if self.tracker.is_in_pause else "end_pause"
        def _run():
            try:
                nova.run_nova_action(action)
            except Exception as e:
                print(f"[Nova Pause] {action} failed: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def handle_dienstgang_click(self):
        if self.tracker.is_in_pause:
            return
        self._do_toggle_dienstgang()

    def update_start_button(self):
        if self.tracker.start_time_stamp > 0:
            self.start_button.config(text="Clock Out",
                                     bg=Color.BTN_CLOCKOUT_BG.value,
                                     fg=Color.BTN_CLOCKOUT_FG.value,
                                     activebackground=Color.BTN_CLOCKOUT_BG.value,
                                     activeforeground=Color.BTN_CLOCKOUT_FG.value)
        else:
            self.start_button.config(text="Clock In",
                                     bg=Color.BTN_CLOCKIN_BG.value,
                                     fg=Color.BTN_CLOCKIN_FG.value,
                                     activebackground=Color.BTN_CLOCKIN_BG.value,
                                     activeforeground=Color.BTN_CLOCKIN_FG.value)

    def update_pause_button_text(self):
        if self.tracker.is_in_pause:
            self.pause_button.config(text="End Break",
                                     bg=Color.BTN_ENDPAUSE_BG.value,
                                     fg=Color.BTN_ENDPAUSE_FG.value,
                                     activebackground=Color.BTN_ENDPAUSE_BG.value,
                                     activeforeground=Color.BTN_ENDPAUSE_FG.value,
                                     state="normal")
            self.dienstgang_button.config(state="disabled", fg="#888888")
        else:
            self.pause_button.config(text="Break",
                                     bg=Color.BTN_PAUSE_BG.value,
                                     fg=Color.BTN_PAUSE_FG.value,
                                     activebackground=Color.BTN_PAUSE_BG.value,
                                     activeforeground=Color.BTN_PAUSE_FG.value)
            if not self.tracker.is_on_dienstgang:
                self.dienstgang_button.config(state="normal",
                                              fg=Color.BTN_TRIP_FG.value,
                                              activeforeground=Color.BTN_TRIP_FG.value)

    def update_dienstgang_button_text(self):
        if self.tracker.is_on_dienstgang:
            self.dienstgang_button.config(
                text="🏠 Business Trip End",
                bg=Color.BTN_ENDTRIP_BG.value,
                fg=Color.BTN_ENDTRIP_FG.value,
                activebackground=Color.BTN_ENDTRIP_BG.value,
                activeforeground=Color.BTN_ENDTRIP_FG.value,
            )
            self.pause_button.config(state="disabled",
                                     bg=Color.BTN_PAUSE_BG.value, fg="#888888")
        else:
            self.dienstgang_button.config(
                text="🚗 Business Trip Start",
                bg=Color.BTN_TRIP_BG.value,
                fg=Color.BTN_TRIP_FG.value,
                activebackground=Color.BTN_TRIP_BG.value,
                activeforeground=Color.BTN_TRIP_FG.value,
            )
            self.pause_button.config(state="normal",
                                     fg=Color.BTN_PAUSE_FG.value,
                                     activeforeground=Color.BTN_PAUSE_FG.value)

    # ── Popup helpers ─────────────────────────────────────────────────────────
    def _make_popup(self, title):
        win = tk.Toplevel(self.master)
        win.title(title)
        win.config(bg=Color.BACKGROUND.value)
        win.resizable(False, False)
        win.withdraw()
        if os.path.exists(self.icon_ico):
            try: win.iconbitmap(self.icon_ico)
            except Exception: pass
        return win

    def _position_left(self, win):
        def _pos():
            self.master.update_idletasks()
            win.update_idletasks()
            sw = win.winfo_reqwidth()  or 300
            sh = win.winfo_reqheight() or 400
            mx = self.master.winfo_x()
            my = self.master.winfo_y()
            mw = self.master.winfo_width()
            mh = self.master.winfo_height()
            x  = mx - sw - 80
            if x < 0:
                x = mx + mw + 8
            y  = my + (mh - sh) // 2
            scr_w = self.master.winfo_screenwidth()
            scr_h = self.master.winfo_screenheight()
            x = max(0, min(x, scr_w - sw - 8))
            y = max(0, min(y, scr_h - sh - 8))
            win.geometry(f"+{x}+{y}")
            win.deiconify()
        win.after(100, _pos)

    def _position_above(self, win, diagonal=False):
        def _pos():
            self.master.update_idletasks()
            win.update_idletasks()
            sw    = win.winfo_reqwidth()  or 360
            sh    = win.winfo_reqheight() or 480
            mx    = self.master.winfo_x()
            my    = self.master.winfo_y()
            mw    = self.master.winfo_width()
            mh    = self.master.winfo_height()
            scr_w = self.master.winfo_screenwidth()
            scr_h = self.master.winfo_screenheight()
            if diagonal:
                # Place diagonally: right edge of popup aligns ~40px past main right,
                # top of popup ~40px above main top
                x = mx + mw - sw - 600
                y = my - 575
            else:
                x = mx + (mw - sw) // 2
                y = my - sh - 8
            x = max(0, min(x, scr_w - sw - 8))
            y = max(0, min(y, scr_h - sh - 8))
            win.geometry(f"+{x}+{y}")
            win.deiconify()
        win.after(100, _pos)

    # ── NovaTime init ─────────────────────────────────────────────────────────
    def _try_init_nova(self):
        """Call nova.init_config() if nova is available and a config file exists."""
        if not NOVA_AVAILABLE:
            return
        cfg = self.nova_cfg
        if not cfg.url:
            return  # no config saved yet
        try:
            nova.init_config(
                cfg_url                  = cfg.url,
                cfg_username             = cfg.username,
                cfg_password             = cfg.password,
                cfg_http_auth_username   = cfg.proxy_auth_username,
                cfg_http_auth_password   = cfg.proxy_auth_password,
                cfg_headless             = not cfg.show_window,
            )
            print("[Nova] init_config() called successfully")
        except Exception as e:
            print(f"[Nova] init_config() failed: {e}")

    def _parse_nova_saldo(self, raw: str) -> float | None:
        """
        Parse a NovaTime saldo string into seconds.
        Handles both hour format  ("Saldo:  -4,57 Std")
        and minute format         ("Saldo:  -274 Min").
        Returns seconds as float, or None if unparseable.
        """
        import re
        # Minutes format:  "Saldo: -274 Min"  or "Saldo: 30 Min"
        m = re.search(r"Saldo:\s*([-+]?\d+[,.]?\d*)\s*Min", raw, re.IGNORECASE)
        if m:
            mins = float(m.group(1).replace(",", "."))
            return mins * 60

        # Hours format:  "Saldo:  -4,57 Std"  or "Saldo: 1.25 Std"
        # NovaTime uses HH,MM notation (comma = colon), NOT decimal hours.
        # e.g. "-4,57 Std" means -4h 57min, not -4.57h.
        m = re.search(r"Saldo:\s*([-+]?)(\d+)[,.](\d+)\s*Std", raw, re.IGNORECASE)
        if m:
            sign    = -1 if m.group(1) == "-" else 1
            hours   = int(m.group(2))
            minutes = int(m.group(3))
            return sign * (hours * 3600 + minutes * 60)

        # Fallback: bare number after "Saldo:" — assume hours
        m = re.search(r"Saldo:\s*([-+]?\d+[,.]?\d*)", raw)
        if m:
            val = float(m.group(1).replace(",", "."))
            print(f"[Nova Saldo] No unit found, assuming hours: {val}")
            return val * 3600

        return None

    def _sync_saldo_from_nova(self, delay_ms=0):
        """
        Fetch the real saldo from NovaTime in a background thread.
        delay_ms: wait this many milliseconds before starting (used after clock-in).
        """
        if not NOVA_AVAILABLE or not self.nova_cfg.url:
            return

        # Show Syncing... immediately regardless of delay
        self._saldo_syncing = True

        def _run():
            import time as _time
            _time.sleep(delay_ms / 1000.0)
            try:
                raw = nova.run_nova_action("saldo")
                if not isinstance(raw, str):
                    print(f"[Nova Saldo] Unexpected return type: {type(raw)}")
                    return

                seconds = self._parse_nova_saldo(raw)
                if seconds is None:
                    print(f"[Nova Saldo] Could not parse: {raw!r}")
                    return

                def _apply():
                    self._saldo_syncing = False
                    self.tracker.total_balance_seconds = seconds
                    self.tracker.save_data()
                    self._nova_saldo_snapshot = (seconds, time.time())
                    hrs = seconds / 3600
                    print(f"[Nova Saldo] Synced: {raw.strip()} → {seconds:.0f}s ({hrs:+.2f}h)")

                self.master.after(0, _apply)
            except Exception as e:
                self.master.after(0, lambda: setattr(self, "_saldo_syncing", False))
                print(f"[Nova Saldo] Sync failed: {e}")

        threading.Thread(target=_run, daemon=True).start()

    # ── Theme Picker ──────────────────────────────────────────────────────────
    def open_theme_picker(self):
        win = self._make_popup("Theme")
        self._position_left(win)

        BG  = Color.BACKGROUND.value
        FG  = Color.TEXT.value
        BTN = Color.BUTTON.value
        ACC = Color.ACCENT.value

        tk.Label(win, text="🎨  Choose Theme",
                 bg=BG, fg=ACC, font=("Arial", 13, "bold")
                 ).pack(pady=(18, 4), padx=24, anchor="w")
        tk.Frame(win, bg=BTN, height=1).pack(fill=tk.X, padx=24, pady=(0, 12))

        current_theme = _load_active_theme_name()

        PREVIEW = {
            "Dark Mode":  ("⬛", "#1f1d1d", "#ffffff"),
            "Dracula":    ("🟣", "#282a36", "#f8f8f2"),
            "Blue Theme": ("🔵", "#0d1b2a", "#e0f0ff"),
        }

        selected_var = tk.StringVar(value=current_theme)

        btn_refs = {}
        for name in THEMES:
            icon, bg_col, fg_col = PREVIEW[name]
            is_active = (name == current_theme)

            row = tk.Frame(win, bg=BG)
            row.pack(fill=tk.X, padx=20, pady=3)

            # Colour swatch
            swatch = tk.Frame(row, bg=bg_col, width=24, height=24,
                              highlightbackground=fg_col, highlightthickness=1)
            swatch.pack(side="left", padx=(0, 8))
            swatch.pack_propagate(False)
            tk.Label(swatch, text=" ", bg=bg_col).pack()

            btn = tk.Button(
                row, text=f"{icon}  {name}",
                bg=ACC if is_active else BTN,
                fg=FG,
                font=("Arial", 10, "bold" if is_active else "normal"),
                bd=0, padx=14, pady=6, anchor="w", width=16,
                relief="flat",
            )
            btn.pack(side="left")
            btn_refs[name] = btn

            def _pick(n=name):
                # Update button styles
                for bname, b in btn_refs.items():
                    b.config(
                        bg=ACC if bname == n else BTN,
                        font=("Arial", 10, "bold" if bname == n else "normal"),
                    )
                selected_var.set(n)
                # Apply theme and redraw main window
                _apply_theme(n)
                _save_active_theme_name(n)
                self._redraw_all_colors()

            btn.config(command=_pick)

        tk.Frame(win, bg=BTN, height=1).pack(fill=tk.X, padx=24, pady=(14, 8))
        tk.Label(win, text="Changes apply instantly.", bg=BG, fg=BTN,
                 font=("Arial", 8)).pack(pady=(0, 14))

        win.protocol("WM_DELETE_WINDOW", win.destroy)

    def _redraw_all_colors(self):
        """Re-apply all current Color values to the main window widgets."""
        BG  = Color.BACKGROUND.value
        FG  = Color.FOREGROUND.value
        BTN = Color.BUTTON.value
        TXT = Color.TEXT.value
        ACC = Color.ACCENT.value

        # ── Root + frames ─────────────────────────────────────────────────────
        self.master.config(bg=BG)
        self.main_frame.config(bg=FG)
        self.info_frame.config(bg=BG)
        self.btn_frame.config(bg=FG)

        # ── Header buttons ────────────────────────────────────────────────────
        self.hdr_settings_btn.config(bg=Color.BTN_SETTINGS_BG.value, fg=Color.BTN_SETTINGS_FG.value,
                                      activebackground=Color.BTN_SETTINGS_BG.value, activeforeground=Color.BTN_SETTINGS_FG.value)
        self.hdr_api_btn.config(    bg=Color.BTN_API_BG.value,       fg=Color.BTN_API_FG.value,
                                      activebackground=Color.BTN_API_BG.value, activeforeground=Color.BTN_API_FG.value)
        self.hdr_overtime_btn.config(bg=Color.BTN_OVERTIME_BG.value, fg=Color.BTN_OVERTIME_FG.value,
                                      activebackground=Color.BTN_OVERTIME_BG.value, activeforeground=Color.BTN_OVERTIME_FG.value)
        self.hdr_bored_btn.config(  bg=Color.BTN_BORED_BG.value,     fg=Color.BTN_BORED_FG.value,
                                      activebackground=Color.BTN_BORED_BG.value, activeforeground=Color.BTN_BORED_FG.value)
        self.hdr_theme_btn.config(  bg=Color.BTN_THEME_BG.value,     fg=Color.BTN_THEME_FG.value,
                                      activebackground=Color.BTN_THEME_BG.value, activeforeground=Color.BTN_THEME_FG.value)

        # Parent frame of header buttons
        for child in self.main_frame.winfo_children():
            if child.winfo_class() == "Frame" and child not in (self.info_frame, self.btn_frame):
                child.config(bg=FG)
                break

        # ── Info labels & canvases ────────────────────────────────────────────
        self.time_display.config(bg=BG, fg=TXT)
        self.balance_account_label.config(bg=BG)
        self.worked_label.config(bg=BG, fg=TXT)
        self.work_hours_left.config(bg=BG, fg=TXT)
        self.pause_info.config(bg=BG)
        self.you_can_go_in.config(bg=BG, fg=ACC)
        self.work_bar_canvas.config(bg=BG)
        self.pause_bar_canvas.config(bg=BG)

        # Separator lines inside info_frame
        for child in self.info_frame.winfo_children():
            try:
                if child.winfo_class() == "Frame":
                    child.config(bg=BTN)
            except Exception:
                pass

        # ── Action buttons (state-aware) ──────────────────────────────────────
        self.update_start_button()
        self.update_pause_button_text()
        self.update_dienstgang_button_text()
    # ── API Settings window ───────────────────────────────────────────────────
    def open_api_settings(self):
        win = self._make_popup("Nova Time API Settings")
        self._position_above(win)

        BG  = Color.BACKGROUND.value
        FG  = Color.TEXT.value
        FG2 = "#aaaaaa"

        tk.Label(win, text="Nova Time API Settings",
                 bg=BG, fg=Color.API.value,
                 font=("Arial", 13, "bold")).pack(pady=(18, 4), padx=24, anchor="w")
        tk.Label(win, text="─" * 46, bg=BG, fg=Color.BUTTON.value).pack(padx=24, anchor="w")

        def field_row(parent, label, default="", show=None):
            """Return a StringVar pre-filled with default, with a labelled entry above it."""
            tk.Label(parent, text=label, bg=BG, fg=FG2,
                     font=("Arial", 9)).pack(pady=(12, 1), padx=24, anchor="w")
            var = tk.StringVar(value=default)
            kw  = {"show": show} if show else {}
            tk.Entry(parent, textvariable=var, bg=Color.FOREGROUND.value, fg=FG,
                     insertbackground=FG, relief="flat", font=("Arial", 11),
                     width=36, **kw).pack(padx=24, anchor="w", ipady=4)
            return var

        url_var   = field_row(win, "NovaTime URL",          self.nova_cfg.url)
        user_var  = field_row(win, "Username",              self.nova_cfg.username)
        pass_var  = field_row(win, "Password",              self.nova_cfg.password,  show="•")
        puser_var = field_row(win, "Proxy Auth Username",   self.nova_cfg.proxy_auth_username)
        ppass_var = field_row(win, "Proxy Auth Password",   self.nova_cfg.proxy_auth_password, show="•")

        # Show NovaTime Window checkbox
        tk.Label(win, text="─" * 46, bg=BG, fg=Color.BUTTON.value).pack(pady=(14, 0), padx=24, anchor="w")

        show_var = tk.BooleanVar(value=self.nova_cfg.show_window)
        chk_frame = tk.Frame(win, bg=BG)
        chk_frame.pack(pady=(6, 0), padx=24, anchor="w")
        tk.Checkbutton(
            chk_frame, text=" Show NovaTime Window",
            variable=show_var,
            bg=BG, fg=FG, selectcolor=Color.FOREGROUND.value,
            activebackground=BG, activeforeground=FG,
            font=("Arial", 10),
        ).pack(side="left")

        # Save button
        tk.Label(win, text="─" * 46, bg=BG, fg=Color.BUTTON.value).pack(pady=(14, 0), padx=24, anchor="w")

        def save_and_close():
            self.nova_cfg.url                 = url_var.get().strip()
            self.nova_cfg.username            = user_var.get().strip()
            self.nova_cfg.password            = pass_var.get()
            self.nova_cfg.proxy_auth_username = puser_var.get().strip()
            self.nova_cfg.proxy_auth_password = ppass_var.get()
            self.nova_cfg.show_window         = show_var.get()
            self.nova_cfg.save()
            self._try_init_nova()
            win.destroy()

        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(pady=(10, 18), padx=24, anchor="w")

        tk.Button(btn_row, text="💾  Save", bg=Color.API.value, fg=FG,
                  font=("Arial", 11, "bold"), bd=0, padx=20, pady=8,
                  command=save_and_close).pack(side="left", padx=(0, 8))

        # Status label shown after test (hidden initially)
        test_status = tk.Label(btn_row, text="", bg=BG,
                               font=("Arial", 10, "bold"))
        # (packed after button so it appears to the right)

        def _set_test_status(ok, msg):
            """Called from background thread via win.after — safe for tkinter."""
            test_status.config(
                text=msg,
                fg=Color.OVERTIME.value if ok else Color.NEGATIVE.value,
            )
            test_status.pack(side="left", padx=(10, 0))

        def test_api():
            if not NOVA_AVAILABLE:
                _set_test_status(False, "✗ novatime not found")
                return
            if not self.nova_cfg.url:
                _set_test_status(False, "✗ No URL configured")
                return

            test_btn.config(state="disabled", text="⏳  Testing…")
            test_status.pack_forget()   # hide previous result while running

            def _run():
                try:
                    nova.run_nova_action("test")
                    win.after(0, lambda: _set_test_status(True,  "✓ Connection OK"))
                except Exception as e:
                    print(f"[API Test] Error: {e}")
                    win.after(0, lambda: _set_test_status(False, f"✗ {e}"))
                finally:
                    win.after(0, lambda: test_btn.config(
                        state="normal", text="🔌  Test API"))

            threading.Thread(target=_run, daemon=True).start()

        test_btn = tk.Button(btn_row, text="🔌  Test API", bg=Color.BUTTON.value, fg=FG,
                  font=("Arial", 11, "bold"), bd=0, padx=20, pady=8,
                  command=test_api)
        test_btn.pack(side="left")
        test_status.pack_forget()   # keep hidden until first test

        win.protocol("WM_DELETE_WINDOW", win.destroy)

    # ── Settings ──────────────────────────────────────────────────────────────
    def open_settings(self):
        win = self._make_popup("Settings")
        self._position_left(win)
        win.geometry("620x460")

        BG  = Color.BACKGROUND.value
        FG  = Color.FOREGROUND.value
        TXT = Color.TEXT.value
        BTN = Color.BUTTON.value
        ACC = Color.ACCENT.value

        # ── Helper: card frame ────────────────────────────────────────────────
        def make_card(parent, title, title_color):
            # parent is already grid-placed; configure it as the card
            parent.config(bg=FG)
            tk.Label(parent, text=title, bg=FG, fg=title_color,
                     font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
            tk.Frame(parent, bg=BTN, height=1).pack(fill=tk.X, padx=8, pady=(0, 4))
            inner = tk.Frame(parent, bg=BG)
            inner.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
            return inner

        # ── Helper: compact slider row (fits inside a card) ───────────────────
        # tk.Scale adds ~25px left padding internally; _LX aligns labels to track.
        _LX = 26

        def slider_row(parent, label, var, from_, to, resolution, fmt_fn, color):
            tk.Label(parent, text=label, bg=BG, fg=TXT,
                     font=("Arial", 9)).pack(anchor="w", padx=(_LX, 4), pady=(6, 0))
            disp = tk.Label(parent, text="", bg=BG, fg=color,
                            font=("Arial", 12, "bold"))
            disp.pack(anchor="w", padx=(_LX, 4))
            def upd(*_): disp.config(text=fmt_fn(var.get()))
            var.trace_add("write", upd)
            tk.Scale(parent, variable=var, from_=from_, to=to, resolution=resolution,
                     orient=tk.HORIZONTAL, bg=BG, fg=TXT,
                     highlightthickness=0, showvalue=False, length=230
                     ).pack(padx=4, pady=(0, 2))
            upd()
            return upd

        def hhmm_slider_row(parent, label, var_hours, from_h, to_h, color):
            """Compact HH:MM slider row for inside a card."""
            tk.Label(parent, text=label, bg=BG, fg=TXT,
                     font=("Arial", 9)).pack(anchor="w", padx=(_LX, 4), pady=(6, 0))
            row_frame = tk.Frame(parent, bg=BG)
            row_frame.pack(anchor="w", padx=(_LX, 4))
            disp = tk.Label(row_frame, text="", bg=BG, fg=color,
                            font=("Arial", 12, "bold"))
            disp.pack(side="left", padx=(0, 8))
            tk.Label(row_frame, text="h", bg=BG, fg=TXT,
                     font=("Arial", 9)).pack(side="left")
            sb_h = tk.Spinbox(row_frame, from_=int(from_h), to=int(to_h),
                              width=3, font=("Arial", 10),
                              bg=FG, fg=TXT, buttonbackground=BTN,
                              insertbackground=TXT, relief="flat")
            sb_h.pack(side="left", padx=(2, 5))
            tk.Label(row_frame, text="min", bg=BG, fg=TXT,
                     font=("Arial", 9)).pack(side="left")
            sb_m = tk.Spinbox(row_frame, from_=0, to=59, width=3,
                              font=("Arial", 10),
                              bg=FG, fg=TXT, buttonbackground=BTN,
                              insertbackground=TXT, relief="flat")
            sb_m.pack(side="left", padx=(2, 0))
            _upd = [False]
            def _refresh(*_):
                v = var_hours.get(); h = int(v); m = round((v - h) * 60)
                disp.config(text=f"{h:02d}:{m:02d} h")
            def _s2sp(*_):
                if _upd[0]: return
                _upd[0] = True
                v = var_hours.get(); h = int(v); m = round((v - h) * 60)
                sb_h.delete(0, "end"); sb_h.insert(0, str(h))
                sb_m.delete(0, "end"); sb_m.insert(0, str(m))
                _refresh(); _upd[0] = False
            def _sp2s(*_):
                if _upd[0]: return
                _upd[0] = True
                try:
                    h = max(int(from_h), min(int(to_h), int(sb_h.get())))
                    m = max(0, min(59, int(sb_m.get())))
                except ValueError:
                    _upd[0] = False; return
                var_hours.set(round(h + m / 60, 10)); _refresh(); _upd[0] = False
            var_hours.trace_add("write", _s2sp)
            sb_h.config(command=_sp2s); sb_m.config(command=_sp2s)
            sb_h.bind("<FocusOut>", _sp2s); sb_h.bind("<Return>", _sp2s)
            sb_m.bind("<FocusOut>", _sp2s); sb_m.bind("<Return>", _sp2s)
            tk.Scale(parent, variable=var_hours, from_=from_h, to=to_h,
                     resolution=1/60, orient=tk.HORIZONTAL,
                     bg=BG, fg=TXT, highlightthickness=0,
                     showvalue=False, length=230
                     ).pack(padx=4, pady=(0, 2))
            _s2sp()
            return _refresh

        def pause_slider_row(parent, label, var_mins, color):
            """Compact pause (minutes) slider row for inside a card."""
            tk.Label(parent, text=label, bg=BG, fg=TXT,
                     font=("Arial", 9)).pack(anchor="w", padx=(_LX, 4), pady=(6, 0))
            row_frame = tk.Frame(parent, bg=BG)
            row_frame.pack(anchor="w", padx=(_LX, 4))
            disp = tk.Label(row_frame, text="", bg=BG, fg=color,
                            font=("Arial", 12, "bold"))
            disp.pack(side="left", padx=(0, 8))
            tk.Label(row_frame, text="h", bg=BG, fg=TXT,
                     font=("Arial", 9)).pack(side="left")
            sb_h = tk.Spinbox(row_frame, from_=0, to=1, width=3,
                              font=("Arial", 10),
                              bg=FG, fg=TXT, buttonbackground=BTN,
                              insertbackground=TXT, relief="flat")
            sb_h.pack(side="left", padx=(2, 5))
            tk.Label(row_frame, text="min", bg=BG, fg=TXT,
                     font=("Arial", 9)).pack(side="left")
            sb_m = tk.Spinbox(row_frame, from_=0, to=59, width=3,
                              font=("Arial", 10),
                              bg=FG, fg=TXT, buttonbackground=BTN,
                              insertbackground=TXT, relief="flat")
            sb_m.pack(side="left", padx=(2, 0))
            _upd = [False]
            def _refresh(*_):
                total = var_mins.get()
                disp.config(text=f"{total:.0f} min")
            def _s2sp(*_):
                if _upd[0]: return
                _upd[0] = True
                total = int(round(var_mins.get()))
                sb_h.delete(0, "end"); sb_h.insert(0, str(total // 60))
                sb_m.delete(0, "end"); sb_m.insert(0, str(total % 60))
                _refresh(); _upd[0] = False
            def _sp2s(*_):
                if _upd[0]: return
                _upd[0] = True
                try:
                    h = max(0, min(1, int(sb_h.get())))
                    m = max(0, min(59, int(sb_m.get())))
                except ValueError:
                    _upd[0] = False; return
                var_mins.set(min(90, h * 60 + m)); _refresh(); _upd[0] = False
            var_mins.trace_add("write", _s2sp)
            sb_h.config(command=_sp2s); sb_m.config(command=_sp2s)
            sb_h.bind("<FocusOut>", _sp2s); sb_h.bind("<Return>", _sp2s)
            sb_m.bind("<FocusOut>", _sp2s); sb_m.bind("<Return>", _sp2s)
            tk.Scale(parent, variable=var_mins, from_=0, to=90,
                     resolution=1, orient=tk.HORIZONTAL,
                     bg=BG, fg=TXT, highlightthickness=0,
                     showvalue=False, length=230
                     ).pack(padx=4, pady=(0, 2))
            _s2sp()
            return _refresh

        # ── Title bar ─────────────────────────────────────────────────────────
        title_bar = tk.Frame(win, bg=BG)
        title_bar.pack(fill=tk.X, padx=14, pady=(12, 6))
        tk.Label(title_bar, text="⚙  Settings", bg=BG, fg=ACC,
                 font=("Arial", 13, "bold")).pack(side="left")
        tk.Frame(win, bg=BTN, height=1).pack(fill=tk.X, padx=14, pady=(0, 8))

        # ── 2×2 Grid container ────────────────────────────────────────────────
        grid_outer = tk.Frame(win, bg=BG)
        grid_outer.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))
        grid_outer.columnconfigure(0, weight=1, uniform="col")
        grid_outer.columnconfigure(1, weight=1, uniform="col")
        grid_outer.rowconfigure(0, weight=1, uniform="row")
        grid_outer.rowconfigure(1, weight=1, uniform="row")

        # ── Variables ─────────────────────────────────────────────────────────
        goal_var        = tk.DoubleVar(value=self.tracker.daily_goal)
        pause_var       = tk.DoubleVar(value=self.tracker.default_pause_mins)
        credit_var      = tk.DoubleVar(value=self.tracker.daily_credit_mins)
        warn_var        = tk.DoubleVar(value=self.tracker.pause_warn_before_mins)
        brk_after_var   = tk.DoubleVar(value=self.tracker.break_required_after_hours)

        # ── Card: Work (top-left) ─────────────────────────────────────────────
        work_card_outer = tk.Frame(grid_outer, bg=FG)
        work_card_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 5))
        work_inner = make_card(work_card_outer, "💼  Work", Color.OVERTIME.value)
        hhmm_slider_row(work_inner, "Daily Goal:",
                        goal_var, 1.0, 12.0, Color.OVERTIME.value)
        slider_row(work_inner, "Daily Credit:",
                   credit_var, 0, 60, 1,
                   lambda v: f"{int(v)} min", ACC)

        # ── Card: Break (top-right) ───────────────────────────────────────────
        break_card_outer = tk.Frame(grid_outer, bg=FG)
        break_card_outer.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0, 5))
        break_inner = make_card(break_card_outer, "☕  Break", Color.PAUSE.value)
        pause_slider_row(break_inner, "Target Break:",
                         pause_var, Color.PAUSE.value)
        slider_row(break_inner, "Break Warning (min before trigger):",
                   warn_var, 0, 60, 1,
                   lambda v: f"{int(v)} min before", Color.NEGATIVE.value)

        # ── Card: Extras (bottom-left) ────────────────────────────────────────
        extras_card_outer = tk.Frame(grid_outer, bg=FG)
        extras_card_outer.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(5, 0))
        extras_inner = make_card(extras_card_outer, "⚡  Extras", ACC)
        slider_row(extras_inner, "Break Required After (hours):",
                   brk_after_var, 1.0, 12.0, 0.5,
                   lambda v: f"{v:.1f} h", ACC)

        def hard_reset():
            if messagebox.askyesno("Hard Reset",
                                   "Really reset everything?\nBalance + current session will be cleared."):
                self.tracker.total_balance_seconds = 0.0
                self.tracker.reset_values()
                self.tracker.save_data()
                win.destroy()

        # ── Card: Correction (bottom-right) ───────────────────────────────────
        corr_card_outer = tk.Frame(grid_outer, bg=FG)
        corr_card_outer.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=(5, 0))
        corr_inner = make_card(corr_card_outer, "🔧  Correction", Color.ACCENT.value)

        # apply callback (wired after all vars exist)
        def apply(*_):
            self.tracker.daily_goal                 = goal_var.get()
            self.tracker.default_pause_mins         = pause_var.get()
            self.tracker.daily_credit_mins          = credit_var.get()
            self.tracker.pause_warn_before_mins     = warn_var.get()
            self.tracker.break_required_after_hours = brk_after_var.get()
            self.tracker.save_data()

        for v in (goal_var, pause_var, credit_var, warn_var, brk_after_var):
            v.trace_add("write", apply)

        # ── Correction buttons (defined inline, placed in corr_inner) ─────────
        def open_already_checked_in():
            """Open a dialog to retroactively set today's check-in time (migration helper)."""
            if self.tracker.start_time_stamp > 0:
                messagebox.showinfo(
                    "Already Running",
                    "There is already an active tracking session.\n"
                    "Stop it first before using 'Already Checked In'."
                )
                return

            dlg = tk.Toplevel(win)
            dlg.title("Already Checked In")
            dlg.config(bg=Color.BACKGROUND.value)
            dlg.resizable(False, False)
            dlg.grab_set()
            if os.path.exists(self.icon_ico):
                try: dlg.iconbitmap(self.icon_ico)
                except Exception: pass

            BG2  = Color.BACKGROUND.value
            FG2  = Color.TEXT.value
            ACC2 = Color.ACCENT.value

            tk.Label(dlg, text="Already Checked In",
                     bg=BG2, fg=ACC2, font=("Arial", 13, "bold")
                     ).pack(pady=(18, 2), padx=24, anchor="w")
            tk.Label(dlg, text="Set the time you actually clocked in today.\n"
                               "No API call will be made – local data only.",
                     bg=BG2, fg="#aaaaaa", font=("Arial", 9)
                     ).pack(pady=(0, 6), padx=24, anchor="w")
            tk.Frame(dlg, bg=Color.BUTTON.value, height=1).pack(fill=tk.X, padx=24, pady=(0, 12))

            # Determine sensible default: current time
            now_dt = datetime.now()
            hour_var   = tk.IntVar(value=now_dt.hour)
            minute_var = tk.IntVar(value=now_dt.minute)

            time_disp = tk.Label(dlg, text="", bg=BG2, fg=ACC2,
                                 font=("Arial", 22, "bold"))
            time_disp.pack(pady=(0, 8))

            def refresh_disp(*_):
                time_disp.config(
                    text=f"{hour_var.get():02d}:{minute_var.get():02d} Uhr"
                )

            # Hour slider
            tk.Label(dlg, text="Hour", bg=BG2, fg=FG2,
                     font=("Arial", 10)).pack(padx=24, anchor="w")
            tk.Scale(dlg, variable=hour_var, from_=0, to=23, resolution=1,
                     orient=tk.HORIZONTAL, bg=BG2, fg=FG2,
                     troughcolor="#333", highlightthickness=0,
                     showvalue=True, length=260
                     ).pack(padx=24, pady=(0, 10))

            # Minute slider (1-min steps)
            tk.Label(dlg, text="Minute", bg=BG2, fg=FG2,
                     font=("Arial", 10)).pack(padx=24, anchor="w")
            tk.Scale(dlg, variable=minute_var, from_=0, to=59, resolution=1,
                     orient=tk.HORIZONTAL, bg=BG2, fg=FG2,
                     troughcolor="#333", highlightthickness=0,
                     showvalue=True, length=260
                     ).pack(padx=24, pady=(0, 12))

            hour_var.trace_add("write",   refresh_disp)
            minute_var.trace_add("write", refresh_disp)
            refresh_disp()

            tk.Frame(dlg, bg=Color.BUTTON.value, height=1).pack(fill=tk.X, padx=24, pady=(0, 10))

            def confirm():
                today = datetime.now().date()
                checkin_dt = datetime(
                    today.year, today.month, today.day,
                    hour_var.get(), minute_var.get(), 0
                )
                checkin_ts = checkin_dt.timestamp()
                if checkin_ts > time.time():
                    messagebox.showwarning(
                        "Future time",
                        "The check-in time you selected is in the future.\n"
                        "Please choose an earlier time.",
                        parent=dlg
                    )
                    return
                # Set the start timestamp retroactively – no API call
                self.tracker.start_time_stamp = checkin_ts
                self.tracker.is_in_pause      = False
                self.tracker.pauses           = []
                self.tracker.is_on_dienstgang = False
                self._notified_work_done      = False
                self._notified_pause_done     = False
                self._notified_pause_warn     = False
                self.tracker.save_data()
                dlg.destroy()
                messagebox.showinfo(
                    "Check-In Set",
                    f"Check-in time set to {checkin_dt.strftime('%H:%M Uhr')}.\n"
                    "Session is now active (local only – no API call made)."
                )

            btn_row2 = tk.Frame(dlg, bg=BG2)
            btn_row2.pack(pady=(0, 18), padx=24)

            tk.Button(btn_row2, text="✔  Confirm",
                      bg=Color.ACCENT.value, fg=FG2,
                      font=("Arial", 11, "bold"), bd=0, padx=20, pady=8,
                      command=confirm).pack(side="left", padx=(0, 8))
            tk.Button(btn_row2, text="Cancel",
                      bg=Color.BUTTON.value, fg=FG2,
                      font=("Arial", 11), bd=0, padx=20, pady=8,
                      command=dlg.destroy).pack(side="left")

            # Centre the dialog over the settings window
            dlg.update_idletasks()
            wx = win.winfo_x() + (win.winfo_width()  - dlg.winfo_reqwidth())  // 2
            wy = win.winfo_y() + (win.winfo_height() - dlg.winfo_reqheight()) // 2
            dlg.geometry(f"+{max(0,wx)}+{max(0,wy)}")

        tk.Button(corr_inner, text="⏱  Already Checked In",
                  bg=Color.ACCENT.value, fg=Color.TEXT.value,
                  font=("Arial", 9, "bold"), bd=0, padx=8, pady=5,
                  command=open_already_checked_in, relief="flat").pack(fill=tk.X, padx=4, pady=(8, 3))

        def open_correct_pause():
            """Open a dialog to retroactively add a break to the current session (migration helper)."""
            if not self.tracker.start_time_stamp:
                messagebox.showinfo(
                    "No Session",
                    "No active tracking session.\nStart or check in first."
                )
                return

            dlg = tk.Toplevel(win)
            dlg.title("Correct Break")
            dlg.config(bg=Color.BACKGROUND.value)
            dlg.resizable(False, False)
            dlg.grab_set()
            if os.path.exists(self.icon_ico):
                try: dlg.iconbitmap(self.icon_ico)
                except Exception: pass

            BG2  = Color.BACKGROUND.value
            FG2  = Color.TEXT.value
            PAU  = Color.PAUSE.value

            tk.Label(dlg, text="Correct Break",
                     bg=BG2, fg=PAU, font=("Arial", 13, "bold")
                     ).pack(pady=(18, 2), padx=24, anchor="w")
            tk.Label(dlg, text="Add a missed break to the current session.\n"
                               "No API call will be made – local data only.",
                     bg=BG2, fg="#aaaaaa", font=("Arial", 9)
                     ).pack(pady=(0, 6), padx=24, anchor="w")
            tk.Frame(dlg, bg=Color.BUTTON.value, height=1).pack(fill=tk.X, padx=24, pady=(0, 14))

            # ── Duration picker ───────────────────────────────────────────────
            pause_mins_var = tk.IntVar(value=30)
            _upd_lock = [False]

            dur_disp = tk.Label(dlg, text="", bg=BG2, fg=PAU,
                                font=("Arial", 22, "bold"))
            dur_disp.pack(pady=(0, 10))

            def _refresh_dur(*_):
                total = pause_mins_var.get()
                h = total // 60
                m = total % 60
                dur_disp.config(text=f"{h:01d}h {m:02d}min")

            # Spinbox row
            spin_frame = tk.Frame(dlg, bg=BG2)
            spin_frame.pack(pady=(0, 6))

            tk.Label(spin_frame, text="h", bg=BG2, fg=FG2,
                     font=("Arial", 10)).pack(side="left")
            sb_h = tk.Spinbox(spin_frame, from_=0, to=1, width=3,
                              font=("Arial", 12),
                              bg=Color.FOREGROUND.value, fg=FG2,
                              buttonbackground=Color.BUTTON.value,
                              insertbackground=FG2, relief="flat")
            sb_h.pack(side="left", padx=(2, 10))

            tk.Label(spin_frame, text="min", bg=BG2, fg=FG2,
                     font=("Arial", 10)).pack(side="left")
            sb_m = tk.Spinbox(spin_frame, from_=0, to=59, width=3,
                              font=("Arial", 12),
                              bg=Color.FOREGROUND.value, fg=FG2,
                              buttonbackground=Color.BUTTON.value,
                              insertbackground=FG2, relief="flat")
            sb_m.pack(side="left", padx=(2, 0))

            # Slider (1 min – 90 min)
            tk.Label(dlg, text="Duration (1 min – 1h 30min)", bg=BG2, fg=FG2,
                     font=("Arial", 9)).pack(padx=24, anchor="w")
            pause_slider = tk.Scale(dlg, variable=pause_mins_var,
                                    from_=1, to=90, resolution=1,
                                    orient=tk.HORIZONTAL, bg=BG2, fg=FG2,
                                    troughcolor="#333", highlightthickness=0,
                                    showvalue=False, length=260)
            pause_slider.pack(padx=24, pady=(2, 14))

            def _slider_to_spin(*_):
                if _upd_lock[0]: return
                _upd_lock[0] = True
                total = pause_mins_var.get()
                sb_h.delete(0, "end"); sb_h.insert(0, str(total // 60))
                sb_m.delete(0, "end"); sb_m.insert(0, str(total % 60))
                _refresh_dur()
                _upd_lock[0] = False

            def _spin_to_slider(*_):
                if _upd_lock[0]: return
                _upd_lock[0] = True
                try:
                    h = max(0, min(1, int(sb_h.get())))
                    m = max(0, min(59, int(sb_m.get())))
                except ValueError:
                    _upd_lock[0] = False
                    return
                total = max(1, min(90, h * 60 + m))
                pause_mins_var.set(total)
                _refresh_dur()
                _upd_lock[0] = False

            pause_mins_var.trace_add("write", _slider_to_spin)
            sb_h.config(command=_spin_to_slider)
            sb_m.config(command=_spin_to_slider)
            sb_h.bind("<FocusOut>", _spin_to_slider)
            sb_h.bind("<Return>",   _spin_to_slider)
            sb_m.bind("<FocusOut>", _spin_to_slider)
            sb_m.bind("<Return>",   _spin_to_slider)

            # Initialise spinboxes
            _slider_to_spin()

            tk.Frame(dlg, bg=Color.BUTTON.value, height=1).pack(fill=tk.X, padx=24, pady=(0, 10))

            def confirm_pause():
                duration_secs = pause_mins_var.get() * 60
                now_ts = time.time()
                pause_start = now_ts - duration_secs
                # Make sure the pause doesn't start before the session itself
                if pause_start < self.tracker.start_time_stamp:
                    pause_start = self.tracker.start_time_stamp
                # Add the pause as a completed entry
                self.tracker.pauses.append([pause_start, now_ts])
                self.tracker.save_data()
                dlg.destroy()
                h = pause_mins_var.get() // 60
                m = pause_mins_var.get() % 60
                messagebox.showinfo(
                    "Break Added",
                    f"A break of {h}h {m:02d}min has been added to today's session.\n"
                    "No API call was made."
                )

            btn_row3 = tk.Frame(dlg, bg=BG2)
            btn_row3.pack(pady=(0, 18), padx=24)

            tk.Button(btn_row3, text="✔  Confirm",
                      bg=PAU, fg=FG2,
                      font=("Arial", 11, "bold"), bd=0, padx=20, pady=8,
                      command=confirm_pause).pack(side="left", padx=(0, 8))
            tk.Button(btn_row3, text="Cancel",
                      bg=Color.BUTTON.value, fg=FG2,
                      font=("Arial", 11), bd=0, padx=20, pady=8,
                      command=dlg.destroy).pack(side="left")

            # Centre dialog over settings window
            dlg.update_idletasks()
            wx = win.winfo_x() + (win.winfo_width()  - dlg.winfo_reqwidth())  // 2
            wy = win.winfo_y() + (win.winfo_height() - dlg.winfo_reqheight()) // 2
            dlg.geometry(f"+{max(0,wx)}+{max(0,wy)}")

        tk.Button(corr_inner, text="☕  Correct Break",
                  bg=Color.PAUSE.value, fg=Color.TEXT.value,
                  font=("Arial", 9, "bold"), bd=0, padx=8, pady=5,
                  command=open_correct_pause, relief="flat").pack(fill=tk.X, padx=4, pady=3)

        tk.Button(corr_inner, text="🗑  Hard Reset (Balance + Session)",
                  bg=Color.TEST.value, fg=Color.TEXT.value,
                  font=("Arial", 9, "bold"), bd=0, padx=8, pady=5,
                  command=hard_reset, relief="flat").pack(fill=tk.X, padx=4, pady=3)

        win.protocol("WM_DELETE_WINDOW", lambda: [apply(), win.destroy()])

    # ── AutoOvertime window ───────────────────────────────────────────────────
    def open_auto_overtime(self):
        win = self._make_popup("AutoOvertime Planner")
        self._position_above(win, diagonal=True)
        win.geometry("800x540")
        win.resizable(True, True)

        BG  = Color.BACKGROUND.value
        ACC = Color.ACCENT.value
        TXT = Color.TEXT.value
        BTN = Color.BUTTON.value
        POS = Color.OVERTIME.value
        NEG = Color.NEGATIVE.value
        PAU = Color.PAUSE.value

        # Title bar
        title_bar = tk.Frame(win, bg=BG)
        title_bar.pack(fill=tk.X, padx=20, pady=(14, 0))
        tk.Label(title_bar, text="AutoOvertime Planner",
                 bg=BG, fg=ACC, font=("Arial", 14, "bold")).pack(side="left")
        tk.Label(title_bar, text="  Plan how to work down your balance over N days.",
                 bg=BG, fg=BTN, font=("Arial", 9)).pack(side="left")
        tk.Frame(win, bg=BTN, height=1).pack(fill=tk.X, padx=20, pady=(6, 0))

        # 2-column body
        body = tk.Frame(win, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)
        body.columnconfigure(0, minsize=268, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # LEFT panel
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))

        def sec_lbl(parent, text):
            tk.Label(parent, text=text.upper(), bg=BG, fg=BTN,
                     font=("Arial", 8, "bold")).pack(anchor="w", pady=(14, 1))
            tk.Frame(parent, bg=BTN, height=1).pack(fill=tk.X)

        def val_lbl(parent, color=TXT, size=13):
            lbl = tk.Label(parent, bg=BG, fg=color, font=("Arial", size, "bold"))
            lbl.pack(anchor="w", pady=(4, 0))
            return lbl

        def make_slider(parent, variable, from_, to, resolution):
            tk.Scale(parent, variable=variable, from_=from_, to=to,
                     resolution=resolution, orient=tk.HORIZONTAL,
                     bg=BG, fg=TXT, troughcolor="#333",
                     highlightthickness=0, showvalue=False,
                     length=240).pack(anchor="w", pady=(2, 0))

        # Balance slider
        sec_lbl(left, "Balance to clear")
        _bal_steps = 72
        bal_var  = tk.IntVar(value=0)
        bal_disp = val_lbl(left, color=NEG)

        def upd_bal(*_):
            secs = bal_var.get() * 600
            neg  = secs < 0
            h, s = divmod(abs(secs), 3600); m = s // 60
            bal_disp.config(text=f"{'-' if neg else '+'}{h:02d}:{m:02d}h",
                            fg=NEG if neg else POS)

        bal_var.trace_add("write", upd_bal)
        make_slider(left, bal_var, -_bal_steps, _bal_steps, 1)
        axis_frame = tk.Frame(left, bg=BG)
        axis_frame.pack(anchor="w", fill=tk.X, padx=2)
        tk.Label(axis_frame, text="-12h", bg=BG, fg=BTN,
                 font=("Arial", 7)).pack(side="left")
        tk.Label(axis_frame, text="0", bg=BG, fg=BTN,
                 font=("Arial", 7)).pack(side="left", expand=True)
        tk.Label(axis_frame, text="+12h", bg=BG, fg=BTN,
                 font=("Arial", 7)).pack(side="right")

        _init = round(self.tracker.total_balance_seconds / 600)
        bal_var.set(max(-_bal_steps, min(_bal_steps, _init)))

        # Days slider
        sec_lbl(left, "Spread over")
        days_var  = tk.IntVar(value=5)
        days_disp = val_lbl(left, color=ACC)
        def upd_days(*_):
            days_disp.config(text=f"{days_var.get()} day{'s' if days_var.get()!=1 else ''}")
        days_var.trace_add("write", upd_days)
        make_slider(left, days_var, 1, 31, 1)
        upd_days()

        # Skip Saturday checkbox
        skip_sat_var = tk.BooleanVar(value=True)
        sat_frame = tk.Frame(left, bg=BG)
        sat_frame.pack(anchor="w", pady=(6, 0))
        tk.Checkbutton(sat_frame, text="Skip Saturdays", variable=skip_sat_var,
                       bg=BG, fg=TXT, activebackground=BG, activeforeground=TXT,
                       selectcolor="#333", font=("Arial", 9),
                       command=lambda: compute(force=True)).pack(side="left")

        # Mode + time slider
        sec_lbl(left, "Fixed time")
        mode_var = tk.StringVar(value="arrive")
        mf = tk.Frame(left, bg=BG)
        mf.pack(anchor="w", pady=(6, 4))
        btn_arrive = tk.Button(mf, text="Arrive at", bd=0, padx=10, pady=4,
                               font=("Arial", 9, "bold"),
                               command=lambda: mode_var.set("arrive"))
        btn_leave  = tk.Button(mf, text="Leave at",  bd=0, padx=10, pady=4,
                               font=("Arial", 9, "bold"),
                               command=lambda: mode_var.set("leave"))
        btn_arrive.pack(side="left", padx=(0, 4))
        btn_leave.pack(side="left")

        time_var  = tk.DoubleVar(value=8.0)
        time_disp = val_lbl(left, color=POS)
        def upd_time(*_):
            v = time_var.get(); h = int(v); m = round((v - h) * 60)
            time_disp.config(text=f"{h:02d}:{m:02d} Uhr")
        time_var.trace_add("write", upd_time)
        make_slider(left, time_var, 0, 24.0, 0.25)
        upd_time()

        def refresh_mode_buttons(*_):
            m = mode_var.get()
            btn_arrive.config(bg=POS if m == "arrive" else BTN, fg=TXT)
            btn_leave.config( bg=NEG if m == "leave"  else BTN, fg=TXT)
            time_disp.config( fg=POS if m == "arrive" else NEG)
        mode_var.trace_add("write", refresh_mode_buttons)
        refresh_mode_buttons()

        # Summary strip at bottom of left panel
        tk.Frame(left, bg=BTN, height=1).pack(fill=tk.X, pady=(18, 6))
        summary_lbl = tk.Label(left, bg=BG, fg=TXT, font=("Arial", 9),
                               justify="left", wraplength=240)
        summary_lbl.pack(anchor="w")

        # RIGHT panel — scrollable day cards
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")

        canvas = tk.Canvas(right, bg=BG, highlightthickness=0)
        vsb    = tk.Scrollbar(right, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        cards_frame = tk.Frame(canvas, bg=BG)
        cid = canvas.create_window((0, 0), window=cards_frame, anchor="nw")
        cards_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(cid, width=e.width))

        def _on_mw(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mw)

        _last_snapshot = {}

        def compute(force=False):
            snapshot = {
                "bal":      bal_var.get(),   "goal":   self.tracker.daily_goal,
                "pause":    self.tracker.default_pause_mins,
                "credit":   self.tracker.daily_credit_mins,
                "time":     time_var.get(),  "days":   days_var.get(),
                "mode":     mode_var.get(),  "skipsat": skip_sat_var.get(),
            }
            if not force and snapshot == _last_snapshot:
                return
            _last_snapshot.clear(); _last_snapshot.update(snapshot)
            for w in cards_frame.winfo_children(): w.destroy()

            balance_s      = bal_var.get() * 600
            n_days         = snapshot["days"]
            goal_s         = snapshot["goal"] * 3600
            pause_s        = snapshot["pause"] * 60
            credit_s       = snapshot["credit"] * 60
            per_day_s      = balance_s / n_days if n_days else 0
            work_per_day_s = goal_s - per_day_s - credit_s
            total_day_s    = work_per_day_s + pause_s
            fixed_s        = snapshot["time"] * 3600
            mode           = snapshot["mode"]

            def fmt_t(secs):
                secs = secs % 86400
                return f"{int(secs//3600):02d}:{int((secs%3600)//60):02d}"

            def fmt_dur(secs):
                neg = secs < 0; s = abs(int(secs))
                return f"{'-' if neg else ''}{s//3600:02d}:{(s%3600)//60:02d}h"

            # Update summary
            adj       = "shorter" if per_day_s >= 0 else "longer"
            bal_after = balance_s - (per_day_s * n_days)
            summary_lbl.config(
                text=f"Per day:           {fmt_dur(abs(per_day_s))} {adj}\n"
                     f"Work / day:      {fmt_dur(work_per_day_s)}\n"
                     f"Balance after: {fmt_dur(bal_after)}",
                fg=POS if bal_after >= 0 else NEG)
            
            # Column header row
            hdr = tk.Frame(cards_frame, bg=BG)
            hdr.pack(fill=tk.X, padx=6, pady=(4, 0))
            cols = [("Day", BTN, 14, 8), ("Arrive", POS, 8, 4),
                    ("Leave", NEG, 9, 4), ("Work", TXT, 9, 4), ("Break", PAU, 8, 1)]
            for txt, clr, w, px in cols:
                tk.Label(hdr, text=txt, bg=BG, fg=clr,
                         font=("Arial", 8, "bold"),
                         width=w, anchor="w").pack(side="left", padx=(px, 0))
            tk.Frame(cards_frame, bg=BTN, height=1).pack(fill=tk.X, padx=6, pady=(2, 2))

            today = datetime.now().date()

            # compute needed day range due to sundays and potrentialy skipped saturdays
            target = days_var.get()
            calendar_days = []  # all days to display (including skipped ones)
            productive = 0
            offset = 1

            while productive < target:
                day = today + timedelta(days=offset)
                is_sunday   = day.weekday() == 6
                is_saturday = day.weekday() == 5
                is_skipped  = is_sunday or (is_saturday and skip_sat_var.get())
                
                calendar_days.append((day, is_skipped))
                
                if not is_skipped:
                    productive += 1
                
                offset += 1
            
            # create cards
            for day, is_skipped in calendar_days:
                is_weekend = day.weekday() >= 5

                is_sunday   = day.weekday() == 6
                is_skipped  = is_sunday or (day.weekday() == 5 and skip_sat_var.get())

                if mode == "arrive":
                    arrive_s = fixed_s
                    leave_s  = arrive_s + total_day_s
                else:
                    leave_s  = fixed_s
                    arrive_s = leave_s - total_day_s

                card_bg = "#181824" if is_weekend else "#1e1e2e"
                card    = tk.Frame(cards_frame, bg=card_bg,
                                   highlightbackground="#2a2a3e",
                                   highlightthickness=1)
                card.pack(fill=tk.X, padx=6, pady=2)

                day_fg = BTN if is_weekend else TXT
                tk.Label(card,
                         text=f"{day.strftime('%a')}  {day.strftime('%d.%m.')}",
                         bg=card_bg, fg=day_fg,
                         font=("Arial", 10, "bold"),
                         width=11, anchor="w").pack(side="left", padx=(8, 4), pady=7)

                # Data cells — dashes on Sunday, real values otherwise
                if is_skipped:
                    for clr in [POS, NEG, TXT, PAU]:
                        tk.Label(card, text="  -----", bg=card_bg, fg=BTN,
                                 font=("Arial", 10), width=8,
                                 anchor="w").pack(side="left", pady=7)
                else:
                    for val, clr in [
                        (f"  {fmt_t(arrive_s)}", POS),
                        (f"  {fmt_t(leave_s)}",  NEG),
                        (f"  {fmt_dur(work_per_day_s)}", TXT),
                        (f"  {fmt_dur(pause_s)}",        PAU),
                    ]:
                        tk.Label(card, text=val, bg=card_bg, fg=clr,
                                 font=("Arial", 10, "bold"),
                                 width=8, anchor="w").pack(side="left", pady=7)
            
            if len(calendar_days) > 10:
                vsb.pack(side="right", fill="y")
            else:
                vsb.pack_forget()

        def _on_change(*_): compute(force=True)
        bal_var.trace_add("write",  _on_change)
        time_var.trace_add("write", _on_change)
        days_var.trace_add("write", _on_change)
        mode_var.trace_add("write", _on_change)
        compute(force=True)
        self._ot_compute = compute

        def _on_close():
            self._ot_compute = None
            canvas.unbind_all("<MouseWheel>")
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", _on_close)

    def format_seconds(self, seconds):
        neg = seconds < 0
        s   = abs(int(seconds))
        return f"{'-' if neg else ''}{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

    def format_seconds_as_hhmm(self, seconds):
        """Format seconds as ±HH,MM (NovaTime-style) for the bracket hint."""
        neg = seconds < 0
        s   = abs(int(seconds))
        h   = s // 3600
        m   = (s % 3600) // 60
        return f"{'-' if neg else '+'}{h},{m:02d}"

    # ── Main update loop ──────────────────────────────────────────────────────
    def __update(self):
        # ── Row 1: Date + time ────────────────────────────────────────────────
        now_dt = datetime.now()
        self.time_display.config(
            text=now_dt.strftime("%a, %d.%m.%Y  %H:%M:%S"))
        self.update_start_button()
        self.update_pause_button_text()
        self.update_dienstgang_button_text()

        if self._ot_compute:
            try: self._ot_compute()
            except Exception: self._ot_compute = None

        if self.tracker.start_time_stamp > 0:
            now              = time.time()
            total_pause_done = self.tracker.get_total_pause_duration()
            work_elapsed     = (now - self.tracker.start_time_stamp) - total_pause_done
            extra_pause      = 15 * 60 if work_elapsed > 9 * 3600 else 0
            required_pause_s = (self.tracker.default_pause_mins * 60) + extra_pause
            pause_left       = max(0, required_pause_s - total_pause_done)
            goal_secs        = self.tracker.daily_goal * 3600
            credit_secs      = self.tracker.daily_credit_mins * 60
            effective_goal_s = goal_secs - credit_secs
            work_left_secs   = effective_goal_s - work_elapsed

            # ── Row 2: Balance — fetched Nova saldo, -1s each second ──────────
            if not self.tracker.is_in_pause:
                if self._saldo_syncing:
                    self.balance_account_label.config(
                        text="Balance:  Syncing...", fg=Color.ACCENT.value)
                elif self._nova_saldo_snapshot is not None:
                    snap_saldo, snap_time = self._nova_saldo_snapshot
                    bal = snap_saldo + (time.time() - snap_time)
                    bal_color = Color.OVERTIME.value if bal >= 0 else Color.NEGATIVE.value
                    self.balance_account_label.config(
                        text=f"Balance:  {self.format_seconds(bal)} ({self.format_seconds_as_hhmm(bal)}h)",
                        fg=bal_color)
                else:
                    bal = self.tracker.total_balance_seconds
                    bal_color = Color.OVERTIME.value if bal >= 0 else Color.NEGATIVE.value
                    self.balance_account_label.config(
                        text=f"Balance:  {self.format_seconds(bal)} ({self.format_seconds_as_hhmm(bal)}h)",
                        fg=bal_color)

            def _draw_bar(canvas, progress, color, label=""):
                canvas.delete("all")
                bw, bh = self._bar_w, self._bar_h
                canvas.create_rectangle(0, 0, bw, bh, fill=Color.BAR_EMPTY.value, outline="")
                fill_w = int(bw * min(1.0, progress))
                if fill_w > 0:
                    canvas.create_rectangle(0, 0, fill_w, bh, fill=color, outline="")
                canvas.create_text(bw // 2, bh // 2, text=label,
                                fill=Color.BAR_TEXT.value, font=("Arial", 8, "bold"))

            # Row 3: Worked label + work progress bar
            g_h = int(self.tracker.daily_goal)
            g_m = round((self.tracker.daily_goal - g_h) * 60)
            we_h = int(work_elapsed) // 3600
            we_m = (int(work_elapsed) % 3600) // 60
            we_s = int(work_elapsed) % 60
            self.worked_label.config(
                text=f"Worked:  {we_h:02d}:{we_m:02d}:{we_s:02d} / {g_h:02d}:{g_m:02d} h")

            work_progress = work_elapsed / effective_goal_s if effective_goal_s > 0 else 0
            overtime = work_elapsed > effective_goal_s
            work_bar_color = Color.OVERTIME.value if overtime else Color.ACCENT.value
            _draw_bar(self.work_bar_canvas, work_progress, work_bar_color,
                      f"Work: {min(int(work_progress*100), 100)}%{'  ✓' if work_left_secs <= 0 else ''}")

            # Row 4: Work Left / Goal Reached + pause progress bar
            if work_left_secs > 0:
                wl_h = int(work_left_secs) // 3600
                wl_m = (int(work_left_secs) % 3600) // 60
                wl_s = int(work_left_secs) % 60
                self.work_hours_left.config(
                    text=f"Work Left:  {wl_h:02d}:{wl_m:02d}:{wl_s:02d}",
                    fg=Color.TEXT.value)
            else:
                if not self._notified_work_done:
                    self._notified_work_done = True
                    self._fire_notify("✅ Goal Reached!",
                                      "You've completed your daily work goal. Great job!")
                self.work_hours_left.config(
                    text="Goal Reached! ✅", fg=Color.OVERTIME.value)

            pause_progress = total_pause_done / required_pause_s if required_pause_s > 0 else 1.0
            pause_ok       = total_pause_done >= required_pause_s
            pause_bar_col  = Color.OVERTIME.value if pause_ok else Color.PAUSE.value
            _draw_bar(self.pause_bar_canvas, pause_progress, pause_bar_col,
                      f"Break {min(int(pause_progress*100), 100)}%{'  ✓' if pause_ok else ''}")


            # ── Row 5: Target leave time ──────────────────────────────────────
            effective_pause = max(required_pause_s, total_pause_done)
            leave_ts  = self.tracker.start_time_stamp + effective_goal_s + effective_pause
            self.you_can_go_in.config(
                text=f"Leave at:  {datetime.fromtimestamp(leave_ts).strftime('%H:%M Uhr')}")

            # ── Row 6: Pause info ─────────────────────────────────────────────
            p_text = (f"Break: {self.format_seconds(total_pause_done)} / "
                      f"{self.format_seconds(required_pause_s)}")
            if pause_left > 0:
                p_text += f"  ({self.format_seconds(pause_left)} left)"
                self.pause_info.config(fg=Color.PAUSE.value)
                self._notified_pause_done = False
            else:
                p_text += "  (OK)"
                self.pause_info.config(fg=Color.OVERTIME.value)
                if self.tracker.is_in_pause and not self._notified_pause_done:
                    self._notified_pause_done = True
                    self._fire_notify("☕ Break complete",
                                      "Required break done – you can get back to work!")
            self.pause_info.config(text=p_text)

            # ── Pause warnings ────────────────────────────────────────────────
            six_hours_s   = self.tracker.break_required_after_hours * 3600
            warn_before_s = self.tracker.pause_warn_before_mins * 60
            until_6h      = six_hours_s - work_elapsed
            if (0 <= until_6h <= warn_before_s) and not self._notified_pause_warn and total_pause_done == 0:
                self._notified_pause_warn = True
                mins_left = max(1, int(math.ceil(until_6h / 60)))
                self._fire_notify(
                    "⏰ Break needed!",
                    f"You have {mins_left} Minutes left until you worked for 6 hours – "
                    f"You need a break!")
            if work_elapsed < six_hours_s - warn_before_s:
                self._notified_pause_warn = False

        else:
            # No active session
            if self._saldo_syncing:
                self.balance_account_label.config(
                    text="Balance:  Syncing...", fg=Color.ACCENT.value)
            else:
                bal       = self.tracker.total_balance_seconds
                bal_color = Color.OVERTIME.value if bal >= 0 else Color.NEGATIVE.value
                self.balance_account_label.config(
                    text=f"Balance:  {self.format_seconds(bal)}", fg=bal_color)
            self.worked_label.config(text="")
            self.work_hours_left.config(text="")
            self.you_can_go_in.config(text="")
            self.pause_info.config(text="")
            self.work_bar_canvas.delete("all")
            self.pause_bar_canvas.delete("all")

        self.master.after(1000, self.__update)

    def _launch_game(self):
        """Launch a game exe located in the same directory as this script."""
        try:
            # Use resolve() to get the absolute path
            script_dir = Path(__file__).resolve().parent
            # Find all .exe files
            # Optimization: Filter out 'python.exe' or the script's own name if compiled
            current_file = Path(__file__).name
            exes = [
                f for f in script_dir.glob("*.exe") 
                if f.name.lower() != current_file.lower()
            ]
            exes.sort()

            if not exes:
                messagebox.showinfo("Bored?", f"No executable found in:\n{script_dir}")
                return

            target_exe = exes[0]
            # Use Popen with creationflags to decouple the process 
            # (prevents the game from closing if the script is closed)
            subprocess.Popen(
                [str(target_exe)],
                cwd=str(script_dir),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        except Exception as e:
            messagebox.showerror("Launch failed", f"Error: {str(e)}")

    def on_closing(self):
        self.tracker.save_data()
        if self.tray_icon: self.tray_icon.stop()
        self.master.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _apply_theme(_load_active_theme_name())
    root = tk.Tk()
    app  = TrackMe(root)
    root.mainloop()