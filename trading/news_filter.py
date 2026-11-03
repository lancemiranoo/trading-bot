"""
High-impact news filter backed by the Finance Calendar API
(https://www.financecalendar.com/api/).

Pure logic, no MetaTrader5 import, so it can be unit-tested anywhere.
Data courtesy of https://www.financecalendar.com
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pytz

from core import config
from core.logger import get_logger

logger = get_logger("NewsFilter")


@dataclass
class NewsEvent:
    id: str
    name: str
    series_code: str
    country: str
    impact: str
    time_utc: Optional[datetime]
    all_day: bool
    status: str
    time_precision: str = "minute"
    date: Optional[str] = None  # YYYY-MM-DD, used for untimed / all-day events

    @property
    def is_timed(self) -> bool:
        return self.time_utc is not None and not self.all_day and self.time_precision in ("minute", "second")


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_events(payload: dict) -> List[NewsEvent]:
    """Convert an API /calendar payload into NewsEvent objects (cancelled events dropped)."""
    events = []
    for e in payload.get("events", []):
        status = (e.get("status") or "").lower()
        if status == "cancelled":
            continue
        events.append(NewsEvent(
            id=e.get("id", ""),
            name=e.get("name") or e.get("title") or e.get("series_code", "Unknown"),
            series_code=e.get("series_code") or "",
            country=e.get("country") or "",
            impact=(e.get("impact") or "").lower(),
            time_utc=_parse_dt(e.get("time_utc") or e.get("release_at_utc")),
            all_day=bool(e.get("all_day")),
            status=status,
            time_precision=e.get("time_precision") or "minute",
            date=e.get("date"),
        ))
    return events


class NewsFilter:
    def __init__(self):
        self.events: List[NewsEvent] = []
        self.last_success: Optional[datetime] = None
        self.last_refresh_attempt: Optional[datetime] = None
        self.rate_limited_until: Optional[datetime] = None
        self.in_blackout = False

    # ------------------------------------------------------------------ fetch
    def _get(self, params: dict) -> dict:
        url = f"{config.NEWS_API_BASE}/calendar?{urllib.parse.urlencode(params)}"
        headers = {"Accept": "application/json", "User-Agent": "mt5-telegram-trading-bot"}
        if config.FINANCECALENDAR_API_KEY:
            headers["X-API-Key"] = config.FINANCECALENDAR_API_KEY
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def refresh(self, now_utc: Optional[datetime] = None) -> bool:
        """Fetch upcoming events. On failure keep the previous cache. Returns True on success."""
        now_utc = now_utc or datetime.now(timezone.utc)
        self.last_refresh_attempt = now_utc

        if self.rate_limited_until and now_utc < self.rate_limited_until:
            logger.warning(f"News API rate-limited until {self.rate_limited_until:%Y-%m-%d %H:%M} UTC; using cache.")
            return False

        start = (now_utc - timedelta(days=1)).date()
        end = (now_utc + timedelta(days=config.NEWS_LOOKAHEAD_DAYS)).date()
        base = {"from": start.isoformat(), "to": end.isoformat(), "limit": 500}

        try:
            queries = [dict(base,
                            series=",".join(config.NEWS_SERIES),
                            impact=",".join(config.NEWS_IMPACT))]

            merged = {}
            for q in queries:
                for ev in parse_events(self._get(q)):
                    merged[ev.id or f"{ev.series_code}-{ev.time_utc}"] = ev
            self.events = sorted(
                merged.values(),
                key=lambda e: e.time_utc or datetime.max.replace(tzinfo=timezone.utc),
            )
            self.last_success = now_utc
            logger.info(f"News calendar refreshed: {len(self.events)} event(s) loaded.")
            return True
        except urllib.error.HTTPError as e:
            if e.code == 429:
                reset = e.headers.get("Retry-After")
                wait = int(reset) if reset and reset.isdigit() else 3600
                self.rate_limited_until = now_utc + timedelta(seconds=wait)
                logger.error(f"News API rate limit hit (429). Backing off {wait}s.")
            else:
                logger.error(f"News API HTTP error {e.code}: {e.reason}")
        except Exception as e:
            logger.error(f"News API refresh failed: {e}")
        return False

    # ----------------------------------------------------------------- queries
    def _cache_is_stale(self, now_utc: datetime) -> bool:
        if self.last_success is None:
            return True
        return now_utc - self.last_success > timedelta(hours=config.NEWS_MAX_CACHE_AGE_HOURS)

    def active_event(self, now_utc: Optional[datetime] = None) -> Optional[NewsEvent]:
        """Return the event whose blackout window contains `now_utc`, else None.

        If the calendar data is stale/never loaded and NEWS_FAIL_MODE == "block",
        a synthetic event is returned so trading stays paused.
        """
        now_utc = now_utc or datetime.now(timezone.utc)
        before = timedelta(minutes=config.NEWS_BLOCK_BEFORE_MIN)
        after = timedelta(minutes=config.NEWS_BLOCK_AFTER_MIN)

        for ev in self.events:
            if ev.status == "cancelled":
                continue
            if ev.is_timed:
                if ev.time_utc - before <= now_utc <= ev.time_utc + after:
                    return ev
            elif config.NEWS_UNTIMED_POLICY == "block_day":
                day = ev.date or (ev.time_utc.date().isoformat() if ev.time_utc else None)
                if day == now_utc.date().isoformat():
                    return ev

        if self._cache_is_stale(now_utc) and config.NEWS_FAIL_MODE == "block":
            return NewsEvent(
                id="stale-cache", name="News calendar unavailable (fail-safe)",
                series_code="", country="", impact="high",
                time_utc=now_utc, all_day=False, status="confirmed",
            )
        return None

    def upcoming_events(self, now_utc: Optional[datetime] = None) -> List[NewsEvent]:
        """Timed events whose blackout window has not ended yet."""
        now_utc = now_utc or datetime.now(timezone.utc)
        after = timedelta(minutes=config.NEWS_BLOCK_AFTER_MIN)
        return [e for e in self.events if e.is_timed and e.time_utc + after >= now_utc]

    def next_event(self, now_utc: Optional[datetime] = None) -> Optional[NewsEvent]:
        now_utc = now_utc or datetime.now(timezone.utc)
        for ev in self.events:
            if ev.is_timed and ev.time_utc > now_utc:
                return ev
        return None


# ---------------------------------------------------------------------- display
def _local(dt: datetime) -> datetime:
    return dt.astimezone(pytz.timezone(getattr(config, "DISPLAY_TIMEZONE", "UTC")))


def _clock(dt: datetime) -> str:
    return _local(dt).strftime("%I:%M %p").lstrip("0")


def blackout_window(ev: NewsEvent):
    """(start, end) of the no-trading window for a timed event, else (None, None)."""
    if not ev.is_timed:
        return None, None
    return (ev.time_utc - timedelta(minutes=config.NEWS_BLOCK_BEFORE_MIN),
            ev.time_utc + timedelta(minutes=config.NEWS_BLOCK_AFTER_MIN))


def describe(ev: NewsEvent) -> str:
    """One-line human description, e.g.
    'FOMC decision (high impact) at 12:00 PM | no trading 11:00 AM - 1:00 PM America/Edmonton'"""
    if ev.id == "stale-cache":
        return "News calendar could not be loaded (fail-safe is ON)"
    start, end = blackout_window(ev)
    if start is None:
        return f"{ev.name} ({ev.impact} impact) on {ev.date} (time not announced)"
    tz = getattr(config, "DISPLAY_TIMEZONE", "UTC")
    day = _local(ev.time_utc).strftime("%a %b %d")
    return (f"{ev.name} ({ev.impact} impact) on {day} at {_clock(ev.time_utc)} | "
            f"no trading {_clock(start)} - {_clock(end)} {tz}")


def banner(title: str, lines: List[str]) -> str:
    width = max([len(title)] + [len(l) for l in lines]) + 4
    bar = "=" * width
    body = "\n".join(f"  {l}" for l in lines)
    return f"\n{bar}\n  {title}\n{bar}\n{body}\n{bar}" if lines else f"\n{bar}\n  {title}\n{bar}"
