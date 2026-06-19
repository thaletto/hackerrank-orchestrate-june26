"""Deterministic fallback rules and risk enrichment."""

from __future__ import annotations

KEYWORD_PARTS = {
    "car": [
        ("front_bumper", ["front bumper", "front side", "bumper ke upar"]),
        ("rear_bumper", ["rear bumper", "back bumper", "back of the car", "rear side"]),
        ("windshield", ["windshield", "front glass"]),
        ("side_mirror", ["side mirror", "mirror"]),
        ("headlight", ["headlight"]),
        ("taillight", ["taillight", "tail light"]),
        ("door", ["door"]),
        ("hood", ["hood", "bonnet"]),
        ("fender", ["fender"]),
    ],
    "laptop": [
        ("screen", ["screen", "display"]),
        ("keyboard", ["keyboard", "key"]),
        ("trackpad", ["trackpad", "touchpad"]),
        ("hinge", ["hinge"]),
        ("lid", ["lid", "cover"]),
        ("corner", ["corner"]),
        ("port", ["port", "usb"]),
        ("base", ["base", "bottom"]),
    ],
    "package": [
        ("box", ["box", "carton"]),
        ("package_corner", ["corner"]),
        ("package_side", ["side"]),
        ("seal", ["seal", "tape"]),
        ("label", ["label"]),
        ("contents", ["contents", "inside"]),
        ("item", ["item", "product"]),
    ],
}

KEYWORD_ISSUES = [
    ("glass_shatter", ["shattered", "shatter"]),
    ("crushed_packaging", ["crushed", "smashed"]),
    ("torn_packaging", ["torn", "ripped", "tear"]),
    ("water_damage", ["water", "wet", "soaked"]),
    ("missing_part", ["missing"]),
    ("broken_part", ["broken", "broke", "damaged"]),
    ("crack", ["crack", "cracked"]),
    ("scratch", ["scratch", "scrape", "mark"]),
    ("dent", ["dent"]),
    ("stain", ["stain"]),
]


def infer_part(claim_object: str, text: str) -> str:
    lowered = text.lower()
    for part, needles in KEYWORD_PARTS.get(claim_object, []):
        if any(needle in lowered for needle in needles):
            return part
    return "unknown"


def infer_issue(text: str) -> str:
    lowered = text.lower()
    for issue, needles in KEYWORD_ISSUES:
        if any(needle in lowered for needle in needles):
            return issue
    return "unknown"


def history_risk_flags(user_history: dict[str, str] | None) -> list[str]:
    if not user_history:
        return []
    flags = [
        flag.strip()
        for flag in user_history.get("history_flags", "").split(";")
        if flag.strip() and flag.strip() != "none"
    ]
    rejected = int(user_history.get("rejected_claim") or 0)
    recent = int(user_history.get("last_90_days_claim_count") or 0)
    if rejected >= 2 or recent >= 4:
        flags.append("user_history_risk")
    if "user_history_risk" in flags and "manual_review_required" not in flags:
        flags.append("manual_review_required")
    deduped: list[str] = []
    for flag in flags:
        if flag not in deduped:
            deduped.append(flag)
    return deduped


def fallback_prediction(
    row: dict[str, str],
    user_history: dict[str, str] | None,
    image_meta: list[dict[str, object]],
    reason: str,
) -> dict[str, object]:
    image_ids = [str(item["id"]) for item in image_meta if item["exists"]]
    missing = [item for item in image_meta if not item["exists"]]
    claim_text = row.get("user_claim", "")
    flags = history_risk_flags(user_history)
    if missing or not image_ids:
        flags.extend(["damage_not_visible", "manual_review_required"])
        return {
            "evidence_standard_met": False,
            "evidence_standard_met_reason": "One or more submitted images are missing or unavailable.",
            "risk_flags": flags,
            "issue_type": infer_issue(claim_text),
            "object_part": infer_part(row.get("claim_object", ""), claim_text),
            "claim_status": "not_enough_information",
            "claim_status_justification": "The image evidence could not be reviewed automatically.",
            "supporting_image_ids": "none",
            "valid_image": False,
            "severity": "unknown",
        }
    if "manual_review_required" not in flags:
        flags.append("manual_review_required")
    return {
        "evidence_standard_met": False,
        "evidence_standard_met_reason": reason,
        "risk_flags": flags,
        "issue_type": infer_issue(claim_text),
        "object_part": infer_part(row.get("claim_object", ""), claim_text),
        "claim_status": "not_enough_information",
        "claim_status_justification": reason,
        "supporting_image_ids": "none",
        "valid_image": True,
        "severity": "unknown",
    }


def merge_history_risk(prediction: dict[str, str], user_history: dict[str, str] | None) -> None:
    flags = history_risk_flags(user_history)
    if not flags:
        return
    current = [] if prediction.get("risk_flags") == "none" else prediction["risk_flags"].split(";")
    for flag in flags:
        if flag not in current:
            current.append(flag)
    prediction["risk_flags"] = ";".join(current) if current else "none"
