"""Health module for IF Prototype A1.

Provides DynamoDB-backed training program storage and ChromaDB-backed RAG
for health documents.

Public API:
    - ProgramStore: DynamoDB store for training programs
    - ProgramNotFoundError: Exception when program not found
    - HealthDocsRAG: ChromaDB RAG for health documents
    - render_program_summary: Render program as markdown
    - render_session: Render session as markdown

Note: Tool functions have moved to tools/health/core.py
"""
from health.program_store import ProgramStore, ProgramNotFoundError
from health.rag import HealthDocsRAG
from health.renderer import render_program_summary, render_session

__all__ = [
    "ProgramStore",
    "ProgramNotFoundError",
    "HealthDocsRAG",
    "render_program_summary",
    "render_session",
]
