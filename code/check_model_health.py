"""CLI entry point for checking model/provider health."""

from __future__ import annotations

from orchestrate.config import default_config
from orchestrate.model_health import haiku


def main() -> int:
    message = haiku(default_config())
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
