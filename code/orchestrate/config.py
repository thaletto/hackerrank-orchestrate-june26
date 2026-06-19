"""Runtime configuration for the evidence review pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "dataset"

_ = load_dotenv(REPO_ROOT / "code" / ".env")


@dataclass(frozen=True)
class PipelineConfig:
    input_csv: Path
    output_csv: Path
    user_history_csv: Path
    evidence_requirements_csv: Path
    cache_path: Path
    model: str
    fallback_model: str | None
    temperature: float
    max_tokens: int
    use_llm: bool


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def default_config(
    input_csv: Path | None = None,
    output_csv: Path | None = None,
    cache_name: str = "test_cache.json",
) -> PipelineConfig:
    cache_dir = REPO_ROOT / ".cache" / "orchestrate"
    return PipelineConfig(
        input_csv=input_csv or DATASET_DIR / "claims.csv",
        output_csv=output_csv or REPO_ROOT / "output.csv",
        user_history_csv=DATASET_DIR / "user_history.csv",
        evidence_requirements_csv=DATASET_DIR / "evidence_requirements.csv",
        cache_path=cache_dir / cache_name,
        model=os.getenv("HRO_MODEL", "gpt-4o-mini"),
        fallback_model=os.getenv("HRO_FALLBACK_MODEL") or None,
        temperature=float(os.getenv("HRO_TEMPERATURE", "0")),
        max_tokens=int(os.getenv("HRO_MAX_TOKENS", "900")),
        use_llm=env_bool("HRO_USE_LLM", True),
    )
