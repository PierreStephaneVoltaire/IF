#!/usr/bin/env python3
"""Seed the if-models DynamoDB table from the OpenRouter API.

Reads model IDs from a newline-delimited file, fetches metadata from the
OpenRouter /api/v1/models endpoint, and upserts into DynamoDB.

Also importable as a module for startup refresh.

Usage:
    python scripts/seed_models.py [--models-file models/model_ids.txt]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# Add app/src to path for imports when run as script
_SCRIPT_DIR = Path(__file__).resolve().parent
_APP_SRC = _SCRIPT_DIR.parent / "app" / "src"
if str(_APP_SRC) not in sys.path:
    sys.path.insert(0, str(_APP_SRC))

from storage.model_registry import ModelInfo, ModelRegistry

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"


def _parse_pricing(pricing_raw: Any) -> tuple[List[Dict], List[Dict]]:
    """Parse OpenRouter pricing data into input/output provider lists.

    OpenRouter returns pricing as:
      - string: "0.15" (single provider, input=output price)
      - dict: {"prompt": "0.15", "completion": "0.60"} (single provider)
      - list of dicts: [{"prompt": "0.15", "completion": "0.60"}, ...] (multi-provider)
    """
    input_pricing: List[Dict[str, str]] = []
    output_pricing: List[Dict[str, str]] = []

    if isinstance(pricing_raw, str):
        input_pricing.append({"provider": "openrouter", "price": pricing_raw})
        output_pricing.append({"provider": "openrouter", "price": pricing_raw})
    elif isinstance(pricing_raw, dict):
        input_pricing.append({"provider": "openrouter", "price": str(pricing_raw.get("prompt", "0"))})
        output_pricing.append({"provider": "openrouter", "price": str(pricing_raw.get("completion", "0"))})
    elif isinstance(pricing_raw, list):
        for i, entry in enumerate(pricing_raw):
            if isinstance(entry, dict):
                provider = entry.get("provider", f"provider-{i}")
                input_pricing.append({"provider": provider, "price": str(entry.get("prompt", "0"))})
                output_pricing.append({"provider": provider, "price": str(entry.get("completion", "0"))})

    return input_pricing, output_pricing


def _extract_model_info(model_id: str, model_data: Dict[str, Any]) -> ModelInfo:
    """Convert raw OpenRouter model data to ModelInfo."""
    arch = model_data.get("architecture", {})
    top_provider = model_data.get("top_provider", {})
    pricing_raw = model_data.get("pricing", {})
    params = model_data.get("supported_parameters", [])

    # Modalities
    input_modalities = ["text"]
    output_modalities = ["text"]

    modality = arch.get("modality", "")
    if modality:
        input_modalities = [m.strip() for m in modality.split("+") if m.strip()]
        output_modalities = list(input_modalities)

    # Tool support
    tool_support = "tools" in params or "tool_choice" in params

    # Caching support
    caching_support = "prompt_caching" in params or "caching" in params

    # Max output tokens
    max_output = top_provider.get("max_completion_tokens", 4096)
    if not max_output or max_output <= 0:
        max_output = 4096

    # Context size
    context_size = model_data.get("context_length", 4096)

    input_pricing, output_pricing = _parse_pricing(pricing_raw)

    now = datetime.now(timezone.utc).isoformat()

    return ModelInfo(
        model_id=model_id,
        context_size=context_size,
        max_output_tokens=max_output,
        input_pricing=input_pricing,
        output_pricing=output_pricing,
        input_modalities=input_modalities,
        output_modalities=output_modalities,
        tool_support=tool_support,
        caching_support=caching_support,
        zero_data_retention=model_data.get("data_controls", []) == [],
        throughput=None,
        latency=None,
        updated_at=now,
    )


async def fetch_models(
    wanted_ids: List[str],
    api_key: str,
) -> List[ModelInfo]:
    """Fetch model metadata from OpenRouter API.

    Args:
        wanted_ids: List of model IDs to look up
        api_key: OpenRouter API key

    Returns:
        List of ModelInfo for found models
    """
    wanted_set = set(wanted_ids)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(OPENROUTER_API_URL, headers=headers)
        resp.raise_for_status()

    data = resp.json()
    all_models = data.get("data", [])

    found = []
    for model in all_models:
        mid = model.get("id", "")
        if mid in wanted_set:
            info = _extract_model_info(mid, model)
            found.append(info)
            wanted_set.discard(mid)

    if wanted_set:
        logger.warning(f"Models not found on OpenRouter: {wanted_set}")

    return found


async def seed_models(
    models_file: str,
    api_key: Optional[str] = None,
    table_name: str = "if-models",
    region: str = "ca-central-1",
) -> int:
    """Seed DynamoDB from OpenRouter API.

    Args:
        models_file: Path to newline-delimited model IDs file
        api_key: OpenRouter API key (falls back to OPENROUTER_API_KEY env)
        table_name: DynamoDB table name
        region: AWS region

    Returns:
        Number of models upserted
    """
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required")

    models_path = Path(models_file)
    if not models_path.exists():
        raise FileNotFoundError(f"Models file not found: {models_path}")

    wanted_ids = [
        line.strip()
        for line in models_path.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not wanted_ids:
        logger.warning("No model IDs found in models file")
        return 0

    logger.info(f"Fetching metadata for {len(wanted_ids)} models from OpenRouter...")
    models = await fetch_models(wanted_ids, api_key)
    logger.info(f"Found {len(models)} models on OpenRouter")

    if not models:
        return 0

    registry = ModelRegistry(table_name=table_name, region=region)

    try:
        registry.load()
    except Exception as e:
        logger.warning(f"Could not load existing registry (table may not exist yet): {e}")

    registry.upsert_batch(models)
    return len(models)


def main():
    parser = argparse.ArgumentParser(description="Seed if-models DynamoDB table from OpenRouter API")
    parser.add_argument(
        "--models-file",
        default="models/model_ids.txt",
        help="Path to newline-delimited model IDs file",
    )
    parser.add_argument("--table-name", default=None, help="DynamoDB table name")
    parser.add_argument("--region", default=None, help="AWS region")
    args = parser.parse_args()

    import asyncio

    table_name = args.table_name or os.environ.get("IF_MODELS_TABLE_NAME", "if-models")
    region = args.region or os.environ.get("AWS_REGION", "ca-central-1")

    count = asyncio.run(seed_models(
        models_file=args.models_file,
        table_name=table_name,
        region=region,
    ))
    print(f"Done: {count} models upserted to {table_name}")


if __name__ == "__main__":
    main()
