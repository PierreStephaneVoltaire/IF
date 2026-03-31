"""OpenRouter-compatible function schemas for domain tools.

These schemas are used by specialist subagents to call health and finance tools
via the OpenRouter function calling interface. The dispatcher in subagents.py
routes tool calls to the actual executor functions.

Only tools referenced in specialist configs (specialists.py) are included here.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from orchestrator.executor import TERMINAL_EXECUTE_SCHEMA

logger = logging.getLogger(__name__)


# =============================================================================
# Health Tool Schemas
# =============================================================================

HEALTH_TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "health_get_program": {
        "name": "health_get_program",
        "description": (
            "Get the full training program from DynamoDB. "
            "Returns the cached program dict with all sessions, phases, meta, and preferences."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "health_get_session": {
        "name": "health_get_session",
        "description": "Get a single training session by date.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Session date (YYYY-MM-DD)",
                },
            },
            "required": ["date"],
        },
    },
    "health_update_session": {
        "name": "health_update_session",
        "description": "Update fields on an existing training session.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "ISO8601 date string (YYYY-MM-DD) of the session to update",
                },
                "patch": {
                    "type": "object",
                    "description": "Dict with session fields to update. Allowed keys: completed, session_rpe, body_weight_kg, session_notes, exercises",
                },
            },
            "required": ["date", "patch"],
        },
    },
    "health_new_version": {
        "name": "health_new_version",
        "description": "Create a new program version with the given patches.",
        "parameters": {
            "type": "object",
            "properties": {
                "change_reason": {
                    "type": "string",
                    "description": "Human-readable reason for the version change",
                },
                "patches": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of patches, each with 'path' and 'value' keys",
                },
            },
            "required": ["change_reason", "patches"],
        },
    },
    "health_rag_search": {
        "name": "health_rag_search",
        "description": "Search health documents using RAG.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for health documents"},
                "n_results": {"type": "integer", "description": "Number of results to return", "default": 4},
            },
            "required": ["query"],
        },
    },
    "health_get_competition": {
        "name": "health_get_competition",
        "description": "Get competition details by date.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Competition date (YYYY-MM-DD)"},
            },
            "required": ["date"],
        },
    },
    "health_get_diet_notes": {
        "name": "health_get_diet_notes",
        "description": "Get diet notes for a date range.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Start of date range (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "End of date range (YYYY-MM-DD)"},
            },
            "required": [],
        },
    },
    "health_get_sessions_range": {
        "name": "health_get_sessions_range",
        "description": "Get training sessions for a date range.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Start of date range (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "End of date range (YYYY-MM-DD)"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    "health_get_supplements": {
        "name": "health_get_supplements",
        "description": "Get the supplement protocol from the program.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "health_get_meta": {
        "name": "health_get_meta",
        "description": "Get program metadata (name, dates, weight class, etc.).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "health_get_phases": {
        "name": "health_get_phases",
        "description": "Get the training phases from the program.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "health_get_current_maxes": {
        "name": "health_get_current_maxes",
        "description": "Get current training maxes (squat, bench, deadlift).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "health_update_competition": {
        "name": "health_update_competition",
        "description": "Update competition fields by date.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Competition date to update (YYYY-MM-DD)"},
                "patch": {"type": "object", "description": "Fields to update (targets, status, notes, etc.)"},
            },
            "required": ["date", "patch"],
        },
    },
    "health_update_diet_note": {
        "name": "health_update_diet_note",
        "description": "Create or replace a diet note for a date.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date for the diet note (YYYY-MM-DD)"},
                "notes": {"type": "string", "description": "The diet notes content"},
            },
            "required": ["date", "notes"],
        },
    },
    "health_update_supplements": {
        "name": "health_update_supplements",
        "description": "Update the supplement protocol.",
        "parameters": {
            "type": "object",
            "properties": {
                "patch": {"type": "object", "description": '{"supplements": [...]} or {"supplement_phases": [...]}'},
            },
            "required": ["patch"],
        },
    },
    "health_create_session": {
        "name": "health_create_session",
        "description": "Create a new training session.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Session date (YYYY-MM-DD)"},
                "day": {"type": "string", "description": "Day label e.g. Monday"},
                "week_number": {"type": "integer", "description": "Training week number"},
                "exercises": {"type": "array", "items": {"type": "object"}, "description": "Optional list of exercises"},
                "session_notes": {"type": "string", "description": "Optional session notes", "default": ""},
            },
            "required": ["date", "day", "week_number"],
        },
    },
    "health_delete_session": {
        "name": "health_delete_session",
        "description": "Delete a training session by date.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Session date to delete (YYYY-MM-DD)"},
            },
            "required": ["date"],
        },
    },
    "health_reschedule_session": {
        "name": "health_reschedule_session",
        "description": "Move a training session from one date to another.",
        "parameters": {
            "type": "object",
            "properties": {
                "old_date": {"type": "string", "description": "Current session date (YYYY-MM-DD)"},
                "new_date": {"type": "string", "description": "Target date to move to (YYYY-MM-DD)"},
            },
            "required": ["old_date", "new_date"],
        },
    },
    "health_add_exercise": {
        "name": "health_add_exercise",
        "description": "Add an exercise to a training session.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Session date (YYYY-MM-DD)"},
                "exercise": {"type": "object", "description": "Exercise dict: {name, sets, reps, kg, rpe, notes}"},
            },
            "required": ["date", "exercise"],
        },
    },
    "health_remove_exercise": {
        "name": "health_remove_exercise",
        "description": "Remove an exercise from a training session by index.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Session date (YYYY-MM-DD)"},
                "exercise_index": {"type": "integer", "description": "Zero-based index of the exercise to remove"},
            },
            "required": ["date", "exercise_index"],
        },
    },
    "health_create_competition": {
        "name": "health_create_competition",
        "description": "Create a new competition entry.",
        "parameters": {
            "type": "object",
            "properties": {
                "competition": {
                    "type": "object",
                    "description": "Competition dict: name, date, federation, status, weight_class_kg, location, targets, notes",
                },
            },
            "required": ["competition"],
        },
    },
    "health_delete_competition": {
        "name": "health_delete_competition",
        "description": "Delete a competition entry by date.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Competition date to delete (YYYY-MM-DD)"},
            },
            "required": ["date"],
        },
    },
    "health_delete_diet_note": {
        "name": "health_delete_diet_note",
        "description": "Delete a diet note by date.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Diet note date to delete (YYYY-MM-DD)"},
            },
            "required": ["date"],
        },
    },
    "health_update_meta": {
        "name": "health_update_meta",
        "description": "Update program metadata fields.",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {"type": "object", "description": "Dict of meta fields to update"},
            },
            "required": ["updates"],
        },
    },
    "health_update_phases": {
        "name": "health_update_phases",
        "description": "Replace the full phases list.",
        "parameters": {
            "type": "object",
            "properties": {
                "phases": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Complete phases list. Each: {name, start_week, end_week, intent}",
                },
            },
            "required": ["phases"],
        },
    },
    "health_update_current_maxes": {
        "name": "health_update_current_maxes",
        "description": "Update current training maxes.",
        "parameters": {
            "type": "object",
            "properties": {
                "squat_kg": {"type": "number", "description": "New squat max in kg"},
                "bench_kg": {"type": "number", "description": "New bench max in kg"},
                "deadlift_kg": {"type": "number", "description": "New deadlift max in kg"},
            },
            "required": [],
        },
    },
    "kg_to_lb": {
        "name": "kg_to_lb",
        "description": "Convert kilograms to pounds.",
        "parameters": {
            "type": "object",
            "properties": {"kg": {"type": "number", "description": "Weight in kilograms"}},
            "required": ["kg"],
        },
    },
    "lb_to_kg": {
        "name": "lb_to_kg",
        "description": "Convert pounds to kilograms.",
        "parameters": {
            "type": "object",
            "properties": {"lb": {"type": "number", "description": "Weight in pounds"}},
            "required": ["lb"],
        },
    },
    "ipf_weight_classes": {
        "name": "ipf_weight_classes",
        "description": "Get IPF weight classes for a given sex.",
        "parameters": {
            "type": "object",
            "properties": {"sex": {"type": "string", "description": "Sex: 'M' or 'F'"}},
            "required": ["sex"],
        },
    },
    "pct_of_max": {
        "name": "pct_of_max",
        "description": "Calculate a percentage of a max weight.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_kg": {"type": "number", "description": "Maximum weight in kg"},
                "pct": {"type": "number", "description": "Percentage (0-150, not 0-1)"},
            },
            "required": ["max_kg", "pct"],
        },
    },
    "calculate_attempts": {
        "name": "calculate_attempts",
        "description": "Calculate competition attempt weights based on opener.",
        "parameters": {
            "type": "object",
            "properties": {
                "lift": {"type": "string", "description": "Lift type: squat, bench, or deadlift"},
                "opener_kg": {"type": "number", "description": "First attempt weight in kg"},
                "j1_override": {"type": "number", "description": "Override jump 1 from program prefs (kg)"},
                "j2_override": {"type": "number", "description": "Override jump 2 from program prefs (kg)"},
                "last_felt": {"type": "string", "description": "If 'hard', halve j2 for conservative third attempt"},
            },
            "required": ["lift", "opener_kg"],
        },
    },
    "days_until": {
        "name": "days_until",
        "description": "Calculate days until a target date.",
        "parameters": {
            "type": "object",
            "properties": {
                "target_date": {"type": "string", "description": "Target date (YYYY-MM-DD)"},
                "label": {"type": "string", "description": "Human label for the milestone", "default": "target"},
            },
            "required": ["target_date"],
        },
    },
}


# =============================================================================
# Finance Tool Schemas
# =============================================================================

FINANCE_TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "finance_get_profile": {
        "name": "finance_get_profile",
        "description": "Get the full financial profile.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "finance_get_goals": {
        "name": "finance_get_goals",
        "description": "Get financial goals (short, medium, long-term).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "finance_get_accounts": {
        "name": "finance_get_accounts",
        "description": "Get all financial accounts.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "finance_get_investments": {
        "name": "finance_get_investments",
        "description": "Get investment holdings across all accounts.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "finance_get_cashflow": {
        "name": "finance_get_cashflow",
        "description": "Get cashflow breakdown (income, expenses, savings).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "finance_get_tax": {
        "name": "finance_get_tax",
        "description": "Get tax information (RRSP, TFSA room, capital gains).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "finance_get_insurance": {
        "name": "finance_get_insurance",
        "description": "Get insurance policies.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "finance_get_net_worth": {
        "name": "finance_get_net_worth",
        "description": "Get net worth snapshot.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "finance_update_profile": {
        "name": "finance_update_profile",
        "description": "Update financial profile fields (age, income, employment, etc.).",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "object",
                    "description": "Profile fields to update.",
                },
            },
            "required": ["updates"],
        },
    },
    "finance_update_goals": {
        "name": "finance_update_goals",
        "description": "Replace financial goals.",
        "parameters": {
            "type": "object",
            "properties": {
                "short_term": {"type": "array", "items": {"type": "object"}, "description": "Short-term goals (<1yr)"},
                "medium_term": {"type": "array", "items": {"type": "object"}, "description": "Medium-term goals (1-5yr)"},
                "long_term": {"type": "array", "items": {"type": "object"}, "description": "Long-term goals (5yr+)"},
            },
            "required": [],
        },
    },
    "finance_update_risk_profile": {
        "name": "finance_update_risk_profile",
        "description": "Update risk profile (tolerance, time horizon, philosophy).",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {"type": "object", "description": "Risk profile fields to update"},
            },
            "required": ["updates"],
        },
    },
    "finance_update_net_worth": {
        "name": "finance_update_net_worth",
        "description": "Update net worth snapshot.",
        "parameters": {
            "type": "object",
            "properties": {
                "total_assets": {"type": "number", "description": "Total assets in dollars"},
                "total_liabilities": {"type": "number", "description": "Total liabilities in dollars"},
                "as_of": {"type": "string", "description": "Snapshot date (YYYY-MM-DD)"},
            },
            "required": [],
        },
    },
    "finance_update_account": {
        "name": "finance_update_account",
        "description": "Update fields on a financial account.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_type": {"type": "string", "description": "Account type: chequing, savings, credit_cards, etc."},
                "account_id": {"type": "string", "description": "Account id field value"},
                "updates": {"type": "object", "description": "Fields to update"},
            },
            "required": ["account_type", "account_id", "updates"],
        },
    },
    "finance_add_holding": {
        "name": "finance_add_holding",
        "description": "Add an investment holding to an account.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Investment account id"},
                "ticker": {"type": "string", "description": "Ticker symbol"},
                "shares": {"type": "number", "description": "Number of shares"},
                "avg_cost": {"type": "number", "description": "Average cost per share"},
                "current_price": {"type": "number", "description": "Current market price per share"},
                "notes": {"type": "string", "description": "Optional notes", "default": ""},
            },
            "required": ["account_id", "ticker", "shares", "avg_cost"],
        },
    },
    "finance_update_holding": {
        "name": "finance_update_holding",
        "description": "Update an investment holding.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Investment account id"},
                "ticker": {"type": "string", "description": "Ticker symbol to update"},
                "updates": {"type": "object", "description": "Fields: shares, avg_cost, current_price, notes"},
            },
            "required": ["account_id", "ticker", "updates"],
        },
    },
    "finance_update_watchlist": {
        "name": "finance_update_watchlist",
        "description": "Replace the full watchlist.",
        "parameters": {
            "type": "object",
            "properties": {
                "watchlist": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "New watchlist array. Each item: {ticker, notes}",
                },
            },
            "required": ["watchlist"],
        },
    },
    "finance_update_cashflow": {
        "name": "finance_update_cashflow",
        "description": "Update cashflow sections.",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {"type": "object", "description": "Cashflow sections to update"},
            },
            "required": ["updates"],
        },
    },
    "finance_update_tax": {
        "name": "finance_update_tax",
        "description": "Update tax fields.",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {"type": "object", "description": "Tax fields to update"},
            },
            "required": ["updates"],
        },
    },
    "finance_update_insurance": {
        "name": "finance_update_insurance",
        "description": "Replace the full insurance policies list.",
        "parameters": {
            "type": "object",
            "properties": {
                "policies": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Full insurance policies list",
                },
            },
            "required": ["policies"],
        },
    },
}


# =============================================================================
# All Schemas Registry
# =============================================================================

ALL_TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    **HEALTH_TOOL_SCHEMAS,
    **FINANCE_TOOL_SCHEMAS,
    "terminal_execute": TERMINAL_EXECUTE_SCHEMA,
}


def get_schemas_for_specialist(tool_names: List[str]) -> List[Dict[str, Any]]:
    """Resolve a specialist's tool names to OpenRouter function schemas.

    Always includes terminal_execute in addition to the specialist's
    configured tools.

    Args:
        tool_names: Tool names from specialist config

    Returns:
        List of OpenRouter-compatible function schemas
    """
    schemas = [TERMINAL_EXECUTE_SCHEMA]  # All specialists get terminal access
    for name in tool_names:
        if name in ALL_TOOL_SCHEMAS and name != "terminal_execute":
            schemas.append(ALL_TOOL_SCHEMAS[name])
        elif name not in ALL_TOOL_SCHEMAS:
            logger.debug(f"[ToolSchemas] Unknown tool '{name}' for specialist, skipping")
    return schemas


# =============================================================================
# Domain Tool Dispatcher
# =============================================================================

async def execute_domain_tool(tool_name: str, args: Dict[str, Any]) -> str:
    """Execute a health or finance tool by name.

    Imports the underlying function from the health/finance modules and calls it.
    Returns the result as a string.

    Args:
        tool_name: The tool name (e.g., "health_get_program")
        args: Parsed arguments dict

    Returns:
        Result string
    """
    try:
        if tool_name.startswith("health_"):
            return await _execute_health_tool(tool_name, args)
        elif tool_name.startswith("finance_"):
            return await _execute_finance_tool(tool_name, args)
        else:
            return f"Unknown domain tool: {tool_name}"
    except Exception as e:
        logger.error(f"[ToolSchemas] Error executing {tool_name}: {e}")
        return f"ERROR: {type(e).__name__}: {e}"


async def _execute_health_tool(tool_name: str, args: Dict[str, Any]) -> str:
    """Route health tool calls to the underlying health module functions."""
    from health import (
        health_get_program,
        health_get_session,
        health_update_session as do_update_session,
        health_rag_search,
        health_get_competition,
        health_get_diet_notes,
        health_get_sessions_range,
        health_get_supplements,
        health_get_meta,
        health_get_phases,
        health_get_current_maxes,
        health_update_competition as do_update_competition,
        health_update_diet_note as do_update_diet_note,
        health_update_supplements as do_update_supplements,
        health_create_session as do_create_session,
        health_delete_session as do_delete_session,
        health_reschedule_session as do_reschedule_session,
        health_add_exercise as do_add_exercise,
        health_remove_exercise as do_remove_exercise,
        health_create_competition as do_create_competition,
        health_delete_competition as do_delete_competition,
        health_delete_diet_note as do_delete_diet_note,
        health_update_meta as do_update_meta,
        health_update_phases as do_update_phases,
        health_update_current_maxes as do_update_current_maxes,
        kg_to_lb,
        lb_to_kg,
        ipf_weight_classes,
        pct_of_max,
        calculate_attempts,
        days_until,
        health_new_version as do_new_version,
    )

    HEALTH_ROUTES = {
        "health_get_program": lambda: health_get_program(),
        "health_get_session": lambda: health_get_session(args["date"]),
        "health_update_session": lambda: do_update_session(args["date"], args["patch"]),
        "health_new_version": lambda: do_new_version(args["change_reason"], args["patches"]),
        "health_rag_search": lambda: health_rag_search(args["query"], args.get("n_results", 4)),
        "health_get_competition": lambda: health_get_competition(args["date"]),
        "health_get_diet_notes": lambda: health_get_diet_notes(
            args.get("start_date"), args.get("end_date")
        ),
        "health_get_sessions_range": lambda: health_get_sessions_range(
            args["start_date"], args["end_date"]
        ),
        "health_get_supplements": lambda: health_get_supplements(),
        "health_get_meta": lambda: health_get_meta(),
        "health_get_phases": lambda: health_get_phases(),
        "health_get_current_maxes": lambda: health_get_current_maxes(),
        "health_update_competition": lambda: do_update_competition(args["date"], args["patch"]),
        "health_update_diet_note": lambda: do_update_diet_note(args["date"], args["notes"]),
        "health_update_supplements": lambda: do_update_supplements(args["patch"]),
        "health_create_session": lambda: do_create_session(
            args["date"], args["day"], args["week_number"],
            args.get("exercises"), args.get("session_notes", ""),
        ),
        "health_delete_session": lambda: do_delete_session(args["date"]),
        "health_reschedule_session": lambda: do_reschedule_session(args["old_date"], args["new_date"]),
        "health_add_exercise": lambda: do_add_exercise(args["date"], args["exercise"]),
        "health_remove_exercise": lambda: do_remove_exercise(args["date"], args["exercise_index"]),
        "health_create_competition": lambda: do_create_competition(args["competition"]),
        "health_delete_competition": lambda: do_delete_competition(args["date"]),
        "health_delete_diet_note": lambda: do_delete_diet_note(args["date"]),
        "health_update_meta": lambda: do_update_meta(args["updates"]),
        "health_update_phases": lambda: do_update_phases(args["phases"]),
        "health_update_current_maxes": lambda: do_update_current_maxes(
            args.get("squat_kg"), args.get("bench_kg"), args.get("deadlift_kg")
        ),
        "kg_to_lb": lambda: kg_to_lb(args["kg"]),
        "lb_to_kg": lambda: lb_to_kg(args["lb"]),
        "ipf_weight_classes": lambda: ipf_weight_classes(args["sex"]),
        "pct_of_max": lambda: pct_of_max(args["max_kg"], args["pct"]),
        "calculate_attempts": lambda: calculate_attempts(
            args["lift"], args["opener_kg"], args.get("j1_override"),
            args.get("j2_override"), args.get("last_felt"),
        ),
        "days_until": lambda: days_until(args["target_date"], args.get("label", "target")),
    }

    handler = HEALTH_ROUTES.get(tool_name)
    if not handler:
        return f"Unknown health tool: {tool_name}"

    result = handler()
    if isinstance(result, str):
        return result
    return json.dumps(result, indent=2, default=str)


async def _execute_finance_tool(tool_name: str, args: Dict[str, Any]) -> str:
    """Route finance tool calls to the underlying finance module functions."""
    from finance import (
        finance_get_profile,
        finance_get_goals,
        finance_get_accounts,
        finance_get_investments,
        finance_get_cashflow,
        finance_get_tax,
        finance_get_insurance,
        finance_get_net_worth,
        finance_update_profile,
        finance_update_goals,
        finance_update_risk_profile,
        finance_update_net_worth,
        finance_update_account,
        finance_add_holding,
        finance_update_holding,
        finance_update_watchlist,
        finance_update_cashflow,
        finance_update_tax,
        finance_update_insurance,
    )

    FINANCE_ROUTES = {
        "finance_get_profile": lambda: finance_get_profile(),
        "finance_get_goals": lambda: finance_get_goals(),
        "finance_get_accounts": lambda: finance_get_accounts(),
        "finance_get_investments": lambda: finance_get_investments(),
        "finance_get_cashflow": lambda: finance_get_cashflow(),
        "finance_get_tax": lambda: finance_get_tax(),
        "finance_get_insurance": lambda: finance_get_insurance(),
        "finance_get_net_worth": lambda: finance_get_net_worth(),
        "finance_update_profile": lambda: finance_update_profile(args["updates"]),
        "finance_update_goals": lambda: finance_update_goals(
            args.get("short_term"), args.get("medium_term"), args.get("long_term")
        ),
        "finance_update_risk_profile": lambda: finance_update_risk_profile(args["updates"]),
        "finance_update_net_worth": lambda: finance_update_net_worth(
            args.get("total_assets"), args.get("total_liabilities"), args.get("as_of")
        ),
        "finance_update_account": lambda: finance_update_account(
            args["account_type"], args["account_id"], args["updates"]
        ),
        "finance_add_holding": lambda: finance_add_holding(
            args["account_id"], args["ticker"], args["shares"], args["avg_cost"],
            args.get("current_price"), args.get("notes", ""),
        ),
        "finance_update_holding": lambda: finance_update_holding(
            args["account_id"], args["ticker"], args["updates"]
        ),
        "finance_update_watchlist": lambda: finance_update_watchlist(args["watchlist"]),
        "finance_update_cashflow": lambda: finance_update_cashflow(args["updates"]),
        "finance_update_tax": lambda: finance_update_tax(args["updates"]),
        "finance_update_insurance": lambda: finance_update_insurance(args["policies"]),
    }

    handler = FINANCE_ROUTES.get(tool_name)
    if not handler:
        return f"Unknown finance tool: {tool_name}"

    result = handler()
    if isinstance(result, str):
        return result
    return json.dumps(result, indent=2, default=str)
