"""Validate required submission artifacts."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = CODE_DIR.parent

# Ensure code/ is on path so orchestrate imports work when run directly
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _output_columns() -> list[str]:
    # Lazy import to avoid circular deps if schema moves later.
    from orchestrate.schema import OUTPUT_COLUMNS

    return OUTPUT_COLUMNS


def check(condition: bool, message: str, errors: list[str]) -> None:
    prefix = "OK" if condition else "FAIL"
    print(f"[{prefix}] {message}")
    if not condition:
        errors.append(message)


def validate_submission() -> list[str]:
    errors: list[str] = []
    output_csv = REPO_ROOT / "output.csv"
    claims_csv = REPO_ROOT / "dataset" / "claims.csv"
    report = CODE_DIR / "evaluation" / "evaluation_report.md"
    readme = CODE_DIR / "README.md"

    check(output_csv.exists(), "root output.csv exists", errors)
    check(claims_csv.exists(), "dataset/claims.csv exists", errors)
    check(report.exists(), "code/evaluation/evaluation_report.md exists", errors)
    check(readme.exists(), "code/README.md exists", errors)

    if output_csv.exists() and claims_csv.exists():
        output_rows = read_csv(output_csv)
        claim_rows = read_csv(claims_csv)
        with output_csv.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            columns: list[str] = next(reader, [])
        check(columns == _output_columns(), "output.csv columns match required order", errors)
        check(len(output_rows) == len(claim_rows), "output.csv row count matches claims.csv", errors)

    return errors


def main() -> int:
    errors = validate_submission()
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
