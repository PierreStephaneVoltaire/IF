"""Specialist subagent registry and configuration.

This module defines the specialist subagents that can be spawned by the
main agent for deep domain expertise. Each specialist has:
- A specific domain focus (debugger, architect, secops, etc.)
- Filtered directives relevant to their domain
- Custom prompt templates
- Optional MCP servers and tools

Specialists are spawned via the spawn_specialist tool in subagents.py.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config import SPECIALIST_PRESET, SPECIALIST_MAX_TURNS
from agent.prompts.loader import render_template


logger = logging.getLogger(__name__)


@dataclass
class SpecialistConfig:
    """Configuration for a specialist subagent.

    Attributes:
        slug: URL-safe identifier (e.g., "debugger", "architect")
        description: Human-readable description for tool UI
        template: Jinja2 template name (e.g., "specialists/debugger.j2")
        tools: List of tool names this specialist can use
        mcp_servers: List of MCP server slugs to attach
        directive_types: Types of directives to inject (e.g., ["code", "security"])
        preset: OpenRouter preset to use
        max_turns: Maximum turns before timeout
    """
    slug: str
    description: str
    template: str
    tools: List[str] = field(default_factory=list)
    mcp_servers: List[str] = field(default_factory=list)
    directive_types: List[str] = field(default_factory=lambda: ["core"])
    preset: str = SPECIALIST_PRESET
    max_turns: int = SPECIALIST_MAX_TURNS


# =============================================================================
# Specialist Registry
# =============================================================================

SPECIALISTS: Dict[str, SpecialistConfig] = {
    "debugger": SpecialistConfig(
        slug="debugger",
        description="Deep code debugging and error analysis specialist",
        template="specialists/debugger.j2",
        tools=["terminal_execute", "read_file", "write_file", "search_files"],
        mcp_servers=[],
        directive_types=["code", "architecture"],
    ),
    "architect": SpecialistConfig(
        slug="architect",
        description="System architecture and design patterns specialist",
        template="specialists/architect.j2",
        tools=["read_file", "write_file", "search_files"],
        mcp_servers=["aws_docs"],
        directive_types=["architecture", "code"],
    ),
    "secops": SpecialistConfig(
        slug="secops",
        description="Security operations and vulnerability analysis specialist",
        template="specialists/secops.j2",
        tools=["terminal_execute", "read_file", "search_files"],
        mcp_servers=[],
        directive_types=["security", "code"],
    ),
    "devops": SpecialistConfig(
        slug="devops",
        description="Infrastructure and deployment automation specialist",
        template="specialists/devops.j2",
        tools=["terminal_execute", "read_file", "write_file"],
        mcp_servers=[],
        directive_types=["code", "architecture"],
    ),
    "financial_analyst": SpecialistConfig(
        slug="financial_analyst",
        description="Financial data analysis and market research specialist",
        template="specialists/financial_analyst.j2",
        tools=["read_file"],
        mcp_servers=["yahoo_finance", "alpha_vantage"],
        directive_types=["finance", "competition"],
    ),
    "health_write": SpecialistConfig(
        slug="health_write",
        description="Use health_write when a mutation to the training program is required: logging a completed session, updating body weight, recording RPE, changing attempt targets, updating supplement protocol, or any other write to the health DynamoDB record. Do not use for read-only queries.",
        template="specialists/health_write.j2",
        tools=["health_get_program", "health_get_session", "health_update_session"],
        mcp_servers=[],
        directive_types=["health"],
    ),
    "web_researcher": SpecialistConfig(
        slug="web_researcher",
        description="Web research and information synthesis specialist",
        template="specialists/web_researcher.j2",
        tools=["read_file", "write_file"],
        mcp_servers=[],
        directive_types=["core", "competition"],
    ),
    "finance_write": SpecialistConfig(
        slug="finance_write",
        description=(
            "Use finance_write when a mutation to the finance snapshot is required: "
            "updating account balances, modifying goals, changing cashflow entries, "
            "updating investment holdings, recording tax room, or any other write "
            "to the finance DynamoDB record. Do not use for read-only queries."
        ),
        template="specialists/finance_write.j2",
        tools=[
            "finance_get_profile", "finance_get_goals", "finance_get_accounts",
            "finance_get_investments", "finance_get_cashflow", "finance_get_tax",
            "finance_get_insurance", "finance_get_net_worth",
            "finance_update_profile", "finance_update_goals", "finance_update_risk_profile",
            "finance_update_net_worth", "finance_update_account",
            "finance_add_holding", "finance_update_holding", "finance_update_watchlist",
            "finance_update_cashflow", "finance_update_tax", "finance_update_insurance",
        ],
        mcp_servers=[],
        directive_types=["finance"],
    ),
    "proofreader": SpecialistConfig(
        slug="proofreader",
        description=(
            "General prose proofreading, editing, and rewriting. Use for grammar, "
            "clarity, tone, flow, and structure improvements on any non-code text."
        ),
        template="specialists/proofreader.j2",
        tools=[],
        mcp_servers=[],
        directive_types=["writing", "core"],
    ),
    "jira_writer": SpecialistConfig(
        slug="jira_writer",
        description=(
            "Jira ticket writing specialist. Use when the operator needs a well-structured "
            "issue with summary, description, acceptance criteria, subtasks, and metadata."
        ),
        template="specialists/jira_writer.j2",
        tools=[],
        mcp_servers=[],
        directive_types=["writing", "code"],
    ),
    "email_writer": SpecialistConfig(
        slug="email_writer",
        description=(
            "Professional and formal email drafting. Use for emails requiring careful "
            "tone, relationship-aware structure, or sensitive subject matter."
        ),
        template="specialists/email_writer.j2",
        tools=[],
        mcp_servers=[],
        directive_types=["writing"],
    ),
    "constrained_writer": SpecialistConfig(
        slug="constrained_writer",
        description=(
            "Character-limited content specialist. Use for tweets (280), YouTube superchats (200), "
            "Discord messages, SMS, Bluesky (300), or any content with a hard character limit. "
            "Always include character count in output."
        ),
        template="specialists/constrained_writer.j2",
        tools=[],
        mcp_servers=[],
        directive_types=["writing"],
    ),
}


# =============================================================================
# Skills (mode modifiers for specialists)
# =============================================================================

SKILLS: List[str] = [
    "red_team",   # Adversarial/attack perspective
    "blue_team",  # Defensive/protection perspective
    "pro_con",    # Pros and cons analysis
]


# =============================================================================
# Helper Functions
# =============================================================================

def get_specialist(slug: str) -> Optional[SpecialistConfig]:
    """Get specialist configuration by slug.

    Args:
        slug: Specialist identifier (e.g., "debugger")

    Returns:
        SpecialistConfig if found, None otherwise
    """
    return SPECIALISTS.get(slug)


def list_specialists() -> List[SpecialistConfig]:
    """Get all available specialist configurations.

    Returns:
        List of all SpecialistConfig objects
    """
    return list(SPECIALISTS.values())


def render_specialist_prompt(
    specialist: SpecialistConfig,
    task: str,
    context: Optional[str] = None,
    directives: Optional[str] = None,
    skill: Optional[str] = None,
    pk: Optional[str] = None,
    sk: Optional[str] = None
) -> str:
    """Render a specialist's prompt template.

    Args:
        specialist: SpecialistConfig object
        task: The task description for the specialist
        context: Optional context/background information
        directives: Optional formatted directives block
        skill: Optional skill mode (red_team, blue_team, pro_con)
        pk: Optional primary key for DynamoDB operations
        sk: Optional sort key for DynamoDB operations

    Returns:
        Rendered prompt string
    """
    return render_template(
        specialist.template,
        task=task,
        context=context or "",
        directives=directives or "",
        skill=skill,
        pk=pk or "operator",
        sk=sk or "program#current",
    )
