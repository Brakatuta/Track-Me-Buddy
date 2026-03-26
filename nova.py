import asyncio
import json

from .novatime import NovaTime, NovaConfig

cfg: NovaConfig | None = None


def init_config(cfg_url, cfg_username, cfg_password,
                cfg_http_auth_username, cfg_http_auth_password, cfg_headless,
                cfg_url_journal=""):
    global cfg
    cfg = NovaConfig(
        url                = cfg_url,
        url_journal        = cfg_url_journal,
        username           = cfg_username,
        password           = cfg_password,
        http_auth_username = cfg_http_auth_username,
        http_auth_password = cfg_http_auth_password,
        headless           = cfg_headless,
        wait_ms            = 3000,
    )
    print(f"[Nova] Config initialised for user '{cfg_username}' @ {cfg_url}")


# ── Async action implementations ──────────────────────────────────────────────

async def arbeits_beginn():
    async with NovaTime(cfg) as nt:
        await nt.kommen()

async def arbeits_ende():
    async with NovaTime(cfg) as nt:
        await nt.gehen()

async def dienstgang_gehen():
    async with NovaTime(cfg) as nt:
        await nt.dg_gehen()

async def dienstgang_kommen():
    async with NovaTime(cfg) as nt:
        await nt.dg_kommen()

async def pause_start():
    async with NovaTime(cfg) as nt:
        await nt.pause_start()

async def pause_ende():
    async with NovaTime(cfg) as nt:
        await nt.pause_ende()

async def get_saldo():
    async with NovaTime(cfg) as nt:
        return await nt.info()

async def fetch_journal():
    """Fetch the journal table using the journal URL (or fallback to main URL)."""
    if cfg is None:
        raise RuntimeError("Nova config not initialised — call init_config() first.")
    # get_journal() needs the journal-specific URL as the entry point.
    # Build a temporary config that uses url_journal as the primary URL so
    # NovaTime.start() navigates to the correct page.
    active_url = cfg.url_journal if cfg.url_journal else cfg.url
    journal_cfg = NovaConfig(
        url                = active_url,
        url_journal        = cfg.url_journal,
        username           = cfg.username,
        password           = cfg.password,
        http_auth_username = cfg.http_auth_username,
        http_auth_password = cfg.http_auth_password,
        headless           = cfg.headless,
        wait_ms            = cfg.wait_ms,
    )
    async with NovaTime(journal_cfg) as nt:
        return await nt.get_journal()

async def test_journal():
    """Same as fetch_journal but prints a summary to stdout — used for quick testing."""
    result = await fetch_journal()
    meta    = result.get("meta", {})
    rows    = result.get("rows", [])
    header  = result.get("header", [])
    summary = result.get("summary", [])

    print("\n" + "=" * 60)
    print("  JOURNAL — TEST OUTPUT")
    print("=" * 60)
    print(f"  Name    : {meta.get('name',  'n/a')}")
    print(f"  PersNr  : {meta.get('persnr','n/a')}")
    print(f"  Monat   : {meta.get('month', 'n/a')}")
    print(f"  Columns : {len(header)}")
    print(f"  Rows    : {len(rows)}")
    print("-" * 60)

    # Print first 5 non-empty rows as a preview
    printed = 0
    for row in rows:
        if printed >= 5:
            break
        # Only show rows that have at least a date or time value
        if any(row.get(k, "").strip() for k in ("Datum", "von", "bis", "Ist Std", "Ist")):
            print("  " + " | ".join(f"{k}: {v}" for k, v in row.items() if v.strip()))
            printed += 1

    if summary:
        print("-" * 60)
        print("  Summary entries:")
        for s in summary[:4]:
            print("  " + " | ".join(f"{k}: {v}" for k, v in s.items()))

    print("=" * 60 + "\n")
    return result


nova_funcs: dict[str, callable] = {
    "start_work":          arbeits_beginn,
    "end_work":            arbeits_ende,
    "start_business_trip": dienstgang_gehen,
    "end_business_trip":   dienstgang_kommen,
    "start_pause":         pause_start,
    "end_pause":           pause_ende,
    "saldo":               get_saldo,
    "test":                get_saldo,
    "journal":             fetch_journal,
    "test_journal":        test_journal,
}


def run_nova_action(action_type: str):
    """
    Run a NovaTime action synchronously.
    Raises RuntimeError if cfg is not initialised.
    Raises KeyError if action_type is unknown.
    Propagates any exception from the async action so callers can react.
    Returns the action's return value (e.g. the saldo string).
    """
    if cfg is None:
        raise RuntimeError("Nova config not initialised — call init_config() first.")

    action = nova_funcs.get(action_type)
    if action is None:
        raise KeyError(f"Action '{action_type}' not found. Available: {list(nova_funcs)}")

    return_data = asyncio.run(action())

    if isinstance(return_data, str):
        print(f"[Nova] {action_type} result: {return_data}")

    return return_data


# ── Standalone runner ─────────────────────────────────────────────────────────
# Run directly:  python nova.py
# Loads nova_config.json from the same folder, fetches the journal and prints
# the full table to the terminal.

if __name__ == "__main__":
    import sys
    import os
    from pathlib import Path

    # When run directly the relative import doesn't work — re-import novatime
    # from the same directory instead.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from novatime import NovaTime as _NovaTime, NovaConfig as _NovaConfig  # noqa: E402

    # ── Load config ───────────────────────────────────────────────────────────
    config_path = Path(__file__).resolve().parent / "save" / "nova_config.json"
    if not config_path.exists():
        # Fallback: same directory as the script
        config_path = Path(__file__).resolve().parent / "nova_config.json"

    if not config_path.exists():
        print(f"[Nova] ERROR: nova_config.json not found at {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as _f:
        _raw = json.load(_f)

    _url         = _raw.get("url", "")
    _url_journal = _raw.get("url_journal", "")
    _username    = _raw.get("username", "")
    _password    = _raw.get("password", "")
    _proxy_user  = _raw.get("proxy_auth_username", "")
    _proxy_pass  = _raw.get("proxy_auth_password", "")
    _show_window = _raw.get("show_window", True)

    if not _url and not _url_journal:
        print("[Nova] ERROR: No URL found in nova_config.json")
        sys.exit(1)

    print(f"[Nova] Loaded config for user '{_username}'")
    print(f"[Nova] URL         : {_url or '(not set)'}")
    print(f"[Nova] URL Journal : {_url_journal or '(not set, using main URL)'}")

    # ── Build NovaConfig ──────────────────────────────────────────────────────
    _active_url = _url_journal if _url_journal else _url
    _nova_cfg = _NovaConfig(
        url                = _active_url,
        url_journal        = _url_journal,
        username           = _username,
        password           = _password,
        http_auth_username = _proxy_user  or None,
        http_auth_password = _proxy_pass  or None,
        headless           = False,  # always visible when run directly
        wait_ms            = 3000,
    )

    # ── Fetch journal ─────────────────────────────────────────────────────────
    async def _run():
        async with _NovaTime(_nova_cfg) as nt:
            return await nt.get_journal()

    print("\n[Nova] Fetching User Journal ...\n")
    _result = asyncio.run(_run())

    # ── Pretty-print ──────────────────────────────────────────────────────────
    _meta    = _result.get("meta",    {})
    _header  = _result.get("header",  [])
    _rows    = _result.get("rows",    [])
    _summary = _result.get("summary", [])

    # Columns to show (subset of what NovaTime returns — adjust as needed)
    _SHOW_COLS = [
        "Wt", "Datum", "Uhr von", "Zeit bis", "Bu art",
        "Ist Std", "Soll Std", "Pause",
        "Ü-Std > 42 Std", "Tages Saldo", "Wochensal do",
        "Gesamt Saldo", "Tages Plan", "Studium Gesamt",
        "ANW-SUM", "Pause gesamt",
        "Kommentar", "Bemerkungstext",
    ]
    # Keep only columns that actually exist in the extracted header
    _cols = [c for c in _SHOW_COLS if c in _header]
    # Fallback: just use all headers if none of our preferred names matched
    if not _cols:
        _cols = _header

    # Calculate column widths
    _widths = {c: max(len(c), 4) for c in _cols}
    for row in _rows:
        for c in _cols:
            _widths[c] = max(_widths[c], len(str(row.get(c, ""))))

    def _pad(text: str, width: int) -> str:
        return str(text).ljust(width)

    _SEP  = "─"
    _CROSS = "┼"
    _sep_line = _CROSS.join(_SEP * (_widths[c] + 2) for c in _cols)

    def _row_line(row: dict) -> str:
        return "│".join(f" {_pad(row.get(c,''), _widths[c])} " for c in _cols)

    def _header_line() -> str:
        return "│".join(f" {_pad(c, _widths[c])} " for c in _cols)

    # ── Print ─────────────────────────────────────────────────────────────────
    print("=" * (sum(_widths[c] + 3 for c in _cols) - 1))
    print(f"  User Journal  │  {_meta.get('name','?')}  │  "
          f"PersNr {_meta.get('persnr','?')}  │  {_meta.get('month','?')}")
    print("=" * (sum(_widths[c] + 3 for c in _cols) - 1))
    print(_header_line())
    print(_sep_line)

    for _row in _rows:
        # Skip completely empty rows
        if not any(str(_row.get(c, "")).strip() for c in _cols):
            continue
        print(_row_line(_row))

    if _summary:
        print(_sep_line)
        print("  SUMMARY:")
        for _s in _summary:
            print("  " + "   │   ".join(
                f"{k}: {v}" for k, v in _s.items() if v.strip()
            ))

    print("=" * (sum(_widths[c] + 3 for c in _cols) - 1))
    print(f"  {len(_rows)} Zeilen  │  {len(_cols)} Spalten angezeigt")
    print("=" * (sum(_widths[c] + 3 for c in _cols) - 1) + "\n")