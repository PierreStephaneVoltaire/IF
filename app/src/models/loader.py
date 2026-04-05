"""YAML-based model preset and tier configuration loaders.

Two separate configs:
- models/presets.yaml — subagent presets (code, architecture, shell, etc.)
- models/tiers.yaml — internal tier config (air/standard/heavy + media tiers)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from config import MODELS_PATH

logger = logging.getLogger(__name__)

_PRESETS_FILE = Path(MODELS_PATH) / "presets.yaml"
_TIERS_FILE = Path(MODELS_PATH) / "tiers.yaml"


@dataclass
class ModelPreset:
    """A named preset mapping to concrete model IDs."""

    name: str
    model_ids: List[str] = field(default_factory=list)
    sort_by: str = "price_asc"
    when: str = ""


@dataclass
class TierConfig:
    """Tier configuration."""

    name: str
    model_ids: List[str] = field(default_factory=list)
    sort_by: str = "price_asc"
    context_limit: int = 200000


class ModelPresetManager:
    """Loads and provides access to subagent model preset configurations.

    Reads from models/presets.yaml only. For tier config, use TierConfigManager.
    """

    def __init__(self):
        self.presets: Dict[str, ModelPreset] = {}
        self.provider: str = "openrouter"
        self._initialized = False

    def load(self) -> None:
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

        self._initialized = True
        logger.info(f"[ModelPresets] Loaded {len(self.presets)} presets from {_PRESETS_FILE}")

    def get_preset(self, name: str) -> Optional[ModelPreset]:
        return self.presets.get(name)

    @staticmethod
    def resolve_preset_name(specialist_preset: str) -> Optional[str]:
        """Map @preset/code -> code. Returns None if not an @preset/ reference."""
        if specialist_preset.startswith("@preset/"):
            return specialist_preset[len("@preset/"):]
        return None

    def is_initialized(self) -> bool:
        return self._initialized


class TierConfigManager:
    """Loads and provides access to internal tier configurations.

    Reads from models/tiers.yaml. Handles both conversation tiers (air/standard/heavy)
    and media tiers (air/standard/heavy for vision tasks).
    """

    def __init__(self):
        self.tiers: Dict[str, TierConfig] = {}
        self.media_tiers: Dict[str, TierConfig] = {}
        self._initialized = False

    def load(self) -> None:
        from agent.prompts.yaml_loader import load_yaml

        if not _TIERS_FILE.exists():
            logger.warning(f"[TierConfig] Config not found: {_TIERS_FILE}")
            return

        try:
            data = load_yaml(_TIERS_FILE)
        except Exception as e:
            logger.error(f"[TierConfig] Failed to load {_TIERS_FILE}: {e}")
            return

        for name, tier_data in data.get("tiers", {}).items():
            self.tiers[name] = TierConfig(
                name=name,
                model_ids=tier_data.get("models", []),
                sort_by=tier_data.get("sort_by", "price_asc"),
                context_limit=tier_data.get("context_limit", 200000),
            )

        for name, tier_data in data.get("media_tiers", {}).items():
            self.media_tiers[name] = TierConfig(
                name=name,
                model_ids=tier_data.get("models", []),
                sort_by=tier_data.get("sort_by", "price_asc"),
                context_limit=tier_data.get("context_limit", 200000),
            )

        self._initialized = True
        logger.info(
            f"[TierConfig] Loaded {len(self.tiers)} tiers, "
            f"{len(self.media_tiers)} media tiers from {_TIERS_FILE}"
        )

    _TIER_NAMES = {0: "air", 1: "standard", 2: "heavy"}

    def get_tier(self, tier_number: int) -> Optional[TierConfig]:
        """Map tier number (0, 1, 2) to tier config."""
        name = self._TIER_NAMES.get(tier_number)
        if name is None:
            return None
        return self.tiers.get(name)

    def get_media_tier(self, tier_number: int) -> Optional[TierConfig]:
        """Map tier number (0, 1, 2) to media tier config."""
        name = self._TIER_NAMES.get(tier_number)
        if name is None:
            return None
        return self.media_tiers.get(name)

    def is_initialized(self) -> bool:
        return self._initialized


_model_preset_manager: Optional[ModelPresetManager] = None
_tier_config_manager: Optional[TierConfigManager] = None


def get_model_preset_manager() -> ModelPresetManager:
    global _model_preset_manager
    if _model_preset_manager is None:
        _model_preset_manager = ModelPresetManager()
    return _model_preset_manager


def get_tier_config_manager() -> TierConfigManager:
    global _tier_config_manager
    if _tier_config_manager is None:
        _tier_config_manager = TierConfigManager()
    return _tier_config_manager
