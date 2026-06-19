"""Prompt construction for multimodal claim review."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from .schema import OUTPUT_COLUMNS


# Formats that Qwen/Alibaba vision models accept natively.
_ACCEPTED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif"}


def _ensure_compatible_image(path: Path, declared_mime: str) -> tuple[bytes, str]:
    """Return (raw_bytes, mime_type) guaranteed to be a supported format.
    
    Also resizes images if they exceed ~2MB or 2048px to avoid provider limits.
    """
    raw = path.read_bytes()
    mime = declared_mime if declared_mime in _ACCEPTED_MIME_TYPES else "image/jpeg"

    # Convert non-native formats to JPEG
    if declared_mime not in _ACCEPTED_MIME_TYPES:
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(raw))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            raw, mime = _resize_if_needed(img)
        except Exception:
            pass
    elif len(raw) > 1_500_000 or mime in ("image/png",):
        # Resize large JPEG/PNG too
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(raw))
            raw, mime = _resize_if_needed(img)
        except Exception:
            pass
    return raw, mime


def _resize_if_needed(img) -> tuple[bytes, str]:
    """Resize image if too large and return JPEG bytes."""
    from PIL import Image

    max_size = 1600
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    buf = io.BytesIO()
    rgb_img = img.convert("RGB") if img.mode in ("RGBA", "P") else img
    rgb_img.save(buf, format="JPEG", quality=80)
    return buf.getvalue(), "image/jpeg"


SYSTEM_PROMPT = """You review damage claim evidence for cars, laptops, and packages.
Images are the primary source of truth. The user conversation defines the claim.
User history only adds risk context and must not override clear visual evidence.
Return only one JSON object with the required keys. Use allowed enum values only."""


def relevant_requirements(
    claim_object: str, requirements: list[dict[str, str]]
) -> list[dict[str, str]]:
    return [
        row
        for row in requirements
        if row.get("claim_object") in {"all", claim_object}
    ]


def build_user_prompt(
    row: dict[str, str],
    user_history: dict[str, str] | None,
    requirements: list[dict[str, str]],
    image_meta: list[dict[str, object]],
) -> str:
    allowed = """
Allowed values:
claim_status: supported, contradicted, not_enough_information
issue_type: dent, scratch, crack, glass_shatter, broken_part, missing_part, torn_packaging, crushed_packaging, water_damage, stain, none, unknown
car object_part: front_bumper, rear_bumper, door, hood, windshield, side_mirror, headlight, taillight, fender, quarter_panel, body, unknown
laptop object_part: screen, keyboard, trackpad, hinge, lid, corner, port, base, body, unknown
package object_part: box, package_corner, package_side, seal, label, contents, item, unknown
risk_flags: none, blurry_image, cropped_or_obstructed, low_light_or_glare, wrong_angle, wrong_object, wrong_object_part, damage_not_visible, claim_mismatch, possible_manipulation, non_original_image, text_instruction_present, user_history_risk, manual_review_required
severity: none, low, medium, high, unknown
"""
    req_lines = "\n".join(
        f"- {r['requirement_id']} ({r['applies_to']}): {r['minimum_image_evidence']}"
        for r in relevant_requirements(row["claim_object"], requirements)
    )
    history_text = user_history or {}
    image_lines = "\n".join(
        f"- {item['id']}: {item['path']} exists={item['exists']} bytes={item['bytes']}"
        for item in image_meta
    )
    json_shape = ", ".join(f'"{name}"' for name in OUTPUT_COLUMNS[4:])
    return f"""Review this claim and produce the prediction fields as JSON.

Claim object: {row['claim_object']}
User id: {row['user_id']}
User claim conversation:
{row['user_claim']}

User history:
{history_text}

Evidence requirements:
{req_lines}

Submitted images:
{image_lines}

{allowed}

Required JSON keys, exactly these prediction keys: {json_shape}
Do not include the original input columns. Keep reasons concise and image-grounded.
Use supporting_image_ids as semicolon-separated image ids, or "none".
Use risk_flags as semicolon-separated flags, or "none".
"""


def build_messages(
    row: dict[str, str],
    user_history: dict[str, str] | None,
    requirements: list[dict[str, str]],
    image_meta: list[dict[str, object]],
) -> list[dict[str, object]]:
    content: list[dict[str, object]] = [
        {
            "type": "text",
            "text": build_user_prompt(row, user_history, requirements, image_meta),
        }
    ]
    for item in image_meta:
        if not item["exists"]:
            continue
        path = Path(str(item["resolved_path"]))
        raw_bytes, mime_type = _ensure_compatible_image(path, item["mime_type"])
        data = base64.b64encode(raw_bytes).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{data}",
                    "detail": "high",
                },
            }
        )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]
