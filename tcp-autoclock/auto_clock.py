"""
auto_clock.py
GitHub Actions version — multi-session TimeClock Plus automation with:
- File-based master toggle (ON.flag) that overrides env var TCP_ON
- Holidays + ad-hoc skip dates
- Discord-friendly run status (run_status.txt)
- Duplicate protection via state.json

FILES IN REPO ROOT:
  - schedule.yaml     -> timezone, window_minutes, week:{day:{sessions:[{in,out}, ...]}}
  - holidays.txt      -> YYYY-MM-DD per line (fixed days to skip)
  - skip_dates.txt    -> YYYY-MM-DD per line (ad-hoc skip days)
  - state.json        -> auto-created; records today's actions (in_0, out_0, ...)
  - ON.flag           -> OPTIONAL. If present, first char must be '1' or '0' (1 = ON, 0 = OFF)
                         When present, it OVERRIDES TCP_ON env var.
ENV SECRETS (in GitHub):
  - TCP_URL           -> your WebClock URL
  - TCP_USERNAME      -> External ID
  - TCP_PASSWORD      -> password
REPO VARIABLE (fallback if ON.flag absent):
  - TCP_ON            -> "1" to enable, "0" to pause

USAGE:
  - Run via GitHub Actions workflow (every 5 minutes, UTC). The script decides if it’s time.
  - On success: writes run_status.txt with a short message for Discord.
"""

# ================
# Setup
# ================
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from zoneinfo import ZoneInfo  # Python 3.9+

ROOT = Path(__file__).parent


# ================
# Models
# ================
@dataclass
class Session:
    """Represents a single work block (clock-in & out)."""
    clock_in: str   # "HH:MM" 24h
    clock_out: str  # "HH:MM" 24h


@dataclass
class Config:
    """All configuration the run needs."""
    url: str
    username: str
    password: str
    timezone: ZoneInfo
    window_minutes: int
    week: dict      # schedule per weekday


# ================
# IO helpers
# ================
def write_status(status: str, message: str) -> None:
    """
    Write a single-line status for the workflow/Discord to read.
    status: ok | skip | noop | error
    """
    (ROOT / "run_status.txt").write_text(f"{status.upper()}: {message}\n", encoding="utf-8")


def load_config() -> Config:
    """
    Load secrets (URL/creds) from env and schedule from YAML.
    Returns a Config object used everywhere else.
    """
    url = os.environ.get("TCP_URL", "").strip()
    username = os.environ.get("TCP_USERNAME", "").strip()
    password = os.environ.get("TCP_PASSWORD", "").strip()
    if not (url and username and password):
        write_status("error", "Missing credentials (TCP_URL/TCP_USERNAME/TCP_PASSWORD).")
        raise SystemExit(1)

    sched = yaml.safe_load((ROOT / "schedule.yaml").read_text(encoding="utf-8"))
    tz = ZoneInfo(sched.get("timezone", "America/New_York"))
    window = int(sched.get("window_minutes", 7))
    week = sched.get("week", {}) or {}

    return Config(url=url, username=username, password=password,
                  timezone=tz, window_minutes=window, week=week)


def load_state() -> dict:
    """Load or initialize state.json; used to avoid double clocking."""
    p = ROOT / "state.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    """Persist state.json in a readable way."""
    (ROOT / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_date_file(path: Path) -> set:
    """
    Read a file containing YYYY-MM-DD per line; ignore blanks and comments.
    Returns a set of date strings.
    """
    if not path.exists():
        path.write_text("", encoding="utf-8")
    return {
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }


def read_on_flag() -> Optional[str]:
    """
    If ON.flag exists, read its first character and return '1' or '0'.
    If not present or malformed, return None (caller will use env var TCP_ON).
    """
    p = ROOT / "ON.flag"
    if not p.exists():
        return None
    val = p.read_text(encoding="utf-8").strip()[:1]
    return val if val in ("0", "1") else None


# ================
# Web automation (Playwright)
# ================
def _click_if_visible(page, text: str, timeout_ms=1200) -> bool:
    """
    Clicks a button if it's visible and returns True; otherwise returns False.
    We try both role-based and text-based fallbacks.
    """
    try:
        page.get_by_role("button", name=text, exact=False).click(timeout=timeout_ms)
        return True
    except Exception:
        try:
            page.locator(f"button:has-text('{text}')").first.click(timeout=timeout_ms)
            return True
        except Exception:
            return False


def perform_clock(action: str, cfg: Config) -> None:
    """
    Performs the Clock In/Out sequence, now tolerant of extra confirmation
    screens that require multiple 'Continue' and/or 'OK' presses.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.set_default_timeout(15000)

        try:
            # 1) Open WebClock
            page.goto(cfg.url, wait_until="domcontentloaded")

            # 2) Fill External ID
            try:
                page.get_by_label("External ID").fill(cfg.username)
            except Exception:
                page.locator(
                    "input[placeholder*='External ID'], input[aria-label*='External ID']"
                ).first.fill(cfg.username)

            # 3) Click Clock In/Out
            target_btn = "Clock In" if action == "in" else "Clock Out"
            page.get_by_role("button", name=target_btn).click()

            # 4) Password modal → Log On
            try:
                page.get_by_label("Password").fill(cfg.password)
            except Exception:
                page.locator("input[type='password']").first.fill(cfg.password)

            # Primary button name varies; try both
            if not _click_if_visible(page, "Log On", timeout_ms=2000):
                _click_if_visible(page, "Log On To Dashboard", timeout_ms=2000) or page.keyboard.press("Enter")

            # 5) Handle confirmation pages
            # Some tenants show multiple confirmation steps (Continue → Continue → OK).
            # We loop a few times and click anything that looks like a finalizer.
            for _ in range(6):  # up to 6 presses just to be safe
                clicked = False
                # Common TCP labels seen in the wild
                for label in ("Continue", "OK", "Ok", "Okay", "Confirm", "Yes"):
                    clicked |= _click_if_visible(page, label, timeout_ms=1200)
                if not clicked:
                    break
                page.wait_for_timeout(400)  # brief pause between dialogs

            # Optional: small settle wait
            page.wait_for_timeout(800)

        finally:
            ctx.close()
            browser.close()



# ================
# Decision engine
# ================
def within_window(now_local: datetime, hhmm: Optional[str], window_min: int) -> bool:
    """
    Return True if now is within +/- window_min minutes of the given HH:MM time.
    """
    if not hhmm:
        return False
    h, m = map(int, hhmm.split(":"))
    target = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
    return abs((now_local - target).total_seconds()) <= window_min * 60


def sessions_today(cfg: Config, now_local: datetime) -> List[Session]:
    """
    Parse today's sessions from schedule.yaml.
    Supports keys {in, out} or {clock_in, clock_out}.
    """
    weekday = now_local.strftime("%A").lower()
    day_cfg = (cfg.week.get(weekday) or {})
    raw = day_cfg.get("sessions", []) or []
    out: List[Session] = []
    for s in raw:
        _in = s.get("in") or s.get("clock_in")
        _out = s.get("out") or s.get("clock_out")
        if _in and _out:
            out.append(Session(clock_in=_in, clock_out=_out))
    return out


def next_action(cfg: Config, now_local: datetime, state: dict) -> Optional[Tuple[str, int]]:
    """
    Decide what to do now. Return ('in'|'out', session_index) or None.
    Checks each session window; skips those already marked in state.json.
    """
    day_key = now_local.date().isoformat()
    done = state.get(day_key, {})

    for idx, s in enumerate(sessions_today(cfg, now_local)):
        if within_window(now_local, s.clock_in, cfg.window_minutes) and not done.get(f"in_{idx}"):
            return "in", idx
        if within_window(now_local, s.clock_out, cfg.window_minutes) and not done.get(f"out_{idx}"):
            return "out", idx
    return None


def mark_done(state: dict, today: date, action: str, idx: int) -> None:
    """Mark an action as completed for a given session index in state.json."""
    key = today.isoformat()
    state.setdefault(key, {})[f"{action}_{idx}"] = True


# ================
# Entrypoint
# ================
def main() -> int:
    # --- Master toggle: ON.flag overrides TCP_ON env var ---
    flag_val = read_on_flag()                       # '1'/'0' or None
    env_val = os.environ.get("TCP_ON", "1").strip() # fallback
    effective = flag_val if flag_val is not None else env_val
    if effective != "1":
        write_status("skip", "Master toggle OFF (ON.flag or TCP_ON).")
        return 0

    # Load config + state + skip lists
    cfg = load_config()
    state = load_state()
    skip_dates = load_date_file(ROOT / "skip_dates.txt")
    holidays = load_date_file(ROOT / "holidays.txt")

    now_local = datetime.now(cfg.timezone)
    today_str = now_local.date().isoformat()

    # Skip if listed
    if today_str in skip_dates:
        write_status("skip", f"skip_dates.txt contains {today_str}.")
        return 0
    if today_str in holidays:
        write_status("skip", f"holidays.txt contains {today_str}.")
        return 0

    # Decide action (or do nothing)
    decision = next_action(cfg, now_local, state)
    if not decision:
        write_status("noop", "No action needed at this time.")
        return 0

    action, idx = decision
    try:
        perform_clock(action, cfg)
        mark_done(state, now_local.date(), action, idx)
        save_state(state)
        write_status("ok", f"Performed CLOCK {action.upper()} (session {idx}).")
        return 0
    except Exception as e:
        write_status("error", f"{type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
