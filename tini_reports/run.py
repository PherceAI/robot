from __future__ import annotations

import argparse
import logging
from datetime import datetime

from .automation import TiniAutomation
from .config import load_config, resolve_report_dates
from .logging_setup import configure_logging
from .webhook import send_file

LOGGER = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--only", help="Run only one report id")
    parser.add_argument("--dry-run", action="store_true", help="Fill dialogs but do not process/export/send")
    parser.add_argument("--skip-webhook", action="store_true")
    args = parser.parse_args()

    configure_logging()
    config = load_config(args.config)
    dates = resolve_report_dates(config)
    reports = [report for report in config.get("reports", []) if report.get("enabled", True)]
    if args.only:
        reports = [report for report in reports if report.get("id") == args.only]
    if not reports:
        raise SystemExit("No enabled reports matched the request")

    bot = TiniAutomation(config, dry_run=args.dry_run)
    bot.connect()

    exported = []
    for report in reports:
        result = bot.run_report(report, dates)
        if result.path:
            exported.append(result)

    if args.dry_run or args.skip_webhook:
        LOGGER.info("Skipping webhook. dry_run=%s skip_webhook=%s", args.dry_run, args.skip_webhook)
        return

    for item in exported:
        send_file(
            config.get("webhook", {}),
            item.path,
            {
                "report_id": item.report_id,
                "from_date": dates.from_date.isoformat(),
                "to_date": dates.to_date.isoformat(),
                "sent_at": datetime.now().isoformat(timespec="seconds"),
            },
        )


if __name__ == "__main__":
    main()
