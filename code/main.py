from __future__ import annotations

import argparse
from pathlib import Path
import os
from orchestrate.config import default_config
from orchestrate.pipeline import run_pipeline

os.environ["LITELLM_LOG"] = "DEBUG" 

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run evidence review on claims.csv.")
    parser.add_argument("--input", type=Path, default=None, help="Claims CSV path.")
    parser.add_argument("--output", type=Path, default=None, help="Output CSV path.")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LiteLLM calls and emit schema-valid fallback predictions.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = default_config(input_csv=args.input, output_csv=args.output)
    if args.no_llm:
        config = config.__class__(**{**config.__dict__, "use_llm": False})
    stats = run_pipeline(config)
    print(
        "Wrote "
        f"{config.output_csv} for {stats.rows} rows "
        f"({stats.model_calls} model calls, {stats.cache_hits} cache hits, "
        f"{stats.fallback_rows} fallback rows)."
    )


if __name__ == "__main__":
    main()
