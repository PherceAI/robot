from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ReportDates:
    from_date: date
    to_date: date


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def resolve_report_dates(config: dict[str, Any]) -> ReportDates:
    schedule = config.get("schedule", {})
    mode = schedule.get("date_mode", "yesterday")
    today = date.today()

    if mode == "today":
        return ReportDates(today, today)
    if mode == "yesterday":
        yesterday = today - timedelta(days=1)
        return ReportDates(yesterday, yesterday)
    if mode == "explicit":
        from_date = date.fromisoformat(str(schedule["from_date"]))
        to_date = date.fromisoformat(str(schedule["to_date"]))
        return ReportDates(from_date, to_date)

    raise ValueError(f"Unsupported schedule.date_mode: {mode}")


def render_template(value: Any, dates: ReportDates) -> Any:
    if not isinstance(value, str):
        return value
    return value.format(from_date=dates.from_date, to_date=dates.to_date)

