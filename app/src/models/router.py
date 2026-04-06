"""Smart model selection router.

Uses a fast LLM to select the best model from a preset's candidate list
based on task intent. Falls back to the first sorted model if the router
is disabled or fails.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from config import MODEL_ROUTER_MODEL, MODEL_ROUTER_ENABLED, LLM_API_KEY
from models.loader import ModelPreset, TierConfig, get_model_preset_manager, get_tier_config_manager
from storage.model_registry import ModelInfo

logger = logging.getLogger(__name__)


def _build_router_prompt(
    condensed_intent: str,
    preset_name: str,
    sort_strategy: str,
    models: List[ModelInfo],
) -> str:
    """Build a compact prompt for the router model."""
    lines = [
        "You are a model router. Given a task and candidate models, select the best one.",
        "",
        f"Task: {condensed_intent}",
        f"Category: {preset_name} (pre-sorted by {sort_strategy})",
        "",
        "Candidates:",
    ]
    for i, m in enumerate(models, 1):
        price = m.avg_price()
        price_str = f"${price * 1_000_000:.2f}/M" if price < float("inf") else "N/A"
        ctx_str = f"{m.context_size // 1000}K"
        lat_str = f"{int(m.latency)}ms" if m.latency else "N/A"
        tools_str = "yes" if m.tool_support else "no"
        lines.append(
            f"  {i}. {m.model_id}  context={ctx_str}  price={price_str}  "
            f"latency={lat_str}  tools={tools_str}"
        )

    lines.extend([
        "",
        "Select the best model for this task. Consider capability needs, cost, and speed.",
        "Respond with ONLY the model ID. No explanation.",
    ])
    return "\n".join(lines)


async def select_model(
    preset: ModelPreset,
    condensed_intent: str,
    model_registry: Optional["ModelRegistry"] = None,
) -> str:
    """Select the best model from a preset's candidate list.

    If MODEL_ROUTER_ENABLED is false or the router call fails, returns
    the first model in the pre-sorted list.

    Args:
        preset: The ModelPreset to select from
        condensed_intent: The task description for routing
        model_registry: Optional ModelRegistry for metadata (defaults to factory)

    Returns:
        Selected model ID string
    """
    if model_registry is None:
        try:
            from storage.factory import get_model_registry
            model_registry = get_model_registry()
        except RuntimeError:
            model_registry = None

    # Get model info for candidates
    if model_registry:
        sorted_ids = model_registry.sort_models(preset.model_ids, preset.sort_by)
        models = model_registry.get_models(sorted_ids)
    else:
        sorted_ids = list(preset.model_ids)
        models = []

    if not sorted_ids:
        logger.warning(f"[Router] No models in preset '{preset.name}', falling back")
        return preset.model_ids[0] if preset.model_ids else ""

    # If router is disabled, return first sorted model
    if not MODEL_ROUTER_ENABLED:
        logger.info(f"[Router] Disabled, using first sorted: {sorted_ids[0]}")
        return sorted_ids[0]

    # If no model metadata available, return first sorted
    if not models:
        logger.warning(f"[Router] No model metadata (registry likely empty), using first YAML fallback: {sorted_ids[0]}")
        return sorted_ids[0]

    # Build prompt and call router model
    prompt = _build_router_prompt(condensed_intent, preset.name, preset.sort_by, models)

    try:
        import httpx
        from orchestrator.executor import call_openrouter

        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await call_openrouter(
                model=f"openrouter/{MODEL_ROUTER_MODEL}",
                messages=[{"role": "user", "content": prompt}],
                tools=None,
                http_client=http_client,
            )

        selected = response.content.strip()

        # Validate response is a known model ID
        candidate_set = set(sorted_ids)
        if selected in candidate_set:
            logger.info(f"[Router] Selected: {selected} for preset={preset.name}")
            return selected

        # Try partial match (some models may have provider prefix stripped)
        for mid in sorted_ids:
            if mid in selected or selected in mid:
                logger.info(f"[Router] Selected: {mid} (matched '{selected}') for preset={preset.name}")
                return mid

        # Fallback to first sorted
        logger.warning(f"[Router] Invalid selection '{selected}', falling back to {sorted_ids[0]}")
        return sorted_ids[0]

    except Exception as e:
        logger.warning(f"[Router] Call failed: {e}, falling back to {sorted_ids[0]}")
        return sorted_ids[0]


async def select_model_for_specialist(
    specialist_preset: str,
    condensed_intent: str,
) -> str:
    """Select a model for a specialist subagent.

    Maps specialist.preset (e.g., "@preset/code") to a ModelPreset from
    the YAML config, then calls the router. Falls back to the original
    specialist.preset if no matching YAML preset exists.

    Args:
        specialist_preset: The specialist's preset string (e.g., "@preset/code")
        condensed_intent: The condensed task from the delegation pipeline

    Returns:
        Selected model ID, or the original specialist_preset as fallback
    """
    mgr = get_model_preset_manager()
    if not mgr.is_initialized():
        return specialist_preset

    preset_name = mgr.resolve_preset_name(specialist_preset)

    preset = mgr.get_preset(preset_name)
    if preset is None:
        # No matching YAML preset, fall back to original
        logger.debug(f"[Router] No YAML preset for '{preset_name}', using original: {specialist_preset}")
        return specialist_preset

    return await select_model(preset, condensed_intent)


def select_model_for_tier(tier_number: int) -> Optional[str]:
    """Select a model for the main agent based on tier.

    No router LLM call -- tier selection itself is the routing decision.
    Returns the first model in the tier's sorted list.

    Args:
        tier_number: Tier number (0=air, 1=standard, 2=heavy)

    Returns:
        Selected model ID, or None if tier config not found
    """
    mgr = get_tier_config_manager()
    if not mgr.is_initialized():
        return None

    tier_config = mgr.get_tier(tier_number)
    if tier_config is None:
        return None

    try:
        from storage.factory import get_model_registry
        model_registry = get_model_registry()
        sorted_ids = model_registry.sort_models(tier_config.model_ids, tier_config.sort_by)
    except RuntimeError:
        logger.warning(f"[Router] Model registry not available, using YAML fallback for tier {tier_number}")
        sorted_ids = list(tier_config.model_ids)

    if sorted_ids:
        logger.info(f"[Router] Tier {tier_number} -> {sorted_ids[0]}")
        return sorted_ids[0]

    return None
