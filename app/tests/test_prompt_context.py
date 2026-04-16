import pytest
from typing import Any
from tools.health.prompt_context import _serialize_planned_exercise_for_prompt

def test_serialize_planned_exercise_absolute():
    # Case (a): kg > 0 only
    ex = {"name": "Squat", "kg": 100, "sets": 3, "reps": 5}
    result = _serialize_planned_exercise_for_prompt(ex)
    assert result["load"] == "100kg"
    assert result["load_type"] == "absolute"
    assert result["kg"] == 100

def test_serialize_planned_exercise_rpe():
    # Case (b): rpe_target only (or rpe)
    ex = {"name": "Squat", "kg": 0, "rpe_target": 8, "sets": 3, "reps": 5}
    result = _serialize_planned_exercise_for_prompt(ex)
    assert result["load"] == "@RPE 8"
    assert result["load_type"] == "rpe"
    assert result["rpe_target"] == 8

    ex_legacy = {"name": "Squat", "kg": 0, "rpe": 7.5, "sets": 3, "reps": 5}
    result_legacy = _serialize_planned_exercise_for_prompt(ex_legacy)
    assert result_legacy["load"] == "@RPE 7.5"
    assert result_legacy["load_type"] == "rpe"
    assert result_legacy["rpe_target"] == 7.5

def test_serialize_planned_exercise_both():
    # Case (c): both (should prefer absolute if kg > 0)
    ex = {"name": "Squat", "kg": 100, "rpe_target": 8, "sets": 3, "reps": 5}
    result = _serialize_planned_exercise_for_prompt(ex)
    assert result["load"] == "100kg"
    assert result["load_type"] == "absolute"
    assert result["kg"] == 100
    assert result["rpe_target"] == 8

def test_serialize_planned_exercise_neither():
    # Case (d): neither
    ex = {"name": "Squat", "kg": 0, "rpe_target": None, "sets": 3, "reps": 5}
    result = _serialize_planned_exercise_for_prompt(ex)
    assert result["load"] == "unspecified"
    assert result["load_type"] == "unspecified"

def test_serialize_planned_exercise_load_source():
    # Test load_source explicitly
    ex = {"name": "Squat", "kg": 100, "load_source": "rpe", "rpe_target": 9, "sets": 1, "reps": 1}
    result = _serialize_planned_exercise_for_prompt(ex)
    assert result["load"] == "@RPE 9"
    assert result["load_type"] == "rpe"
