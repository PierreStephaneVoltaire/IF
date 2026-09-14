from pathlib import Path
import os
import sys

import pytest


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))

from agent.codex_specialists import (
    MAX_NATIVE_CHILDREN,
    generate_specialist_tomls,
    load_codex_specialists,
    render_specialist_toml,
    validate_specialist_scope,
)


def test_loads_all_specialists_and_preserves_persona():
    specialists = load_codex_specialists(ROOT)
    assert len(specialists) == 54
    assert "coder" in specialists
    assert "software engineering specialist" in specialists["coder"].prompt
    assert specialists["powerlifting_coach"].directive_types == ("health", "competition")


def test_rendering_scopes_tools_directives_and_credentials():
    specialist = load_codex_specialists(ROOT)["finance_write"]
    rendered = render_specialist_toml(
        specialist,
        ROOT,
        "job-123",
        mcp_endpoints={"if_tools": "https://if-tools.invalid/mcp"},
        mcp_credentials={"if_tools": "IF_TOOLS_TOKEN"},
        directive_text=lambda types: f"types={','.join(types)}",
    )
    assert "job-123" in rendered
    assert "finance_update_account" in rendered
    assert "types=finance" in rendered
    assert "IF_TOOLS_TOKEN" not in rendered
    assert "secret-value" not in rendered
    assert "shell_tool = false" in rendered
    assert "apps = false" in rendered


def test_generation_is_offline_and_validates_scopes(tmp_path):
    specialists = load_codex_specialists(ROOT)
    for specialist in specialists.values():
        validate_specialist_scope(specialist)
    paths = generate_specialist_tomls(ROOT, "job-123", tmp_path)
    assert len(paths) == 54
    assert paths["coder"].read_text().startswith('name = "coder"')
    with pytest.raises(ValueError, match="cannot exceed"):
        validate_specialist_scope(specialists["coder"], MAX_NATIVE_CHILDREN + 1)
