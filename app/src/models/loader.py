"""YAML-based model preset configuration loader.

Loads model preset definitions from models/presets.yaml. Each preset maps
a named category (code, architecture, general, etc.) to a list of concrete
OpenRouter model IDs with a sorting strategy.

Mirrors the specialist auto-discovery pattern: scans MODELS_PATH at import
time, no code changes needed to add presets.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from config import MODELS_PATH

logger = logging.getLogger(__name__)

_PRESETS_FILE = Path(MODELS_PATH) / "presets.yaml"


@dataclass
class ModelPreset:
    """A named preset mapping to concrete model IDs."""

    name: str
    model_ids: List[str] = field(default_factory=list)
    sort_by: str = "price_asc"
    when: str = ""


@dataclass
class TierConfig:
    """Tier configuration for the main agent."""

    name: str
    model_ids: List[str] = field(default_factory=list)
    sort_by: str = "price_asc"
    context_limit: int = 200000


class ModelPresetManager:
    """Loads and provides access to model preset configurations."""

    def __init__(self):
        self.presets: Dict[str, ModelPreset] = {}
        self.tiers: Dict[str, TierConfig] = {}
        self.provider: str = "openrouter"
        self._initialized = False

    def load(self) -> None:
        """Load presets from YAML file."""
        from agent.prompts.yaml_loader import load_yaml

        if not _PRESETS_FILE.exists():
            logger.warning(f"[ModelPresets] Config not found: {_PRESETS_FILE}")
            return

        try:
            data = load_yaml(_PRESETS_FILE)
        except Exception as e:
            logger.error(f"[ModelPresets] Failed to load {_PRESETS_FILE}: {e}")
            return

        self.provider = data.get("provider", "openrouter")

        for name, preset_data in data.get("presets", {}).items():
            self.presets[name] = ModelPreset(
                name=name,
                model_ids=preset_data.get("models", []),
                sort_by=preset_data.get("sort_by", "price_asc"),
                when=preset_data.get("when", ""),
            )

        for name, tier_data in data.get("tiers", {}).items():
            self.tiers[name] = TierConfig(
                name=name,
                model_ids=tier_data.get("models", []),
                sort_by=tier_data.get("sort_by", "price_asc"),
                context_limit=tier_data.get("context_limit", 200000),
            )

        self._initialized = True
        logger.info(
            f"[ModelPresets] Loaded {len(self.presets)} presets, "
            f"{len(self.tiers)} tiers from {_PRESETS_FILE}"
        )

    def get_preset(self, name: str) -> Optional[ModelPreset]:
        return self.presets.get(name)

    def get_tier(self, name: str) -> Optional[TierConfig]:
        return self.tiers.get(name)

    def get_tier_by_number(self, tier_number: int) -> Optional[TierConfig]:
        """Map tier number (0, 1, 2) to tier config."""
        names = {0: "air", 1: "standard", 2: "heavy"}
        return self.tiers.get(names.get(tier_number, ""))

    @staticmethod
    def resolve_preset_name(specialist_preset: str) -> Optional[str]:
        """Map @preset/code -> code. Returns None if not an @preset/ reference."""
        if specialist_preset.startswith("@preset/"):
            return specialist_preset[len("@preset/"):]
        return None

    def is_initialized(self) -> bool:
        return self._initialized


_model_preset_manager: Optional[ModelPresetManager] = None


def get_model_preset_manager() -> ModelPresetManager:
    """Get the global ModelPresetManager singleton."""
    global _model_preset_manager
    if _model_preset_manager is None:
        _model_preset_manager = ModelPresetManager()
    return _model_preset_manager
