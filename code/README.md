# HackerRank Orchestrate Solution

Python evidence-review pipeline for the multi-modal damage-claim task.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r code/requirements.txt
```

Set provider credentials through environment variables only. For example:

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
export HRO_MODEL="openrouter/qwen/qwen3.5-flash-02-23"
```

Or use the provided `code/.env` file which is auto-loaded at runtime.

`LiteLLM` is used as the client abstraction. The pipeline imports it only inside `code/orchestrate/llm_client.py`, so provider/model changes stay isolated from the rest of the workflow.

---

## 1. Run the Pipeline

Generate predictions on the full test set:

```bash
python3 code/main.py
```

This reads `dataset/claims.csv` and writes root-level `output.csv`.

Useful options:

```bash
# Custom input/output paths
python3 code/main.py --input dataset/claims.csv --output output.csv

# Fallback mode — no LLM calls, deterministic rules only
python3 code/main.py --no-llm --output /tmp/fallback_output.csv

# Check model health before running
python3 code/check_model_health.py
```

> `--no-llm` is a schema-valid fallback/smoke-test mode. The intended quality path uses a vision-capable model through LiteLLM.

---

## 2. Evaluate

Compare predictions against `dataset/sample_claims.csv`:

```bash
# Fallback baseline only (fast, no API calls)
python3 code/evaluation/main.py

# Include LLM predictions (slower, costs tokens)
python3 code/evaluation/main.py --run-llm
```

Outputs:

- `code/evaluation/evaluation_report.md` — full markdown report with accuracy tables
- `code/evaluation/sample_predictions_keyword_fallback.csv` — fallback predictions
- `code/evaluation/sample_predictions_litellm_vision.csv` — LLM predictions (only with `--run-llm`)

The report shows:
- **Exact row accuracy** — % of rows where every field matches expected
- **Per-field accuracy** — broken down by `claim_status`, `issue_type`, `object_part`, etc.
- **Error analysis** — first 12 mismatches with expected vs predicted
- **Operational stats** — model calls, token usage, cache hits

Cache files live under `.cache/orchestrate/` and are not needed for submission.

---

## 3. Review GUI (Optional)

Browse predictions with an inline image viewer:

```bash
python3 code/gui.py --predictions output.csv
```

The GUI uses Tkinter from the Python standard library. Install Pillow for inline JPEG previews; otherwise use the image buttons to open files externally.

---

## 4. Validate and Submit

Check that all required artifacts are present:

```bash
python3 code/validate_submission.py
```

The validator checks `output.csv` row count, required columns, `code/evaluation/evaluation_report.md`, and `code/README.md`.

Create the submission zip:

```bash
python3 code/package_submission.py
```

This creates root-level `code.zip` and excludes caches, virtualenvs, bytecode, and temporary files.

You can also use the `submission` module directly:

```bash
python3 -m submission validate
python3 -m submission package --output my_submission.zip
```

---

## Runtime Notes

- The pipeline makes at most one model call per uncached claim row.
- Successful model responses are cached using row content, image metadata, and model name.
- Temperature defaults to `0` for reproducibility.
- Required output values are normalized against the allowed enums in `problem_statement.md`.
- The evaluation pipeline uses `dataset/sample_claims.csv` which contains expected outputs for development.
