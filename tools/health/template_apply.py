"""Logic for applying a Template to a concrete Program block.

Handles the Max Resolution Gate, e1RM resolution, and calendar mapping.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Literal, List

def round_to_2_5(kg: float) -> float:
    """Round a weight to the nearest 2.5kg (standard plate increment)."""
    return round(kg / 2.5) * 2.5

def check_max_resolution_gate(
    template: dict[str, Any], 
    current_maxes: dict[str, float], 
    glossary_exercises: list[dict[str, Any]]
) -> list[str]:
    """Return list of glossary_ids that need e1RM but have none.
    
    A max is resolved if:
    1. It's in current_maxes (SBD)
    2. The glossary entry has e1rm_estimate
    """
    required_ids = template.get("required_maxes", [])
    missing = []
    
    glossary_map = {ex["id"]: ex for ex in glossary_exercises}
    
    for gid in required_ids:
        # SBD check
        if gid in ["squat", "bench", "deadlift"]:
            if gid not in current_maxes or not current_maxes[gid]:
                missing.append(gid)
            continue
            
        # Accessory check
        ex = glossary_map.get(gid)
        if not ex:
            missing.append(gid)
            continue
            
        if not ex.get("e1rm_estimate"):
            missing.append(gid)
            
    return missing

def _get_e1rm(gid: str, current_maxes: dict[str, float], glossary_map: dict[str, dict]) -> float | None:
    if gid in current_maxes:
        return current_maxes[gid]
    ex = glossary_map.get(gid)
    if ex and ex.get("e1rm_estimate"):
        return ex["e1rm_estimate"].get("value_kg")
    return None

def concretize(
    template: dict[str, Any],
    current_maxes: dict[str, float],
    glossary_exercises: list[dict[str, Any]],
    start_date: date,
    week_start_day: Literal["Saturday", "Monday", "Sunday"] = "Monday",
) -> list[dict[str, Any]]:
    """Map template sessions to calendar dates and resolve loads."""
    glossary_map = {ex["id"]: ex for ex in glossary_exercises}
    
    # Map week_start_day to weekday int (Monday=0, Sunday=6)
    wd_map = {"Monday": 0, "Sunday": 6, "Saturday": 5}
    target_start_wd = wd_map[week_start_day]
    
    # Calculate the anchor: the Monday of the week containing start_date
    # based on the week_start_day rule.
    # If week_start_day is Monday, and start_date is a Sunday, it's the end of previous week.
    
    # Simpler approach: find the "Day 1" of the template and map it to start_date.
    # Then all other sessions are relative to that.
    
    sessions = template.get("sessions", [])
    if not sessions:
        return []
        
    # Find the earliest session in the template
    sessions_sorted = sorted(sessions, key=lambda s: (s["week_number"], s["day_index"]))
    first_session = sessions_sorted[0]
    
    base_week = first_session["week_number"]
    base_day_idx = first_session["day_index"]
    
    concrete_sessions = []
    
    for tpl_sess in sessions:
        # Date calculation: offset from start_date
        week_offset = tpl_sess["week_number"] - base_week
        day_offset = tpl_sess["day_index"] - base_day_idx
        
        sess_date = start_date + timedelta(weeks=week_offset, days=day_offset)
        
        exercises = []
        for tpl_ex in tpl_sess.get("exercises", []):
            gid = tpl_ex.get("glossary_id")
            load_type = tpl_ex.get("load_type", "unresolvable")
            load_value = tpl_ex.get("load_value")
            rpe_target = tpl_ex.get("rpe_target")
            
            kg = None
            load_source = load_type
            
            if load_type == "percentage" and load_value:
                e1rm = _get_e1rm(gid, current_maxes, glossary_map)
                if e1rm:
                    kg = round_to_2_5(e1rm * load_value)
                else:
                    load_source = "unresolvable"
            elif load_type == "absolute":
                kg = load_value
            elif load_type == "rpe":
                kg = None # resolved at runtime
                
            exercises.append({
                "name": tpl_ex["name"],
                "glossary_id": gid,
                "sets": tpl_ex.get("sets"),
                "reps": tpl_ex.get("reps"),
                "kg": kg,
                "rpe_target": rpe_target,
                "load_source": load_source,
                "notes": tpl_ex.get("notes", "")
            })
            
        concrete_sessions.append({
            "date": sess_date.isoformat(),
            "day": sess_date.strftime("%A"),
            "week": tpl_sess.get("label", f"W{tpl_sess['week_number']}"),
            "week_number": tpl_sess["week_number"],
            "status": "planned",
            "completed": False,
            "planned_exercises": exercises,
            "exercises": [], # actuals start empty
            "session_notes": ""
        })
        
    return concrete_sessions
