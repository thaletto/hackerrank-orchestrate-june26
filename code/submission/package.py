"""Create code.zip for HackerRank Orchestrate submission."""

from __future__ import annotations

import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = REPO_ROOT / "code"
ZIP_PATH = REPO_ROOT / "code.zip"
EXCLUDED_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "submission",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def should_include(path: Path) -> bool:
    relative = path.relative_to(CODE_DIR)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def create_submission_zip(zip_path: Path | None = None) -> Path:
    target = zip_path or ZIP_PATH
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(CODE_DIR.rglob("*")):
            if should_include(path):
                archive.write(path, path.relative_to(REPO_ROOT))
    return target


def main() -> None:
    path = create_submission_zip()
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
