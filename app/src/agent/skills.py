"""Skill loader for AgentSkills-compliant skill packages.

Skills are loaded per-specialist at spawn time, not globally.
The main agent does not load skills (context size concern).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

from config import SKILLS_PATH

logger = logging.getLogger(__name__)

# Module-level cache: skill_name → Skill object
_skill_cache: Dict[str, object] = {}
_loaded = False


def _ensure_loaded() -> None:
    """Load skills from SKILLS_PATH directory if not already loaded."""
    global _loaded, _skill_cache

    if _loaded:
        return

    skills_dir = Path(SKILLS_PATH)
    if not skills_dir.is_dir():
        logger.debug(f"[Skills] Skills directory not found: {skills_dir}")
        _loaded = True
        return

    try:
        from openhands.sdk import load_skills_from_dir

        repo_skills, knowledge_skills, agent_skills = load_skills_from_dir(str(skills_dir))

        # Flatten all skill categories into single cache
        for skill_dict in (repo_skills, knowledge_skills, agent_skills):
            for name, skill in skill_dict.items():
                _skill_cache[name] = skill

        logger.info(f"[Skills] Loaded {len(_skill_cache)} skills from {skills_dir}")
        _loaded = True

    except Exception as e:
        logger.warning(f"[Skills] Failed to load skills from {skills_dir}: {e}")
        _loaded = True


def load_skills_for_specialist(skill_names: List[str]) -> List[object]:
    """Load specific skills by name for a specialist.

    Args:
        skill_names: List of skill names the specialist declared

    Returns:
        List of Skill objects that were found
    """
    if not skill_names:
        return []

    _ensure_loaded()

    skills = []
    missing = []

    for name in skill_names:
        if name in _skill_cache:
            skills.append(_skill_cache[name])
        else:
            missing.append(name)

    if missing:
        logger.warning(f"[Skills] Skills not found: {missing}")

    if skills:
        logger.info(f"[Skills] Loaded {len(skills)} skills for specialist: {skill_names}")

    return skills


def list_available_skills() -> List[str]:
    """List all available skill names.

    Returns:
        List of skill names that can be used in specialist configs
    """
    _ensure_loaded()
    return list(_skill_cache.keys())


def reload_skills() -> int:
    """Force reload of skills from disk.

    Returns:
        Number of skills loaded
    """
    global _loaded, _skill_cache
    _loaded = False
    _skill_cache = {}
    _ensure_loaded()
    return len(_skill_cache)
