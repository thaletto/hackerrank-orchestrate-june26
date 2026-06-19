"""CSV, image, and cache helpers."""

from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any

from .config import REPO_ROOT
from .schema import OUTPUT_COLUMNS


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_output(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def load_user_history(path: Path) -> dict[str, dict[str, str]]:
    return {row["user_id"]: row for row in read_csv(path)}


def load_requirements(path: Path) -> list[dict[str, str]]:
    return read_csv(path)


def split_image_paths(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


def image_id(image_path: str) -> str:
    return Path(image_path).stem


def resolve_image_path(image_path: str) -> Path:
    path = Path(image_path)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "images":
        return REPO_ROOT / "dataset" / path
    return REPO_ROOT / path


def _detect_mime_type(path: Path) -> str:
    """Detect actual image MIME type from file content, not extension."""
    try:
        from PIL import Image

        with Image.open(path) as img:
            fmt = img.format
            if fmt == "JPEG":
                return "image/jpeg"
            if fmt == "PNG":
                return "image/png"
            if fmt == "GIF":
                return "image/gif"
            if fmt == "WEBP":
                return "image/webp"
            if fmt == "AVIF":
                return "image/avif"
    except Exception:
        pass
    return mimetypes.guess_type(str(path))[0] or "image/jpeg"


def image_metadata(image_paths: list[str]) -> list[dict[str, Any]]:
    metadata = []
    for image_path in image_paths:
        resolved = resolve_image_path(image_path)
        exists = resolved.exists()
        metadata.append(
            {
                "id": image_id(image_path),
                "path": image_path,
                "resolved_path": str(resolved),
                "exists": exists,
                "bytes": resolved.stat().st_size if exists else 0,
                "mime_type": _detect_mime_type(resolved) if exists else "image/jpeg",
            }
        )
    return metadata


def cache_key(row: dict[str, str], image_meta: list[dict[str, Any]], model: str) -> str:
    payload = {
        "model": model,
        "row": {
            "user_id": row.get("user_id"),
            "image_paths": row.get("image_paths"),
            "user_claim": row.get("user_claim"),
            "claim_object": row.get("claim_object"),
        },
        "images": [
            {
                "path": item["path"],
                "exists": item["exists"],
                "bytes": item["bytes"],
            }
            for item in image_meta
        ],
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(cache, handle, indent=2, sort_keys=True)
