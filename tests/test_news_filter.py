import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from trading import news_filter as nf
from trading.news_filter import NewsFilter, parse_events

UTC = timezone.utc


def payload(*events):
    return {"events": list(events)}


def ev(id="us-nfp-1", time_utc="2026-11-06T13:30:00+00:00", status="confirmed", **kw):
    d = {"id": id, "series_code": "us-nfp", "name": "US jobs report (NFP)", "country": "US",
         "impact": "high", "time_utc": time_utc, "all_day": False,
         "time_precision": "minute", "status": status, "date": "2026-11-06"}
    d.update(kw)
    return d


def make_filter(*events, last_success=datetime(2026, 11, 6, 0, 0, tzinfo=UTC)):
    f = NewsFilter()
    f.events = parse_events(payload(*events))
    f.last_success = last_success
    return f


class NewsFilterTests(unittest.TestCase):
    def setUp(self):
        for name, val in [("NEWS_BLOCK_BEFORE_MIN", 60), ("NEWS_BLOCK_AFTER_MIN", 60),
                          ("NEWS_UNTIMED_POLICY", "ignore"), ("NEWS_FAIL_MODE", "block"),
                          ("NEWS_MAX_CACHE_AGE_HOURS", 24)]:
            p = patch.object(nf.config, name, val, create=True)
            p.start()
            self.addCleanup(p.stop)

    def at(self, h, m):
        return datetime(2026, 11, 6, h, m, tzinfo=UTC)

    def test_window_is_one_hour_each_side(self):
        f = make_filter(ev())
        self.assertIsNone(f.active_event(self.at(12, 29)))
        self.assertIsNotNone(f.active_event(self.at(12, 30)))
        self.assertIsNotNone(f.active_event(self.at(13, 30)))
        self.assertIsNotNone(f.active_event(self.at(14, 30)))
        self.assertIsNone(f.active_event(self.at(14, 31)))

    def test_cancelled_event_ignored(self):
        f = make_filter(ev(status="cancelled"))
        self.assertEqual(f.events, [])
        self.assertIsNone(f.active_event(self.at(13, 30)))

    def test_untimed_ignore(self):
        f = make_filter(ev(time_utc=None, all_day=True, time_precision="date"))
        self.assertIsNone(f.active_event(self.at(13, 30)))

    def test_untimed_block_day(self):
        f = make_filter(ev(time_utc=None, all_day=True, time_precision="date"),
                        last_success=datetime(2026, 11, 7, 0, 0, tzinfo=UTC))
        with patch.object(nf.config, "NEWS_UNTIMED_POLICY", "block_day"):
            self.assertIsNotNone(f.active_event(self.at(5, 0)))
            self.assertIsNone(f.active_event(self.at(5, 0) + timedelta(days=1)))

    def test_stale_cache_fail_modes(self):
        f = make_filter(last_success=datetime(2026, 11, 4, tzinfo=UTC))
        with patch.object(nf.config, "NEWS_FAIL_MODE", "block"):
            self.assertIsNotNone(f.active_event(self.at(3, 0)))
        with patch.object(nf.config, "NEWS_FAIL_MODE", "allow"):
            self.assertIsNone(f.active_event(self.at(3, 0)))

    def test_never_loaded_blocks_in_block_mode(self):
        f = NewsFilter()
        self.assertIsNotNone(f.active_event(self.at(3, 0)))

    def test_api_error_keeps_previous_events(self):
        f = make_filter(ev())
        with patch.object(f, "_get", side_effect=OSError("boom")), \
             patch.object(nf.config, "NEWS_SERIES", ["us-nfp"], create=True), \
             patch.object(nf.config, "NEWS_IMPACT", ["high", "medium"], create=True), \
             patch.object(nf.config, "NEWS_LOOKAHEAD_DAYS", 7, create=True):
            self.assertFalse(f.refresh(self.at(10, 0)))
        self.assertEqual(len(f.events), 1)

    def test_refresh_queries_gold_series_high_and_medium(self):
        f = NewsFilter()
        calls = []
        def fake_get(params):
            calls.append(params)
            return payload(ev(id="claims", series_code="us-jobless-claims", impact="medium"))
        with patch.object(f, "_get", side_effect=fake_get), \
             patch.object(nf.config, "NEWS_SERIES", ["fomc", "us-jobless-claims"], create=True), \
             patch.object(nf.config, "NEWS_IMPACT", ["high", "medium"], create=True), \
             patch.object(nf.config, "NEWS_LOOKAHEAD_DAYS", 7, create=True):
            self.assertTrue(f.refresh(self.at(10, 0)))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["series"], "fomc,us-jobless-claims")
        self.assertEqual(calls[0]["impact"], "high,medium")
        self.assertNotIn("country", calls[0])
        self.assertIsNotNone(f.active_event(self.at(13, 0)))  # medium-impact event blocks

    def test_next_event(self):
        f = make_filter(ev())
        self.assertEqual(f.next_event(self.at(0, 0)).series_code, "us-nfp")
        self.assertIsNone(f.next_event(self.at(20, 0)))


if __name__ == "__main__":
    unittest.main()
