from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pywinauto import Desktop

from .logging_setup import configure_logging

LOGGER = logging.getLogger(__name__)


def control_to_dict(control: Any) -> dict[str, Any]:
    info = control.element_info
    rect = control.rectangle()
    return {
        "handle": int(control.handle) if getattr(control, "handle", None) else None,
        "name": info.name,
        "class_name": info.class_name,
        "control_type": getattr(info, "control_type", None),
        "automation_id": getattr(info, "automation_id", None),
        "control_id": control.control_id() if hasattr(control, "control_id") else None,
        "rectangle": {
            "left": rect.left,
            "top": rect.top,
            "right": rect.right,
            "bottom": rect.bottom,
        },
    }


def inspect_windows(title_re: str | None, backend: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    desktop = Desktop(backend=backend)
    windows = desktop.windows(title_re=title_re) if title_re else desktop.windows()
    snapshot = []

    for window in windows:
        LOGGER.info("Inspecting window: %s", window.window_text())
        item = control_to_dict(window)
        item["children"] = []
        for child in window.descendants():
            try:
                item["children"].append(control_to_dict(child))
            except Exception as exc:
                item["children"].append({"error": str(exc)})
        snapshot.append(item)

    out_file = output_dir / f"inspect_{datetime.now():%Y%m%d_%H%M%S}.json"
    out_file.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("Wrote inspection snapshot to %s", out_file)
    return out_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title-re", default=".*Sistema Integrado TINI.*")
    parser.add_argument("--backend", default="win32", choices=["win32", "uia"])
    parser.add_argument("--output", default="artifacts/inspect")
    args = parser.parse_args()

    configure_logging()
    inspect_windows(args.title_re, args.backend, Path(args.output))


if __name__ == "__main__":
    main()
