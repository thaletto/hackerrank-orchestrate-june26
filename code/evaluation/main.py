from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from orchestrate.config import DATASET_DIR, default_config
from orchestrate.pipeline import RunStats, run_pipeline
from orchestrate.schema import PREDICTION_COLUMNS


SAMPLE_CSV = DATASET_DIR / "sample_claims.csv"
REPORT_PATH = CODE_DIR / "evaluation" / "evaluation_report.md"

# Fields that require exact string matching (categorical/structured)
EXACT_MATCH_FIELDS = {
    "evidence_standard_met",
    "claim_status",
    "issue_type",
    "object_part",
    "valid_image",
    "severity",
    "risk_flags",
    "supporting_image_ids",
}

# Fields evaluated with semantic similarity (free-text justifications)
SEMANTIC_FIELDS = {
    "evidence_standard_met_reason",
    "claim_status_justification",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _tokenize(text: str) -> set[str]:
    """Normalize and tokenize text into a set of words."""
    lowered = text.lower()
    # Remove punctuation, keep alphanumeric and spaces
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    # Filter out stopwords and short tokens
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "need", "dare",
        "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
        "from", "as", "into", "through", "during", "before", "after", "above",
        "below", "between", "under", "and", "but", "or", "yet", "so", "if",
        "because", "although", "though", "while", "where", "when", "that",
        "which", "who", "whom", "whose", "what", "this", "these", "those",
        "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
        "us", "them", "my", "your", "his", "its", "our", "their", "mine",
        "yours", "hers", "ours", "theirs", "s", "t", "don", "doesn", "didn",
        "wasn", "weren", "haven", "hasn", "hadn", "won", "wouldn", "couldn",
        "shouldn", "isn", "aren", "ain", "nt",
    }
    tokens = {token for token in cleaned.split() if len(token) > 2 and token not in stopwords}
    return tokens


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Calculate Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _text_similarity(expected: str, predicted: str) -> float:
    """Calculate semantic similarity between two text strings."""
    # Direct match shortcut
    if expected.strip().lower() == predicted.strip().lower():
        return 1.0
    tokens_exp = _tokenize(expected)
    tokens_pred = _tokenize(predicted)
    return _jaccard_similarity(tokens_exp, tokens_pred)


def _fields_match(field: str, expected: str, predicted: str) -> bool:
    """Check if a field matches according to its type."""
    if field in EXACT_MATCH_FIELDS:
        return expected == predicted
    if field in SEMANTIC_FIELDS:
        similarity = _text_similarity(expected, predicted)
        return similarity >= 0.25  # 25% word overlap threshold
    return expected == predicted


def compare_rows(expected: list[dict[str, str]], predicted: list[dict[str, str]]) -> dict[str, object]:
    by_field: dict[str, dict[str, int]] = {
        field: {"correct": 0, "total": len(expected)} for field in PREDICTION_COLUMNS
    }
    exact_rows = 0
    partial_rows = 0  # rows with >= 8/10 fields correct
    mismatches: list[dict[str, object]] = []
    for index, (exp, pred) in enumerate(zip(expected, predicted), start=1):
        row_ok = True
        row_correct_count = 0
        row_mismatches = []
        for field in PREDICTION_COLUMNS:
            if _fields_match(field, exp.get(field, ""), pred.get(field, "")):
                by_field[field]["correct"] += 1
                row_correct_count += 1
            else:
                row_ok = False
                row_mismatches.append(
                    {
                        "field": field,
                        "expected": exp.get(field, ""),
                        "predicted": pred.get(field, ""),
                    }
                )
        if row_ok:
            exact_rows += 1
        if row_correct_count >= 8:
            partial_rows += 1
        if row_mismatches:
            mismatches.append(
                {
                    "row": index,
                    "user_id": exp.get("user_id", ""),
                    "claim_object": exp.get("claim_object", ""),
                    "mismatches": row_mismatches,
                    "justification": pred.get("claim_status_justification", ""),
                }
            )
    return {
        "rows": len(expected),
        "exact_rows": exact_rows,
        "exact_row_accuracy": exact_rows / len(expected) if expected else 0,
        "partial_rows": partial_rows,
        "partial_row_accuracy": partial_rows / len(expected) if expected else 0,
        "by_field": by_field,
        "mismatches": mismatches,
    }


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_report(results: dict[str, dict[str, object]], stats: dict[str, RunStats]) -> str:
    lines = [
        "# Evaluation Report",
        "",
        "## Strategy Comparison",
        "",
        "| Strategy | Rows | Exact row accuracy | Partial (≥8/10) | Model calls | Cache hits | Fallback rows | Images |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, result in results.items():
        run_stats = stats[name]
        lines.append(
            "| "
            f"{name} | {result['rows']} | {format_percent(result['exact_row_accuracy'])} | "
            f"{format_percent(result['partial_row_accuracy'])} | "
            f"{run_stats.model_calls} | {run_stats.cache_hits} | {run_stats.fallback_rows} | {run_stats.images} |"
        )

    lines.extend(["", "## Field Accuracy", ""])
    lines.append("*Note: `evidence_standard_met_reason` and `claim_status_justification` use semantic similarity (≥25% word overlap) instead of exact string matching.*")
    lines.append("")
    for name, result in results.items():
        lines.extend([f"### {name}", "", "| Field | Accuracy | Correct / Total |", "|---|---:|---:|"])
        for field, counts in result["by_field"].items():
            correct = counts["correct"]
            total = counts["total"]
            lines.append(f"| {field} | {format_percent(correct / total if total else 0)} | {correct} / {total} |")
        lines.append("")

    lines.extend(["## Error Analysis", ""])
    for name, result in results.items():
        mismatches = result["mismatches"][:12]
        lines.append(f"### {name}")
        if not mismatches:
            lines.append("No mismatches.")
        for item in mismatches:
            fields = ", ".join(
                f"{m['field']} expected={m['expected']!r} predicted={m['predicted']!r}"
                for m in item["mismatches"][:4]
            )
            lines.append(
                f"- Row {item['row']} ({item['user_id']}, {item['claim_object']}): {fields}. "
                f"Justification: {item['justification']}"
            )
        lines.append("")

    total_model_calls = sum(s.model_calls for s in stats.values())
    total_input_tokens = sum(s.input_tokens for s in stats.values())
    total_output_tokens = sum(s.output_tokens for s in stats.values())
    total_images = sum(s.images for s in stats.values())
    lines.extend(
        [
            "## Operational Analysis",
            "",
            f"- Sample strategies run: {', '.join(results.keys())}.",
            f"- Approximate sample model calls: {total_model_calls}.",
            f"- Approximate sample token usage: {total_input_tokens} input tokens, {total_output_tokens} output tokens from provider usage metadata when available.",
            f"- Approximate sample images processed: {total_images}.",
            "- Full test set size: 44 claims. Expected model calls are up to one call per uncached claim.",
            "- Approximate full-test cost should be calculated from the selected provider's current image and token pricing after a real model run.",
            "- Latency is dominated by vision model calls; cache hits avoid repeated calls during prompt tuning.",
            "- TPM/RPM strategy: run sequentially by default, keep temperature at 0, cache every successful row, and retry manually by rerunning after transient provider errors.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_strategy(name: str, use_llm: bool) -> tuple[dict[str, object], RunStats]:
    output_path = CODE_DIR / "evaluation" / f"sample_predictions_{name}.csv"
    config = default_config(
        input_csv=SAMPLE_CSV,
        output_csv=output_path,
        cache_name=f"sample_{name}_cache.json",
    )
    config = config.__class__(**{**config.__dict__, "use_llm": use_llm})
    stats = run_pipeline(config)
    expected = read_csv(SAMPLE_CSV)
    predicted = read_csv(output_path)
    return compare_rows(expected, predicted), stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate sample claim predictions.")
    parser.add_argument(
        "--run-llm",
        action="store_true",
        help="Run the configured LiteLLM strategy in addition to the fallback baseline.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, object]] = {}
    stats: dict[str, RunStats] = {}

    result, run_stats = run_strategy("keyword_fallback", use_llm=False)
    results["keyword_fallback"] = result
    stats["keyword_fallback"] = run_stats

    if args.run_llm:
        result, run_stats = run_strategy("litellm_vision", use_llm=True)
        results["litellm_vision"] = result
        stats["litellm_vision"] = run_stats

    report = render_report(results, stats)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    for name, result in results.items():
        print(
            f"{name}: exact={format_percent(result['exact_row_accuracy'])} "
            f"partial={format_percent(result['partial_row_accuracy'])}"
        )


if __name__ == "__main__":
    main()
