"""Wind forecast decision dashboard API.

The assignment's decision window is January 2026. For each delivery interval,
we select the latest forecast published by the decision cutoff and compare it
with actual generation. The default lead time is 24 hours to represent a day-ahead
purchase decision; users can adjust it to explore sensitivity.
"""
from __future__ import annotations

import asyncio
import math
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Wind Forecast Decision Dashboard", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

ELEXON_BASE = "https://data.elexon.co.uk/bmrs/api/v1"
UTC = timezone.utc
DECISION_START = datetime(2026, 1, 1, tzinfo=UTC)
DECISION_END = datetime(2026, 2, 1, tzinfo=UTC)  # exclusive
# Dataset stream endpoints filter by publication time. Actual records can be
# published after their delivery interval, so fetch a small buffer after Jan.
ACTUAL_PUBLISH_END = datetime(2026, 2, 5, tzinfo=UTC)
CACHE_TTL_SECONDS = 15 * 60
_data_cache: dict[str, Any] = {"expires_at": 0.0, "actuals": None, "forecasts": None}
_cache_lock = asyncio.Lock()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "wind-forecast-api"}


def iso_z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        normalised = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalised)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (ValueError, TypeError):
        return None


def number(value: Any) -> float | None:
    try:
        parsed = float(value) if value is not None else None
        return parsed if parsed is not None and math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def unpack_rows(payload: Any) -> list[dict[str, Any]]:
    """Support the documented stream list and common wrapped JSON responses."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "results", "result"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
    return []


async def fetch_dataset(dataset: str, publish_from: datetime, publish_to: datetime) -> list[dict[str, Any]]:
    url = f"{ELEXON_BASE}/datasets/{dataset}/stream"
    params = {
        "publishDateTimeFrom": iso_z(publish_from),
        "publishDateTimeTo": iso_z(publish_to),
    }
    if dataset == "FUELHH":
        params["fuelType"] = "WIND"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
        response = await client.get(url, params=params, headers={"Accept": "application/json"})
        response.raise_for_status()
        return unpack_rows(response.json())


async def load_source_data(force_refresh: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch both source datasets once, then reuse them briefly across UI controls."""
    now = time.monotonic()
    if not force_refresh and _data_cache["expires_at"] > now:
        return _data_cache["actuals"], _data_cache["forecasts"]

    async with _cache_lock:
        now = time.monotonic()
        if not force_refresh and _data_cache["expires_at"] > now:
            return _data_cache["actuals"], _data_cache["forecasts"]
        actuals, forecasts = await asyncio.gather(
            fetch_dataset("FUELHH", DECISION_START, ACTUAL_PUBLISH_END),
            fetch_dataset("WINDFOR", DECISION_START, DECISION_END),
        )
        _data_cache.update(
            expires_at=time.monotonic() + CACHE_TTL_SECONDS,
            actuals=actuals,
            forecasts=forecasts,
        )
        return actuals, forecasts


def calculate_dashboard(
    actuals: list[dict[str, Any]], forecasts: list[dict[str, Any]], lead_hours: int
) -> dict[str, Any]:
    """Join actuals with the latest forecast knowable at each January decision time."""
    actual_by_start: dict[str, float] = {}
    for row in actuals:
        target = parse_time(row.get("startTime"))
        generation = number(row.get("generation"))
        if target is None or generation is None:
            continue
        # Keep only target intervals whose purchase-decision time is in January.
        decision_time = target - timedelta(hours=lead_hours)
        if DECISION_START <= decision_time < DECISION_END:
            actual_by_start[target.isoformat()] = generation

    forecasts_by_start: dict[str, list[tuple[datetime, float]]] = {}
    for row in forecasts:
        target = parse_time(row.get("startTime"))
        published = parse_time(row.get("publishTime"))
        generation = number(row.get("generation"))
        if target is None or published is None or generation is None:
            continue
        decision_time = target - timedelta(hours=lead_hours)
        # Only forecasts published in January can be relevant to a January decision.
        if not (DECISION_START <= published < DECISION_END):
            continue
        if not (DECISION_START <= decision_time < DECISION_END):
            continue
        forecasts_by_start.setdefault(target.isoformat(), []).append((published, generation))

    rows: list[dict[str, Any]] = []
    for target_iso, actual in sorted(actual_by_start.items()):
        target = parse_time(target_iso)
        if target is None:
            continue
        cutoff = target - timedelta(hours=lead_hours)
        eligible = [item for item in forecasts_by_start.get(target_iso, []) if item[0] <= cutoff]
        if not eligible:
            continue
        published, forecast = max(eligible, key=lambda item: item[0])
        error = forecast - actual
        rows.append({
            "startTime": target_iso,
            "publishTime": published.isoformat(),
            "decisionCutoff": cutoff.isoformat(),
            "forecast": round(forecast, 2),
            "actual": round(actual, 2),
            "error": round(error, 2),
            "absoluteError": round(abs(error), 2),
        })

    if not rows:
        return {
            "period": "January 2026 purchase decisions",
            "leadHours": lead_hours,
            "assumption": (
                f"Purchase decision time = delivery start minus {lead_hours} hours. "
                "Only decision times in January 2026 are included; for each interval, "
                "the latest forecast published on or before the decision time is selected."
            ),
            "rows": [],
            "metrics": {"matchedIntervals": 0, "mae": None, "rmse": None, "bias": None},
            "message": "No matched intervals were found for this decision lead time. Check Elexon data availability and response fields.",
        }

    errors = [row["error"] for row in rows]
    return {
        "period": "January 2026 purchase decisions",
        "leadHours": lead_hours,
        "assumption": (
            f"Purchase decision time = delivery start minus {lead_hours} hours. "
            "Only decision times in January 2026 are included; for each interval, "
            "the latest forecast published on or before the decision time is selected."
        ),
        "rows": rows,
        "metrics": {
            "matchedIntervals": len(rows),
            "mae": round(sum(abs(error) for error in errors) / len(errors), 2),
            "rmse": round(math.sqrt(sum(error * error for error in errors) / len(errors)), 2),
            "bias": round(sum(errors) / len(errors), 2),
        },
        "message": None,
    }


@app.get("/api/dashboard")
async def dashboard(
    lead_hours: int = Query(
        default=24,
        ge=0,
        le=48,
        description="Assumed time between the purchase decision and delivery; default is 24 hours.",
    ),
    refresh: bool = Query(default=False, description="Bypass the short-lived in-memory data cache."),
) -> dict[str, Any]:
    try:
        actuals, forecasts = await load_source_data(force_refresh=refresh)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not retrieve or parse Elexon data. Please retry shortly. ({type(exc).__name__})",
        ) from exc
    result = calculate_dashboard(actuals, forecasts, lead_hours)
    result["dataSource"] = "Elexon BMRS FUELHH (WIND) and WINDFOR stream datasets"
    result["cacheTtlSeconds"] = CACHE_TTL_SECONDS
    return result
