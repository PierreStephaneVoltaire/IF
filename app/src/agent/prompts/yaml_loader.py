"""YAML configuration loader with environment variable interpolation.

Supports ${VAR_NAME} syntax in YAML values for secrets and runtime config.
"""
from __future__ import annotations

import os
import re
import logging
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _interpolate_env_vars(value: Any) -> Any:
    """Recursively interpolate ${VAR_NAME} patterns with environment variables.

    Args:
        value: Any YAML-parsed value (str, dict, list, etc.)

    Returns:
        Value with all ${VAR_NAME} patterns replaced by os.environ values.
        Unset variables are replaced with empty string.
    """
    if isinstance(value, str):
        def _replace(match):
            var_name = match.group(1)
            return os.environ.get(var_name, "")
        return _ENV_VAR_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _interpolate_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env_vars(item) for item in value]
    return value


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file and interpolate environment variables.

    Args:
        path: Path to the YAML file

    Returns:
        Parsed YAML data as a dictionary

    Raises:
        FileNotFoundError: If the YAML file doesn't exist
        yaml.YAMLError: If the YAML is malformed
    """
    if not path.exists():
        raise FileNotFoundError(f"YAML config not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        return {}

    return _interpolate_env_vars(data)
