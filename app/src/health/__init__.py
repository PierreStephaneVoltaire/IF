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
    # Granular load tools
    health_get_competition,
    health_list_competitions,
    health_get_diet_notes,
    health_get_session,
    health_get_sessions_range,
    health_get_supplements,
    health_get_meta,
    health_get_phases,
    health_get_current_maxes,
    health_get_operator_prefs,
    health_get_breaks,
    # Granular edit tools
    health_update_competition,
    health_update_diet_note,
    health_update_supplements,
    # Session CRUD
    health_create_session,
    health_delete_session,
    health_reschedule_session,
    health_add_exercise,
    health_remove_exercise,
    # Competition CRUD
    health_create_competition,
    health_delete_competition,
    # Diet note delete
    health_delete_diet_note,
    # Meta & structure
    health_update_meta,
    health_update_phases,
    health_update_current_maxes,
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
    # Granular load tools
    "health_get_competition",
    "health_list_competitions",
    "health_get_diet_notes",
    "health_get_session",
    "health_get_sessions_range",
    "health_get_supplements",
    "health_get_meta",
    "health_get_phases",
    "health_get_current_maxes",
    "health_get_operator_prefs",
    "health_get_breaks",
    # Granular edit tools
    "health_update_competition",
    "health_update_diet_note",
    "health_update_supplements",
    # Session CRUD
    "health_create_session",
    "health_delete_session",
    "health_reschedule_session",
    "health_add_exercise",
    "health_remove_exercise",
    # Competition CRUD
    "health_create_competition",
    "health_delete_competition",
    # Diet note delete
    "health_delete_diet_note",
    # Meta & structure
    "health_update_meta",
    "health_update_phases",
    "health_update_current_maxes",
    # Renderer
    "render_program_summary",
    "render_session",
]
