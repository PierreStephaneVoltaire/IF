from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

import yaml
from jinja2 import Environment, FileSystemLoader


DEFAULT_MODEL = "gpt-5.6-luna"
MAX_NATIVE_CHILDREN = 2
DEFAULT_SKILLS = {
    "deep_think": "reason deeply, state assumptions, and preserve uncertainty",
    "sequential_plan": "sequence dependent work and verify each completed step",
    "parallel_analysis": "delegate at most two independent lenses and synthesize agreement and disagreement",
}


@dataclass(frozen=True)
class CodexSpecialist:
    slug: str
    description: str
    prompt: str
    tools: tuple[str, ...] = ()
    mcp_servers: tuple[str, ...] = ()
    directive_types: tuple[str, ...] = ("core",)
    model: str = DEFAULT_MODEL
    reasoning_effort: str = "medium"
    max_turns: int = 15
    max_iterations: int = 25
    skills: tuple[str, ...] = ()
    sandbox_mode: str = "workspace-write"
    permissions: Mapping[str, str] = field(default_factory=dict)


def _specialists_root(root: Path) -> Path:
    return root / "specialists"


def _render_prompt(environment: Environment, slug: str, task: str = "", context: str = "", directives: str = "", athlete: str = "") -> str:
    return environment.get_template(f"{slug}/agent.j2").render(
        task=task,
        context=context,
        directives=directives,
        skill=None,
        pk=athlete or "authenticated Athlete",
        sk="program#current",
        injected_context="",
    ).strip()


def load_codex_specialists(
    root: str | Path,
    models: Mapping[str, str] | None = None,
    task: str = "",
    context: str = "",
    directives: str = "",
    athlete: str = "",
) -> dict[str, CodexSpecialist]:
    root_path = Path(root).resolve()
    specialists_root = _specialists_root(root_path)
    environment = Environment(
        loader=FileSystemLoader(str(specialists_root)),
        autoescape=False,
    )
    result: dict[str, CodexSpecialist] = {}
    for config_path in sorted(specialists_root.glob("*/specialist.yaml")):
        data = yaml.safe_load(config_path.read_text()) or {}
        slug = config_path.parent.name
        prompt_path = config_path.parent / "agent.j2"
        if not prompt_path.exists():
            continue
        prompt = _render_prompt(environment, slug, task, context, directives, athlete)
        result[slug] = CodexSpecialist(
            slug=slug,
            description=str(data.get("description") or slug).strip(),
            prompt=prompt,
            tools=tuple(str(value) for value in data.get("tools", []) or []),
            mcp_servers=tuple(str(value) for value in data.get("mcp_servers", []) or []),
            directive_types=tuple(str(value) for value in data.get("directive_types", ["core"]) or ["core"]),
            model=(models or {}).get(slug, "gpt-5.6-terra" if any(term in slug for term in ("review", "analys", "coach", "research")) else DEFAULT_MODEL),
            reasoning_effort=str(data.get("reasoning_effort", "medium")),
            max_turns=int(data.get("max_turns", data.get("max_iterations", 15))),
            max_iterations=int(data.get("max_iterations", 25)),
            skills=tuple(str(value) for value in data.get("skills", []) or []),
            sandbox_mode=str(data.get("sandbox_mode", "workspace-write" if data.get("agentic") else "read-only")),
            permissions={str(name): "allow" for name in data.get("tools", []) or []},
        )
    return result


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _toml_array(values: tuple[str, ...] | list[str]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def _scoped_directives(
    specialist: CodexSpecialist,
    directive_text: str | Callable[[tuple[str, ...]], str] | None,
) -> str:
    if callable(directive_text):
        return directive_text(specialist.directive_types).strip()
    return str(directive_text or "").strip()


def render_specialist_toml(
    specialist: CodexSpecialist,
    root_path: str | Path,
    current_job: str,
    mcp_endpoints: Mapping[str, str] | None = None,
    mcp_credentials: Mapping[str, str] | None = None,
    directive_text: str | Callable[[tuple[str, ...]], str] | None = None,
    selected_skills: tuple[str, ...] = (),
) -> str:
    directives = _scoped_directives(specialist, directive_text)
    skills = tuple(dict.fromkeys((*specialist.skills, *selected_skills)))
    instructions = [
        specialist.prompt,
        f"You are the native Codex Specialist '{specialist.slug}'.",
        f"Current turn scope: {current_job}.",
        "The parent native turn owns this Conversation. Return your result to the parent and never submit another top-level job.",
        "Use only your scoped IF tools: " + ", ".join(specialist.tools) + ". Use the declared search tools for research. Treat files outside the current Conversation scope as unavailable.",
    ]
    if directives:
        instructions.extend(("Applicable Directives:", directives))
    if skills:
        instructions.append("Native skills: " + "; ".join(DEFAULT_SKILLS.get(skill, skill) for skill in skills))
    lines = [
        f"name = {_toml_string(specialist.slug)}",
        f"description = {_toml_string(specialist.description)}",
        f"model = {_toml_string(specialist.model)}",
        f"model_reasoning_effort = {_toml_string(specialist.reasoning_effort)}",
        f"developer_instructions = {_toml_string(chr(10).join(instructions))}",
        "",
        "[features]",
        "shell_tool = false",
        "apps = false",
        "plugins = false",
        "memory_tool = false",
        "request_permissions_tool = false",
    ]
    return "\n".join(lines) + "\n"


def generate_specialist_tomls(
    root_path: str | Path,
    current_job: str,
    output_dir: str | Path,
    models: Mapping[str, str] | None = None,
    mcp_endpoints: Mapping[str, str] | None = None,
    mcp_credentials: Mapping[str, str] | None = None,
    directive_text: str | Callable[[tuple[str, ...]], str] | None = None,
    selected_skills: tuple[str, ...] = (),
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    generated = {}
    for slug, specialist in load_codex_specialists(root_path, models=models).items():
        path = output / f"{slug}.toml"
        path.write_text(render_specialist_toml(
            specialist,
            root_path,
            current_job,
            mcp_endpoints,
            mcp_credentials,
            directive_text,
            selected_skills,
        ))
        generated[slug] = path
    return generated


def validate_specialist_scope(specialist: CodexSpecialist, max_children: int = MAX_NATIVE_CHILDREN) -> None:
    if max_children > MAX_NATIVE_CHILDREN:
        raise ValueError(f"native child limit cannot exceed {MAX_NATIVE_CHILDREN}")
    if len(set(specialist.tools)) != len(specialist.tools):
        raise ValueError(f"duplicate tool in specialist {specialist.slug}")
    if set(specialist.permissions) != set(specialist.tools):
        raise ValueError(f"tool permissions are incomplete for specialist {specialist.slug}")
    if any(not value for value in specialist.mcp_servers):
        raise ValueError(f"empty MCP server in specialist {specialist.slug}")


def specialist_models_from_environment(slugs: tuple[str, ...]) -> dict[str, str]:
    return {slug: os.getenv(f"IF_CODEX_MODEL_{slug.upper()}", DEFAULT_MODEL) for slug in slugs}


def codex_runtime_overrides() -> tuple[str, ...]:
    return (
        "agents.enabled=true",
        f"agents.max_concurrent_threads_per_session={MAX_NATIVE_CHILDREN}",
    )
