from datetime import datetime, timezone

from main import calculate_dashboard, parse_time, unpack_rows

UTC = timezone.utc


def test_parse_time_handles_z_and_rejects_invalid():
    assert parse_time("2026-01-01T00:00:00Z") == datetime(2026, 1, 1, tzinfo=UTC)
    assert parse_time("not-a-date") is None


def test_unpack_rows_supports_list_and_wrapped_payload():
    assert unpack_rows([{"generation": 1}, "skip"]) == [{"generation": 1}]
    assert unpack_rows({"data": [{"generation": 2}]}) == [{"generation": 2}]
    assert unpack_rows({"data": "wrong"}) == []


def test_uses_latest_forecast_published_before_decision_cutoff():
    actuals = [{"startTime": "2026-01-02T12:00:00Z", "generation": 100}]
    forecasts = [
        {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T10:00:00Z", "generation": 80},
        {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T11:59:00Z", "generation": 90},
        # Too late for a 24-hour-ahead decision; must not leak future information.
        {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T12:01:00Z", "generation": 999},
    ]
    result = calculate_dashboard(actuals, forecasts, lead_hours=24)
    assert result["metrics"]["matchedIntervals"] == 1
    assert result["rows"][0]["forecast"] == 90
    assert result["rows"][0]["actual"] == 100
    assert result["rows"][0]["error"] == -10
    assert result["metrics"]["mae"] == 10
    assert result["metrics"]["rmse"] == 10
    assert result["metrics"]["bias"] == -10


def test_only_january_decision_times_are_included():
    actuals = [
        {"startTime": "2026-01-01T12:00:00Z", "generation": 10},
        {"startTime": "2026-01-02T12:00:00Z", "generation": 20},
        {"startTime": "2026-02-02T12:00:00Z", "generation": 30},
    ]
    forecasts = [
        {"startTime": "2026-01-01T12:00:00Z", "publishTime": "2025-12-31T11:00:00Z", "generation": 11},
        {"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T11:00:00Z", "generation": 21},
        {"startTime": "2026-02-02T12:00:00Z", "publishTime": "2026-02-01T11:00:00Z", "generation": 31},
    ]
    result = calculate_dashboard(actuals, forecasts, lead_hours=24)
    # Jan 1 delivery's decision was in Dec; Feb 2 delivery's decision was in Feb.
    assert [row["startTime"] for row in result["rows"]] == ["2026-01-02T12:00:00+00:00"]


def test_missing_eligible_forecast_is_excluded():
    result = calculate_dashboard(
        [{"startTime": "2026-01-02T12:00:00Z", "generation": 10}],
        [{"startTime": "2026-01-02T12:00:00Z", "publishTime": "2026-01-01T12:01:00Z", "generation": 11}],
        lead_hours=24,
    )
    assert result["rows"] == []
    assert result["metrics"]["matchedIntervals"] == 0
