"""Tests for src/bid_euchre/ops/time_util.py."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from bid_euchre.ops.time_util import (
    PT_TZ,
    fmt_operator,
    fmt_operator_iso,
    to_operator_tz,
)

PT_FORMAT_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} PT$")


def test_naive_datetime_treated_as_utc() -> None:
    naive = datetime(2026, 1, 15, 12, 0, 0)
    converted = to_operator_tz(naive)
    assert converted.tzinfo == PT_TZ
    # 12:00 UTC in Jan = 04:00 PST (UTC-8)
    assert converted.hour == 4


def test_aware_utc_datetime_converted() -> None:
    aware = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    converted = to_operator_tz(aware)
    assert converted.tzinfo == PT_TZ
    assert converted.hour == 4


def test_aware_non_utc_datetime_converted() -> None:
    eastern = ZoneInfo("America/New_York")
    aware = datetime(2026, 1, 15, 15, 0, 0, tzinfo=eastern)
    converted = to_operator_tz(aware)
    assert converted.tzinfo == PT_TZ
    # 15:00 EST = 12:00 PST
    assert converted.hour == 12


def test_dst_spring_forward_boundary() -> None:
    # 2026 spring-forward: 2026-03-08 02:00 PST -> 03:00 PDT.
    # 10:00 UTC on that date is 02:00 PST (just before jump) -> 03:00 PDT after.
    # zoneinfo handles by skipping; 09:59 UTC = 01:59 PST, 10:00 UTC = 03:00 PDT.
    before = datetime(2026, 3, 8, 9, 59, tzinfo=timezone.utc)
    after = datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc)
    pt_before = to_operator_tz(before)
    pt_after = to_operator_tz(after)
    assert pt_before.hour == 1
    assert pt_before.minute == 59
    assert pt_after.hour == 3
    assert pt_after.minute == 0


def test_dst_fall_back_boundary() -> None:
    # 2026 fall-back: 2026-11-01 02:00 PDT -> 01:00 PST.
    # 08:59 UTC = 01:59 PDT (-7), 09:00 UTC = 01:00 PST (-8).
    before = datetime(2026, 11, 1, 8, 59, tzinfo=timezone.utc)
    after = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
    pt_before = to_operator_tz(before)
    pt_after = to_operator_tz(after)
    assert pt_before.hour == 1
    assert pt_before.minute == 59
    assert pt_after.hour == 1
    assert pt_after.minute == 0


def test_fmt_operator_literal_pt_suffix() -> None:
    dt = datetime(2026, 6, 15, 19, 30, tzinfo=timezone.utc)
    out = fmt_operator(dt)
    assert PT_FORMAT_RE.match(out), f"format mismatch: {out!r}"
    assert out.endswith(" PT")
    # Must NOT contain PST/PDT (we use literal PT to avoid DST drift).
    assert "PST" not in out
    assert "PDT" not in out


def test_fmt_operator_naive_input() -> None:
    naive = datetime(2026, 6, 15, 19, 30)
    out = fmt_operator(naive)
    assert PT_FORMAT_RE.match(out), f"format mismatch: {out!r}"
    # 19:30 UTC in June = 12:30 PDT (UTC-7).
    assert out == "2026-06-15 12:30 PT"


def test_fmt_operator_winter_vs_summer() -> None:
    winter = datetime(2026, 1, 15, 20, 0, tzinfo=timezone.utc)
    summer = datetime(2026, 7, 15, 20, 0, tzinfo=timezone.utc)
    # Winter: 20:00 UTC -> 12:00 PST. Summer: 20:00 UTC -> 13:00 PDT.
    assert fmt_operator(winter) == "2026-01-15 12:00 PT"
    assert fmt_operator(summer) == "2026-07-15 13:00 PT"


def test_fmt_operator_iso_z_suffix() -> None:
    assert fmt_operator_iso("2026-06-15T19:30:00Z") == "2026-06-15 12:30 PT"


def test_fmt_operator_iso_offset() -> None:
    assert fmt_operator_iso("2026-06-15T19:30:00+00:00") == "2026-06-15 12:30 PT"


def test_fmt_operator_iso_empty_returns_empty() -> None:
    assert fmt_operator_iso(None) == ""
    assert fmt_operator_iso("") == ""


def test_fmt_operator_iso_unparseable_returns_input() -> None:
    assert fmt_operator_iso("not-a-timestamp") == "not-a-timestamp"
