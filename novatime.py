from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Browser, Page, Playwright

# ── Browser detection ─────────────────────────────────────────────────────────
# Edge is pre-installed on every Windows machine — always first choice.
# Chrome is used as fallback if Edge is not found.

_EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
    os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
]

_CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

def _find_browser() -> str:
    """Return the path to Edge (preferred) or Chrome. Raises if neither is found."""
    for path in _EDGE_CANDIDATES + _CHROME_CANDIDATES:
        if Path(path).exists():
            _log(f"Browser found: {path}")
            return path
    raise RuntimeError(
        "Neither Edge nor Chrome found!\n"
        "Edge is normally pre-installed on every Windows machine.\n"
        "Please verify that Microsoft Edge is installed."
    )

# ── Confirmation words ────────────────────────────────────────────────────────
# After any booking action NovaTime updates the status area.
# We wait until at least one of these words appears in the page body to confirm
# that the server has processed the request — regardless of which action was used.

_CONFIRMATION_WORDS = [
    "Kommen", "kommen",
    "Gehen", "gehen",
    "Anwesend", "anwesend",
    "Abwesend", "abwesend",
    "Pause", "pause",
    "Dienstgang", "dienstgang",
    "Gebucht", "gebucht",
    "OK",
]

# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class NovaConfig:
    """Connection and behaviour configuration for NovaTime."""

    url: str
    url_journal: str
    username: str
    password: str

    # False = browser window visible (useful for debugging)
    headless: bool = True

    # Default navigation / selector timeout in milliseconds
    timeout: int = 10_000

    # HTTP Basic-Auth credentials for the proxy login dialog that appears
    # when opening the page — usually the same as your Windows login.
    # Leave as None if no proxy dialog appears.
    http_auth_username: str | None = None
    http_auth_password: str | None = None

    # How long to wait (ms) for a confirmation word to appear after a click.
    # Also used as a fallback fixed wait if no word ever appears.
    # Increase on slow connections.
    wait_ms: int = 2000

    # Exact button labels as shown in the NovaTime UI (needs to be adjusted depending on company layout)
    labels: dict[str, str] = field(default_factory=lambda: {
        "kommen": "Kommen",
        "gehen": "Gehen",
        "pause_start": "Pause Start",
        "pause_ende": "Pause Ende",
        "dg_kommen": "DG-Kommen",
        "dg_gehen": "DG-Gehen",
    })

# ── Main class ────────────────────────────────────────────────────────────────

class NovaTime:
    """
    Controls NovaTime bookings via browser automation.

    Recommended usage as a context manager:
        async with NovaTime(cfg) as nt:
            await nt.kommen()

    Or manually:
        nt = NovaTime(cfg)
        await nt.start()
        await nt.kommen()
        await nt.stop()
    """

    def __init__(self, config: NovaConfig) -> None:
        self.cfg = config
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Launch the browser and navigate to the NovaTime page."""
        self._playwright = await async_playwright().start()

        exe = _find_browser()
        _log(f"Starting Chromium engine with: {Path(exe).name}")

        self._browser = await self._playwright.chromium.launch(
            headless=self.cfg.headless,
            executable_path=exe,
        )

        # Pass HTTP Basic-Auth via browser context so the proxy login dialog
        # is handled automatically without any user interaction.
        http_credentials = None
        if self.cfg.http_auth_username:
            http_credentials = {
                "username": self.cfg.http_auth_username,
                "password": self.cfg.http_auth_password or "",
            }
            _log(f"HTTP auth configured for user: {self.cfg.http_auth_username}")

        context = await self._browser.new_context(http_credentials=http_credentials)
        self._page = await context.new_page()
        self._page.set_default_timeout(self.cfg.timeout)

        _log(f"Opening {self.cfg.url} ...")
        await self._page.goto(self.cfg.url, wait_until="networkidle")
        _log("Page loaded.")

    async def stop(self) -> None:
        """Close the browser cleanly."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._page = self._browser = self._playwright = None
        _log("Browser closed.")

    async def __aenter__(self) -> "NovaTime":
        await self.start()
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop()

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _fill_credentials(self) -> None:
        """Fill in the Name and Password fields on the NovaTime login form."""
        page = self._page
        _log(f"Filling credentials for '{self.cfg.username}' ...")
        await page.fill(
            'input[name*="user" i], input[id*="user" i], '
            'input[placeholder*="Name" i], input[type="text"]:visible',
            self.cfg.username,
        )
        await page.fill(
            'input[name*="pass" i], input[id*="pass" i], '
            'input[placeholder*="Pass" i], input[type="password"]:visible',
            self.cfg.password,
        )

    async def _click_button(self, label: str) -> None:
        """Click a button identified by its visible label text."""
        page = self._page
        _log(f"Clicking button '{label}' ...")
        btn = page.get_by_role("button", name=label, exact=True)
        if not await btn.is_visible():
            # Fallback: try input[value] or anchor with exact text
            btn = page.locator(
                f'input[type="button"][value="{label}"], '
                f'input[type="submit"][value="{label}"], '
                f'a:text-is("{label}")'
            )
        await btn.click()

    async def _wait_for_confirmation(self) -> None:
        """
        Wait until any word from _CONFIRMATION_WORDS appears in the page body,
        confirming the server processed the last action.
        Falls back to a fixed wait of wait_ms if none of the words appear in time.
        """
        # Build a JS expression that returns true when any confirmation word is present
        checks = " || ".join(
            f"document.body.innerText.includes('{w}')"
            for w in _CONFIRMATION_WORDS
        )
        try:
            await self._page.wait_for_function(checks, timeout=self.cfg.wait_ms)
            _log("Confirmation word detected in page.")
        except Exception:
            _log(
                f"No confirmation word appeared within {self.cfg.wait_ms}ms — "
                "falling back to fixed wait."
            )
            await self._page.wait_for_timeout(self.cfg.wait_ms)

    # ── Bookings ──────────────────────────────────────────────────────────────

    async def buchen(self, aktion: str) -> None:
        """
        Perform a time booking and wait for server confirmation.

        Parameters
        ----------
        aktion : str
            One of: 'kommen' | 'gehen' | 'pause_start' | 'pause_ende' |
                    'dg_kommen' | 'dg_gehen'
        """
        assert self._page, "NovaTime not started — call start() first."

        if aktion not in self.cfg.labels:
            raise ValueError(
                f"Unknown action '{aktion}'. Allowed: {list(self.cfg.labels)}"
            )

        label = self.cfg.labels[aktion]

        await self._fill_credentials()
        await self._click_button(label)
        await self._page.wait_for_load_state("networkidle")
        await self._wait_for_confirmation()

        _log(f"✓ '{label}' booked successfully.")

    # ── Convenience methods ───────────────────────────────────────────────────

    async def kommen(self) -> None: await self.buchen("kommen")
    async def gehen(self) -> None: await self.buchen("gehen")
    async def pause_start(self) -> None: await self.buchen("pause_start")
    async def pause_ende(self) -> None: await self.buchen("pause_ende")
    async def dg_kommen(self) -> None: await self.buchen("dg_kommen")
    async def dg_gehen(self) -> None: await self.buchen("dg_gehen")

    async def get_journal(self) -> dict:
        """
        Log in, navigate to User Journal via the sidebar, and extract
        the full time-tracking table for the current month.

        Returns
        -------
        dict with keys:
            "header"   : list[str]        – column headers
            "rows"     : list[dict]       – each row as {header: value, ...}
            "raw_rows" : list[list[str]]  – raw cell values (no header mapping)
            "meta"     : dict             – page metadata (name, persnr, month)
            "summary"  : list[dict]       – bottom summary rows (Nachtzuschlag etc.)

        Frame layout
        ------------
        F1 = top bar (date / company name)
        F2 = sidebar (navigation buttons)
        F3 = name bar (PersNr / Name)
        F4 = main content (journal table loads here when User Journal is clicked)
        """
        assert self._page, "NovaTime not started — call start() first."
        page = self._page

        # ── Helper: find a frame by name ──────────────────────────────────────
        def _frame(name: str):
            return page.frame(name=name)

        # ── Step 1: wait for frameset to settle, then log in via frame F3 ─────
        _log("Waiting for frames to load ...")
        await page.wait_for_timeout(1_500)

        f3 = _frame("F3")
        if f3 is None:
            await page.wait_for_timeout(2_000)
            f3 = _frame("F3")
        if f3 is None:
            raise RuntimeError("Frame F3 (name bar) not found — page structure unexpected.")

        # Check if login form is present in F3
        _log("Checking for login form in frame F3 ...")
        try:
            await f3.wait_for_selector('input[name="Ident1"]', timeout=3_000)
            _log("Login form detected — filling credentials ...")
            await f3.fill('input[name="Ident1"]', self.cfg.username)
            await f3.fill('input[name="Ident2"]', self.cfg.password)
            _log("Clicking Anmelden ...")
            await f3.click('input[name="Btn0001"]')
            # After login the frameset reloads — wait for it
            await page.wait_for_timeout(2_000)
            _log("Logged in via form.")
        except Exception as _e:
            _log(f"No login form in F3 ({_e}) — assuming already authenticated.")

        # ── Step 2: click User Journal in the sidebar (frame F2) ────────
        _log("Navigating to User Journal via frame F2 ...")
        f2 = _frame("F2")
        if f2 is None:
            await page.wait_for_timeout(1_000)
            f2 = _frame("F2")
        if f2 is None:
            raise RuntimeError("Frame F2 (sidebar) not found.")

        try:
            await f2.wait_for_selector('input[value="Mitarbeiterjournal"]', timeout=5_000)
            await f2.click('input[value="Mitarbeiterjournal"]')
        except Exception:
            # Fallback: try button or anchor
            try:
                await f2.click("text=Mitarbeiterjournal")
            except Exception as _e:
                raise RuntimeError(f"Could not click Mitarbeiterjournal in sidebar: {_e}")

        _log("Clicked User Journal — waiting for table in F4 ...")

        # ── Step 3: wait for journal table in F4 ──────────────────────────────
        # The sidebar (F2) submits with target="F4", so the journal loads in F4.
        await page.wait_for_timeout(1_000)
        f4 = _frame("F4")
        if f4 is None:
            await page.wait_for_timeout(1_000)
            f4 = _frame("F4")
        if f4 is None:
            raise RuntimeError("Frame F4 (journal content) not found.")

        try:
            await f4.wait_for_selector("table", timeout=8_000)
            _log("Journal table detected in F4.")
        except Exception:
            _log("Table wait timed out — reading F4 anyway.")

        # ── Step 4: extract metadata ──────────────────────────────────────────
        # Re-fetch f3 — it gets detached after the login-triggered frameset reload.
        f3 = _frame("F3")
        meta: dict = {}

        f3_text = (await f3.inner_text("body")).strip() if f3 else ""
        m = re.search(r"PersNr[:\s]+(\d+)", f3_text)
        if m:
            meta["persnr"] = m.group(1).strip()
        m = re.search(r"Name[:\s]+([^\n]+)", f3_text)
        if m:
            meta["name"] = m.group(1).strip()

        f4_text = (await f4.inner_text("body")).strip()
        m = re.search(r"Mitarbeiterjournal\s+([^\n]+)", f4_text)
        if m:
            meta["month"] = m.group(1).strip()

        _log(f"Meta extracted: {meta}")

        # ── Step 5: extract the main journal table from F4 ────────────────────
        tables = await f4.query_selector_all("table")
        _log(f"Found {len(tables)} table(s) in F4.")

        best_table = None
        best_row_count = 0
        for tbl in tables:
            rows = await tbl.query_selector_all("tr")
            if len(rows) > best_row_count:
                best_row_count = len(rows)
                best_table = tbl

        if best_table is None:
            _log("No table found in F4 — returning empty result.")
            return {"header": [], "rows": [], "raw_rows": [], "meta": meta, "summary": []}

        _log(f"Using table with {best_row_count} rows.")
        all_rows = await best_table.query_selector_all("tr")

        # ── Step 6: split header rows from data rows ──────────────────────────
        header: list[str] = []
        data_start = 0
        raw_headers: list[list[str]] = []

        for i, row in enumerate(all_rows[:3]):
            cells = await row.query_selector_all("th, td")
            texts = [(await c.inner_text()).strip().replace("\n", " ") for c in cells]
            if any(t in ("Datum", "Wt", "Ist", "Soll", "Pause", "Saldo") for t in texts):
                raw_headers.append(texts)
                data_start = i + 1
            else:
                break

        if len(raw_headers) == 2:
            top, bot = raw_headers[0], raw_headers[1]
            max_len = max(len(top), len(bot))
            top += [""] * (max_len - len(top))
            bot += [""] * (max_len - len(bot))
            header = [f"{t} {b}".strip() if t and b else (t or b) for t, b in zip(top, bot)]
        elif raw_headers:
            header = raw_headers[0]

        # Deduplicate headers
        seen: dict[str, int] = {}
        clean_header: list[str] = []
        for h in header:
            if not h:
                h = f"Col{len(clean_header)}"
            if h in seen:
                seen[h] += 1
                h = f"{h}_{seen[h]}"
            else:
                seen[h] = 0
            clean_header.append(h)
        header = clean_header

        # ── Step 7: parse data rows ───────────────────────────────────────────
        raw_rows: list[list[str]] = []
        summary_raw: list[list[str]] = []
        in_summary = False

        for row in all_rows[data_start:]:
            cells = await row.query_selector_all("td, th")
            texts = [(await c.inner_text()).strip().replace("\n", " ") for c in cells]
            if not any(t for t in texts):
                continue
            if len(texts) < max(2, len(header) // 2):
                in_summary = True
            if in_summary:
                summary_raw.append(texts)
            else:
                while len(texts) < len(header):
                    texts.append("")
                raw_rows.append(texts[:len(header)])

        rows: list[dict] = [dict(zip(header, r)) for r in raw_rows]

        summary: list[dict] = []
        for sr in summary_raw:
            pairs = {}
            it = iter(sr)
            for label in it:
                value = next(it, "")
                if label:
                    pairs[label] = value
            if pairs:
                summary.append(pairs)

        _log(f"✓ Journal extracted: {len(rows)} data rows, {len(summary)} summary entries.")
        return {
            "header": header,
            "rows": rows,
            "raw_rows": raw_rows,
            "meta": meta,
            "summary": summary,
        }

    async def info(self) -> str:
        """
        Click the Info button and return the Saldo (time balance) string
        from the page.

        Returns
        -------
        str
            e.g. "Saldo: -7,01 Std"
            Falls back to the full page body text if no Saldo line is found.
        """
        assert self._page, "NovaTime not started — call start() first."
        page = self._page

        await self._fill_credentials()
        await self._click_button("Info")
        await page.wait_for_load_state("networkidle")

        # Wait until "Saldo:" is present before reading the page
        try:
            await page.wait_for_function(
                "document.body.innerText.includes('Saldo:')",
                timeout=self.cfg.wait_ms,
            )
        except Exception:
            _log("'Saldo:' did not appear — reading page anyway.")

        text = (await page.inner_text("body")).strip()
        match = re.search(r"Saldo:.*?Std", text)
        if match:
            result = match.group(0).strip().replace("\xa0", " ")
            _log(f"Saldo extracted: {result!r}")
        else:
            _log("No 'Saldo:' line found — returning full page text.")
            result = text

        _log("✓ Info retrieved.")
        return result

# ── Internal logging ──────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(f"[NovaTime {datetime.now().strftime('%H:%M:%S')}] {msg}")
