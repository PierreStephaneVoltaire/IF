"""Health module for IF Prototype A1.

Provides DynamoDB-backed training program storage, powerlifting tools,
and ChromaDB-backed RAG for health documents.

Public API:
    - ProgramStore: DynamoDB store for training programs
    - ProgramNotFoundError: Exception when program not found
    - HealthDocsRAG: ChromaDB RAG for health documents
    - init_tools: Initialize tools with store instance
    - health_get_program: Get full training program
    - health_comp_countdown: Competition countdown metrics
    - health_update_session: Update a session by date
    - health_new_version: Create new program version
    - kg_to_lb: Convert kg to pounds
    - lb_to_kg: Convert pounds to kg
    - ipf_weight_classes: Get IPF weight classes
    - pct_of_max: Calculate percentage of max
    - calculate_attempts: Calculate competition attempts
    - days_until: Calculate days until target date
    - health_rag_search: Search health documents
    - render_program_summary: Render program as markdown
    - render_session: Render session as markdown
"""
from health.program_store import ProgramStore, ProgramNotFoundError
from health.rag import HealthDocsRAG
from health.tools import (
    init_tools,
    health_get_program,
    health_comp_countdown,
    health_update_session,
    health_new_version,
    kg_to_lb,
    lb_to_kg,
    ipf_weight_classes,
    pct_of_max,
    calculate_attempts,
    days_until,
    health_rag_search,
)
from health.renderer import render_program_summary, render_session

__all__ = [
    # Classes
    "ProgramStore",
    "ProgramNotFoundError",
    "HealthDocsRAG",
    # Initialization
    "init_tools",
    # Tools
    "health_get_program",
    "health_comp_countdown",
    "health_update_session",
    "health_new_version",
    "kg_to_lb",
    "lb_to_kg",
    "ipf_weight_classes",
    "pct_of_max",
    "calculate_attempts",
    "days_until",
    "health_rag_search",
    # Renderer
    "render_program_summary",
    "render_session",
]
