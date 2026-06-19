"""End-to-end evidence review pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import PipelineConfig
from .data_io import (
    cache_key,
    image_metadata,
    load_requirements,
    load_user_history,
    read_cache,
    read_csv,
    split_image_paths,
    write_cache,
    write_output,
)
from .llm_client import LLMUnavailable, LiteLLMClient
from .prompting import build_messages
from .rules import fallback_prediction, merge_history_risk
from .schema import normalize_prediction, parse_json_object


@dataclass
class RunStats:
    rows: int = 0
    model_calls: int = 0
    cache_hits: int = 0
    fallback_rows: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    images: int = 0


def run_pipeline(config: PipelineConfig) -> RunStats:
    claims = read_csv(config.input_csv)
    user_history = load_user_history(config.user_history_csv)
    requirements = load_requirements(config.evidence_requirements_csv)
    cache = read_cache(config.cache_path)
    client = LiteLLMClient(
        model=config.model,
        fallback_model=config.fallback_model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    output_rows: list[dict[str, str]] = []
    stats = RunStats(rows=len(claims))

    for row in claims:
        image_paths = split_image_paths(row.get("image_paths", ""))
        meta = image_metadata(image_paths)
        image_ids = [str(item["id"]) for item in meta]
        stats.images += len(meta)
        history = user_history.get(row.get("user_id", ""))
        default_reason = "The claim needs vision-model review to verify the submitted images."
        key = cache_key(row, meta, config.model)

        raw_prediction: dict[str, Any]
        user_id = row.get("user_id", "?")
        claim_object = row.get("claim_object", "?")
        num_images = len(meta)
        if key in cache:
            stats.cache_hits += 1
            raw_prediction = cache[key]["prediction"]
            print(f"[{stats.cache_hits + stats.model_calls + stats.fallback_rows}/{stats.rows}] {user_id} {claim_object} images={num_images} source=cache")
        elif config.use_llm:
            try:
                messages = build_messages(row, history, requirements, meta)
                result = client.complete(messages)
                stats.model_calls += 1
                stats.input_tokens += result.input_tokens
                stats.output_tokens += result.output_tokens
                raw_prediction = parse_json_object(result.content)
                cache[key] = {
                    "prediction": raw_prediction,
                    "model": result.model,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                }
                write_cache(config.cache_path, cache)
                print(f"[{stats.cache_hits + stats.model_calls + stats.fallback_rows}/{stats.rows}] {user_id} {claim_object} images={num_images} source=llm tokens={result.input_tokens}+{result.output_tokens}")
            except (LLMUnavailable, ValueError, KeyError) as exc:
                stats.fallback_rows += 1
                raw_prediction = fallback_prediction(row, history, meta, f"LLM review unavailable: {exc}")
                err_msg = str(exc).replace("\n", " ")
                print(f"[{stats.cache_hits + stats.model_calls + stats.fallback_rows}/{stats.rows}] {user_id} {claim_object} images={num_images} source=fallback reason=llm_error error='{err_msg}'")
        else:
            stats.fallback_rows += 1
            raw_prediction = fallback_prediction(row, history, meta, default_reason)
            print(f"[{stats.cache_hits + stats.model_calls + stats.fallback_rows}/{stats.rows}] {user_id} {claim_object} images={num_images} source=fallback reason=no_llm")

        prediction = normalize_prediction(
            raw_prediction,
            row.get("claim_object", ""),
            image_ids,
            default_reason,
        )
        merge_history_risk(prediction, history)
        output_rows.append({**row, **prediction})

    write_output(config.output_csv, output_rows)
    write_cache(config.cache_path, cache)
    return stats
