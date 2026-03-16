"""OpenHands SDK wrappers for health module tools.

Wraps the health module functions in the Action/Observation/Executor/ToolDefinition
pattern required by the OpenHands SDK.
"""
from __future__ import annotations
import asyncio
import json
from typing import List, Optional, Dict, Any, Sequence

from pydantic import Field

from openhands.sdk import (
    Action,
    Observation,
    Tool,
    ToolDefinition,
    register_tool,
)
from openhands.sdk.tool import ToolExecutor


# =============================================================================
# Helper functions to run async operations in sync context
# =============================================================================

def _run_async(coro):
    """Run an async coroutine in a sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're in an async context, run in a new thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


def _format_result(result: Any) -> str:
    """Format a result (dict or str) as a string for Observation."""
    if isinstance(result, str):
        return result
    return json.dumps(result, indent=2, default=str)


# =============================================================================
# health_get_program
# =============================================================================

class HealthGetProgramAction(Action):
    pass


class HealthGetProgramObservation(Observation):
    pass


class HealthGetProgramExecutor(ToolExecutor[HealthGetProgramAction, HealthGetProgramObservation]):
    def __call__(self, action: HealthGetProgramAction, conversation=None) -> HealthGetProgramObservation:
        from health import health_get_program
        result = _run_async(health_get_program())
        return HealthGetProgramObservation.from_text(_format_result(result))


class HealthGetProgramTool(ToolDefinition[HealthGetProgramAction, HealthGetProgramObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthGetProgramTool"]:
        return [cls(
            description=(
                "Get the full training program from DynamoDB. "
                "Returns the cached program dict with all sessions, phases, meta, and preferences."
            ),
            action_type=HealthGetProgramAction,
            observation_type=HealthGetProgramObservation,
            executor=HealthGetProgramExecutor(),
        )]


# =============================================================================
# health_comp_countdown
# =============================================================================

class HealthCompCountdownAction(Action):
    pass


class HealthCompCountdownObservation(Observation):
    pass


class HealthCompCountdownExecutor(ToolExecutor[HealthCompCountdownAction, HealthCompCountdownObservation]):
    def __call__(self, action: HealthCompCountdownAction, conversation=None) -> HealthCompCountdownObservation:
        from health import health_comp_countdown
        result = _run_async(health_comp_countdown())
        return HealthCompCountdownObservation.from_text(_format_result(result))


class HealthCompCountdownTool(ToolDefinition[HealthCompCountdownAction, HealthCompCountdownObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthCompCountdownTool"]:
        return [cls(
            description=(
                "Calculate competition countdown metrics. "
                "Returns days/weeks to competition, current week/phase, break status, and remaining sessions."
            ),
            action_type=HealthCompCountdownAction,
            observation_type=HealthCompCountdownObservation,
            executor=HealthCompCountdownExecutor(),
        )]


# =============================================================================
# health_update_session
# =============================================================================

class HealthUpdateSessionAction(Action):
    date: str = Field(description="ISO8601 date string (YYYY-MM-DD) of the session to update")
    patch: Dict[str, Any] = Field(
        description="Dict with session fields to update. Allowed keys: completed, session_rpe, body_weight_kg, session_notes, exercises"
    )


class HealthUpdateSessionObservation(Observation):
    pass


class HealthUpdateSessionExecutor(ToolExecutor[HealthUpdateSessionAction, HealthUpdateSessionObservation]):
    def __call__(self, action: HealthUpdateSessionAction, conversation=None) -> HealthUpdateSessionObservation:
        from health import health_update_session
        result = _run_async(health_update_session(action.date, action.patch))
        return HealthUpdateSessionObservation.from_text(_format_result(result))


class HealthUpdateSessionTool(ToolDefinition[HealthUpdateSessionAction, HealthUpdateSessionObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthUpdateSessionTool"]:
        return [cls(
            description=(
                "Update a training session by date. "
                "Use to log session completion, RPE, body weight, notes, or exercise details."
            ),
            action_type=HealthUpdateSessionAction,
            observation_type=HealthUpdateSessionObservation,
            executor=HealthUpdateSessionExecutor(),
        )]


# =============================================================================
# health_new_version
# =============================================================================

class HealthNewVersionAction(Action):
    change_reason: str = Field(description="Human-readable reason for the version change")
    patches: List[Dict[str, Any]] = Field(
        description="List of patches, each with 'path' (e.g., 'sessions[0].exercises[1].kg') and 'value' keys"
    )


class HealthNewVersionObservation(Observation):
    pass


class HealthNewVersionExecutor(ToolExecutor[HealthNewVersionAction, HealthNewVersionObservation]):
    def __call__(self, action: HealthNewVersionAction, conversation=None) -> HealthNewVersionObservation:
        from health import health_new_version
        result = _run_async(health_new_version(action.change_reason, action.patches))
        return HealthNewVersionObservation.from_text(_format_result(result))


class HealthNewVersionTool(ToolDefinition[HealthNewVersionAction, HealthNewVersionObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthNewVersionTool"]:
        return [cls(
            description=(
                "Create a new major version of the training program with patches. "
                "Use for significant program changes that warrant version tracking."
            ),
            action_type=HealthNewVersionAction,
            observation_type=HealthNewVersionObservation,
            executor=HealthNewVersionExecutor(),
        )]


# =============================================================================
# kg_to_lb
# =============================================================================

class KgToLbAction(Action):
    kg: float = Field(description="Weight in kilograms")


class KgToLbObservation(Observation):
    pass


class KgToLbExecutor(ToolExecutor[KgToLbAction, KgToLbObservation]):
    def __call__(self, action: KgToLbAction, conversation=None) -> KgToLbObservation:
        from health import kg_to_lb
        result = kg_to_lb(action.kg)
        return KgToLbObservation.from_text(_format_result(result))


class KgToLbTool(ToolDefinition[KgToLbAction, KgToLbObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["KgToLbTool"]:
        return [cls(
            description="Convert kilograms to pounds. Returns both kg and lb values.",
            action_type=KgToLbAction,
            observation_type=KgToLbObservation,
            executor=KgToLbExecutor(),
        )]


# =============================================================================
# lb_to_kg
# =============================================================================

class LbToKgAction(Action):
    lb: float = Field(description="Weight in pounds")


class LbToKgObservation(Observation):
    pass


class LbToKgExecutor(ToolExecutor[LbToKgAction, LbToKgObservation]):
    def __call__(self, action: LbToKgAction, conversation=None) -> LbToKgObservation:
        from health import lb_to_kg
        result = lb_to_kg(action.lb)
        return LbToKgObservation.from_text(_format_result(result))


class LbToKgTool(ToolDefinition[LbToKgAction, LbToKgObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["LbToKgTool"]:
        return [cls(
            description="Convert pounds to kilograms. Returns both lb and kg values.",
            action_type=LbToKgAction,
            observation_type=LbToKgObservation,
            executor=LbToKgExecutor(),
        )]


# =============================================================================
# ipf_weight_classes
# =============================================================================

class IpfWeightClassesAction(Action):
    sex: str = Field(description="Sex for weight classes: 'M' or 'F'")


class IpfWeightClassesObservation(Observation):
    pass


class IpfWeightClassesExecutor(ToolExecutor[IpfWeightClassesAction, IpfWeightClassesObservation]):
    def __call__(self, action: IpfWeightClassesAction, conversation=None) -> IpfWeightClassesObservation:
        from health import ipf_weight_classes
        result = ipf_weight_classes(action.sex)
        return IpfWeightClassesObservation.from_text(_format_result(result))


class IpfWeightClassesTool(ToolDefinition[IpfWeightClassesAction, IpfWeightClassesObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["IpfWeightClassesTool"]:
        return [cls(
            description=(
                "Get IPF weight classes for men or women. "
                "Returns weight classes in kg and the operator's current weight class if available."
            ),
            action_type=IpfWeightClassesAction,
            observation_type=IpfWeightClassesObservation,
            executor=IpfWeightClassesExecutor(),
        )]


# =============================================================================
# pct_of_max
# =============================================================================

class PctOfMaxAction(Action):
    max_kg: float = Field(description="Maximum weight in kilograms")
    pct: float = Field(description="Percentage (0-150, not 0-1). E.g., 85 for 85%")


class PctOfMaxObservation(Observation):
    pass


class PctOfMaxExecutor(ToolExecutor[PctOfMaxAction, PctOfMaxObservation]):
    def __call__(self, action: PctOfMaxAction, conversation=None) -> PctOfMaxObservation:
        from health import pct_of_max
        result = pct_of_max(action.max_kg, action.pct)
        return PctOfMaxObservation.from_text(_format_result(result))


class PctOfMaxTool(ToolDefinition[PctOfMaxAction, PctOfMaxObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["PctOfMaxTool"]:
        return [cls(
            description=(
                "Calculate percentage of max weight. "
                "Returns raw kg, rounded to nearest 2.5kg, and lb conversion."
            ),
            action_type=PctOfMaxAction,
            observation_type=PctOfMaxObservation,
            executor=PctOfMaxExecutor(),
        )]


# =============================================================================
# calculate_attempts
# =============================================================================

class CalculateAttemptsAction(Action):
    lift: str = Field(description="Lift type: 'squat', 'bench', or 'deadlift'")
    opener_kg: float = Field(description="First attempt weight in kg")
    j1_override: Optional[float] = Field(default=None, description="Override jump 1 from program prefs (kg)")
    j2_override: Optional[float] = Field(default=None, description="Override jump 2 from program prefs (kg)")
    last_felt: Optional[str] = Field(default=None, description="If 'hard', halve j2 for conservative third attempt")


class CalculateAttemptsObservation(Observation):
    pass


class CalculateAttemptsExecutor(ToolExecutor[CalculateAttemptsAction, CalculateAttemptsObservation]):
    def __call__(self, action: CalculateAttemptsAction, conversation=None) -> CalculateAttemptsObservation:
        from health import calculate_attempts
        result = _run_async(calculate_attempts(
            lift=action.lift,
            opener_kg=action.opener_kg,
            j1_override=action.j1_override,
            j2_override=action.j2_override,
            last_felt=action.last_felt,
        ))
        return CalculateAttemptsObservation.from_text(_format_result(result))


class CalculateAttemptsTool(ToolDefinition[CalculateAttemptsAction, CalculateAttemptsObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["CalculateAttemptsTool"]:
        return [cls(
            description=(
                "Calculate competition attempts based on opener and program preferences. "
                "Returns three attempts with jumps used and any warnings."
            ),
            action_type=CalculateAttemptsAction,
            observation_type=CalculateAttemptsObservation,
            executor=CalculateAttemptsExecutor(),
        )]


# =============================================================================
# health_rag_search
# =============================================================================

class HealthRagSearchAction(Action):
    query: str = Field(description="Search query for health documents")
    n_results: int = Field(default=4, description="Number of results to return")


class HealthRagSearchObservation(Observation):
    pass


class HealthRagSearchExecutor(ToolExecutor[HealthRagSearchAction, HealthRagSearchObservation]):
    def __call__(self, action: HealthRagSearchAction, conversation=None) -> HealthRagSearchObservation:
        from health import health_rag_search
        result = _run_async(health_rag_search(action.query, action.n_results))
        return HealthRagSearchObservation.from_text(_format_result(result))


class HealthRagSearchTool(ToolDefinition[HealthRagSearchAction, HealthRagSearchObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthRagSearchTool"]:
        return [cls(
            description=(
                "Search health documents (IPF rulebook, anti-doping list, supplement info) using semantic search. "
                "Use for questions about rules, banned substances, or supplement guidance."
            ),
            action_type=HealthRagSearchAction,
            observation_type=HealthRagSearchObservation,
            executor=HealthRagSearchExecutor(),
        )]


# =============================================================================
# Granular Load Tools
# =============================================================================

# --- health_get_competition ---

class HealthGetCompetitionAction(Action):
    date: str = Field(description="Competition date (YYYY-MM-DD)")


class HealthGetCompetitionObservation(Observation):
    pass


class HealthGetCompetitionExecutor(ToolExecutor[HealthGetCompetitionAction, HealthGetCompetitionObservation]):
    def __call__(self, action: HealthGetCompetitionAction, conversation=None) -> HealthGetCompetitionObservation:
        from health import health_get_competition
        result = _run_async(health_get_competition(action.date))
        return HealthGetCompetitionObservation.from_text(_format_result(result))


class HealthGetCompetitionTool(ToolDefinition[HealthGetCompetitionAction, HealthGetCompetitionObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthGetCompetitionTool"]:
        return [cls(
            description=(
                "Load a specific competition by date. "
                "Returns full competition object including targets, between_comp_plan, and comp_day_protocol."
            ),
            action_type=HealthGetCompetitionAction,
            observation_type=HealthGetCompetitionObservation,
            executor=HealthGetCompetitionExecutor(),
        )]


# --- health_list_competitions ---

class HealthListCompetitionsAction(Action):
    pass


class HealthListCompetitionsObservation(Observation):
    pass


class HealthListCompetitionsExecutor(ToolExecutor[HealthListCompetitionsAction, HealthListCompetitionsObservation]):
    def __call__(self, action: HealthListCompetitionsAction, conversation=None) -> HealthListCompetitionsObservation:
        from health import health_list_competitions
        result = _run_async(health_list_competitions())
        return HealthListCompetitionsObservation.from_text(_format_result(result))


class HealthListCompetitionsTool(ToolDefinition[HealthListCompetitionsAction, HealthListCompetitionsObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthListCompetitionsTool"]:
        return [cls(
            description=(
                "List all competitions with summary info. "
                "Returns array of {name, date, status, weight_class_kg, federation}."
            ),
            action_type=HealthListCompetitionsAction,
            observation_type=HealthListCompetitionsObservation,
            executor=HealthListCompetitionsExecutor(),
        )]


# --- health_get_diet_notes ---

class HealthGetDietNotesAction(Action):
    start_date: Optional[str] = Field(default=None, description="Optional start of date range (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="Optional end of date range (YYYY-MM-DD)")


class HealthGetDietNotesObservation(Observation):
    pass


class HealthGetDietNotesExecutor(ToolExecutor[HealthGetDietNotesAction, HealthGetDietNotesObservation]):
    def __call__(self, action: HealthGetDietNotesAction, conversation=None) -> HealthGetDietNotesObservation:
        from health import health_get_diet_notes
        result = _run_async(health_get_diet_notes(action.start_date, action.end_date))
        return HealthGetDietNotesObservation.from_text(_format_result(result))


class HealthGetDietNotesTool(ToolDefinition[HealthGetDietNotesAction, HealthGetDietNotesObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthGetDietNotesTool"]:
        return [cls(
            description=(
                "Get diet notes, optionally filtered by date range. "
                "Returns array of {date, notes} sorted by date descending."
            ),
            action_type=HealthGetDietNotesAction,
            observation_type=HealthGetDietNotesObservation,
            executor=HealthGetDietNotesExecutor(),
        )]


# --- health_get_session ---

class HealthGetSessionAction(Action):
    date: str = Field(description="Session date (YYYY-MM-DD)")


class HealthGetSessionObservation(Observation):
    pass


class HealthGetSessionExecutor(ToolExecutor[HealthGetSessionAction, HealthGetSessionObservation]):
    def __call__(self, action: HealthGetSessionAction, conversation=None) -> HealthGetSessionObservation:
        from health import health_get_session
        result = _run_async(health_get_session(action.date))
        return HealthGetSessionObservation.from_text(_format_result(result))


class HealthGetSessionTool(ToolDefinition[HealthGetSessionAction, HealthGetSessionObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthGetSessionTool"]:
        return [cls(
            description=(
                "Load a single training session by date. "
                "Returns session with exercises and resolved phase object."
            ),
            action_type=HealthGetSessionAction,
            observation_type=HealthGetSessionObservation,
            executor=HealthGetSessionExecutor(),
        )]


# --- health_get_sessions_range ---

class HealthGetSessionsRangeAction(Action):
    start_date: str = Field(description="Start of date range (YYYY-MM-DD)")
    end_date: str = Field(description="End of date range (YYYY-MM-DD)")


class HealthGetSessionsRangeObservation(Observation):
    pass


class HealthGetSessionsRangeExecutor(ToolExecutor[HealthGetSessionsRangeAction, HealthGetSessionsRangeObservation]):
    def __call__(self, action: HealthGetSessionsRangeAction, conversation=None) -> HealthGetSessionsRangeObservation:
        from health import health_get_sessions_range
        result = _run_async(health_get_sessions_range(action.start_date, action.end_date))
        return HealthGetSessionsRangeObservation.from_text(_format_result(result))


class HealthGetSessionsRangeTool(ToolDefinition[HealthGetSessionsRangeAction, HealthGetSessionsRangeObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthGetSessionsRangeTool"]:
        return [cls(
            description=(
                "Load training sessions within a date range. "
                "Returns array of sessions in date order, each with resolved phase."
            ),
            action_type=HealthGetSessionsRangeAction,
            observation_type=HealthGetSessionsRangeObservation,
            executor=HealthGetSessionsRangeExecutor(),
        )]


# --- health_get_supplements ---

class HealthGetSupplementsAction(Action):
    pass


class HealthGetSupplementsObservation(Observation):
    pass


class HealthGetSupplementsExecutor(ToolExecutor[HealthGetSupplementsAction, HealthGetSupplementsObservation]):
    def __call__(self, action: HealthGetSupplementsAction, conversation=None) -> HealthGetSupplementsObservation:
        from health import health_get_supplements
        result = _run_async(health_get_supplements())
        return HealthGetSupplementsObservation.from_text(_format_result(result))


class HealthGetSupplementsTool(ToolDefinition[HealthGetSupplementsAction, HealthGetSupplementsObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthGetSupplementsTool"]:
        return [cls(
            description=(
                "Load supplements and supplement phases. "
                "Returns {supplements: [...], supplement_phases: [...]}."
            ),
            action_type=HealthGetSupplementsAction,
            observation_type=HealthGetSupplementsObservation,
            executor=HealthGetSupplementsExecutor(),
        )]


# =============================================================================
# Granular Edit Tools
# =============================================================================

# --- health_update_competition ---

class HealthUpdateCompetitionAction(Action):
    date: str = Field(description="Competition date to update (YYYY-MM-DD)")
    patch: Dict[str, Any] = Field(
        description="Fields to update (targets, status, notes, between_comp_plan, comp_day_protocol, etc.)"
    )


class HealthUpdateCompetitionObservation(Observation):
    pass


class HealthUpdateCompetitionExecutor(ToolExecutor[HealthUpdateCompetitionAction, HealthUpdateCompetitionObservation]):
    def __call__(self, action: HealthUpdateCompetitionAction, conversation=None) -> HealthUpdateCompetitionObservation:
        from health import health_update_competition
        result = _run_async(health_update_competition(action.date, action.patch))
        return HealthUpdateCompetitionObservation.from_text(_format_result(result))


class HealthUpdateCompetitionTool(ToolDefinition[HealthUpdateCompetitionAction, HealthUpdateCompetitionObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthUpdateCompetitionTool"]:
        return [cls(
            description=(
                "Update a competition by date. Creates a new minor program version. "
                "Use to update targets, status, notes, between_comp_plan, or comp_day_protocol."
            ),
            action_type=HealthUpdateCompetitionAction,
            observation_type=HealthUpdateCompetitionObservation,
            executor=HealthUpdateCompetitionExecutor(),
        )]


# --- health_update_diet_note ---

class HealthUpdateDietNoteAction(Action):
    date: str = Field(description="Date for the diet note (YYYY-MM-DD)")
    notes: str = Field(description="The diet notes content (replaces existing)")


class HealthUpdateDietNoteObservation(Observation):
    pass


class HealthUpdateDietNoteExecutor(ToolExecutor[HealthUpdateDietNoteAction, HealthUpdateDietNoteObservation]):
    def __call__(self, action: HealthUpdateDietNoteAction, conversation=None) -> HealthUpdateDietNoteObservation:
        from health import health_update_diet_note
        result = _run_async(health_update_diet_note(action.date, action.notes))
        return HealthUpdateDietNoteObservation.from_text(_format_result(result))


class HealthUpdateDietNoteTool(ToolDefinition[HealthUpdateDietNoteAction, HealthUpdateDietNoteObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthUpdateDietNoteTool"]:
        return [cls(
            description=(
                "Update or create a diet note for a specific date. "
                "Creates a new minor program version. Replaces existing content."
            ),
            action_type=HealthUpdateDietNoteAction,
            observation_type=HealthUpdateDietNoteObservation,
            executor=HealthUpdateDietNoteExecutor(),
        )]


# --- health_update_supplements ---

class HealthUpdateSupplementsAction(Action):
    patch: Dict[str, Any] = Field(
        description='{"supplements": [...]} or {"supplement_phases": [...]} or both'
    )


class HealthUpdateSupplementsObservation(Observation):
    pass


class HealthUpdateSupplementsExecutor(ToolExecutor[HealthUpdateSupplementsAction, HealthUpdateSupplementsObservation]):
    def __call__(self, action: HealthUpdateSupplementsAction, conversation=None) -> HealthUpdateSupplementsObservation:
        from health import health_update_supplements
        result = _run_async(health_update_supplements(action.patch))
        return HealthUpdateSupplementsObservation.from_text(_format_result(result))


class HealthUpdateSupplementsTool(ToolDefinition[HealthUpdateSupplementsAction, HealthUpdateSupplementsObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthUpdateSupplementsTool"]:
        return [cls(
            description=(
                "Update supplements or supplement phases. "
                "Creates a new minor program version."
            ),
            action_type=HealthUpdateSupplementsAction,
            observation_type=HealthUpdateSupplementsObservation,
            executor=HealthUpdateSupplementsExecutor(),
        )]


# =============================================================================
# Register all tools
# =============================================================================

register_tool("HealthGetProgramTool", HealthGetProgramTool)
register_tool("HealthCompCountdownTool", HealthCompCountdownTool)
register_tool("HealthUpdateSessionTool", HealthUpdateSessionTool)
register_tool("HealthNewVersionTool", HealthNewVersionTool)
register_tool("KgToLbTool", KgToLbTool)
register_tool("LbToKgTool", LbToKgTool)
register_tool("IpfWeightClassesTool", IpfWeightClassesTool)
register_tool("PctOfMaxTool", PctOfMaxTool)
register_tool("CalculateAttemptsTool", CalculateAttemptsTool)
register_tool("HealthRagSearchTool", HealthRagSearchTool)
# Granular load tools
register_tool("HealthGetCompetitionTool", HealthGetCompetitionTool)
register_tool("HealthListCompetitionsTool", HealthListCompetitionsTool)
register_tool("HealthGetDietNotesTool", HealthGetDietNotesTool)
register_tool("HealthGetSessionTool", HealthGetSessionTool)
register_tool("HealthGetSessionsRangeTool", HealthGetSessionsRangeTool)
register_tool("HealthGetSupplementsTool", HealthGetSupplementsTool)
# Granular edit tools
register_tool("HealthUpdateCompetitionTool", HealthUpdateCompetitionTool)
register_tool("HealthUpdateDietNoteTool", HealthUpdateDietNoteTool)
register_tool("HealthUpdateSupplementsTool", HealthUpdateSupplementsTool)


# =============================================================================
# Getter function
# =============================================================================

def get_health_tools() -> List[Tool]:
    """Get all health tools for session initialization."""
    return [
        Tool(name="HealthGetProgramTool"),
        Tool(name="HealthCompCountdownTool"),
        Tool(name="HealthUpdateSessionTool"),
        Tool(name="HealthNewVersionTool"),
        Tool(name="KgToLbTool"),
        Tool(name="LbToKgTool"),
        Tool(name="IpfWeightClassesTool"),
        Tool(name="PctOfMaxTool"),
        Tool(name="CalculateAttemptsTool"),
        Tool(name="HealthRagSearchTool"),
        # Granular load tools
        Tool(name="HealthGetCompetitionTool"),
        Tool(name="HealthListCompetitionsTool"),
        Tool(name="HealthGetDietNotesTool"),
        Tool(name="HealthGetSessionTool"),
        Tool(name="HealthGetSessionsRangeTool"),
        Tool(name="HealthGetSupplementsTool"),
        # Granular edit tools
        Tool(name="HealthUpdateCompetitionTool"),
        Tool(name="HealthUpdateDietNoteTool"),
        Tool(name="HealthUpdateSupplementsTool"),
    ]
