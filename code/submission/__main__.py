"""CLI entry point for submission packaging and validation."""

from __future__ import annotations

import argparse

from .package import create_submission_zip
from .validate import validate_submission


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submission packaging and validation.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    package_parser = subparsers.add_parser("package", help="Create code.zip for submission.")
    package_parser.add_argument("--output", type=str, default=None, help="Zip output path.")

    validate_parser = subparsers.add_parser("validate", help="Validate submission artifacts.")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "package":
        from pathlib import Path

        path = create_submission_zip(Path(args.output) if args.output else None)
        print(f"Wrote {path}")
        return 0
    if args.command == "validate":
        errors = validate_submission()
        if errors:
            print(f"Validation failed with {len(errors)} error(s).")
            return 1
        print("Validation passed.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
