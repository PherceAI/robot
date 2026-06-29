from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


def send_file(webhook_config: dict[str, Any], file_path: str | Path, payload: dict[str, Any]) -> None:
    url = webhook_config.get("url")
    if not url:
        raise ValueError("webhook.url is required")

    path = Path(file_path)
    headers = webhook_config.get("extra_headers") or {}
    timeout = int(webhook_config.get("timeout_seconds", 60))

    LOGGER.info("Sending %s to webhook", path)
    with path.open("rb") as fh:
        response = requests.post(
            url,
            headers=headers,
            data=payload,
            files={"file": (path.name, fh, "application/octet-stream")},
            timeout=timeout,
        )
    response.raise_for_status()
    LOGGER.info("Webhook accepted %s with status %s", path.name, response.status_code)
