"""Validate optional reproducibility metadata without importing the evaluation runner."""

from datetime import datetime, timedelta
from hashlib import sha256
import json
import re

MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,149}")


def prompt_hash(prompt):
    return sha256(prompt.encode("utf-8")).hexdigest()


def prompt_hashes(conditions):
    return {id_: prompt_hash(row["prompt"]) for id_, row in conditions.items()}


def condition_design(conditions):
    """Compare model-independent condition keys and exact prompt bytes."""
    keys = ("experiment", "fixture", "module", "version", "repeat", "temperature", "top_p")
    return {tuple(row[key] for key in keys) + (prompt_hash(row["prompt"]),) for row in conditions.values()}


def parse_run_manifest(raw, conditions):
    manifest = json.loads(raw)
    if not isinstance(manifest, dict):
        raise ValueError("The reproducibility manifest must be an object.")
    model = manifest.get("model_id")
    recorded, planned = manifest.get("recorded_conditions"), manifest.get("planned_conditions")
    try:
        timestamp = datetime.fromisoformat(manifest.get("timestamp_utc", ""))
    except (TypeError, ValueError) as error:
        raise ValueError("The reproducibility manifest has an invalid UTC timestamp.") from error
    if (type(manifest.get("schema")) is not int or manifest["schema"] != 1
            or not isinstance(model, str) or not MODEL_ID.fullmatch(model)
            or {row["model"] for row in conditions.values()} != {model}
            or manifest.get("prompt_sha256") != prompt_hashes(conditions)
            or not all(isinstance(manifest.get(name), dict) for name in ("packages", "seeds", "settings"))
            or type(recorded) is not int or type(planned) is not int or recorded != len(conditions) or planned < recorded
            or timestamp.utcoffset() != timedelta(0)):
        raise ValueError("The reproducibility manifest does not match the run.")
    return manifest
