"""
GitHub Actions version: multi-session TimeClock Plus automation with holidays and Discord-friendly status.

- Credentials come from environment secrets (TCP_URL, TCP_USERNAME, TCP_PASSWORD)
- Master toggle via repo variable TCP_ON (1/0)
- Skips if today is in skip_dates.txt OR holidays.txt
- Writes state.json and run_status.txt; the workflow commits/reads these and posts to Discord

Files: schedule.yaml, skip_dates.txt, holidays.txt, state.json
"""
import json, os, sys
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent

# ---------- Models ----------
@dataclass
class Session:
    clock_in: str
    clock_out: str

@dataclass
class Config:
    url: str
    username: str
    password: str
    timezone: ZoneInfo
    window_minutes: int
    week: dict

# ---------- IO helpers ----------
def load_config() -> Config:
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
    return Config(url, username, password, tz, window, week)

def load_state() -> dict:
    try:
        return json.loads((ROOT / "state.json").read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_state(state: dict) -> None:
    (ROOT / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

def load_date_file(path: Path) -> set:
    if not path.exists():
        path.write_text("", encoding="utf-8")
    return {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")}

def write_status(status: str, message: str) -> None:
    """
    Write a single-line status summary for the workflow/Discord.
    status: ok | skip | noop | error
    """
    (ROOT / "run_status.txt").write_text(f"{status.upper()}: {message}\n", encoding="utf-8")

# ---------- Web automation ----------
def perform_clock(action: str, cfg: Config) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.set_default_timeout(15000)
        try:
            page.goto(cfg.url, wait_until="domcontentloaded")
            # External ID
            try:
                page.get_by_label("External ID").fill(cfg.username)
            except PWTimeout:
                page.locator("input[placeholder*='External ID'], input[aria-label*='External ID']").first.fill(cfg.username)
            # Click Clock In/Out
            btn = "Clock In" if action == "in" else "Clock Out"
            page.get_by_role("button", name=btn).click()
            # Password
            try:
                page.get_by_label("Password").fill(cfg.password)
            except PWTimeout:
                page.locator("input[type='password']").fill(cfg.password)
            # Log On
            try:
                page.get_by_role("button", name="Log On").click()
            except PWTimeout:
                try:
                    page.get_by_role("button", name="Log On To Dashboard").click()
                except PWTimeout:
                    page.keyboard.press("Enter")
            # Continue
            page.get_by_role("button", name="Continue").click()
            page.wait_for_timeout(1000)
        finally:
            ctx.close()
            browser.close()

# ---------- Decision logic ----------
def within_window(now_local: datetime, hhmm: Optional[str], window_min: int) -> bool:
    if not hhmm:
        return False
    h, m = map(int, hhmm.split(":"))
    tgt = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
    return abs((now_local - tgt).total_seconds()) <= window_min * 60

def sessions_today(cfg: Config, now_local: datetime) -> List[Session]:
    wd = now_local.strftime("%A").lower()
    day_cfg = (cfg.week.get(wd) or {})
    raw = day_cfg.get("sessions", []) or []
    out = []
    for s in raw:
        _in = s.get("in") or s.get("clock_in")
        _out = s.get("out") or s.get("clock_out")
        if _in and _out:
            out.append(Session(_in, _out))
    return out

def next_action(cfg: Config, now_local: datetime, state: dict) -> Optional[Tuple[str, int]]:
    day_key = now_local.date().isoformat()
    done = state.get(day_key, {})
    for idx, s in enumerate(sessions_today(cfg, now_local)):
        if within_window(now_local, s.clock_in, cfg.window_minutes) and not done.get(f"in_{idx}"):
            return ("in", idx)
        if within_window(now_local, s.clock_out, cfg.window_minutes) and not done.get(f"out_{idx}"):
            return ("out", idx)
    return None

def mark_done(state: dict, today: date, action: str, idx: int) -> None:
    key = today.isoformat()
    state.setdefault(key, {})[f"{action}_{idx}"] = True

# ---------- Main ----------
def main() -> int:
    # Master toggle
    if os.environ.get("TCP_ON", "1").strip() != "1":
        write_status("skip", "Master toggle OFF (TCP_ON!=1).")
        return 0

    cfg = load_config()
    state = load_state()
    skips = load_date_file(ROOT / "skip_dates.txt")
    holidays = load_date_file(ROOT / "holidays.txt")

    now_local = datetime.now(cfg.timezone)
    today_str = now_local.date().isoformat()

    if today_str in skips:
        write_status("skip", f"skip_dates.txt contains {today_str}.")
        return 0
    if today_str in holidays:
        write_status("skip", f"holidays.txt contains {today_str}.")
        return 0

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
