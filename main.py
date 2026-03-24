import tkinter as tk
from tkinter import messagebox
import time
import json
import os
import threading
import subprocess
import math
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum
import sys
import re

# ── NovaTime integration ──────────────────────────────────────────────────────
try:
    from NovaTime import nova
    NOVA_AVAILABLE = True
except ImportError:
    nova = None
    NOVA_AVAILABLE = False

# ── Extra deps ────────────────────────────────────────────────────────────────
try:
    import pystray
    from PIL import Image as PilImage
    TRAY_AVAILABLE = True
except ImportError:
    pystray = None
    PilImage = None
    TRAY_AVAILABLE = False

try:
    from plyer import notification as plyer_notify
    NOTIFY_AVAILABLE = True
except ImportError:
    plyer_notify = None
    NOTIFY_AVAILABLE = False

try:
    from PIL import ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ── Spacing constants ─────────────────────────────────────────────────────────
PAD_SM  = 4
PAD_MD  = 10
PAD_LG  = 18

# ── Colours ───────────────────────────────────────────────────────────────────
class C(Enum):
    BACKGROUND = "#1a1a2e"
    SURFACE    = "#16213e"
    CARD       = "#0f3460"
    BUTTON     = "#4a4a6a"
    TEXT       = "#e0e0e0"
    SUBTEXT    = "#888aaa"
    PAUSE      = "#ff9800"
    OVERTIME   = "#4caf50"
    NEGATIVE   = "#f44336"
    STOP       = "#c62828"
    ACCENT     = "#5b9bd5"
    API        = "#2e86ab"
    DIVIDER    = "#2a2a4a"
    WARN       = "#e6b800"


class _Tooltip:
    def __init__(self, widget, text):
        self._w = widget; self._t = text; self._tip = None
        widget.bind("<Enter>", self._show); widget.bind("<Leave>", self._hide)
    def _show(self, e=None):
        x = self._w.winfo_rootx() + self._w.winfo_width()//2
        y = self._w.winfo_rooty() + self._w.winfo_height() + 4
        self._tip = tk.Toplevel(self._w)
        self._tip.overrideredirect(True); self._tip.attributes("-topmost", True)
        tk.Label(self._tip, text=self._t, bg="#2a2a4a", fg="#e0e0e0",
                 font=("Segoe UI", 9), padx=6, pady=3).pack()
        self._tip.geometry(f"+{x}+{y}")
    def _hide(self, e=None):
        if self._tip: self._tip.destroy(); self._tip = None

def _floor_minute(ts: float) -> float:
    """Floor Unix timestamp to the nearest full minute (Novatime records in minute intervals)."""
    return math.floor(ts / 60) * 60

# ── Base / save dirs ──────────────────────────────────────────────────────────
def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def _get_save_dir() -> Path:
    d = _get_base_dir() / "save"
    d.mkdir(exist_ok=True)
    return d

# ── NovaConfig ────────────────────────────────────────────────────────────────
class NovaConfig:
    DEFAULTS = {
        "url": "", "username": "", "password": "",
        "proxy_auth_username": "", "proxy_auth_password": "",
        "show_window": True,
    }

    def __init__(self):
        self.file_path = str(_get_save_dir() / "nova_config.json")
        self.data = dict(self.DEFAULTS)
        self.load()

    def load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path) as f:
                    saved = json.load(f)
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

# ── Tracker ───────────────────────────────────────────────────────────────────
class Tracker:
    def __init__(self):
        self.file_path = str(_get_save_dir() / "data.json")
        self.reset_values()
        self.daily_goal                  = 8.0
        self.default_pause_mins          = 30.0
        self.min_legal_pause_mins        = 30.0
        self.total_balance_seconds       = 0.0
        self.daily_credit_mins           = 0.0
        self.pause_warn_before_mins      = 15.0
        self.legal_work_limit_h          = 6.0
        self.legal_work_limit_2_h        = 9.0
        self.min_legal_pause_2_mins      = 45.0
        # Core work hours (Kernarbeitszeit): start/end as decimal hours
        self.core_start_h                = 9.0    # 09:00
        self.core_end_h                  = 15.0   # 15:00
        self.load_data()

    def reset_values(self):
        self.start_time_stamp = 0
        self.is_in_pause      = False
        self.pauses           = []
        self.is_on_dienstgang = False
        self.last_reset_date  = datetime.now().strftime("%Y-%m-%d")

    def start_tracking(self):
        if self.start_time_stamp == 0:
            self.start_time_stamp = _floor_minute(time.time())

    def stop_tracking(self):
        self.end_open_pause()
        self.reset_values()

    def toggle_pause(self):
        if not self.start_time_stamp:
            return
        now_floored = _floor_minute(time.time())
        if not self.is_in_pause:
            self.pauses.append([now_floored, None])
            self.is_in_pause = True
        else:
            if self.pauses and self.pauses[-1][1] is None:
                self.pauses[-1][1] = now_floored
            self.is_in_pause = False

    def toggle_dienstgang(self):
        self.is_on_dienstgang = not self.is_on_dienstgang

    def end_open_pause(self):
        if self.is_in_pause and self.pauses and self.pauses[-1][1] is None:
            self.pauses[-1][1] = _floor_minute(time.time())
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
        try:
            self._save_data_impl()
        except Exception as e:
            print(f"[Tracker] Save error: {e}")

    def _save_data_impl(self):
        data = {
            "start_time_stamp":       self.start_time_stamp,
            "is_in_pause":            self.is_in_pause,
            "pauses":                 self.pauses,
            "daily_goal":             self.daily_goal,
            "default_pause_mins":     self.default_pause_mins,
            "min_legal_pause_mins":   self.min_legal_pause_mins,
            "total_balance_seconds":  self.total_balance_seconds,
            "last_reset_date":        self.last_reset_date,
            "daily_credit_mins":      self.daily_credit_mins,
            "pause_warn_before_mins": self.pause_warn_before_mins,
            "is_on_dienstgang":       self.is_on_dienstgang,
            "core_start_h":           self.core_start_h,
            "core_end_h":             self.core_end_h,
            "legal_work_limit_h":     self.legal_work_limit_h,
            "legal_work_limit_2_h":   self.legal_work_limit_2_h,
            "min_legal_pause_2_mins": self.min_legal_pause_2_mins,
        }
        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=4)

    def load_data(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path) as f:
                    d = json.load(f)
                self.start_time_stamp       = d.get("start_time_stamp", 0)
                self.is_in_pause            = d.get("is_in_pause", False)
                self.pauses                 = d.get("pauses", [])
                self.daily_goal             = d.get("daily_goal", 8.0)
                self.default_pause_mins     = d.get("default_pause_mins", 30.0)
                self.min_legal_pause_mins   = d.get("min_legal_pause_mins", 30.0)
                self.total_balance_seconds  = d.get("total_balance_seconds",
                                              d.get("total_overtime_seconds", 0.0))
                self.last_reset_date        = d.get("last_reset_date",
                                              datetime.now().strftime("%Y-%m-%d"))
                self.daily_credit_mins      = d.get("daily_credit_mins", 0.0)
                self.pause_warn_before_mins = d.get("pause_warn_before_mins", 15.0)
                self.is_on_dienstgang       = d.get("is_on_dienstgang", False)
                self.core_start_h           = d.get("core_start_h", 9.0)
                self.core_end_h             = d.get("core_end_h", 15.0)
                self.legal_work_limit_h     = d.get("legal_work_limit_h", 6.0)
                self.legal_work_limit_2_h   = d.get("legal_work_limit_2_h", 9.0)
                self.min_legal_pause_2_mins = d.get("min_legal_pause_2_mins", 45.0)
            except Exception as e:
                print(f"[Tracker] Load error: {e}")

# ── UI helpers ────────────────────────────────────────────────────────────────
def _divider(parent, padx=PAD_MD, pady=PAD_SM):
    tk.Frame(parent, bg=C.DIVIDER.value, height=1).pack(fill=tk.X, padx=padx, pady=pady)

def _card(parent, **kw):
    return tk.Frame(parent, bg=C.CARD.value,
                    highlightbackground=C.DIVIDER.value, highlightthickness=1, **kw)

def _btn(parent, text, color, fg=None, command=None, width=14, pady=8):
    return tk.Button(parent, text=text,
                     bg=color, fg=fg or C.TEXT.value,
                     font=("Segoe UI", 10, "bold"),
                     relief="flat", bd=0,
                     padx=PAD_MD, pady=pady,
                     width=width,
                     activebackground=color,
                     activeforeground=fg or C.TEXT.value,
                     highlightthickness=0,
                     cursor="hand2",
                     command=command)

def _fmt_hm(decimal_hours):
    h = int(decimal_hours); m = round((decimal_hours - h) * 60)
    if m == 60:
        h += 1; m = 0
    return f"{h:02d}:{m:02d}"

# ── Main application ──────────────────────────────────────────────────────────
class TrackMe:
    def __init__(self, master):
        self.master   = master
        self.tracker  = Tracker()
        self.nova_cfg = NovaConfig()

        self._notified_work_done   = False
        self._notified_pause_done  = False
        self._notified_pause_warn  = False
        self._auto_pause_booked    = False
        self._auto_pause_entry     = None
        self._auto_pause_9h_booked = False   # live open pause entry for auto-book
        self._ot_compute           = None
        self._nova_saldo_snapshot  = None
        self._saldo_syncing        = False

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

    # ── Window ────────────────────────────────────────────────────────────────
    def _setup_window(self):
        self.master.title("Track Me Buddy")
        self.master.config(bg=C.BACKGROUND.value)
        self.master.geometry("520x580")
        self.master.minsize(440, 500)
        self.master.resizable(True, True)
        if os.path.exists(self.icon_ico):
            try:
                self.master.iconbitmap(self.icon_ico)
            except Exception:
                pass
        elif os.path.exists(self.icon_png) and PIL_AVAILABLE:
            try:
                img = PilImage.open(self.icon_png).resize((32, 32))
                self._tk_icon = ImageTk.PhotoImage(img)
                self.master.iconphoto(True, self._tk_icon)
            except Exception:
                pass

    # ── Tray ──────────────────────────────────────────────────────────────────
    def _load_tray_image(self):
        for path in (self.icon_png, self.icon_ico):
            if os.path.exists(path):
                try:
                    return PilImage.open(path).resize((64, 64)).convert("RGBA")
                except Exception:
                    pass
        return PilImage.new("RGBA", (64, 64), color=(91, 155, 213, 255))

    def _run_tray(self):
        img  = self._load_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("Open Track Me Buddy", self._tray_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Clock In / Clock Out", self._tray_start_work),
            pystray.MenuItem("Break / Resume",       self._tray_toggle_pause),
            pystray.MenuItem("Dienstgang",           self._tray_toggle_dienstgang),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._tray_quit),
        )
        self.tray_icon = pystray.Icon("TrackMeBuddy", img, "Track Me Buddy", menu)
        self.tray_icon.run()

    def _tray_open(self, *_):              self.master.after(0, self.show_window_near_tray)
    def _tray_start_work(self, *_):        self.master.after(0, self._tray_start_work_main)
    def _tray_toggle_pause(self, *_):      self.master.after(0, self._do_toggle_pause)
    def _tray_toggle_dienstgang(self, *_): self.master.after(0, self._do_toggle_dienstgang)
    def _tray_quit(self, *_):              self.master.after(0, self._do_quit)

    def _tray_start_work_main(self):
        if self.tracker.start_time_stamp == 0:
            self.tracker.start_tracking()
            self._notified_work_done = self._notified_pause_done = self._notified_pause_warn = self._auto_pause_booked = False
            self._auto_pause_entry     = None
            self._auto_pause_9h_booked = False
            self.tracker.save_data()
            self._nova_work_async("start_work")
            self._nova_saldo_snapshot = None
            self._saldo_syncing = False
            self._sync_saldo_from_nova(delay_ms=5000)
            self._refresh_clock_button()

    def _do_toggle_pause(self):
        self.tracker.toggle_pause()
        self._refresh_action_buttons()
        self.tracker.save_data()
        self._nova_pause_async()

    def _do_toggle_dienstgang(self):
        self.tracker.toggle_dienstgang()
        self._refresh_action_buttons()
        self.tracker.save_data()
        self._nova_trip_async()

    def _do_quit(self):
        self.tracker.save_data()
        if self.tray_icon:
            self.tray_icon.stop()
        self.master.destroy()

    # ── Window positioning ────────────────────────────────────────────────────
    def _sync_on_restore(self):
        self._sync_saldo_from_nova()

    def show_window_near_tray(self):
        self.master.deiconify()
        self.master.update_idletasks()
        ww, wh = self.master.winfo_width(), self.master.winfo_height()
        sw, sh = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        x, y = sw - ww - 12, sh - wh - 90 - 12
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
        # Prefer pystray's built-in notify — reuses the existing tray icon,
        # so no duplicate icons appear in the taskbar.
        if TRAY_AVAILABLE and self.tray_icon:
            try:
                self.tray_icon.notify(message, title)
                return
            except Exception:
                pass
        # Fallback: plyer (may create a second tray icon on Windows)
        if not NOTIFY_AVAILABLE:
            return
        ico = self.icon_ico if os.path.exists(self.icon_ico) else None
        try:
            plyer_notify.notify(title=title, message=message,
                                app_name="Track Me Buddy", app_icon=ico, timeout=8)
        except Exception as e:
            print(f"[Notify] {e}")

    def _fire_notify(self, title, message):
        threading.Thread(target=self._notify, args=(title, message), daemon=True).start()

    # ── UI build ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header bar ────────────────────────────────────────────────────────
        header = tk.Frame(self.master, bg=C.SURFACE.value,
                          highlightbackground=C.DIVIDER.value, highlightthickness=1)
        header.pack(fill=tk.X)

        _lbl = tk.Label(header, text="Track Me Buddy", bg=C.SURFACE.value,
                        fg=C.ACCENT.value, font=("Segoe UI", 12, "bold"))
        _lbl.pack(side="left", padx=PAD_LG, pady=PAD_MD)

        # Header buttons right-to-left: ⚙ API 🧮 ◑ 🎮
        for txt, cmd, col, fg, tip in [
            ("⚙",  self.open_settings,      C.BUTTON.value,  C.TEXT.value,    "Settings"),
            ("🔌",  self.open_api_settings,  C.API.value,     "#ffffff",        "API Settings"),
            ("🧮",  self.open_simulator,     C.API.value,     "#ffffff",        "What-if Planner"),
            ("◑",  self.open_auto_overtime, C.ACCENT.value,  "#ffffff",        "AutoOvertime Planner"),
            ("🎮", self._launch_game,        C.WARN.value,    "#1a1a2e",        "Bored? Launch Game"),
        ]:
            b = _btn(header, txt, col, fg=fg, command=cmd, width=3, pady=PAD_SM)
            b.pack(side="right", padx=(0, PAD_SM), pady=PAD_SM)
            _Tooltip(b, tip)

        # ── Body ──────────────────────────────────────────────────────────────────
        body = tk.Frame(self.master, bg=C.BACKGROUND.value)
        body.pack(fill=tk.BOTH, expand=True)

        # ── Clock card ────────────────────────────────────────────────────────
        clock_card = _card(body)
        clock_card.pack(fill=tk.X, padx=PAD_MD, pady=(PAD_MD, PAD_SM))
        clock_card.columnconfigure(0, weight=1)

        self.time_display = tk.Label(clock_card, text="",
                                     bg=C.CARD.value, fg=C.TEXT.value,
                                     font=("Segoe UI", 18, "bold"), anchor="w")
        self.time_display.pack(fill=tk.X, padx=PAD_LG, pady=(PAD_MD, 2))

        self.balance_account_label = tk.Label(clock_card, text="",
                                              bg=C.CARD.value, fg=C.OVERTIME.value,
                                              font=("Segoe UI", 12, "bold"), anchor="w")
        self.balance_account_label.pack(fill=tk.X, padx=PAD_LG, pady=(0, PAD_MD))

        # ── Grid container for responsive 2-col layout ───────────────────────
        grid = tk.Frame(body, bg=C.BACKGROUND.value)
        grid.pack(fill=tk.BOTH, expand=True, padx=PAD_MD)
        grid.columnconfigure(0, weight=1, uniform="col")
        grid.columnconfigure(1, weight=1, uniform="col")

        # ── Work progress card ────────────────────────────────────────────────
        work_card = _card(grid)

        # Work card – main label full width, secondary below
        self.worked_label = tk.Label(work_card, text="", bg=C.CARD.value,
                                     fg=C.TEXT.value, font=("Segoe UI", 14, "bold"),
                                     anchor="w")
        self.worked_label.pack(fill=tk.X, padx=PAD_LG, pady=(PAD_MD, 0))

        self.work_hours_left = tk.Label(work_card, text="", bg=C.CARD.value,
                                        fg=C.SUBTEXT.value, font=("Segoe UI", 10),
                                        anchor="w")
        self.work_hours_left.pack(fill=tk.X, padx=PAD_LG, pady=(0, PAD_SM))

        self._bar_h  = 18
        self._tick_h = 6
        self.work_bar_canvas = tk.Canvas(work_card, bg=C.SURFACE.value,
                                         height=self._bar_h, highlightthickness=0)
        self.work_bar_canvas.pack(fill=tk.X, padx=PAD_LG, pady=(0, PAD_MD))

        # ── Core overtime card ────────────────────────────────────────────────
        core_card = _card(grid)
        tk.Label(core_card, text="Core Hours", bg=C.CARD.value,
                 fg=C.SUBTEXT.value, font=("Segoe UI", 8, "bold"), anchor="w"
                 ).pack(fill=tk.X, padx=PAD_LG, pady=(PAD_SM, 0))
        self.core_ot_label = tk.Label(core_card, text="", bg=C.CARD.value,
                                      fg=C.ACCENT.value, font=("Segoe UI", 13, "bold"),
                                      anchor="w")
        self.core_ot_label.pack(fill=tk.X, padx=PAD_LG, pady=(PAD_MD, 0))


        self.core_info_label = tk.Label(core_card, text="", bg=C.CARD.value,
                                        fg=C.SUBTEXT.value, font=("Segoe UI", 9), anchor="w")
        self.core_info_label.pack(fill=tk.X, padx=PAD_LG, pady=(0, PAD_MD))

        # ── Pause card ────────────────────────────────────────────────────────
        pause_card = _card(grid)

        self.pause_info = tk.Label(pause_card, text="", bg=C.CARD.value,
                                   fg=C.PAUSE.value, font=("Segoe UI", 13, "bold"),
                                   anchor="w")
        self.pause_info.pack(fill=tk.X, padx=PAD_LG, pady=(PAD_MD, 0))

        self.pause_deadline_label = tk.Label(pause_card, text="", bg=C.CARD.value,
                                             fg=C.WARN.value, font=("Segoe UI", 10),
                                             anchor="w")
        self.pause_deadline_label.pack(fill=tk.X, padx=PAD_LG, pady=(0, PAD_SM))

        self.pause_bar_canvas = tk.Canvas(pause_card, bg=C.SURFACE.value,
                                          height=self._bar_h, highlightthickness=0)
        self.pause_bar_canvas.pack(fill=tk.X, padx=PAD_LG, pady=(0, PAD_MD))

        # ── Legal pause warning ───────────────────────────────────────────────
        self.legal_pause_warn = tk.Label(body, text="", bg=C.BACKGROUND.value,
                                         fg=C.WARN.value, font=("Segoe UI", 9, "bold"),
                                         anchor="w")
        self.legal_pause_warn.pack(fill=tk.X, padx=PAD_MD + PAD_SM, pady=(0, 2))

        # ── Leave-time card ───────────────────────────────────────────────────
        leave_card = _card(grid)
        tk.Label(leave_card, text="Leave", bg=C.CARD.value,
                 fg=C.SUBTEXT.value, font=("Segoe UI", 8, "bold"), anchor="w"
                 ).pack(fill=tk.X, padx=PAD_LG, pady=(PAD_SM, 0))
        self.you_can_go_in = tk.Label(leave_card, text="",
                                      bg=C.CARD.value, fg=C.ACCENT.value,
                                      font=("Segoe UI", 13, "bold"), anchor="w")
        self.you_can_go_in.pack(fill=tk.X, padx=PAD_LG, pady=(PAD_MD, 0))

        self.ot_if_stay_label = tk.Label(leave_card, text="",
                                         bg=C.CARD.value, fg=C.SUBTEXT.value,
                                         font=("Segoe UI", 9), anchor="w")
        self.ot_if_stay_label.pack(fill=tk.X, padx=PAD_LG, pady=(0, PAD_MD))

        # ── Responsive grid placement ─────────────────────────────────────────
        _relayout_job = [None]
        _last_cols    = [None]

        def _do_relayout():
            w = self.master.winfo_width()
            cols = 2 if w >= 500 else 1
            if cols == _last_cols[0]:
                return  # no change, skip expensive re-grid
            _last_cols[0] = cols
            for card in (work_card, core_card, pause_card, leave_card):
                card.grid_forget()
            if cols == 2:
                work_card.grid( row=0, column=0, sticky="nsew", padx=(0, PAD_SM//2), pady=(0, PAD_SM))
                core_card.grid( row=0, column=1, sticky="nsew", padx=(PAD_SM//2, 0), pady=(0, PAD_SM))
                pause_card.grid(row=1, column=0, sticky="nsew", padx=(0, PAD_SM//2), pady=(0, PAD_SM))
                leave_card.grid(row=1, column=1, sticky="nsew", padx=(PAD_SM//2, 0), pady=(0, PAD_SM))
            else:
                work_card.grid( row=0, column=0, columnspan=2, sticky="ew", pady=(0, PAD_SM))
                pause_card.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, PAD_SM))
                core_card.grid( row=2, column=0, columnspan=2, sticky="ew", pady=(0, PAD_SM))
                leave_card.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, PAD_SM))

        def _relayout(e=None):
            # debounce: only fire 80ms after last resize event
            if _relayout_job[0]:
                self.master.after_cancel(_relayout_job[0])
            _relayout_job[0] = self.master.after(80, _do_relayout)

        self.master.bind("<Configure>", _relayout)
        self.master.after(150, _do_relayout)

        # ── Action buttons ────────────────────────────────────────────────────
        btn_bar = tk.Frame(self.master, bg=C.SURFACE.value,
                           highlightbackground=C.DIVIDER.value, highlightthickness=1)
        btn_bar.pack(fill=tk.X, side="bottom")

        inner = tk.Frame(btn_bar, bg=C.SURFACE.value)
        inner.pack(pady=PAD_LG)

        self.start_button = _btn(inner, "Clock In", C.ACCENT.value, fg="#ffffff",
                                 command=self.handle_start_stop)
        self.start_button.pack(side="left", padx=PAD_SM)

        self.dienstgang_button = _btn(inner, "🚗 Trip Start", C.BUTTON.value,
                                      command=self.handle_dienstgang_click)
        self.dienstgang_button.pack(side="left", padx=PAD_SM)

        self.pause_button = _btn(inner, "☕ Break", C.PAUSE.value,
                                 command=self.handle_pause_click)
        self.pause_button.pack(side="left", padx=PAD_SM)

        _btn(inner, "✏", C.SUBTEXT.value, command=self.open_timeline_editor, width=3)\
            .pack(side="left", padx=PAD_SM)

    # ── Progress bar draw ─────────────────────────────────────────────────────
    def _draw_bar(self, canvas, fraction, fill_color, marker_frac=None):
        canvas.update_idletasks()
        w  = canvas.winfo_width() or 400
        h  = self._bar_h       # total canvas height (bar_area + tick_area)
        canvas.delete("all")
        # background
        canvas.create_rectangle(0, self._tick_h, w, h, fill=C.SURFACE.value, outline="", width=0)
        # filled portion
        filled = max(0, min(1.0, fraction)) * w
        if filled > 1:
            canvas.create_rectangle(0, self._tick_h, filled, h, fill=fill_color, outline="", width=0)
        # marker tick: small downward triangle above bar
        if marker_frac is not None and 0 < marker_frac <= 1.0:
            x  = marker_frac * w
            tw = 5  # half-width of triangle
            # vertical line through bar
            canvas.create_line(x, self._tick_h, x, h, fill=C.WARN.value, width=2)
            # downward triangle above bar
            canvas.create_polygon(
                x - tw, 0,
                x + tw, 0,
                x,      self._tick_h,
                fill=C.WARN.value, outline=""
            )

    # ── Update loop ───────────────────────────────────────────────────────────
    def __update(self):
        now     = time.time()
        tracker = self.tracker
        started = tracker.start_time_stamp > 0

        # ── Clock ─────────────────────────────────────────────────────────────
        dt = datetime.now()
        self.time_display.config(text=dt.strftime("%H:%M:%S"))

        # ── Saldo helpers ─────────────────────────────────────────────────────
        def _pause_between(t_from, t_to):
            """Sekunden tatsächlicher Pause im Zeitraum [t_from, t_to]."""
            total = 0.0
            for p_start, p_end in tracker.pauses:
                p_end_eff = p_end if p_end else now
                overlap_start = max(p_start, t_from)
                overlap_end   = min(p_end_eff, t_to)
                if overlap_end > overlap_start:
                    total += overlap_end - overlap_start
            return total

        def _get_work_at(target_ts):
            _pause_raw = _pause_between(tracker.start_time_stamp, target_ts)
            return max(0.0, target_ts - tracker.start_time_stamp) - _pause_raw

        def _live_saldo():
            """Aktueller Saldo jetzt."""
            if tracker.start_time_stamp == 0:
                return tracker.total_balance_seconds
            start_bal = self._get_start_of_day_balance()
            _eff_goal = tracker.daily_goal * 3600 - tracker.daily_credit_mins * 60
            net_work = _get_work_at(now)
            return start_bal + (net_work - _eff_goal)

        def _projected_saldo(target_ts):
            """Saldo wenn man bei target_ts aufhört – inkl. noch ausstehender Pflichtpause."""
            if tracker.start_time_stamp == 0:
                return tracker.total_balance_seconds

            start_bal = self._get_start_of_day_balance()
            _eff_goal = tracker.daily_goal * 3600 - tracker.daily_credit_mins * 60

            raw_work_at_target = _get_work_at(target_ts)
            _pause_raw = _pause_between(tracker.start_time_stamp, target_ts)

            req   = tracker.default_pause_mins * 60
            legal = tracker.min_legal_pause_2_mins * 60 if raw_work_at_target >= tracker.legal_work_limit_2_h * 3600 else tracker.min_legal_pause_mins * 60

            needed_pause = req
            if raw_work_at_target >= tracker.legal_work_limit_h * 3600:
                needed_pause = max(needed_pause, legal)

            future_pause = max(0.0, needed_pause - _pause_raw) if target_ts > now else 0.0

            net_work = raw_work_at_target - future_pause
            return start_bal + (net_work - _eff_goal)

        # ── Saldo anzeigen ────────────────────────────────────────────────────
        if self._saldo_syncing:
            self.balance_account_label.config(text="⟳ Syncing balance…", fg=C.SUBTEXT.value)
        else:
            _live = _live_saldo()
            sign = "+" if _live >= 0 else "−"
            self.balance_account_label.config(
                text=f"Balance: {sign}{self.format_hhmm(abs(_live))}",
                fg=C.OVERTIME.value if _live >= 0 else C.NEGATIVE.value
            )

        if started:
            total_pause_raw  = tracker.get_total_pause_duration()
            work_elapsed     = (now - tracker.start_time_stamp) - total_pause_raw
            goal_secs        = tracker.daily_goal * 3600
            credit_secs      = tracker.daily_credit_mins * 60
            effective_goal   = goal_secs - credit_secs
            req_pause_secs   = tracker.default_pause_mins * 60

            # Dynamic legal pause: threshold 2 (e.g. >9h) requires extended break
            legal_pause_secs = tracker.min_legal_pause_2_mins * 60 if work_elapsed >= tracker.legal_work_limit_2_h * 3600 else tracker.min_legal_pause_mins * 60

            fraction         = work_elapsed / effective_goal if effective_goal > 0 else 0.0

            # ── Work card ─────────────────────────────────────────────────────
            self.worked_label.config(
                text=f"⏱  {self.format_seconds(work_elapsed)}",
                fg=C.OVERTIME.value if fraction >= 1.0 else C.TEXT.value
            )
            remaining = max(0, effective_goal - work_elapsed)
            self.work_hours_left.config(
                text=(f"✓ Goal reached  ·  +{self.format_hhmm(work_elapsed - effective_goal)}"
                      if fraction >= 1.0 else
                      f"Goal {self.format_hhmm(effective_goal)}  ·  Left {self.format_hhmm(remaining)}"),
                fg=C.OVERTIME.value if fraction >= 1.0 else C.SUBTEXT.value
            )
            # Progress marker: shows first threshold, or second threshold if first is passed
            if work_elapsed < tracker.legal_work_limit_h * 3600:
                marker_frac = (tracker.legal_work_limit_h * 3600) / effective_goal if effective_goal > 0 else None
            else:
                marker_frac = (tracker.legal_work_limit_2_h * 3600) / effective_goal if effective_goal > 0 else None
            self._draw_bar(self.work_bar_canvas, fraction,
                           C.OVERTIME.value if fraction >= 1.0 else C.ACCENT.value,
                           marker_frac=marker_frac)

            # ── Core card ─────────────────────────────────────────────────────
            today      = dt.date()
            core_end   = datetime(today.year, today.month, today.day,
                                  int(tracker.core_end_h),
                                  round((tracker.core_end_h % 1) * 60))
            core_passed = now >= core_end.timestamp()
            saldo_at_core_end = _projected_saldo(core_end.timestamp())
            ce_sign    = "+" if saldo_at_core_end >= 0 else "−"
            ce_color   = C.OVERTIME.value if saldo_at_core_end >= 0 else C.NEGATIVE.value
            if core_passed:
                _live_now  = _live_saldo()
                live_sign  = "+" if _live_now >= 0 else "−"
                live_color = C.OVERTIME.value if _live_now >= 0 else C.NEGATIVE.value
                self.core_ot_label.config(
                    text=f"✓  Core done  →  {live_sign}{self.format_hhmm(abs(_live_now))}",
                    fg=live_color
                )
                self.core_info_label.config(
                    text=f"Past {_fmt_hm(tracker.core_end_h)}  ·  current balance",
                    fg=C.SUBTEXT.value
                )
            else:
                self.core_ot_label.config(
                    text=f"🕘  {_fmt_hm(tracker.core_end_h)}  →  {ce_sign}{self.format_hhmm(abs(saldo_at_core_end))}",
                    fg=ce_color
                )
                self.core_info_label.config(
                    text=f"Core  {_fmt_hm(tracker.core_start_h)} – {_fmt_hm(tracker.core_end_h)}",
                    fg=C.SUBTEXT.value
                )

            # ── Pause card ────────────────────────────────────────────────────
            pause_frac   = total_pause_raw / req_pause_secs if req_pause_secs > 0 else 0.0
            is_pause     = tracker.is_in_pause
            is_trip      = tracker.is_on_dienstgang
            pause_icon   = "▶" if is_pause else ("🚗" if is_trip else "☕")
            self.pause_info.config(
                text=f"{pause_icon}  {self.format_hhmm(total_pause_raw)} / {self.format_hhmm(req_pause_secs)}",
                fg=C.PAUSE.value
            )
            self._draw_bar(self.pause_bar_canvas, pause_frac, C.PAUSE.value)

            # ── Pause deadline ────────────────────────────────────────────────
            six_h_secs      = tracker.legal_work_limit_h * 3600
            latest_start_ts = tracker.start_time_stamp + six_h_secs + total_pause_raw
            latest_start_dt = datetime.fromtimestamp(latest_start_ts)
            already_ok      = total_pause_raw >= legal_pause_secs
            if already_ok:
                self.pause_deadline_label.config(
                    text=f"✓  Min. {int(legal_pause_secs // 60)} min reached",
                    fg=C.OVERTIME.value)
            else:
                time_until_deadline = latest_start_ts - now
                if time_until_deadline > 0:
                    self.pause_deadline_label.config(
                        text=f"⏰  Break by {latest_start_dt.strftime('%H:%M')}",
                        fg=C.WARN.value if time_until_deadline > tracker.pause_warn_before_mins * 60
                        else C.NEGATIVE.value
                    )
                else:
                    self.pause_deadline_label.config(
                        text="⚠  Break overdue!", fg=C.NEGATIVE.value)

            # ── Auto-book pause ────────────────────────────────────────────────
            # Approach: keep an open auto-pause entry ([start, None]) that
            # accumulates live. Once the legal minimum is met we close it.

            # Reset auto-book flag if we hit threshold 2 (e.g. 9h) and haven't booked the upgrade yet
            if work_elapsed >= tracker.legal_work_limit_2_h * 3600 and not getattr(self, "_auto_pause_9h_booked", False):
                self._auto_pause_booked = False  # trigger another auto-book

            if (not self._auto_pause_booked
                    and not tracker.is_in_pause
                    and work_elapsed >= tracker.legal_work_limit_h * 3600):

                still_needed_secs = max(0.0, legal_pause_secs - total_pause_raw)

                # Determine mark to start the pause
                if work_elapsed >= tracker.legal_work_limit_2_h * 3600:
                    mark = _floor_minute(tracker.start_time_stamp + tracker.legal_work_limit_2_h * 3600 + total_pause_raw) # rough
                    rule_text = f"{int(tracker.legal_work_limit_2_h)}h rule"
                else:
                    mark = _floor_minute(tracker.start_time_stamp + tracker.legal_work_limit_h * 3600)
                    rule_text = f"{int(tracker.legal_work_limit_h)}h rule"

                if still_needed_secs > 0:
                    # Open a live pause entry (end=None → grows each tick)
                    if not self._auto_pause_entry:
                        self._auto_pause_entry = [mark, None]
                        tracker.pauses.append(self._auto_pause_entry)
                        self._fire_notify(
                            "⏸ Auto-break booked",
                            f"{int(still_needed_secs // 60)} min break added ({rule_text}). "
                            f"Edit via ✏ if needed."
                        )
                    # Close entry as soon as legal minimum is satisfied
                    new_total = tracker.get_total_pause_duration()
                    if new_total >= legal_pause_secs:
                        # Close the pause
                        self._auto_pause_entry[1] = _floor_minute(
                            self._auto_pause_entry[0] + still_needed_secs) # just close it to fit the requirement
                        self._auto_pause_entry = None
                        self._auto_pause_booked = True
                        if work_elapsed >= tracker.legal_work_limit_2_h * 3600:
                            self._auto_pause_9h_booked = True
                        tracker.save_data()
                else:
                    self._auto_pause_booked = True
                    if work_elapsed >= tracker.legal_work_limit_2_h * 3600:
                        self._auto_pause_9h_booked = True

            # ── Legal pause fill-up warning ────────────────────────────────────
            # If user has taken < min_legal_pause_mins pause but some pause,
            # warn them it doesn't count yet.
            if 0 < total_pause_raw < legal_pause_secs:
                still_needed = legal_pause_secs - total_pause_raw
                self.legal_pause_warn.config(
                    text=f"⚠  Pause < {int(tracker.min_legal_pause_mins)} min – "
                         f"{self.format_hhmm(still_needed)} more to count legally"
                )
            else:
                self.legal_pause_warn.config(text="")

            # ── Leave time ────────────────────────────────────────────────────
            # Gesamtpause die mindestens einzuplanen ist:
            # - req_pause_secs (Ziel), mindestens aber legal wenn >6h
            # - Wenn bereits mehr Pause als Ziel: nimm tatsächliche Pause
            min_required_pause = req_pause_secs
            if work_elapsed >= tracker.legal_work_limit_h * 3600:
                min_required_pause = max(min_required_pause, legal_pause_secs)
            effective_total_pause = max(total_pause_raw, min_required_pause)
            leave_ts  = tracker.start_time_stamp + effective_goal + effective_total_pause
            leave_dt  = datetime.fromtimestamp(leave_ts)
            leave_col      = C.OVERTIME.value if work_elapsed >= effective_goal else C.ACCENT.value
            saldo_at_leave = _projected_saldo(leave_ts)
            lv_sign        = "+" if saldo_at_leave >= 0 else "−"
            lv_color       = C.OVERTIME.value if saldo_at_leave >= 0 else C.NEGATIVE.value
            self.you_can_go_in.config(
                text=f"🚪  {leave_dt.strftime('%H:%M')}  →  {lv_sign}{self.format_hhmm(abs(saldo_at_leave))}",
                fg=leave_col
            )
            start_dt = datetime.fromtimestamp(tracker.start_time_stamp)
            self.ot_if_stay_label.config(
                text=f"Clocked in at {start_dt.strftime('%H:%M')}",
                fg=C.SUBTEXT.value
            )

            # ── Notifications ─────────────────────────────────────────────────
            if work_elapsed >= goal_secs and not self._notified_work_done:
                self._notified_work_done = True
                self._fire_notify("✓ Goal reached!", "You've hit your daily work goal.")

            warn_secs = tracker.pause_warn_before_mins * 60
            time_to_deadline = latest_start_ts - now
            if 0 < time_to_deadline <= warn_secs and not already_ok \
                    and not self._notified_pause_warn:
                self._notified_pause_warn = True
                mins = max(1, int(math.ceil(time_to_deadline / 60)))
                self._fire_notify("⏰ Break needed!",
                                  f"You must start your break within {mins} min (6h rule)!")

            if total_pause_raw >= req_pause_secs and not self._notified_pause_done:
                self._notified_pause_done = True
                self._fire_notify("☕ Break complete", "Required break time reached.")
        else:
            for lbl, txt, fg in [
                (self.worked_label,       "Not clocked in", C.SUBTEXT.value),
                (self.work_hours_left,    "",               C.SUBTEXT.value),
                (self.core_ot_label,      "",               C.SUBTEXT.value),
                (self.core_info_label,    "",               C.SUBTEXT.value),
                (self.pause_info,         "",               C.PAUSE.value),
                (self.pause_deadline_label,"",              C.WARN.value),
                (self.legal_pause_warn,   "",               C.WARN.value),
                (self.you_can_go_in,      "",               C.ACCENT.value),
                (self.ot_if_stay_label,   "",               C.OVERTIME.value),
            ]:
                lbl.config(text=txt, fg=fg)
            self._draw_bar(self.work_bar_canvas,  0, C.ACCENT.value)
            self._draw_bar(self.pause_bar_canvas, 0, C.PAUSE.value)

        self._refresh_action_buttons()
        self.master.after(1000, self.__update)

    # ── Button handlers ───────────────────────────────────────────────────────

    def _get_start_of_day_balance(self):
        """Returns the hypothetical start-of-day balance in seconds."""
        tracker = self.tracker
        if tracker.start_time_stamp == 0:
            return tracker.total_balance_seconds

        _eff_goal = tracker.daily_goal * 3600 - tracker.daily_credit_mins * 60

        if self._nova_saldo_snapshot:
            snap_saldo, snap_time = self._nova_saldo_snapshot
            # How much work was done between clock-in and snap_time?
            gross_elapsed = max(0.0, snap_time - tracker.start_time_stamp)

            # calculate pause between start and snap
            total_pause_then = 0.0
            for p_start, p_end in tracker.pauses:
                p_end_eff = p_end if p_end else time.time()
                overlap_start = max(p_start, tracker.start_time_stamp)
                overlap_end   = min(p_end_eff, snap_time)
                if overlap_end > overlap_start:
                    total_pause_then += overlap_end - overlap_start

            work_then = gross_elapsed - total_pause_then
            # snap_saldo = start_of_day + work_then - eff_goal
            # start_of_day = snap_saldo - work_then + eff_goal
            return snap_saldo - work_then + _eff_goal
        else:
            return tracker.total_balance_seconds

    def handle_start_stop(self):
        if self.tracker.start_time_stamp == 0:
            self.tracker.start_tracking()
            self._notified_work_done = self._notified_pause_done = self._notified_pause_warn = self._auto_pause_booked = False
            self._auto_pause_entry     = None
            self._auto_pause_9h_booked = False
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
            eff_goal_secs = self.tracker.daily_goal * 3600 - self.tracker.daily_credit_mins * 60
            diff          = work_elapsed - eff_goal_secs
            if diff < 0:
                missing = self.format_seconds(abs(diff))
                if not messagebox.askyesno(
                    "⚠ Work not finished",
                    f"You still have {missing} of work remaining!\n\n"
                    f"Stopping now will subtract this time from your balance.\n\nStop anyway?"
                ):
                    return
            if not self._nova_saldo_snapshot:
                self.tracker.total_balance_seconds += diff
            self.tracker.reset_values()
            self.tracker.save_data()
            self._nova_work_async("end_work")
        self._refresh_clock_button()

    def handle_pause_click(self):
        if self.tracker.is_on_dienstgang:
            return
        self._do_toggle_pause()

    def handle_dienstgang_click(self):
        if self.tracker.is_in_pause:
            return
        self._do_toggle_dienstgang()

    def _refresh_clock_button(self):
        if self.tracker.start_time_stamp > 0:
            self.start_button.config(text="Clock Out", bg=C.STOP.value, fg="#ffffff")
        else:
            self.start_button.config(text="Clock In", bg=C.ACCENT.value, fg="#ffffff")

    def _refresh_action_buttons(self):
        self._refresh_clock_button()
        is_p = self.tracker.is_in_pause
        is_t = self.tracker.is_on_dienstgang

        if is_p:
            self.pause_button.config(text="☕ End Break", bg=C.PAUSE.value,
                                     state="normal", fg="#1a1a2e")
            self.dienstgang_button.config(state="disabled", fg="#55557a")
        else:
            self.pause_button.config(text="☕ Break", bg=C.PAUSE.value, fg="#1a1a2e",
                                     state="normal" if not is_t else "disabled")
            if not is_t:
                self.dienstgang_button.config(state="normal", fg=C.TEXT.value)

        if is_t:
            self.dienstgang_button.config(text="🏠 Trip End", bg=C.NEGATIVE.value,
                                          state="normal", fg=C.TEXT.value)
            self.pause_button.config(state="disabled", fg="#55557a")
        elif not is_p:
            self.dienstgang_button.config(text="🚗 Trip Start", bg=C.BUTTON.value,
                                          state="normal", fg=C.TEXT.value)

    # ── Nova async helpers ────────────────────────────────────────────────────
    def _nova_work_async(self, action: str):
        if not NOVA_AVAILABLE or not self.nova_cfg.url:
            return
        def _run():
            try:
                nova.run_nova_action(action)
            except Exception as e:
                print(f"[Nova Work] {action} failed: {e}")
                self.master.after(0, lambda: self._toast(f"Nova: {action} failed", str(e)))
        threading.Thread(target=_run, daemon=True).start()

    def _nova_trip_async(self):
        if not NOVA_AVAILABLE or not self.nova_cfg.url:
            return
        action = "start_business_trip" if self.tracker.is_on_dienstgang else "end_business_trip"
        def _run():
            try:
                nova.run_nova_action(action)
            except Exception as e:
                print(f"[Nova Trip] {action} failed: {e}")
                self.master.after(0, lambda: self._toast(f"Nova: {action} failed", str(e)))
        threading.Thread(target=_run, daemon=True).start()

    def _nova_pause_async(self):
        if not NOVA_AVAILABLE or not self.nova_cfg.url:
            return
        action = "start_pause" if self.tracker.is_in_pause else "end_pause"
        def _run():
            try:
                nova.run_nova_action(action)
            except Exception as e:
                print(f"[Nova Pause] {action} failed: {e}")
                self.master.after(0, lambda: self._toast(f"Nova: {action} failed", str(e)))
        threading.Thread(target=_run, daemon=True).start()

    # ── Toast ─────────────────────────────────────────────────────────────────
    def _toast(self, title, message="", duration=4000):
        try:
            t = tk.Toplevel(self.master)
            t.overrideredirect(True)
            t.attributes("-topmost", True)
            t.config(bg=C.SURFACE.value,
                     highlightbackground=C.NEGATIVE.value, highlightthickness=1)
            tk.Label(t, text=title, bg=C.SURFACE.value, fg=C.NEGATIVE.value,
                     font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=PAD_MD, pady=(PAD_SM, 0))
            if message:
                tk.Label(t, text=message[:80], bg=C.SURFACE.value, fg=C.SUBTEXT.value,
                         font=("Segoe UI", 9)).pack(anchor="w", padx=PAD_MD, pady=(0, PAD_SM))
            t.update_idletasks()
            mx = self.master.winfo_x()
            my = self.master.winfo_y()
            mw = self.master.winfo_width()
            mh = self.master.winfo_height()
            t.geometry(f"+{mx+mw-t.winfo_width()-PAD_SM}+{my+mh-t.winfo_height()-PAD_SM}")
            t.after(duration, t.destroy)
        except Exception:
            pass

    # ── Popup helpers ─────────────────────────────────────────────────────────
    def _make_popup(self, title):
        win = tk.Toplevel(self.master)
        win.title(title)
        win.config(bg=C.BACKGROUND.value)
        win.resizable(False, False)
        win.withdraw()
        if os.path.exists(self.icon_ico):
            try:
                win.iconbitmap(self.icon_ico)
            except Exception:
                pass
        def _dark(e=None):
            try:
                import ctypes
                win.update_idletasks()
                hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
                for attr in (20, 19):
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr,
                        ctypes.byref(ctypes.c_int(1)),
                        ctypes.sizeof(ctypes.c_int))
            except Exception:
                pass
        win.after(100, _dark)
        return win

    def _position_left(self, win):
        def _pos():
            self.master.update_idletasks(); win.update_idletasks()
            sw = win.winfo_reqwidth() or 300; sh = win.winfo_reqheight() or 400
            mx, my = self.master.winfo_x(), self.master.winfo_y()
            mw, mh = self.master.winfo_width(), self.master.winfo_height()
            x = mx - sw - 8
            if x < 0: x = mx + mw + 8
            y = my + (mh - sh) // 2
            sw2 = self.master.winfo_screenwidth(); sh2 = self.master.winfo_screenheight()
            win.geometry(f"+{max(0,min(x,sw2-sw-8))}+{max(0,min(y,sh2-sh-8))}")
            win.deiconify()
        win.after(100, _pos)

    def _position_above(self, win, diagonal=False):
        def _pos():
            self.master.update_idletasks(); win.update_idletasks()
            sw = win.winfo_reqwidth() or 360; sh = win.winfo_reqheight() or 480
            mx, my = self.master.winfo_x(), self.master.winfo_y()
            mw, mh = self.master.winfo_width(), self.master.winfo_height()
            scr_w = self.master.winfo_screenwidth(); scr_h = self.master.winfo_screenheight()
            if diagonal:
                x, y = mx + mw - sw - 600, my - 575
            else:
                x, y = mx + (mw - sw) // 2, my - sh - 8
            win.geometry(f"+{max(0,min(x,scr_w-sw-8))}+{max(0,min(y,scr_h-sh-8))}")
            win.deiconify()
        win.after(100, _pos)

    # ── Nova init / saldo ─────────────────────────────────────────────────────
    def _try_init_nova(self):
        if not NOVA_AVAILABLE or not self.nova_cfg.url:
            return
        try:
            nova.init_config(
                cfg_url                = self.nova_cfg.url,
                cfg_username           = self.nova_cfg.username,
                cfg_password           = self.nova_cfg.password,
                cfg_http_auth_username = self.nova_cfg.proxy_auth_username,
                cfg_http_auth_password = self.nova_cfg.proxy_auth_password,
                cfg_headless           = not self.nova_cfg.show_window,
            )
        except Exception as e:
            print(f"[Nova] init_config() failed: {e}")

    def _parse_nova_saldo(self, raw: str):
        """Nova format: hh,mm where ,mm is literal minutes (not decimal).
        e.g. 1,26 = 1h 26min = 5160s   -0,59 = -59min = -3540s"""
        def hhmm_to_secs(s: str) -> float:
            s = s.strip()
            neg = s.startswith("-")
            s = s.lstrip("+-")
            if "," in s or "." in s:
                sep = "," if "," in s else "."
                h_part, m_part = s.split(sep, 1)
                h = int(h_part) if h_part else 0
                m = int(m_part.ljust(2, "0")[:2])  # treat as two-digit minutes
            else:
                h = int(s); m = 0
            total = h * 3600 + m * 60
            return -total if neg else total

        m = re.search(r"Saldo:\s*([-+]?\d+[,.]\d+|\d+)\s*Min", raw, re.IGNORECASE)
        if m: return float(m.group(1).replace(",", ".")) * 60  # minutes format stays decimal

        m = re.search(r"Saldo:\s*([-+]?\d+[,.]\d+|\d+)\s*Std", raw, re.IGNORECASE)
        if m: return hhmm_to_secs(m.group(1))

        # bare number fallback – assume hh,mm
        m = re.search(r"Saldo:\s*([-+]?\d+[,.]\d+|[-+]?\d+)", raw)
        if m: return hhmm_to_secs(m.group(1))
        return None

    def _sync_saldo_from_nova(self, delay_ms=0):
        if not NOVA_AVAILABLE or not self.nova_cfg.url:
            return
        self._saldo_syncing = True
        def _run():
            time.sleep(delay_ms / 1000.0)
            try:
                raw = nova.run_nova_action("saldo")
                if not isinstance(raw, str): return
                seconds = self._parse_nova_saldo(raw)
                if seconds is None: return
                def _apply():
                    self._saldo_syncing = False
                    self.tracker.total_balance_seconds = seconds
                    self.tracker.save_data()
                    self._nova_saldo_snapshot = (seconds, _floor_minute(time.time()))
                self.master.after(0, _apply)
            except Exception as e:
                self.master.after(0, lambda: setattr(self, "_saldo_syncing", False))
                print(f"[Nova Saldo] Sync failed: {e}")
        threading.Thread(target=_run, daemon=True).start()

    # ── API Settings ──────────────────────────────────────────────────────────
    def open_timeline_editor(self):
        """Edit today's clock-in, pauses and clock-out manually."""
        win = self._make_popup("Edit Timeline")
        win.geometry("360x480")
        win.resizable(False, True)
        win.minsize(320, 300)
        BG, FG, FG2 = C.BACKGROUND.value, C.TEXT.value, C.SUBTEXT.value
        tracker = self.tracker

        # ── Header ────────────────────────────────────────────────────────────
        hf = tk.Frame(win, bg=C.SURFACE.value,
                      highlightbackground=C.DIVIDER.value, highlightthickness=1)
        hf.pack(fill=tk.X)
        tk.Label(hf, text="✏  Edit Today's Timeline", bg=C.SURFACE.value,
                 fg=C.ACCENT.value, font=("Segoe UI", 12, "bold")
                 ).pack(pady=PAD_MD, padx=PAD_LG, anchor="w")

        # ── Scrollable body ───────────────────────────────────────────────────
        outer  = tk.Frame(win, bg=BG)
        outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb    = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=BG)
        cid  = canvas.create_window(0, 0, window=body, anchor="nw")
        body.bind("<Configure>",   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cid, width=e.width))
        def _on_scroll(e):
            canvas.yview_scroll(int(-1 * e.delta / 120), "units")
        canvas.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>", _on_scroll))
        canvas.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))

        # ── Helpers ───────────────────────────────────────────────────────────
        def _ts_to_hhmm(ts):
            if not ts: return ""
            from datetime import datetime
            return datetime.fromtimestamp(ts).strftime("%H:%M")

        def _hhmm_to_ts(s):
            """Parse HH:MM into today's Unix timestamp (floored to minute)."""
            from datetime import datetime
            s = s.strip()
            if not s: return None
            try:
                now = datetime.now()
                t   = datetime.strptime(s, "%H:%M").replace(
                          year=now.year, month=now.month, day=now.day)
                return _floor_minute(t.timestamp())
            except ValueError:
                return None

        # Each row: icon, label, time entry, optional delete button
        # rows is a list of dicts: {type, var, del_cmd}
        rows = []

        def _row(icon, label, ts_val, color, deletable=False, del_cmd=None):
            f = tk.Frame(body, bg=BG)
            f.pack(fill=tk.X, padx=PAD_LG, pady=(0, PAD_SM))

            tk.Label(f, text=icon, bg=BG, fg=color,
                     font=("Segoe UI", 14)).pack(side="left", padx=(0, PAD_SM))

            tk.Label(f, text=label, bg=BG, fg=FG,
                     font=("Segoe UI", 10, "bold"), width=12, anchor="w").pack(side="left")

            var = tk.StringVar(value=_ts_to_hhmm(ts_val))
            e = tk.Entry(f, textvariable=var, width=6,
                         font=("Segoe UI", 11, "bold"), bg=C.SURFACE.value, fg=color,
                         insertbackground=FG, relief="flat", justify="center")
            e.pack(side="left", padx=(PAD_SM, 0))

            if deletable and del_cmd:
                _btn(f, "✕", C.NEGATIVE.value, command=del_cmd, width=2, pady=2
                     ).pack(side="left", padx=(PAD_SM, 0))

            return var

        # ── Divider ───────────────────────────────────────────────────────────
        def _section(txt):
            tk.Label(body, text=txt, bg=BG, fg=C.ACCENT.value,
                     font=("Segoe UI", 8, "bold")).pack(
                         anchor="w", padx=PAD_LG, pady=(PAD_LG, 2))
            tk.Frame(body, bg=C.DIVIDER.value, height=1).pack(
                fill=tk.X, padx=PAD_LG, pady=(0, PAD_SM))

        # ── Clock-in ──────────────────────────────────────────────────────────
        _section("CLOCK")
        ci_var = _row("🟢", "Clock-in", tracker.start_time_stamp or None,
                      C.POSITIVE.value if hasattr(C, "POSITIVE") else C.OVERTIME.value)

        # ── Pauses ────────────────────────────────────────────────────────────
        _section("BREAKS")
        pause_vars = []  # list of (start_var, end_var, frame)

        def _add_pause_row(ps=None, pe=None):
            idx = len(pause_vars)
            pf = tk.Frame(body, bg=BG)
            pf.pack(fill=tk.X, padx=PAD_LG, pady=(0, 4))

            tk.Label(pf, text="⏸", bg=BG, fg=C.PAUSE.value,
                     font=("Segoe UI", 14)).pack(side="left", padx=(0, PAD_SM))
            tk.Label(pf, text=f"Break {idx+1}", bg=BG, fg=FG,
                     font=("Segoe UI", 10, "bold"), width=12, anchor="w").pack(side="left")

            sv = tk.StringVar(value=_ts_to_hhmm(ps))
            ev = tk.StringVar(value=_ts_to_hhmm(pe))

            tk.Entry(pf, textvariable=sv, width=6,
                     font=("Segoe UI", 11, "bold"), bg=C.SURFACE.value, fg=C.PAUSE.value,
                     insertbackground=FG, relief="flat", justify="center").pack(side="left")
            tk.Label(pf, text="–", bg=BG, fg=FG2,
                     font=("Segoe UI", 11)).pack(side="left", padx=2)
            tk.Entry(pf, textvariable=ev, width=6,
                     font=("Segoe UI", 11, "bold"), bg=C.SURFACE.value, fg=C.PAUSE.value,
                     insertbackground=FG, relief="flat", justify="center").pack(side="left")

            def _del(fr=pf, pair=(sv, ev)):
                pause_vars.remove(pair)
                fr.destroy()

            _btn(pf, "✕", C.NEGATIVE.value, command=_del, width=2, pady=2
                 ).pack(side="left", padx=(PAD_SM, 0))

            pause_vars.append((sv, ev))

        for ps, pe in tracker.pauses:
            _add_pause_row(ps, pe)
        # If currently in pause, last entry has no end
        if tracker.is_in_pause and tracker.pauses and tracker.pauses[-1][1] is None:
            pass  # already handled above

        add_f = tk.Frame(body, bg=BG)
        add_f.pack(fill=tk.X, padx=PAD_LG, pady=(0, PAD_SM))
        _btn(add_f, "+ Add Break", C.PAUSE.value, command=_add_pause_row, width=14
             ).pack(side="left")

        # ── Clock-out (only if stopped) ───────────────────────────────────────
        co_var = None
        if not tracker.start_time_stamp:
            _section("CLOCK OUT")
            co_var = _row("🔴", "Clock-out",
                          getattr(tracker, "end_time_stamp", None),
                          C.NEGATIVE.value)

        # ── Save ──────────────────────────────────────────────────────────────
        bf = tk.Frame(win, bg=C.SURFACE.value,
                      highlightbackground=C.DIVIDER.value, highlightthickness=1)
        bf.pack(fill=tk.X, side="bottom")

        def _save():
            errors = []

            # Clock-in
            ci_ts = _hhmm_to_ts(ci_var.get())
            if ci_ts is None:
                errors.append("Invalid Clock-in time.")
            else:
                tracker.start_time_stamp = ci_ts

            # Pauses
            new_pauses = []
            for i, (sv, ev) in enumerate(pause_vars):
                ps = _hhmm_to_ts(sv.get())
                pe = _hhmm_to_ts(ev.get()) if ev.get().strip() else None
                if ps is None:
                    errors.append(f"Break {i+1}: invalid start time.")
                    continue
                new_pauses.append([ps, pe])
            if not errors:
                tracker.pauses = new_pauses
                tracker.is_in_pause = (
                    bool(new_pauses) and new_pauses[-1][1] is None
                )

            if errors:
                from tkinter import messagebox
                messagebox.showerror("Invalid input", "\n".join(errors), parent=win)
                return

            tracker.save_data()
            win.destroy()

        _btn(bf, "💾 Save", C.ACCENT.value, command=_save, width=14
             ).pack(pady=PAD_MD, padx=PAD_LG, anchor="w")
        win.protocol("WM_DELETE_WINDOW", win.destroy)

        self._position_left(win)

    def open_api_settings(self):
        win = self._make_popup("API Settings")
        self._position_above(win)
        BG, FG, FG2 = C.BACKGROUND.value, C.TEXT.value, C.SUBTEXT.value

        tk.Label(win, text="NovaTime API Settings", bg=BG, fg=C.API.value,
                 font=("Segoe UI", 13, "bold")).pack(pady=(PAD_LG, PAD_SM), padx=PAD_LG, anchor="w")
        _divider(win, padx=PAD_LG, pady=(0, PAD_SM))

        def field_row(parent, label, default="", show=None):
            tk.Label(parent, text=label, bg=BG, fg=FG2,
                     font=("Segoe UI", 9)).pack(pady=(PAD_MD, 2), padx=PAD_LG, anchor="w")
            var = tk.StringVar(value=default)
            kw  = {"show": show} if show else {}
            tk.Entry(parent, textvariable=var, bg=C.SURFACE.value, fg=FG,
                     insertbackground=FG, relief="flat", font=("Segoe UI", 11),
                     width=36, **kw).pack(padx=PAD_LG, anchor="w", ipady=PAD_SM)
            return var

        url_var   = field_row(win, "NovaTime URL",        self.nova_cfg.url)
        user_var  = field_row(win, "Username",            self.nova_cfg.username)
        pass_var  = field_row(win, "Password",            self.nova_cfg.password,          show="•")
        puser_var = field_row(win, "Proxy Auth Username", self.nova_cfg.proxy_auth_username)
        ppass_var = field_row(win, "Proxy Auth Password", self.nova_cfg.proxy_auth_password, show="•")

        _divider(win, padx=PAD_LG, pady=(PAD_MD, PAD_SM))
        show_var  = tk.BooleanVar(value=self.nova_cfg.show_window)
        chk_frame = tk.Frame(win, bg=BG)
        chk_frame.pack(pady=(0, PAD_SM), padx=PAD_LG, anchor="w")
        tk.Checkbutton(chk_frame, text=" Show NovaTime Window", variable=show_var,
                       bg=BG, fg=FG, selectcolor=C.SURFACE.value,
                       activebackground=BG, activeforeground=FG,
                       font=("Segoe UI", 10)).pack(side="left")

        _divider(win, padx=PAD_LG, pady=(PAD_SM, PAD_SM))

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

        btn_row    = tk.Frame(win, bg=BG)
        btn_row.pack(pady=(PAD_SM, PAD_LG), padx=PAD_LG, anchor="w")
        test_status = tk.Label(btn_row, text="", bg=BG, font=("Segoe UI", 10, "bold"))

        def _set_status(ok, msg):
            test_status.config(text=msg,
                               fg=C.OVERTIME.value if ok else C.NEGATIVE.value)
            test_status.pack(side="left", padx=(PAD_MD, 0))

        def test_api():
            if not NOVA_AVAILABLE:
                _set_status(False, "✗ novatime not found"); return
            if not self.nova_cfg.url:
                _set_status(False, "✗ No URL configured"); return
            test_btn.config(state="disabled", text="⏳ Testing…")
            test_status.pack_forget()
            def _run():
                try:
                    nova.run_nova_action("test")
                    win.after(0, lambda: _set_status(True, "✓ Connection OK"))
                except Exception as e:
                    win.after(0, lambda: _set_status(False, f"✗ {e}"))
                finally:
                    win.after(0, lambda: test_btn.config(state="normal", text="🔌 Test API"))
            threading.Thread(target=_run, daemon=True).start()

        _btn(btn_row, "💾 Save", C.API.value, command=save_and_close, width=10
             ).pack(side="left", padx=(0, PAD_SM))
        test_btn = _btn(btn_row, "🔌 Test API", C.BUTTON.value, command=test_api, width=10)
        test_btn.pack(side="left")
        test_status.pack_forget()
        win.protocol("WM_DELETE_WINDOW", win.destroy)

    # ── Settings ──────────────────────────────────────────────────────────────
    def open_settings(self):
        win = self._make_popup("Settings")
        self._position_left(win)
        win.resizable(True, True)
        win.geometry("440x680")
        win.minsize(380, 400)
        BG, FG, FG2 = C.BACKGROUND.value, C.TEXT.value, C.SUBTEXT.value

        # ── Header ────────────────────────────────────────────────────────────
        hf = tk.Frame(win, bg=C.SURFACE.value,
                      highlightbackground=C.DIVIDER.value, highlightthickness=1)
        hf.pack(fill=tk.X)
        tk.Label(hf, text="⚙  Settings", bg=C.SURFACE.value, fg=C.ACCENT.value,
                 font=("Segoe UI", 13, "bold")).pack(pady=PAD_MD, padx=PAD_LG, anchor="w")

        # ── Scrollable canvas ─────────────────────────────────────────────────
        outer  = tk.Frame(win, bg=BG)
        outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb    = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=BG)
        cid  = canvas.create_window(0, 0, window=body, anchor="nw")
        body.bind("<Configure>",   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cid, width=e.width))
        def _on_scroll(e):
            canvas.yview_scroll(int(-1 * e.delta / 120), "units")
        canvas.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>", _on_scroll))
        canvas.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))

        # ── Helpers ───────────────────────────────────────────────────────────
        def section(txt):
            tk.Label(body, text=txt, bg=BG, fg=C.ACCENT.value,
                     font=("Segoe UI", 9, "bold")).pack(
                         fill=tk.X, padx=PAD_LG, pady=(PAD_LG, 0), anchor="w")
            tk.Frame(body, bg=C.DIVIDER.value, height=1).pack(
                fill=tk.X, padx=PAD_LG, pady=(2, PAD_SM))

        def _spinpair(parent, lo_h, hi_h):
            """Returns (sb_h, sb_m) packed in parent."""
            sb_h = tk.Spinbox(parent, from_=lo_h, to=hi_h, width=3,
                              font=("Segoe UI", 11), bg=C.SURFACE.value, fg=FG,
                              buttonbackground=C.BUTTON.value, insertbackground=FG,
                              relief="flat", justify="center")
            sb_h.pack(side="left")
            tk.Label(parent, text="h", bg=BG, fg=FG2,
                     font=("Segoe UI", 9)).pack(side="left", padx=(2, 5))
            sb_m = tk.Spinbox(parent, from_=0, to=59, width=3,
                              font=("Segoe UI", 11), bg=C.SURFACE.value, fg=FG,
                              buttonbackground=C.BUTTON.value, insertbackground=FG,
                              relief="flat", justify="center")
            sb_m.pack(side="left")
            tk.Label(parent, text="min", bg=BG, fg=FG2,
                     font=("Segoe UI", 9)).pack(side="left", padx=(2, 0))
            return sb_h, sb_m

        def row_hhmm(label, hint, var_h, lo, hi, color):
            f = tk.Frame(body, bg=BG)
            f.pack(fill=tk.X, padx=PAD_LG, pady=(0, PAD_SM))
            lf = tk.Frame(f, bg=BG); lf.pack(side="left", fill=tk.X, expand=True)
            tk.Label(lf, text=label, bg=BG, fg=FG,
                     font=("Segoe UI", 10, "bold")).pack(anchor="w")
            if hint:
                tk.Label(lf, text=hint, bg=BG, fg=FG2,
                         font=("Segoe UI", 8), wraplength=210, justify="left").pack(anchor="w")
            rf = tk.Frame(f, bg=BG); rf.pack(side="right")
            disp = tk.Label(rf, text="", bg=BG, fg=color,
                            font=("Segoe UI", 12, "bold"), width=6, anchor="e")
            disp.pack(side="left", padx=(0, PAD_SM))
            sb_h, sb_m = _spinpair(rf, int(lo), int(hi))
            _u = [False]
            def _ref(*_):
                v = var_h.get(); h = int(v); m = round((v - h) * 60)
                if m >= 60: h += 1; m = 0
                disp.config(text=f"{h:02d}:{m:02d}")
            def _s2sp(*_):
                if _u[0]: return
                _u[0] = True
                v = var_h.get(); h = int(v); m = round((v - h) * 60)
                if m >= 60: h += 1; m = 0
                sb_h.delete(0, "end"); sb_h.insert(0, str(h))
                sb_m.delete(0, "end"); sb_m.insert(0, str(m))
                _ref(); _u[0] = False
            def _sp2s(*_):
                if _u[0]: return
                _u[0] = True
                try:
                    h = max(int(lo), min(int(hi), int(sb_h.get())))
                    m = max(0, min(59, int(sb_m.get())))
                except ValueError: _u[0] = False; return
                var_h.set(round(h + m / 60, 10)); _ref(); _u[0] = False
            var_h.trace_add("write", _s2sp)
            for sb in (sb_h, sb_m):
                sb.config(command=_sp2s)
                sb.bind("<FocusOut>", _sp2s); sb.bind("<Return>", _sp2s)
            _s2sp()

        def row_mins(label, hint, var_m, color, max_m=600):
            f = tk.Frame(body, bg=BG)
            f.pack(fill=tk.X, padx=PAD_LG, pady=(0, PAD_SM))
            lf = tk.Frame(f, bg=BG); lf.pack(side="left", fill=tk.X, expand=True)
            tk.Label(lf, text=label, bg=BG, fg=FG,
                     font=("Segoe UI", 10, "bold")).pack(anchor="w")
            if hint:
                tk.Label(lf, text=hint, bg=BG, fg=FG2,
                         font=("Segoe UI", 8), wraplength=210, justify="left").pack(anchor="w")
            rf = tk.Frame(f, bg=BG); rf.pack(side="right")
            disp = tk.Label(rf, text="", bg=BG, fg=color,
                            font=("Segoe UI", 12, "bold"), width=6, anchor="e")
            disp.pack(side="left", padx=(0, PAD_SM))
            sb_h, sb_m = _spinpair(rf, 0, max_m // 60)
            _u = [False]
            def _ref(*_):
                t = var_m.get(); h = int(t // 60); m = int(t % 60)
                disp.config(text=f"{h}h {m:02d}m" if h else f"{m} min")
            def _s2sp(*_):
                if _u[0]: return
                _u[0] = True
                t = var_m.get(); h = int(t // 60); m = int(t % 60)
                sb_h.delete(0, "end"); sb_h.insert(0, str(h))
                sb_m.delete(0, "end"); sb_m.insert(0, str(m))
                _ref(); _u[0] = False
            def _sp2s(*_):
                if _u[0]: return
                _u[0] = True
                try:
                    h = max(0, min(max_m // 60, int(sb_h.get())))
                    m = max(0, min(59, int(sb_m.get())))
                except ValueError: _u[0] = False; return
                var_m.set(min(max_m, h * 60 + m)); _ref(); _u[0] = False
            var_m.trace_add("write", _s2sp)
            for sb in (sb_h, sb_m):
                sb.config(command=_sp2s)
                sb.bind("<FocusOut>", _sp2s); sb.bind("<Return>", _sp2s)
            _s2sp()

        def row_decimal(label, hint, var, lo, hi, color, step=0.5):
            f = tk.Frame(body, bg=BG)
            f.pack(fill=tk.X, padx=PAD_LG, pady=(0, PAD_SM))
            lf = tk.Frame(f, bg=BG); lf.pack(side="left", fill=tk.X, expand=True)
            tk.Label(lf, text=label, bg=BG, fg=FG,
                     font=("Segoe UI", 10, "bold")).pack(anchor="w")
            if hint:
                tk.Label(lf, text=hint, bg=BG, fg=FG2,
                         font=("Segoe UI", 8), wraplength=210, justify="left").pack(anchor="w")
            rf = tk.Frame(f, bg=BG); rf.pack(side="right")
            disp = tk.Label(rf, text="", bg=BG, fg=color,
                            font=("Segoe UI", 12, "bold"), width=6, anchor="e")
            disp.pack(side="left", padx=(0, PAD_SM))
            sc = tk.Scale(rf, variable=var, from_=lo, to=hi, resolution=step,
                          orient=tk.HORIZONTAL, bg=BG, fg=FG,
                          troughcolor=C.DIVIDER.value, highlightthickness=0,
                          showvalue=False, length=110)
            sc.pack(side="left")
            def _ref(*_): disp.config(text=f"{var.get():.1f} h")
            var.trace_add("write", _ref); _ref()

        # ── Variables ─────────────────────────────────────────────────────────
        goal_var   = tk.DoubleVar(value=self.tracker.daily_goal)
        credit_var = tk.DoubleVar(value=self.tracker.daily_credit_mins)
        pause_var  = tk.DoubleVar(value=self.tracker.default_pause_mins)
        legal_var  = tk.DoubleVar(value=self.tracker.min_legal_pause_mins)
        limit_var  = tk.DoubleVar(value=self.tracker.legal_work_limit_h)
        legal2_var = tk.DoubleVar(value=self.tracker.min_legal_pause_2_mins)
        limit2_var = tk.DoubleVar(value=self.tracker.legal_work_limit_2_h)
        warn_var   = tk.DoubleVar(value=self.tracker.pause_warn_before_mins)
        core_s_var = tk.DoubleVar(value=self.tracker.core_start_h)
        core_e_var = tk.DoubleVar(value=self.tracker.core_end_h)

        # ── ⏱ Working Hours ───────────────────────────────────────────────────
        section("⏱  WORKING HOURS")
        row_hhmm("Daily Goal",    "Target hours per day",           goal_var,   0, 12, C.OVERTIME.value)
        row_mins ("Daily Credit", "Deducted from goal (flex)",       credit_var, C.ACCENT.value)

        # ── ☕ Break Rules ─────────────────────────────────────────────────────
        section("☕  BREAK RULES")
        row_mins   ("Target Break",          "Planned break – affects leave time",       pause_var, C.PAUSE.value)
        row_mins   ("Legal Min. Break",      "Standard required break",                  legal_var, C.WARN.value)
        row_decimal("Break Req. After",      "Work time before standard break",          limit_var, 1.0, 10.0, C.WARN.value)
        row_mins   ("Legal Min. Break 2",    "Extended required break (e.g. 45m)",       legal2_var, C.WARN.value)
        row_decimal("Break 2 Req. After",    "Work time before extended break (e.g. 9h)", limit2_var, 1.0, 12.0, C.WARN.value)
        row_mins   ("Break Warning",         "Notify X min before break deadline",       warn_var,  C.SUBTEXT.value, max_m=120)

        # ── 🕘 Core Hours ──────────────────────────────────────────────────────
        section("🕘  CORE HOURS")
        tk.Label(body, text="Shows balance if you leave exactly at core hours end.",
                 bg=BG, fg=FG2, font=("Segoe UI", 8)).pack(
                     anchor="w", padx=PAD_LG, pady=(0, PAD_SM))
        row_hhmm("Core Start", "", core_s_var,  0, 12, C.OVERTIME.value)
        row_hhmm("Core End",   "", core_e_var,  8, 20, C.NEGATIVE.value)

        tk.Frame(body, bg=BG, height=PAD_LG).pack()

        # ── Save button (fixed at bottom) ─────────────────────────────────────
        bf = tk.Frame(win, bg=C.SURFACE.value,
                      highlightbackground=C.DIVIDER.value, highlightthickness=1)
        bf.pack(fill=tk.X, side="bottom")

        def _save():
            self.tracker.daily_goal             = goal_var.get()
            self.tracker.default_pause_mins     = pause_var.get()
            self.tracker.min_legal_pause_mins   = legal_var.get()
            self.tracker.min_legal_pause_2_mins = legal2_var.get()
            self.tracker.daily_credit_mins      = credit_var.get()
            self.tracker.pause_warn_before_mins = warn_var.get()
            self.tracker.legal_work_limit_h     = limit_var.get()
            self.tracker.legal_work_limit_2_h   = limit2_var.get()
            self.tracker.core_start_h           = core_s_var.get()
            self.tracker.core_end_h             = core_e_var.get()
            self.tracker.save_data()
            win.destroy()

        _btn(bf, "💾 Save", C.ACCENT.value, command=_save, width=14
             ).pack(pady=PAD_MD, padx=PAD_LG, anchor="w")
        win.protocol("WM_DELETE_WINDOW", win.destroy)


    def open_simulator(self):
        win = self._make_popup("What-if Planner")
        self._position_above(win)
        win.geometry("370x530")

        BG, FG, FG2 = C.BACKGROUND.value, C.TEXT.value, C.SUBTEXT.value

        tk.Label(win, text="🧮  What-if Planner", bg=BG, fg=C.ACCENT.value,
                 font=("Segoe UI", 13, "bold")).pack(pady=(PAD_LG, PAD_SM), padx=PAD_LG, anchor="w")
        tk.Label(win, text="  Enter your hours — see balance & leave time.",
                 bg=BG, fg=FG2, font=("Segoe UI", 9)).pack(padx=PAD_LG, anchor="w")
        _divider(win, padx=PAD_LG, pady=(PAD_SM, PAD_MD))

        inp_f = tk.Frame(win, bg=BG)
        inp_f.pack(fill=tk.X, padx=PAD_LG)

        # Prefill clock-in with real value if already tracked
        if self.tracker.start_time_stamp > 0:
            sd = datetime.fromtimestamp(self.tracker.start_time_stamp)
            def_in_h, def_in_m = sd.hour, sd.minute
        else:
            def_in_h, def_in_m = 8, 0

        def make_time_row(parent, label, def_h, def_m, col):
            """Returns (h_var, m_var). Uses grid so entries never wrap."""
            row_f = tk.Frame(parent, bg=BG)
            row_f.pack(fill=tk.X, pady=3)
            row_f.columnconfigure(1, weight=1)
            tk.Label(row_f, text=label, bg=BG, fg=FG2,
                     font=("Segoe UI", 10, "bold"), anchor="w").grid(
                         row=0, column=0, sticky="w")
            time_f = tk.Frame(row_f, bg=BG)
            time_f.grid(row=0, column=1, sticky="e")
            h_var = tk.StringVar(value=f"{def_h:02d}")
            m_var = tk.StringVar(value=f"{def_m:02d}")
            tk.Entry(time_f, textvariable=h_var, width=3, justify="center",
                     font=("Segoe UI", 12), bg=C.SURFACE.value, fg=col,
                     relief="flat", bd=0, insertbackground=col).pack(side="left", ipady=4)
            tk.Label(time_f, text=":", bg=BG, fg=FG,
                     font=("Segoe UI", 13, "bold")).pack(side="left", padx=2)
            tk.Entry(time_f, textvariable=m_var, width=3, justify="center",
                     font=("Segoe UI", 12), bg=C.SURFACE.value, fg=col,
                     relief="flat", bd=0, insertbackground=col).pack(side="left", ipady=4)
            return h_var, m_var

        sh_var, sm_var = make_time_row(inp_f, "Clock In",  def_in_h, def_in_m, C.OVERTIME.value)
        eh_var, em_var = make_time_row(inp_f, "Clock Out", 16, 30,             C.NEGATIVE.value)

        bp_f = tk.Frame(inp_f, bg=BG)
        bp_f.pack(fill=tk.X, pady=(PAD_MD, 2))
        bp_f.columnconfigure(1, weight=1)
        tk.Label(bp_f, text="Break (min)", bg=BG, fg=FG2,
                 font=("Segoe UI", 10, "bold"), anchor="w").grid(row=0, column=0, sticky="w")
        p_var = tk.StringVar(value=str(int(self.tracker.default_pause_mins)))
        tk.Entry(bp_f, textvariable=p_var, width=6, justify="center",
                 font=("Segoe UI", 12), bg=C.SURFACE.value, fg=FG,
                 relief="flat", bd=0, insertbackground=FG).grid(
                     row=0, column=1, sticky="e", ipady=4)

        _divider(win, padx=PAD_LG, pady=(PAD_MD, PAD_MD))

        res_f = tk.Frame(win, bg=BG)
        res_f.pack(fill=tk.BOTH, expand=True, padx=PAD_LG)
        res_f.columnconfigure(1, weight=1)

        _row_idx = [0]
        def res_row(label, color=FG, bold=False):
            i = _row_idx[0]; _row_idx[0] += 1
            tk.Label(res_f, text=label, bg=BG, fg=FG2,
                     font=("Segoe UI", 10), anchor="w").grid(
                         row=i, column=0, sticky="w", pady=3)
            val = tk.Label(res_f, text="–", bg=BG, fg=color,
                           font=("Segoe UI", 11, "bold" if bold else "normal"), anchor="e")
            val.grid(row=i, column=1, sticky="e", pady=3)
            return val

        l_dur = res_row("Gross time:")
        l_pau = res_row("Effective break:")
        l_eff = res_row("Net work time:")
        # divider row
        div_lbl = tk.Frame(res_f, bg=C.DIVIDER.value, height=1)
        div_lbl.grid(row=_row_idx[0], column=0, columnspan=2, sticky="ew", pady=4)
        _row_idx[0] += 1
        l_lv  = res_row("Leave at goal:",      C.ACCENT.value,    bold=True)
        l_chg = res_row("Balance change today:", bold=True)
        l_end = res_row("Total balance after:", bold=True)

        def recalc(*_):
            try:
                sh = max(0, min(23, int(sh_var.get() or 0)))
                sm = max(0, min(59, int(sm_var.get() or 0)))
                eh = max(0, min(23, int(eh_var.get() or 0)))
                em = max(0, min(59, int(em_var.get() or 0)))
                pm = max(0, int(p_var.get() or 0))
            except ValueError:
                return

            t_start   = sh * 60 + sm
            t_end     = eh * 60 + em
            if t_end <= t_start:
                t_end += 24 * 60

            gross_min = t_end - t_start
            temp_net  = max(0, gross_min - pm)

            # Required pause based on net work (legal rules)
            req_pause = 0
            if temp_net >= self.tracker.legal_work_limit_2_h * 60:
                req_pause = self.tracker.min_legal_pause_2_mins
            elif temp_net >= self.tracker.legal_work_limit_h * 60:
                req_pause = self.tracker.min_legal_pause_mins

            eff_pause = max(pm, req_pause)
            net_work  = max(0, gross_min - eff_pause)

            l_dur.config(text=f"{int(gross_min // 60)}h {int(gross_min % 60):02d}m")
            l_pau.config(text=f"{int(eff_pause)} min",
                         fg=C.WARN.value if eff_pause > pm else FG)
            l_eff.config(text=f"{int(net_work // 60)}h {int(net_work % 60):02d}m")

            eff_goal_min = self.tracker.daily_goal * 60 - self.tracker.daily_credit_mins
            diff_min     = net_work - eff_goal_min

            # ── Leave at goal: when should you leave given clock-in & goal? ──
            # Required pause for the goal amount of work
            req_pause_goal = 0
            if eff_goal_min >= self.tracker.legal_work_limit_2_h * 60:
                req_pause_goal = self.tracker.min_legal_pause_2_mins
            elif eff_goal_min >= self.tracker.legal_work_limit_h * 60:
                req_pause_goal = self.tracker.min_legal_pause_mins
            lag_min      = max(pm, req_pause_goal)  # user-entered break or legal min
            goal_leave   = t_start + eff_goal_min + lag_min
            gl_h = int((goal_leave // 60) % 24)
            gl_m = int(goal_leave % 60)
            l_lv.config(text=f"{gl_h:02d}:{gl_m:02d} Uhr")

            sign_chg = "+" if diff_min >= 0 else "−"
            col_chg  = C.OVERTIME.value if diff_min >= 0 else C.NEGATIVE.value
            l_chg.config(
                text=f"{sign_chg}{int(abs(diff_min) // 60):02d}:{int(abs(diff_min) % 60):02d} h",
                fg=col_chg
            )

            start_bal  = self._get_start_of_day_balance()
            new_bal    = start_bal + diff_min * 60
            sign_end   = "+" if new_bal >= 0 else "−"
            col_end    = C.OVERTIME.value if new_bal >= 0 else C.NEGATIVE.value
            h_end = int(abs(new_bal) // 3600)
            m_end = int((abs(new_bal) % 3600) // 60)
            l_end.config(text=f"{sign_end}{h_end:02d}:{m_end:02d} h", fg=col_end)

        for var in (sh_var, sm_var, eh_var, em_var, p_var):
            var.trace_add("write", recalc)

        recalc()
        win.protocol("WM_DELETE_WINDOW", win.destroy)


    def open_auto_overtime(self):
        win = self._make_popup("AutoOvertime Planner")
        self._position_above(win, diagonal=True)
        win.geometry("820x560")
        win.resizable(True, True)

        BG  = C.BACKGROUND.value
        ACC = C.ACCENT.value
        TXT = C.TEXT.value
        BTN = C.BUTTON.value
        POS = C.OVERTIME.value
        NEG = C.NEGATIVE.value
        PAU = C.PAUSE.value
        SUB = C.SUBTEXT.value

        tb = tk.Frame(win, bg=BG)
        tb.pack(fill=tk.X, padx=PAD_LG, pady=(PAD_LG, 0))
        tk.Label(tb, text="AutoOvertime Planner", bg=BG, fg=ACC,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Label(tb, text="  Plan how to work down your balance over N days.",
                 bg=BG, fg=SUB, font=("Segoe UI", 9)).pack(side="left")
        _divider(win, padx=PAD_LG, pady=(PAD_SM, PAD_SM))

        body = tk.Frame(win, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=PAD_LG, pady=PAD_SM)
        body.columnconfigure(0, minsize=270, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # ── Left panel ────────────────────────────────────────────────────────
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, PAD_LG))

        def seclbl(text):
            tk.Label(left, text=text.upper(), bg=BG, fg=BTN,
                     font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(PAD_LG, 1))
            tk.Frame(left, bg=BTN, height=1).pack(fill=tk.X)

        def vallbl(color=TXT, size=12):
            lbl = tk.Label(left, bg=BG, fg=color, font=("Segoe UI", size, "bold"))
            lbl.pack(anchor="w", pady=(PAD_SM, 0))
            return lbl

        def mkslider(variable, from_, to, resolution):
            tk.Scale(left, variable=variable, from_=from_, to=to, resolution=resolution,
                     orient=tk.HORIZONTAL, bg=BG, fg=TXT, troughcolor=C.DIVIDER.value,
                     highlightthickness=0, showvalue=False, length=240).pack(anchor="w", pady=(2, 0))

        seclbl("Current Balance")
        bal_var  = tk.DoubleVar(value=round(self.tracker.total_balance_seconds / 3600, 2))
        bal_disp = vallbl(POS if self.tracker.total_balance_seconds >= 0 else NEG)
        def upd_bal(*_):
            v = bal_var.get(); sign = "+" if v >= 0 else ""
            h = int(abs(v)); m = round((abs(v)-h)*60)
            bal_disp.config(text=f"{sign}{h:02d}:{m:02d} h",
                            fg=POS if v >= 0 else NEG)
        bal_var.trace_add("write", upd_bal)
        mkslider(bal_var, -20.0, 20.0, 0.25)
        upd_bal()

        seclbl("Fixed time mode")
        mode_var = tk.StringVar(value="arrive")
        mf = tk.Frame(left, bg=BG)
        mf.pack(anchor="w", pady=(PAD_SM, PAD_SM))
        btn_arrive = _btn(mf, "Arrive at", POS, command=lambda: mode_var.set("arrive"), width=8, pady=PAD_SM)
        btn_leave  = _btn(mf, "Leave at",  NEG, command=lambda: mode_var.set("leave"),  width=8, pady=PAD_SM)
        btn_arrive.pack(side="left", padx=(0, PAD_SM))
        btn_leave.pack(side="left")
        time_var  = tk.DoubleVar(value=8.0)
        time_disp = vallbl(POS)
        def upd_time(*_):
            v = time_var.get(); h = int(v); m = round((v-h)*60)
            time_disp.config(text=f"{h:02d}:{m:02d} Uhr",
                             fg=POS if mode_var.get()=="arrive" else NEG)
        def upd_mode(*_):
            m = mode_var.get()
            btn_arrive.config(bg=POS if m=="arrive" else BTN)
            btn_leave.config( bg=NEG if m=="leave"  else BTN)
            upd_time()
        time_var.trace_add("write", upd_time)
        mode_var.trace_add("write", upd_mode)
        mkslider(time_var, 0, 24.0, 0.25)
        upd_mode()

        seclbl("Distribution")
        days_var  = tk.IntVar(value=5)
        days_disp = vallbl(TXT)
        def upd_days(*_):
            days_disp.config(text=f"{days_var.get()} days")
        days_var.trace_add("write", upd_days)
        mkslider(days_var, 1, 30, 1)
        upd_days()

        # Weekends (Sat/Sun) always excluded from plan

        seclbl("Summary")
        summary_lbl = tk.Label(left, bg=BG, fg=SUB, font=("Segoe UI", 9),
                               justify="left", wraplength=240)
        summary_lbl.pack(anchor="w")

        # ── Right panel (NO scrollbar – just frame) ───────────────────────────
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")

        # Header row (fixed, always visible)
        hdr = tk.Frame(right, bg=BG)
        hdr.pack(fill=tk.X, padx=PAD_SM, pady=(PAD_SM, 2))
        for txt, clr, w in [("Day", BTN, 12), ("Arrive", POS, 8),
                              ("Leave", NEG, 8), ("Work", TXT, 8), ("Break", PAU, 7)]:
            tk.Label(hdr, text=txt, bg=BG, fg=clr,
                     font=("Segoe UI", 9, "bold"), width=w, anchor="w"
                     ).pack(side="left", padx=2)
        tk.Frame(right, bg=C.DIVIDER.value, height=1).pack(fill=tk.X, padx=PAD_SM, pady=2)

        # Scrollable cards area — only shown when needed
        cards_outer = tk.Frame(right, bg=BG)
        cards_outer.pack(fill=tk.BOTH, expand=True)

        canvas_r    = tk.Canvas(cards_outer, bg=BG, highlightthickness=0)
        vsb         = tk.Scrollbar(cards_outer, orient="vertical", command=canvas_r.yview)
        canvas_r.configure(yscrollcommand=vsb.set)
        cards_frame = tk.Frame(canvas_r, bg=BG)
        cid         = canvas_r.create_window(0, 0, window=cards_frame, anchor="nw")

        cards_frame.bind("<Configure>", lambda e: _update_scroll())
        canvas_r.bind("<Configure>",    lambda e: canvas_r.itemconfig(cid, width=e.width))

        def _update_scroll(*_):
            canvas_r.update_idletasks()
            bbox = canvas_r.bbox("all")
            if not bbox:
                return
            content_h = bbox[3] - bbox[1]
            canvas_h  = canvas_r.winfo_height()
            # Clamp scrollregion: if content fits, set region = canvas so no overscroll
            if content_h <= canvas_h:
                canvas_r.configure(scrollregion=(0, 0, bbox[2], canvas_h))
                vsb.pack_forget()
            else:
                canvas_r.configure(scrollregion=bbox)
                vsb.pack(side="right", fill="y")
            canvas_r.pack(side="left", fill="both", expand=True)

        canvas_r.pack(side="left", fill="both", expand=True)
        def _on_scroll_r(e):
            canvas_r.yview_scroll(int(-1 * e.delta / 120), "units")
        canvas_r.bind("<Enter>", lambda _: canvas_r.bind_all("<MouseWheel>", _on_scroll_r))
        canvas_r.bind("<Leave>", lambda _: canvas_r.unbind_all("<MouseWheel>"))

        def fmt_dur(secs):
            h = int(abs(secs)//3600); m = int((abs(secs)%3600)//60)
            return f"{h:02d}:{m:02d}"

        last_snap = {}

        def compute(force=False):
            snap = dict(
                bal=bal_var.get(), goal=self.tracker.daily_goal,
                pause=self.tracker.default_pause_mins,
                credit=self.tracker.daily_credit_mins,
                time=time_var.get(), days=days_var.get(),
                mode=mode_var.get()
            )
            if not force and snap == last_snap:
                return
            last_snap.clear(); last_snap.update(snap)

            for w in cards_frame.winfo_children():
                w.destroy()

            ndays       = snap["days"]
            goal_h      = snap["goal"]
            pause_h     = snap["pause"] / 60
            credit_h    = snap["credit"] / 60
            eff_h       = goal_h - credit_h
            total_bal_h = snap["bal"]
            work_per_day = (eff_h * ndays - total_bal_h) / ndays if ndays else eff_h
            if snap["mode"] == "arrive":
                arrives_fixed = snap["time"]
                leaves_fixed  = arrives_fixed + work_per_day + pause_h
            else:
                leaves_fixed  = snap["time"]
                arrives_fixed = leaves_fixed - work_per_day - pause_h

            # Build N working days (Mon–Fri only, skip Sat/Sun)
            today = datetime.now().date()
            work_days = []
            d = today
            while len(work_days) < ndays:
                if d.weekday() < 5:
                    work_days.append(d)
                d += timedelta(days=1)

            COL_WIDTHS = [("Day", BTN, 12), ("Arrive", POS, 8),
                          ("Leave", NEG, 8), ("Work", TXT, 8), ("Break", PAU, 7)]

            for day in work_days:
                card = tk.Frame(cards_frame, bg=BG,
                                highlightbackground=C.DIVIDER.value, highlightthickness=1)
                card.pack(fill=tk.X, padx=PAD_SM, pady=1)
                tk.Label(card, text=f"{day.strftime('%a')} {day.strftime('%d.%m.')}",
                         bg=BG, fg=TXT, font=("Segoe UI", 10, "bold"),
                         width=12, anchor="w").pack(side="left", padx=2, pady=4)
                for (val, clr), (_, _, w) in zip([
                    (_fmt_hm(arrives_fixed),     POS),
                    (_fmt_hm(leaves_fixed),      NEG),
                    (fmt_dur(work_per_day*3600),  TXT),
                    (fmt_dur(pause_h*3600),       PAU),
                ], COL_WIDTHS[1:]):
                    tk.Label(card, text=val, bg=BG, fg=clr,
                             font=("Segoe UI", 10, "bold"), width=w, anchor="w"
                             ).pack(side="left", padx=2, pady=4)

            canvas_r.after(50, _update_scroll)

            sign = "+" if total_bal_h >= 0 else ""
            summary_lbl.config(
                text=f"Balance: {sign}{total_bal_h:+.2f}h  →  "
                     f"{work_per_day:.2f}h/day  |  Leave: ~{_fmt_hm(leaves_fixed)} Uhr"
            )

        for v in (bal_var, time_var, days_var, mode_var):
            try: v.trace_add("write", lambda *_: compute())
            except Exception: pass
        compute(force=True)
        self._ot_compute = compute

        def on_close():
            self._ot_compute = None
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)

    # ── Launch game ───────────────────────────────────────────────────────────
    def _launch_game(self):
        script_dir = _get_base_dir()
        # 1. any .exe in the same folder that isn't the app itself
        candidates = [
            p for p in script_dir.glob("*.exe")
            if p.stem.lower() not in ("track_me_buddy", "trackmebuddy", "trackme")
        ]
        # 2. fallback: try known names
        if not candidates:
            for name in ("FlappyCube.exe", "game.exe"):
                p = script_dir / name
                if p.exists():
                    candidates = [p]
                    break
        if not candidates:
            messagebox.showinfo("Bored?", "No game executable found next to the app.", parent=self.master)
            return
        target_exe = candidates[0]
        script_dir = str(script_dir)
        try:
            subprocess.Popen(
                str(target_exe), cwd=str(script_dir),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        except Exception as e:
            messagebox.showerror("Launch failed", f"Error: {e}", parent=self.master)

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def format_seconds(seconds):
        neg = seconds < 0
        s   = abs(int(seconds))
        return f"{'−' if neg else ''}{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

    @staticmethod
    def format_hhmm(seconds):
        """Format seconds as ±HH:MM (no seconds – Novatime tracks minutes only)."""
        neg = seconds < 0
        s   = abs(int(seconds))
        return f"{'−' if neg else ''}{s//3600:02d}:{(s%3600)//60:02d}"

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app  = TrackMe(root)

    def _dark_titlebar(win):
        try:
            import ctypes
            win.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            if not hwnd:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr,
                    ctypes.byref(ctypes.c_int(1)),
                    ctypes.sizeof(ctypes.c_int))
        except Exception:
            pass

    root.after(200, lambda: _dark_titlebar(root))
    root.mainloop()
