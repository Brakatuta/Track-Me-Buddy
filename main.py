import tkinter as tk
from tkinter import messagebox
import time
import os
import threading
from pathlib import Path
import math
from datetime import datetime, timedelta
import sys

# ── Utils integration ─────────────────────────────────────────────────────────
from Utils import Data
from Utils.Themes import THEMES, Color
from Utils.TimeUtils import fmt_hhmmss, fmt_hhmm, fmt_hhmm_nova, seconds_to_hms, parse_nova_saldo

# ── NovaTime integration ──────────────────────────────────────────────────────
from NovaTime import nova as nova

# ── extra deps ────────────────────────────────────────────────────────────────
import pystray
from PIL import Image as PilImage

from plyer import notification as plyer_notify

NOVA_AVAILABLE = True
TRAY_AVAILABLE = True
NOTIFY_AVAILABLE = True

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
        theme = Data.load_data(path)
        return theme.get("theme", "Dark Mode")
    except Exception:
        pass
    return "Dark Mode"

def _save_active_theme_name(name: str):
    try:
        path = _get_save_dir() / "theme.json"
        Data.save_data(path, {"theme": name})
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
    """Loads and saves NovaTime API settings to nova_config.json./ nova_config.lock"""

    DEFAULTS = {
        "url":                "",
        "url_journal":        "",
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
        try:
            saved = Data.load_data(self.file_path, key=True)
            if saved:
                # Merge saved values over defaults so new keys always exist
                for k, v in self.DEFAULTS.items():
                    self.data[k] = saved.get(k, v)
            else:
                print(f"[NovaConfig] No Config file found!")
        except Exception as e:
            print(f"[NovaConfig] Load error: {e}")

    def save(self):
        try:
            Data.save_data(self.file_path, self.data, key=True)
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
        self.notifications_disabled      = False
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
            "notifications_disabled":     self.notifications_disabled,
        }

        Data.save_data(self.file_path, data)

    def load_data(self):
        if os.path.exists(self.file_path):
            try:
                d = Data.load_data(self.file_path)
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
                self.notifications_disabled     = d.get("notifications_disabled", False)
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
        self.master.geometry("560x480")
        self.master.minsize(540, 480)
        self.master.resizable(True, True)
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
        if self.tracker.notifications_disabled:
            return
        threading.Thread(target=self._notify, args=(title, message), daemon=True).start()

    # ── UI ────────────────────────────────────────────────────────────────────
    # ── Tile factory ──────────────────────────────────────────────────────────
    def _make_tile(self, parent, title=""):
        """Create a rounded-corner-style tile (Frame with inner padding + title label)."""
        outer = tk.Frame(parent, bg=Color.BACKGROUND.value,
                         highlightbackground=Color.BUTTON.value,
                         highlightthickness=1)
        if title:
            tk.Label(outer, text=title, bg=Color.BACKGROUND.value,
                     fg=Color.ACCENT.value, font=("Arial", 8, "bold")).pack(
                anchor="nw", padx=8, pady=(6, 0))
        inner = tk.Frame(outer, bg=Color.BACKGROUND.value)
        inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 8))
        return outer, inner

    def _build_ui(self):
        BG  = Color.BACKGROUND.value
        FG  = Color.FOREGROUND.value
        TXT = Color.TEXT.value

        # ── Outer shell ───────────────────────────────────────────────────────
        self.main_frame = tk.Frame(self.master, bg=FG)
        self.main_frame.pack(padx=8, pady=8, fill=tk.BOTH, expand=True)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        # rows: header-bar | date tile | worked/break row | buttons
        self.main_frame.rowconfigure(2, weight=1)

        # ── Header bar ────────────────────────────────────────────────────────
        header = tk.Frame(self.main_frame, bg=FG)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 4))

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

        self.hdr_journal_btn = tk.Button(header, text="📋 Journal",
                  bg=Color.BTN_BORED_BG.value, fg=Color.BTN_BORED_FG.value,
                  activebackground=Color.BTN_BORED_BG.value, activeforeground=Color.BTN_BORED_FG.value,
                  command=self.open_journal, font=("Arial", 10, "bold"), bd=0, padx=10, relief="flat")
        self.hdr_journal_btn.pack(side="right", padx=(0, 4))

        self.hdr_theme_btn = tk.Button(header, text="🎨 Theme",
                  bg=Color.BTN_THEME_BG.value, fg=Color.BTN_THEME_FG.value,
                  activebackground=Color.BTN_THEME_BG.value, activeforeground=Color.BTN_THEME_FG.value,
                  command=self.open_theme_picker, font=("Arial", 10), bd=0, padx=10, relief="flat")
        self.hdr_theme_btn.pack(side="right", padx=(0, 4))

        # ── Row 1: Date / Time + Balance tile (full width) ────────────────────
        date_outer, date_inner = self._make_tile(self.main_frame)
        date_outer.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=(0, 4))

        # Left: date stacked above time
        dt_stack = tk.Frame(date_inner, bg=BG)
        dt_stack.pack(side="left", padx=(4, 24), pady=6)

        self.date_display = tk.Label(dt_stack, bg=BG, fg=TXT, font=("Arial", 13, "bold"))
        self.date_display.pack(anchor="w")

        self.time_display = tk.Label(dt_stack, bg=BG, fg=TXT, font=("Arial", 24, "bold"))
        self.time_display.pack(anchor="w")

        # Right: Balance
        self.balance_account_label = tk.Label(date_inner, text="",
            bg=BG, fg=Color.OVERTIME.value, font=("Arial", 18, "bold"))
        self.balance_account_label.pack(side="left", pady=6)

        # ── Row 2: 2×2 tile grid ─────────────────────────────────────────────
        grid_frame = tk.Frame(self.main_frame, bg=FG)
        grid_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=6, pady=(0, 4))
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)
        grid_frame.rowconfigure(0, weight=1)
        grid_frame.rowconfigure(1, weight=1)

        # ── Tile: Worked (top-left) ───────────────────────────────────────────
        worked_outer, worked_inner = self._make_tile(grid_frame, "⏱  WORKED")
        worked_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 3), pady=(0, 3))
        worked_inner.columnconfigure(0, weight=1)

        self.worked_label = tk.Label(worked_inner, bg=BG, fg=TXT,
                                     font=("Arial", 15, "bold"), anchor="w")
        self.worked_label.grid(row=0, column=0, sticky="ew", pady=(4, 2))

        self.work_bar_canvas = tk.Canvas(worked_inner, bg=BG, height=14,
                                         highlightthickness=0)
        self.work_bar_canvas.grid(row=1, column=0, sticky="ew", pady=(0, 4))

        self.work_hours_left = tk.Label(worked_inner, bg=BG, fg=TXT,
                                        font=("Arial", 13, "bold"), anchor="w")
        self.work_hours_left.grid(row=2, column=0, sticky="ew", pady=(0, 2))

        # ── Tile: Core Hours (top-right) ──────────────────────────────────────
        core_outer, core_inner = self._make_tile(grid_frame, "🕘  CORE HOURS")
        core_outer.grid(row=0, column=1, sticky="nsew", padx=(3, 0), pady=(0, 3))
        core_inner.columnconfigure(0, weight=1)

        # Clock-in time → projected end
        self.core_clockin_label = tk.Label(core_inner, bg=BG, fg=TXT,
                                           font=("Arial", 13, "bold"), anchor="w")
        self.core_clockin_label.grid(row=0, column=0, sticky="ew", pady=(4, 2))

        self.core_arrow_label = tk.Label(core_inner, bg=BG, fg=Color.ACCENT.value,
                                         font=("Arial", 20, "bold"), anchor="w")
        self.core_arrow_label.grid(row=1, column=0, sticky="ew", pady=(0, 2))

        self.core_sub_label = tk.Label(core_inner, bg=BG, fg=Color.BUTTON.value,
                                       font=("Arial", 9), anchor="w")
        self.core_sub_label.grid(row=2, column=0, sticky="ew", pady=(0, 4))

        # ── Tile: Break (bottom-left) ─────────────────────────────────────────
        break_outer, break_inner = self._make_tile(grid_frame, "☕  BREAK")
        break_outer.grid(row=1, column=0, sticky="nsew", padx=(0, 3), pady=(3, 0))
        break_inner.columnconfigure(0, weight=1)

        self.pause_info = tk.Label(break_inner, bg=BG, fg=Color.PAUSE.value,
                                   font=("Arial", 13, "bold"), anchor="w")
        self.pause_info.grid(row=0, column=0, sticky="ew", pady=(4, 2))

        self.pause_bar_canvas = tk.Canvas(break_inner, bg=BG, height=14,
                                          highlightthickness=0)
        self.pause_bar_canvas.grid(row=1, column=0, sticky="ew", pady=(0, 4))

        self.break_deadline_label = tk.Label(break_inner, bg=BG, fg=Color.TEXT.value,
                                             font=("Arial", 11), anchor="w")
        self.break_deadline_label.grid(row=2, column=0, sticky="ew", pady=(0, 4))

        # ── Tile: Leave (bottom-right) ────────────────────────────────────────
        leave_outer, leave_inner = self._make_tile(grid_frame, "🚪  LEAVE")
        leave_outer.grid(row=1, column=1, sticky="nsew", padx=(3, 0), pady=(3, 0))
        leave_inner.columnconfigure(0, weight=1)

        self.you_can_go_in = tk.Label(leave_inner, bg=BG, fg=Color.ACCENT.value,
                                      font=("Arial", 20, "bold"), anchor="w")
        self.you_can_go_in.grid(row=0, column=0, sticky="ew", pady=(4, 2))

        self.leave_overtime_label = tk.Label(leave_inner, bg=BG, fg=Color.OVERTIME.value,
                                             font=("Arial", 13, "bold"), anchor="w")
        self.leave_overtime_label.grid(row=1, column=0, sticky="ew", pady=(0, 2))

        self.leave_sub_label = tk.Label(leave_inner, bg=BG, fg=Color.BUTTON.value,
                                        font=("Arial", 9), anchor="w")
        self.leave_sub_label.grid(row=2, column=0, sticky="ew", pady=(0, 4))

        # ── Bar width tracking: resize canvases when tiles resize ─────────────
        self._bar_h = 14
        self._bar_w = 200  # fallback; updated dynamically

        def _on_worked_resize(event):
            self._bar_w = max(60, event.width - 4)
            self.work_bar_canvas.config(width=self._bar_w)
        def _on_break_resize(event):
            self.pause_bar_canvas.config(width=max(60, event.width - 4))

        worked_inner.bind("<Configure>", _on_worked_resize)
        break_inner.bind("<Configure>", _on_break_resize)

        # ── Button row ────────────────────────────────────────────────────────
        self.btn_frame = tk.Frame(self.main_frame, bg=FG)
        self.btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew",
                            padx=6, pady=(0, 6))

        self.main_frame.rowconfigure(3, weight=0)

        self.start_button = tk.Button(self.btn_frame, text="Clock In",
                                      bg=Color.BTN_CLOCKIN_BG.value, fg=Color.BTN_CLOCKIN_FG.value,
                                      activebackground=Color.BTN_CLOCKIN_BG.value, activeforeground=Color.BTN_CLOCKIN_FG.value,
                                      command=self.handle_start_stop, relief="flat",
                                      font=("Arial", 11, "bold"), pady=10)
        self.start_button.pack(side="left", padx=6, expand=True, fill=tk.X)

        self.dienstgang_button = tk.Button(
            self.btn_frame,
            text="🚗 Business Trip Start",
            bg=Color.BTN_TRIP_BG.value, fg=Color.BTN_TRIP_FG.value,
            activebackground=Color.BTN_TRIP_BG.value, activeforeground=Color.BTN_TRIP_FG.value,
            command=self.handle_dienstgang_click, relief="flat",
            font=("Arial", 11, "bold"), pady=10,
        )
        self.dienstgang_button.pack(side="left", padx=6, expand=True, fill=tk.X)

        self.pause_button = tk.Button(self.btn_frame, text="Break",
                                      bg=Color.BTN_PAUSE_BG.value, fg=Color.BTN_PAUSE_FG.value,
                                      activebackground=Color.BTN_PAUSE_BG.value, activeforeground=Color.BTN_PAUSE_FG.value,
                                      command=self.handle_pause_click, relief="flat",
                                      font=("Arial", 11, "bold"), pady=10)
        self.pause_button.pack(side="left", padx=6, expand=True, fill=tk.X)

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
                self._fire_notify("NovaTime ✅", "Novatime Call: Success ✅")
            except Exception as e:
                print(f"[Nova Work] {action} failed: {e}")
                self._fire_notify("NovaTime ❌", f"Novatime Call: Failed ❌\n{e}")
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
                self._fire_notify("NovaTime ✅", "Novatime Call: Success ✅")
            except Exception as e:
                print(f"[Nova Trip] {action} failed: {e}")
                self._fire_notify("NovaTime ❌", f"Novatime Call: Failed ❌\n{e}")
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
                self._fire_notify("NovaTime ✅", "Novatime Call: Success ✅")
            except Exception as e:
                print(f"[Nova Pause] {action} failed: {e}")
                self._fire_notify("NovaTime ❌", f"Novatime Call: Failed ❌\n{e}")
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
                cfg_url_journal          = cfg.url_journal,
            )
            print("[Nova] init_config() called successfully")
        except Exception as e:
            print(f"[Nova] init_config() failed: {e}")

    def _parse_nova_saldo(self, raw: str) -> float | None:
        return parse_nova_saldo(raw)

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

                messagebox.showinfo(
                    "Theme-Change", 
                    f"The Theme was changed to '{n}'.\n\n"
                    "The Application will now restart to apply the new theme."
                )

                self._restart_app()

            btn.config(command=_pick)

        tk.Frame(win, bg=BTN, height=1).pack(fill=tk.X, padx=24, pady=(14, 8))
        tk.Label(win, text="Changes apply on restart", bg=BG, fg=BTN,
                 font=("Arial", 8)).pack(pady=(0, 14))

        win.protocol("WM_DELETE_WINDOW", win.destroy)

    def _restart_app(self):
        """Startet die App neu – funktioniert als .py und als .exe."""
        import subprocess

        # reset tray icon
        try:
            if hasattr(self, 'stop_event'):
                self.stop_event.set()
            if hasattr(self, 'icon') and self.icon:
                self.icon.stop()
        except:
            pass

        # check if exe or python script
        if getattr(sys, 'frozen', False):
            executable = sys.executable
            args = sys.argv[1:]
        else:
            executable = sys.executable
            args = [sys.argv[0]] + sys.argv[1:]

        # start new process
        subprocess.Popen([executable] + args, shell=False)
        
        # stop current
        self.master.destroy()
        os._exit(0)

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

        url_var         = field_row(win, "NovaTime URL",              self.nova_cfg.url)
        url_journal_var = field_row(win, "NovaTime User Journal URL", self.nova_cfg.url_journal)
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
            self.nova_cfg.url_journal         = url_journal_var.get().strip()
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
                    self._fire_notify("NovaTime ✅", "Novatime Call: Success ✅")
                except Exception as e:
                    print(f"[API Test] Error: {e}")
                    win.after(0, lambda err=e: _set_test_status(False, f"✗ {err}"))
                    self._fire_notify("NovaTime ❌", f"Novatime Call: Failed ❌\n{e}")
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

        # ── Disable Notifications toggle ──────────────────────────────────────
        notif_var = tk.BooleanVar(value=self.tracker.notifications_disabled)

        def _toggle_notif():
            self.tracker.notifications_disabled = notif_var.get()
            self.tracker.save_data()

        notif_row = tk.Frame(extras_inner, bg=Color.BACKGROUND.value)
        notif_row.pack(anchor="w", padx=26, pady=(10, 4))
        tk.Checkbutton(
            notif_row,
            text="Disable Notifications",
            variable=notif_var,
            command=_toggle_notif,
            bg=Color.BACKGROUND.value,
            fg=Color.TEXT.value,
            selectcolor=Color.BUTTON.value,
            activebackground=Color.BACKGROUND.value,
            activeforeground=Color.TEXT.value,
            font=("Arial", 9),
            bd=0,
        ).pack(side="left")

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
        return fmt_hhmmss(seconds)

    def format_seconds_as_hhmm(self, seconds):
        return fmt_hhmm_nova(seconds)

    # ── Main update loop ──────────────────────────────────────────────────────
    def __update(self):
        # ── Date tile ─────────────────────────────────────────────────────────
        now_dt = datetime.now()
        self.date_display.config(text=now_dt.strftime("%a, %d.%m.%Y"))
        self.time_display.config(text=now_dt.strftime("%H:%M:%S"))
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

            # ── Balance (date tile) ───────────────────────────────────────────
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
                canvas.update_idletasks()
                bw = canvas.winfo_width() or self._bar_w
                bh = self._bar_h
                canvas.delete("all")
                canvas.create_rectangle(0, 0, bw, bh, fill=Color.BAR_EMPTY.value, outline="")
                fill_w = int(bw * min(1.0, progress))
                if fill_w > 0:
                    canvas.create_rectangle(0, 0, fill_w, bh, fill=color, outline="")
                canvas.create_text(bw // 2, bh // 2, text=label,
                                fill=Color.BAR_TEXT.value, font=("Arial", 8, "bold"))

            # ── Worked tile ───────────────────────────────────────────────────
            g_h, g_m, _ = seconds_to_hms(self.tracker.daily_goal * 3600)
            we_h, we_m, we_s = seconds_to_hms(work_elapsed)
            self.worked_label.config(
                text=f"{we_h:02d}:{we_m:02d}:{we_s:02d}  /  {g_h:02d}:{g_m:02d} h")

            work_progress  = work_elapsed / effective_goal_s if effective_goal_s > 0 else 0
            overtime       = work_elapsed > effective_goal_s
            work_bar_color = Color.OVERTIME.value if overtime else Color.ACCENT.value
            _draw_bar(self.work_bar_canvas, work_progress, work_bar_color,
                      f"Work: {min(int(work_progress*100), 100)}%{'  ✓' if work_left_secs <= 0 else ''}")

            if work_left_secs > 0:
                wl_h, wl_m, wl_s = seconds_to_hms(work_left_secs)
                self.work_hours_left.config(
                    text=f"Left:  {wl_h:02d}:{wl_m:02d}:{wl_s:02d}",
                    fg=Color.TEXT.value)
            else:
                if not self._notified_work_done:
                    self._notified_work_done = True
                    self._fire_notify("✅ Goal Reached!",
                                      "You've completed your daily work goal. Great job!")
                self.work_hours_left.config(
                    text="Goal Reached! ✅", fg=Color.OVERTIME.value)

            # ── Core Hours tile ───────────────────────────────────────────────
            clock_in_dt  = datetime.fromtimestamp(self.tracker.start_time_stamp)
            clock_in_str = clock_in_dt.strftime("%H:%M")
            effective_pause = max(required_pause_s, total_pause_done)
            leave_ts        = self.tracker.start_time_stamp + effective_goal_s + effective_pause
            leave_str       = datetime.fromtimestamp(leave_ts).strftime("%H:%M")

            # Overtime now vs raw daily goal
            ot_at_leave = work_elapsed - goal_secs
            ot_sign     = "+" if ot_at_leave >= 0 else "-"
            ot_h, ot_m, _ = seconds_to_hms(ot_at_leave)

            # Projected total balance at leave time
            if self._nova_saldo_snapshot is not None:
                snap_saldo, snap_time = self._nova_saldo_snapshot
                saldo_at_leave = snap_saldo + (leave_ts - effective_pause + credit_secs) - snap_time
            else:
                saldo_at_leave = None

            self.core_clockin_label.config(
                text=f"Clocked in at  {clock_in_str}")
            self.core_arrow_label.config(
                text=f"{clock_in_str}  →  {leave_str}")
            self.core_sub_label.config(
                text=f"Goal {g_h:02d}:{g_m:02d} h  ·  Leave at {leave_str}")

            # ── Break tile ────────────────────────────────────────────────────
            pause_progress = total_pause_done / required_pause_s if required_pause_s > 0 else 1.0
            pause_ok       = total_pause_done >= required_pause_s
            pause_bar_col  = Color.OVERTIME.value if pause_ok else Color.PAUSE.value
            _draw_bar(self.pause_bar_canvas, pause_progress, pause_bar_col,
                      f"Break {min(int(pause_progress*100), 100)}%{'  ✓' if pause_ok else ''}")

            p_done_h, p_done_m, p_done_s = seconds_to_hms(total_pause_done)
            p_req_h,  p_req_m,  _        = seconds_to_hms(required_pause_s)

            if pause_left > 0:
                pl_h, pl_m, pl_s = seconds_to_hms(pause_left)
                self.pause_info.config(
                    text=f"{p_done_h:02d}:{p_done_m:02d}:{p_done_s:02d}  /  "
                         f"{p_req_h:02d}:{p_req_m:02d} h",
                    fg=Color.PAUSE.value)
                self.break_deadline_label.config(
                    text=f"⏳ {pl_h:02d}:{pl_m:02d}:{pl_s:02d} left")
                self._notified_pause_done = False
            else:
                self.pause_info.config(
                    text=f"{p_done_h:02d}:{p_done_m:02d}:{p_done_s:02d}  /  "
                         f"{p_req_h:02d}:{p_req_m:02d} h  ✓",
                    fg=Color.OVERTIME.value)
                self.break_deadline_label.config(text="Break complete ✅")
                if self.tracker.is_in_pause and not self._notified_pause_done:
                    self._notified_pause_done = True
                    self._fire_notify("☕ Break complete",
                                      "Required break done – you can get back to work!")

            # Break-warning deadline (e.g. "Break by 13:30")
            pause_warn_after_hours_s      = self.tracker.break_required_after_hours * 3600
            warn_before_s                 = self.tracker.pause_warn_before_mins * 60
            deadline_ts                   = self.tracker.start_time_stamp + pause_warn_after_hours_s + total_pause_done
            deadline_str                  = datetime.fromtimestamp(deadline_ts).strftime("%H:%M")
            until_warn_after_hours_s      = pause_warn_after_hours_s - work_elapsed
            if total_pause_done == 0 and until_warn_after_hours_s > 0:
                self.break_deadline_label.config(
                    text=f"⏰ Break by  {deadline_str}")
            if (0 <= until_warn_after_hours_s <= warn_before_s) and not self._notified_pause_warn and total_pause_done == 0:
                self._notified_pause_warn = True
                mins_left = max(1, int(math.ceil(until_warn_after_hours_s / 60)))
                self._fire_notify(
                    "⏰ Break needed!",
                    f"You have {mins_left} Minutes left until you worked for 6 hours – "
                    f"You need a break!")
            if work_elapsed < pause_warn_after_hours_s - warn_before_s:
                self._notified_pause_warn = False

            # ── Leave tile ────────────────────────────────────────────────────
            self.you_can_go_in.config(text=f"Leave at  {leave_str}")

            ot_color = Color.OVERTIME.value if ot_at_leave >= 0 else Color.NEGATIVE.value
            self.leave_overtime_label.config(
                text=f"Today:  {ot_sign}{ot_h:02d}:{ot_m:02d} h",
                fg=ot_color)

            if saldo_at_leave is not None:
                sal_h, sal_m, _ = seconds_to_hms(saldo_at_leave)
                sal_sign  = "+" if saldo_at_leave >= 0 else "-"
                sal_color = Color.OVERTIME.value if saldo_at_leave >= 0 else Color.NEGATIVE.value
                self.leave_sub_label.config(
                    text=f"Balance at leave:  {sal_sign}{sal_h:02d}:{sal_m:02d} h",
                    fg=sal_color)
            else:
                self.leave_sub_label.config(
                    text=f"Clocked in  {clock_in_str}  ·  Goal {g_h:02d}:{g_m:02d} h",
                    fg=Color.BUTTON.value)

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
            self.worked_label.config(text="—")
            self.work_hours_left.config(text="")
            self.you_can_go_in.config(text="—")
            self.leave_overtime_label.config(text="")
            self.leave_sub_label.config(text="")
            self.pause_info.config(text="—")
            self.break_deadline_label.config(text="")
            self.core_clockin_label.config(text="Not clocked in")
            self.core_arrow_label.config(text="—")
            self.core_sub_label.config(text="")
            self.work_bar_canvas.delete("all")
            self.pause_bar_canvas.delete("all")

        self.master.after(1000, self.__update)

    def open_journal(self):
        """Fetch and display the journal in a scrollable table window."""
        if not NOVA_AVAILABLE or not self.nova_cfg.url_journal:
            messagebox.showwarning("Journal", "Nova API is not configured.\nPlease set up the API settings first.")
            return

        # ── Create the journal window ─────────────────────────────────────────
        win = tk.Toplevel(self.master)
        win.title("📋 User Journel")
        win.config(bg=Color.BACKGROUND.value)
        win.resizable(True, True)
        win.withdraw()
        if os.path.exists(self.icon_ico):
            try: win.iconbitmap(self.icon_ico)
            except Exception: pass

        BG  = Color.BACKGROUND.value
        FG  = Color.FOREGROUND.value
        TXT = Color.TEXT.value
        ACC = Color.ACCENT.value

        # ── Header bar ────────────────────────────────────────────────────────
        hdr_frame = tk.Frame(win, bg=FG, pady=8)
        hdr_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        self._journal_title_lbl = tk.Label(
            hdr_frame, text="Loading journal…", bg=FG, fg=ACC,
            font=("Arial", 13, "bold"))
        self._journal_title_lbl.pack(side="left", padx=12)

        refresh_btn = tk.Button(
            hdr_frame, text="🔄 Refresh",
            bg=Color.BTN_API_BG.value, fg=Color.BTN_API_FG.value,
            activebackground=Color.BTN_API_BG.value, activeforeground=Color.BTN_API_FG.value,
            font=("Arial", 10), bd=0, padx=10, relief="flat")
        refresh_btn.pack(side="right", padx=8)

        # ── Scrollable table area ─────────────────────────────────────────────
        table_outer = tk.Frame(win, bg=BG)
        table_outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # Canvas + scrollbars for the table
        h_scroll = tk.Scrollbar(table_outer, orient=tk.HORIZONTAL)
        v_scroll = tk.Scrollbar(table_outer, orient=tk.VERTICAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll.pack(side=tk.RIGHT,  fill=tk.Y)

        canvas = tk.Canvas(table_outer, bg=BG,
                           xscrollcommand=h_scroll.set,
                           yscrollcommand=v_scroll.set,
                           highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        h_scroll.config(command=canvas.xview)
        v_scroll.config(command=canvas.yview)

        # Inner frame that holds the actual grid of labels
        self._journal_inner = tk.Frame(canvas, bg=BG)
        canvas_window = canvas.create_window((0, 0), window=self._journal_inner, anchor="nw")

        def _on_inner_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        self._journal_inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse-wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # ── Status label shown while loading ─────────────────────────────────
        self._journal_status_lbl = tk.Label(
            self._journal_inner, text="⏳ Fetching journal…",
            bg=BG, fg=ACC, font=("Arial", 12))
        self._journal_status_lbl.grid(row=0, column=0, padx=20, pady=20)

        # ── Columns to display ────────────────────────────────────────────────
        SHOW_COLS = [
            "Wt", "Datum", "Uhr von", "Zeit bis", "Bu art",
            "Ist Std", "Soll Std", "Pause",
            "Tages Saldo", "Gesamt Saldo",
            "Kommentar", "Bemerkungstext",
        ]

        def _render_table(result: dict):
            """Called from the main thread once the journal data arrives."""
            meta    = result.get("meta",    {})
            header  = result.get("header",  [])
            rows    = result.get("rows",    [])
            summary = result.get("summary", [])

            # Update title label
            name   = meta.get("name",  "")
            persnr = meta.get("persnr","")
            month  = meta.get("month", "")
            title_text = f"{name}  │  PersNr {persnr}  │  {month}  │  {len(rows)} Zeilen"
            self._journal_title_lbl.config(text=title_text)

            # Pick columns
            cols = [c for c in SHOW_COLS if c in header]
            if not cols:
                cols = header

            # Clear inner frame
            for widget in self._journal_inner.winfo_children():
                widget.destroy()

            # ── Column header row ─────────────────────────────────────────────
            HDR_BG  = Color.FOREGROUND.value
            HDR_FG  = Color.ACCENT.value
            ROW_BG  = Color.BACKGROUND.value
            ALT_BG  = Color.FOREGROUND.value
            ROW_FG  = Color.TEXT.value
            SEP_COL = Color.BUTTON.value

            for c_idx, col in enumerate(cols):
                lbl = tk.Label(
                    self._journal_inner, text=col,
                    bg=HDR_BG, fg=HDR_FG, font=("Arial", 9, "bold"),
                    padx=8, pady=5, anchor="w",
                    relief="flat", bd=0)
                lbl.grid(row=0, column=c_idx, sticky="nsew", padx=(0, 1), pady=(0, 1))

            # ── Data rows ─────────────────────────────────────────────────────
            row_num = 1
            for row in rows:
                # Skip completely empty rows
                if not any(str(row.get(c, "")).strip() for c in cols):
                    continue

                bg = ALT_BG if row_num % 2 == 0 else ROW_BG

                # Highlight today
                datum = row.get("Datum", "").strip()
                today_str = datetime.now().strftime("%d.%m.%Y")
                if datum == today_str:
                    bg = "#1a3a1a" if "Dark" in _load_active_theme_name() else "#2a4a2a"

                for c_idx, col in enumerate(cols):
                    val = str(row.get(col, "")).strip()

                    # Colour Tages Saldo / Gesamt Saldo values
                    fg = ROW_FG
                    if col in ("Tages Saldo", "Gesamt Saldo") and val:
                        try:
                            numeric = float(val.replace(",", ".").replace("+", ""))
                            fg = Color.OVERTIME.value if numeric >= 0 else Color.NEGATIVE.value
                        except ValueError:
                            pass

                    lbl = tk.Label(
                        self._journal_inner, text=val,
                        bg=bg, fg=fg, font=("Arial", 9),
                        padx=8, pady=4, anchor="w",
                        relief="flat", bd=0)
                    lbl.grid(row=row_num, column=c_idx, sticky="nsew", padx=(0, 1), pady=(0, 1))

                row_num += 1

            # ── Summary rows ──────────────────────────────────────────────────
            if summary:
                # Separator
                sep = tk.Frame(self._journal_inner, bg=Color.ACCENT.value, height=2)
                sep.grid(row=row_num, column=0, columnspan=len(cols),
                         sticky="ew", pady=(6, 2))
                row_num += 1

                for s in summary:
                    # Render summary as a single merged label spanning all columns
                    text = "   │   ".join(f"{k}: {v}" for k, v in s.items() if str(v).strip())
                    lbl = tk.Label(
                        self._journal_inner, text=text,
                        bg=Color.FOREGROUND.value, fg=Color.ACCENT.value,
                        font=("Arial", 9, "bold"),
                        padx=8, pady=4, anchor="w",
                        relief="flat", bd=0)
                    lbl.grid(row=row_num, column=0, columnspan=len(cols),
                             sticky="ew", padx=(0, 1), pady=(0, 1))
                    row_num += 1

            # Make all columns expand equally
            for c_idx in range(len(cols)):
                self._journal_inner.columnconfigure(c_idx, weight=1)

        def _fetch_and_render():
            """Background thread: fetch journal, then schedule render on main thread."""
            try:
                result = nova.run_nova_action("journal")
                win.after(0, lambda: _render_table(result))
            except Exception as e:
                err_msg = str(e)
                def _show_error():
                    for w in self._journal_inner.winfo_children():
                        w.destroy()
                    tk.Label(
                        self._journal_inner,
                        text=f"❌ Error fetching journal:\n{err_msg}",
                        bg=Color.BACKGROUND.value, fg=Color.NEGATIVE.value,
                        font=("Arial", 11), padx=20, pady=20, justify="left"
                    ).grid(row=0, column=0)
                    self._journal_title_lbl.config(text="Journal — fetch failed")
                win.after(0, _show_error)

        def _do_refresh():
            # Clear table and show loading state again
            for w in self._journal_inner.winfo_children():
                w.destroy()
            self._journal_status_lbl = tk.Label(
                self._journal_inner, text="⏳ Fetching journal…",
                bg=Color.BACKGROUND.value, fg=Color.ACCENT.value,
                font=("Arial", 12))
            self._journal_status_lbl.grid(row=0, column=0, padx=20, pady=20)
            self._journal_title_lbl.config(text="Loading journal…")
            threading.Thread(target=_fetch_and_render, daemon=True).start()

        refresh_btn.config(command=_do_refresh)

        # ── Size & position ───────────────────────────────────────────────────
        win.geometry("1000x540")
        self.master.update_idletasks()
        mx  = self.master.winfo_x()
        my  = self.master.winfo_y()
        mw  = self.master.winfo_width()
        mh  = self.master.winfo_height()
        x   = mx + (mw - 1000) // 2
        y   = my - 560
        scr_h = self.master.winfo_screenheight()
        scr_w = self.master.winfo_screenwidth()
        x = max(0, min(x, scr_w - 1000 - 8))
        y = max(0, min(y, scr_h - 540 - 8))
        win.geometry(f"1000x540+{x}+{y}")
        win.deiconify()

        # ── Start fetching ────────────────────────────────────────────────────
        threading.Thread(target=_fetch_and_render, daemon=True).start()

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