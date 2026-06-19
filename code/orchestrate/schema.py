"""Output schema constants and normalization helpers."""

from __future__ import annotations

import json
from typing import Any


OUTPUT_COLUMNS = [
    "user_id",
    "image_paths",
    "user_claim",
    "claim_object",
    "evidence_standard_met",
    "evidence_standard_met_reason",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "claim_status_justification",
    "supporting_image_ids",
    "valid_image",
    "severity",
]

PREDICTION_COLUMNS = OUTPUT_COLUMNS[4:]

CLAIM_STATUSES = {"supported", "contradicted", "not_enough_information"}
ISSUE_TYPES = {
    "dent",
    "scratch",
    "crack",
    "glass_shatter",
    "broken_part",
    "missing_part",
    "torn_packaging",
    "crushed_packaging",
    "water_damage",
    "stain",
    "none",
    "unknown",
}
OBJECT_PARTS = {
    "car": {
        "front_bumper",
        "rear_bumper",
        "door",
        "hood",
        "windshield",
        "side_mirror",
        "headlight",
        "taillight",
        "fender",
        "quarter_panel",
        "body",
        "unknown",
    },
    "laptop": {
        "screen",
        "keyboard",
        "trackpad",
        "hinge",
        "lid",
        "corner",
        "port",
        "base",
        "body",
        "unknown",
    },
    "package": {
        "box",
        "package_corner",
        "package_side",
        "seal",
        "label",
        "contents",
        "item",
        "unknown",
    },
}
RISK_FLAGS = {
    "none",
    "blurry_image",
    "cropped_or_obstructed",
    "low_light_or_glare",
    "wrong_angle",
    "wrong_object",
    "wrong_object_part",
    "damage_not_visible",
    "claim_mismatch",
    "possible_manipulation",
    "non_original_image",
    "text_instruction_present",
    "user_history_risk",
    "manual_review_required",
}
SEVERITIES = {"none", "low", "medium", "high", "unknown"}


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        stripped = stripped[start : end + 1]
    return json.loads(stripped)


def as_bool_string(value: Any, default: str = "false") -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return "true"
    if text in {"false", "0", "no", "n"}:
        return "false"
    return default


def closest(value: Any, allowed: set[str], default: str) -> str:
    text = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "not_enough_info": "not_enough_information",
        "insufficient": "not_enough_information",
        "glass_shattered": "glass_shatter",
        "broken": "broken_part",
        "missing": "missing_part",
        "tear": "torn_packaging",
        "crushed": "crushed_packaging",
    }
    text = aliases.get(text, text)
    return text if text in allowed else default


def normalize_flags(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, list):
        raw = value
    else:
        raw = [part.strip() for part in str(value).replace(",", ";").split(";")]
    flags = []
    for item in raw:
        flag = closest(item, RISK_FLAGS, "")
        if flag and flag != "none" and flag not in flags:
            flags.append(flag)
    return ";".join(flags) if flags else "none"


def normalize_image_ids(value: Any, valid_ids: list[str]) -> str:
    if value is None:
        return "none"
    raw = value if isinstance(value, list) else str(value).replace(",", ";").split(";")
    ids = []
    for item in raw:
        image_id = str(item).strip()
        if image_id in valid_ids and image_id not in ids:
            ids.append(image_id)
    return ";".join(ids) if ids else "none"


def normalize_prediction(
    prediction: dict[str, Any],
    claim_object: str,
    image_ids: list[str],
    default_reason: str,
) -> dict[str, str]:
    object_parts = OBJECT_PARTS.get(claim_object, {"unknown"})
    normalized = {
        "evidence_standard_met": as_bool_string(prediction.get("evidence_standard_met")),
        "evidence_standard_met_reason": clean_text(
            prediction.get("evidence_standard_met_reason"), default_reason
        ),
        "risk_flags": normalize_flags(prediction.get("risk_flags")),
        "issue_type": closest(prediction.get("issue_type"), ISSUE_TYPES, "unknown"),
        "object_part": closest(prediction.get("object_part"), object_parts, "unknown"),
        "claim_status": closest(
            prediction.get("claim_status"), CLAIM_STATUSES, "not_enough_information"
        ),
        "claim_status_justification": clean_text(
            prediction.get("claim_status_justification"), default_reason
        ),
        "supporting_image_ids": normalize_image_ids(
            prediction.get("supporting_image_ids"), image_ids
        ),
        "valid_image": as_bool_string(prediction.get("valid_image")),
        "severity": closest(prediction.get("severity"), SEVERITIES, "unknown"),
    }
    if normalized["claim_status"] == "not_enough_information":
        if normalized["supporting_image_ids"] == "none" and image_ids:
            normalized["supporting_image_ids"] = "none"
    return normalized


def clean_text(value: Any, default: str) -> str:
    text = " ".join(str(value or "").split())
    return text[:600] if text else default
