from enum import Enum

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