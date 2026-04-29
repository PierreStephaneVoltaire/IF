from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from export import build_program_markdown  # noqa: E402


def test_build_program_markdown_produces_narrative(tmp_path: Path) -> None:
    program = {
        "pk": "operator",
        "meta": {
            "program_name": "Test Program",
            "program_start": "2026-04-01",
            "comp_date": "2026-06-01",
            "sex": "male",
            "current_body_weight_kg": 82.5,
            "target_squat_kg": 200,
            "target_bench_kg": 140,
            "target_dl_kg": 240,
            "target_total_kg": 580,
            "training_notes": ["keep bar speed high"],
        },
        "current_maxes": {"squat": 190, "bench": 132.5, "deadlift": 225},
        "phases": [
            {
                "name": "Base",
                "block": "current",
                "start_week": 1,
                "end_week": 4,
                "intent": "Build volume",
            }
        ],
        "sessions": [
            {
                "id": "session-1",
                "date": "2026-04-02",
                "week_number": 1,
                "block": "current",
                "phase": {"name": "Base"},
                "day": "Upper",
                "status": "completed",
                "completed": True,
                "body_weight_kg": 82.5,
                "session_notes": "felt strong today",
                "exercises": [
                    {
                        "name": "Bench Press",
                        "sets": 3,
                        "reps": 5,
                        "kg": 100,
                        "rpe": 7,
                        "notes": "clean reps",
                    }
                ],
            }
        ],
    }
    out_path = tmp_path / "program_history.md"

    result = build_program_markdown(program, str(out_path))

    text = out_path.read_text(encoding="utf-8")
    assert result == str(out_path)

    # Title and overview
    assert "# Test Program" in text
    assert "**Started:** 2026-04-01" in text
    assert "**Current BW:** 82.5 kg" in text
    assert "### Target Lifts" in text
    assert "Squat 200 kg" in text

    # Current maxes table
    assert "## Current Maxes" in text
    assert "Squat" in text
    assert "190" in text

    # Phases as narrative
    assert "## Training Phases" in text
    assert "**Base**" in text
    assert "Weeks 1" in text
    assert "Build volume" in text

    # Sessions with exercise tables
    assert "## Training Log" in text
    assert "**2026-04-02**" in text
    assert "Upper" in text
    assert "BW: 82.5 kg" in text
    assert "Bench Press" in text
    assert "3 x 5" in text
    assert "100" in text
    assert "clean reps" in text
    assert "felt strong today" in text

    # Training notes
    assert "keep bar speed high" in text

    # No raw data dumps
    assert "## Raw Export" not in text
    assert "## Meta" not in text


def test_build_program_markdown_escapes_pipes_in_tables(tmp_path: Path) -> None:
    program = {
        "pk": "operator",
        "meta": {
            "program_name": "Pipe | Program",
            "sex": "male",
            "training_notes": [],
        },
        "current_maxes": {"bench": 100},
        "sessions": [
            {
                "id": "s1",
                "date": "2026-04-02",
                "week_number": 1,
                "block": "current",
                "phase": "Base",
                "status": "completed",
                "completed": True,
                "exercises": [
                    {
                        "name": "Bench | Press",
                        "sets": 3,
                        "reps": 5,
                        "kg": 100,
                        "rpe": 7,
                        "notes": "clean | reps",
                    }
                ],
            }
        ],
    }
    out_path = tmp_path / "test.md"

    build_program_markdown(program, str(out_path))
    text = out_path.read_text(encoding="utf-8")

    # Pipes in prose are fine, pipes in table cells are escaped
    assert "Bench \\| Press" in text
    assert "clean \\| reps" in text


def test_build_program_markdown_empty_program(tmp_path: Path) -> None:
    program = {
        "pk": "operator",
        "meta": {"program_name": "Empty", "sex": "male"},
    }
    out_path = tmp_path / "empty.md"

    build_program_markdown(program, str(out_path))
    text = out_path.read_text(encoding="utf-8")

    assert "# Empty" in text
    assert "## Current Maxes" not in text
    assert "## Training Log" not in text


def test_session_notes_inline_not_in_notes_section(tmp_path: Path) -> None:
    program = {
        "pk": "operator",
        "meta": {"program_name": "Test", "sex": "male"},
        "sessions": [
            {
                "id": "s1",
                "date": "2026-04-02",
                "week_number": 1,
                "block": "current",
                "phase": "Base",
                "status": "completed",
                "completed": True,
                "session_notes": "felt strong",
                "exercises": [],
            }
        ],
        "competitions": [{"name": "Meet", "date": "2026-06-01", "notes": "bring knee sleeves"}],
        "goals": [{"title": "PR total", "priority": "primary", "notes": "need 580+"}],
    }
    out_path = tmp_path / "test.md"

    build_program_markdown(program, str(out_path))
    text = out_path.read_text(encoding="utf-8")

    # Session notes appear inline in Training Log
    assert "## Training Log" in text
    assert "_felt strong_" in text

    # Competition notes appear inline in Competitions
    assert "## Competitions" in text
    assert "bring knee sleeves" in text

    # Goal notes appear in Goals table
    assert "## Goals" in text
    assert "need 580+" in text

    # No session/competition notes duplicated in Notes section
    assert "## Notes" not in text


def test_dots_and_weight_trends(tmp_path: Path) -> None:
    program = {
        "pk": "operator",
        "meta": {
            "program_name": "Trend Test",
            "sex": "male",
            "current_body_weight_kg": 82.0,
        },
        "sessions": [
            {
                "id": "s1",
                "date": "2026-04-01",
                "week_number": 1,
                "block": "current",
                "status": "completed",
                "completed": True,
                "body_weight_kg": 82.0,
                "exercises": [
                    {"name": "Squat", "sets": 1, "reps": 3, "kg": 150},
                    {"name": "Bench Press", "sets": 1, "reps": 3, "kg": 100},
                    {"name": "Deadlift", "sets": 1, "reps": 3, "kg": 180},
                ],
            },
            {
                "id": "s2",
                "date": "2026-04-08",
                "week_number": 2,
                "block": "current",
                "status": "completed",
                "completed": True,
                "body_weight_kg": 82.5,
                "exercises": [
                    {"name": "Squat", "sets": 1, "reps": 2, "kg": 160},
                    {"name": "Bench Press", "sets": 1, "reps": 2, "kg": 105},
                    {"name": "Deadlift", "sets": 1, "reps": 2, "kg": 190},
                ],
            },
        ],
    }
    out_path = tmp_path / "trends.md"

    build_program_markdown(program, str(out_path))
    text = out_path.read_text(encoding="utf-8")

    assert "### e1RM Progression & DOTS Trend" in text
    assert "DOTS" in text
    assert "### Body Weight Trend" in text
    assert "82.5 kg" in text
