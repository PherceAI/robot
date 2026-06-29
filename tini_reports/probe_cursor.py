from __future__ import annotations

import argparse
import json
import time
from typing import Any

from pywinauto import Desktop, mouse

from .inspect import control_to_dict
from .logging_setup import configure_logging


def parent_chain(control: Any) -> list[dict[str, Any]]:
    chain = []
    current = control
    while current is not None:
        try:
            chain.append(control_to_dict(current))
            current = current.parent()
        except Exception:
            break
    return chain


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="win32", choices=["win32", "uia"])
    parser.add_argument("--delay", type=int, default=0)
    args = parser.parse_args()

    configure_logging()
    if args.delay:
        print(f"Move el mouse al control. Capturando en {args.delay} segundos...")
        time.sleep(args.delay)

    x, y = mouse.get_position()
    desktop = Desktop(backend=args.backend)
    control = desktop.from_point(x, y)
    payload = {
        "point": {"x": x, "y": y},
        "control": control_to_dict(control),
        "parent_chain": parent_chain(control),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
