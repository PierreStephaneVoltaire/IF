"""Health tool plugin — training program management and powerlifting tools.

Exports:
    get_tools()       → SDK Tool objects (side effect: register_tool() calls)
    get_schemas()     → snake_case name → JSON schema
    execute(name, args) → async dispatcher for non-agentic path
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Sequence

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
# Helpers (duplicated from agent/tools/base to avoid cross-dir imports)
# =============================================================================

def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _format_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    return json.dumps(result, indent=2, default=str)


# =============================================================================
# SDK Tool Classes (migrated from agent/tools/health_tools.py)
# =============================================================================

# --- health_get_program ---

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


# --- health_comp_countdown ---

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


# --- health_update_session ---

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


# --- health_new_version ---

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


# --- kg_to_lb ---

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


# --- lb_to_kg ---

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


# --- ipf_weight_classes ---

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


# --- pct_of_max ---

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


# --- calculate_attempts ---

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


# --- health_rag_search ---

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


# --- health_get_meta ---

class HealthGetMetaAction(Action):
    pass


class HealthGetMetaObservation(Observation):
    pass


class HealthGetMetaExecutor(ToolExecutor[HealthGetMetaAction, HealthGetMetaObservation]):
    def __call__(self, action: HealthGetMetaAction, conversation=None) -> HealthGetMetaObservation:
        from health import health_get_meta
        result = _run_async(health_get_meta())
        return HealthGetMetaObservation.from_text(_format_result(result))


class HealthGetMetaTool(ToolDefinition[HealthGetMetaAction, HealthGetMetaObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthGetMetaTool"]:
        return [cls(
            description=(
                "Get program metadata: comp_date, program_start, targets (squat/bench/deadlift/total), "
                "weight_class_kg, version, training_notes, change_log. "
                "Use this instead of health_get_program when you only need program-level info."
            ),
            action_type=HealthGetMetaAction,
            observation_type=HealthGetMetaObservation,
            executor=HealthGetMetaExecutor(),
        )]


# --- health_get_phases ---

class HealthGetPhasesAction(Action):
    pass


class HealthGetPhasesObservation(Observation):
    pass


class HealthGetPhasesExecutor(ToolExecutor[HealthGetPhasesAction, HealthGetPhasesObservation]):
    def __call__(self, action: HealthGetPhasesAction, conversation=None) -> HealthGetPhasesObservation:
        from health import health_get_phases
        result = _run_async(health_get_phases())
        return HealthGetPhasesObservation.from_text(_format_result(result))


class HealthGetPhasesTool(ToolDefinition[HealthGetPhasesAction, HealthGetPhasesObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthGetPhasesTool"]:
        return [cls(
            description=(
                "Get training phases (name, start_week, end_week, intent). "
                "Use to understand the program structure without loading all sessions."
            ),
            action_type=HealthGetPhasesAction,
            observation_type=HealthGetPhasesObservation,
            executor=HealthGetPhasesExecutor(),
        )]


# --- health_get_current_maxes ---

class HealthGetCurrentMaxesAction(Action):
    pass


class HealthGetCurrentMaxesObservation(Observation):
    pass


class HealthGetCurrentMaxesExecutor(ToolExecutor[HealthGetCurrentMaxesAction, HealthGetCurrentMaxesObservation]):
    def __call__(self, action: HealthGetCurrentMaxesAction, conversation=None) -> HealthGetCurrentMaxesObservation:
        from health import health_get_current_maxes
        result = _run_async(health_get_current_maxes())
        return HealthGetCurrentMaxesObservation.from_text(_format_result(result))


class HealthGetCurrentMaxesTool(ToolDefinition[HealthGetCurrentMaxesAction, HealthGetCurrentMaxesObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthGetCurrentMaxesTool"]:
        return [cls(
            description=(
                "Get current competition maxes in kg: {squat, bench, deadlift}. "
                "Use for percentage calculations or attempt planning without loading the full program."
            ),
            action_type=HealthGetCurrentMaxesAction,
            observation_type=HealthGetCurrentMaxesObservation,
            executor=HealthGetCurrentMaxesExecutor(),
        )]


# --- health_get_operator_prefs ---

class HealthGetOperatorPrefsAction(Action):
    pass


class HealthGetOperatorPrefsObservation(Observation):
    pass


class HealthGetOperatorPrefsExecutor(ToolExecutor[HealthGetOperatorPrefsAction, HealthGetOperatorPrefsObservation]):
    def __call__(self, action: HealthGetOperatorPrefsAction, conversation=None) -> HealthGetOperatorPrefsObservation:
        from health import health_get_operator_prefs
        result = _run_async(health_get_operator_prefs())
        return HealthGetOperatorPrefsObservation.from_text(_format_result(result))


class HealthGetOperatorPrefsTool(ToolDefinition[HealthGetOperatorPrefsAction, HealthGetOperatorPrefsObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthGetOperatorPrefsTool"]:
        return [cls(
            description=(
                "Get operator preferences including attempt_jumps per lift (j1, j2 in kg). "
                "Use when calculating competition attempts or checking preferred jump sizes."
            ),
            action_type=HealthGetOperatorPrefsAction,
            observation_type=HealthGetOperatorPrefsObservation,
            executor=HealthGetOperatorPrefsExecutor(),
        )]


# --- health_get_breaks ---

class HealthGetBreaksAction(Action):
    pass


class HealthGetBreaksObservation(Observation):
    pass


class HealthGetBreaksExecutor(ToolExecutor[HealthGetBreaksAction, HealthGetBreaksObservation]):
    def __call__(self, action: HealthGetBreaksAction, conversation=None) -> HealthGetBreaksObservation:
        from health import health_get_breaks
        result = _run_async(health_get_breaks())
        return HealthGetBreaksObservation.from_text(_format_result(result))


class HealthGetBreaksTool(ToolDefinition[HealthGetBreaksAction, HealthGetBreaksObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthGetBreaksTool"]:
        return [cls(
            description=(
                "Get scheduled break/deload periods: [{start, end}, ...]. "
                "Use to check if a date falls in a rest week or when the next break is."
            ),
            action_type=HealthGetBreaksAction,
            observation_type=HealthGetBreaksObservation,
            executor=HealthGetBreaksExecutor(),
        )]


# --- days_until ---

class DaysUntilAction(Action):
    target_date: str = Field(description="Target date (YYYY-MM-DD)")
    label: str = Field(default="target", description="Human label for the milestone, e.g. 'comp', 'deload'")


class DaysUntilObservation(Observation):
    pass


class DaysUntilExecutor(ToolExecutor[DaysUntilAction, DaysUntilObservation]):
    def __call__(self, action: DaysUntilAction, conversation=None) -> DaysUntilObservation:
        from health import days_until
        result = _run_async(days_until(action.target_date, action.label))
        return DaysUntilObservation.from_text(_format_result(result))


class DaysUntilTool(ToolDefinition[DaysUntilAction, DaysUntilObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["DaysUntilTool"]:
        return [cls(
            description=(
                "Calculate days and weeks until (or since) a target date. "
                "Returns days_remaining, weeks_remaining, today, is_past."
            ),
            action_type=DaysUntilAction,
            observation_type=DaysUntilObservation,
            executor=DaysUntilExecutor(),
        )]


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


# --- health_create_session ---

class HealthCreateSessionAction(Action):
    date: str = Field(description="Session date (YYYY-MM-DD)")
    day: str = Field(description="Day label e.g. 'Monday'")
    week_number: int = Field(description="Training week number")
    exercises: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional list of exercises {name, sets, reps, kg, rpe, notes}")
    session_notes: str = Field(default="", description="Optional session notes")


class HealthCreateSessionObservation(Observation):
    pass


class HealthCreateSessionExecutor(ToolExecutor[HealthCreateSessionAction, HealthCreateSessionObservation]):
    def __call__(self, action: HealthCreateSessionAction, conversation=None) -> HealthCreateSessionObservation:
        from health import health_create_session
        result = _run_async(health_create_session(action.date, action.day, action.week_number, action.exercises, action.session_notes))
        return HealthCreateSessionObservation.from_text(_format_result(result))


class HealthCreateSessionTool(ToolDefinition[HealthCreateSessionAction, HealthCreateSessionObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthCreateSessionTool"]:
        return [cls(
            description="Create a new training session. Requires date, day label, and week number. Optionally include exercises.",
            action_type=HealthCreateSessionAction,
            observation_type=HealthCreateSessionObservation,
            executor=HealthCreateSessionExecutor(),
        )]


# --- health_delete_session ---

class HealthDeleteSessionAction(Action):
    date: str = Field(description="Session date to delete (YYYY-MM-DD)")


class HealthDeleteSessionObservation(Observation):
    pass


class HealthDeleteSessionExecutor(ToolExecutor[HealthDeleteSessionAction, HealthDeleteSessionObservation]):
    def __call__(self, action: HealthDeleteSessionAction, conversation=None) -> HealthDeleteSessionObservation:
        from health import health_delete_session
        result = _run_async(health_delete_session(action.date))
        return HealthDeleteSessionObservation.from_text(_format_result(result))


class HealthDeleteSessionTool(ToolDefinition[HealthDeleteSessionAction, HealthDeleteSessionObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthDeleteSessionTool"]:
        return [cls(
            description="Delete a training session by date. Cannot be undone.",
            action_type=HealthDeleteSessionAction,
            observation_type=HealthDeleteSessionObservation,
            executor=HealthDeleteSessionExecutor(),
        )]


# --- health_reschedule_session ---

class HealthRescheduleSessionAction(Action):
    old_date: str = Field(description="Current session date (YYYY-MM-DD)")
    new_date: str = Field(description="Target date to move to (YYYY-MM-DD)")


class HealthRescheduleSessionObservation(Observation):
    pass


class HealthRescheduleSessionExecutor(ToolExecutor[HealthRescheduleSessionAction, HealthRescheduleSessionObservation]):
    def __call__(self, action: HealthRescheduleSessionAction, conversation=None) -> HealthRescheduleSessionObservation:
        from health import health_reschedule_session
        result = _run_async(health_reschedule_session(action.old_date, action.new_date))
        return HealthRescheduleSessionObservation.from_text(_format_result(result))


class HealthRescheduleSessionTool(ToolDefinition[HealthRescheduleSessionAction, HealthRescheduleSessionObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthRescheduleSessionTool"]:
        return [cls(
            description="Move a training session to a different date.",
            action_type=HealthRescheduleSessionAction,
            observation_type=HealthRescheduleSessionObservation,
            executor=HealthRescheduleSessionExecutor(),
        )]


# --- health_add_exercise ---

class HealthAddExerciseAction(Action):
    date: str = Field(description="Session date (YYYY-MM-DD)")
    exercise: Dict[str, Any] = Field(description="Exercise dict: {name (required), sets, reps, kg, rpe, notes}")


class HealthAddExerciseObservation(Observation):
    pass


class HealthAddExerciseExecutor(ToolExecutor[HealthAddExerciseAction, HealthAddExerciseObservation]):
    def __call__(self, action: HealthAddExerciseAction, conversation=None) -> HealthAddExerciseObservation:
        from health import health_add_exercise
        result = _run_async(health_add_exercise(action.date, action.exercise))
        return HealthAddExerciseObservation.from_text(_format_result(result))


class HealthAddExerciseTool(ToolDefinition[HealthAddExerciseAction, HealthAddExerciseObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthAddExerciseTool"]:
        return [cls(
            description="Add an exercise to a training session. Provide the session date and exercise dict {name, sets, reps, kg, rpe, notes}.",
            action_type=HealthAddExerciseAction,
            observation_type=HealthAddExerciseObservation,
            executor=HealthAddExerciseExecutor(),
        )]


# --- health_remove_exercise ---

class HealthRemoveExerciseAction(Action):
    date: str = Field(description="Session date (YYYY-MM-DD)")
    exercise_index: int = Field(description="Zero-based index of the exercise to remove")


class HealthRemoveExerciseObservation(Observation):
    pass


class HealthRemoveExerciseExecutor(ToolExecutor[HealthRemoveExerciseAction, HealthRemoveExerciseObservation]):
    def __call__(self, action: HealthRemoveExerciseAction, conversation=None) -> HealthRemoveExerciseObservation:
        from health import health_remove_exercise
        result = _run_async(health_remove_exercise(action.date, action.exercise_index))
        return HealthRemoveExerciseObservation.from_text(_format_result(result))


class HealthRemoveExerciseTool(ToolDefinition[HealthRemoveExerciseAction, HealthRemoveExerciseObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthRemoveExerciseTool"]:
        return [cls(
            description="Remove an exercise from a session by its zero-based index. Fetch the session first to confirm the correct index.",
            action_type=HealthRemoveExerciseAction,
            observation_type=HealthRemoveExerciseObservation,
            executor=HealthRemoveExerciseExecutor(),
        )]


# --- health_create_competition ---

class HealthCreateCompetitionAction(Action):
    competition: Dict[str, Any] = Field(
        description="Competition dict: name (required), date YYYY-MM-DD (required), federation (required), "
                    "status (confirmed/optional/skipped), weight_class_kg, location, targets {squat_kg, bench_kg, deadlift_kg, total_kg}, notes"
    )


class HealthCreateCompetitionObservation(Observation):
    pass


class HealthCreateCompetitionExecutor(ToolExecutor[HealthCreateCompetitionAction, HealthCreateCompetitionObservation]):
    def __call__(self, action: HealthCreateCompetitionAction, conversation=None) -> HealthCreateCompetitionObservation:
        from health import health_create_competition
        result = _run_async(health_create_competition(action.competition))
        return HealthCreateCompetitionObservation.from_text(_format_result(result))


class HealthCreateCompetitionTool(ToolDefinition[HealthCreateCompetitionAction, HealthCreateCompetitionObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthCreateCompetitionTool"]:
        return [cls(
            description="Create a new competition entry. Required: name, date, federation. Optional: status, weight_class_kg, location, targets, notes.",
            action_type=HealthCreateCompetitionAction,
            observation_type=HealthCreateCompetitionObservation,
            executor=HealthCreateCompetitionExecutor(),
        )]


# --- health_delete_competition ---

class HealthDeleteCompetitionAction(Action):
    date: str = Field(description="Competition date to delete (YYYY-MM-DD)")


class HealthDeleteCompetitionObservation(Observation):
    pass


class HealthDeleteCompetitionExecutor(ToolExecutor[HealthDeleteCompetitionAction, HealthDeleteCompetitionObservation]):
    def __call__(self, action: HealthDeleteCompetitionAction, conversation=None) -> HealthDeleteCompetitionObservation:
        from health import health_delete_competition
        result = _run_async(health_delete_competition(action.date))
        return HealthDeleteCompetitionObservation.from_text(_format_result(result))


class HealthDeleteCompetitionTool(ToolDefinition[HealthDeleteCompetitionAction, HealthDeleteCompetitionObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthDeleteCompetitionTool"]:
        return [cls(
            description="Delete a competition by date. Cannot be undone.",
            action_type=HealthDeleteCompetitionAction,
            observation_type=HealthDeleteCompetitionObservation,
            executor=HealthDeleteCompetitionExecutor(),
        )]


# --- health_delete_diet_note ---

class HealthDeleteDietNoteAction(Action):
    date: str = Field(description="Diet note date to delete (YYYY-MM-DD)")


class HealthDeleteDietNoteObservation(Observation):
    pass


class HealthDeleteDietNoteExecutor(ToolExecutor[HealthDeleteDietNoteAction, HealthDeleteDietNoteObservation]):
    def __call__(self, action: HealthDeleteDietNoteAction, conversation=None) -> HealthDeleteDietNoteObservation:
        from health import health_delete_diet_note
        result = _run_async(health_delete_diet_note(action.date))
        return HealthDeleteDietNoteObservation.from_text(_format_result(result))


class HealthDeleteDietNoteTool(ToolDefinition[HealthDeleteDietNoteAction, HealthDeleteDietNoteObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthDeleteDietNoteTool"]:
        return [cls(
            description="Delete a diet note by date.",
            action_type=HealthDeleteDietNoteAction,
            observation_type=HealthDeleteDietNoteObservation,
            executor=HealthDeleteDietNoteExecutor(),
        )]


# --- health_update_meta ---

class HealthUpdateMetaAction(Action):
    updates: Dict[str, Any] = Field(
        description="Dict of meta fields to update. Allowed: program_name, comp_date, target_squat_kg, "
                    "target_bench_kg, target_dl_kg, target_total_kg, weight_class_kg, "
                    "current_body_weight_kg, federation, practicing_for, program_start"
    )


class HealthUpdateMetaObservation(Observation):
    pass


class HealthUpdateMetaExecutor(ToolExecutor[HealthUpdateMetaAction, HealthUpdateMetaObservation]):
    def __call__(self, action: HealthUpdateMetaAction, conversation=None) -> HealthUpdateMetaObservation:
        from health import health_update_meta
        result = _run_async(health_update_meta(action.updates))
        return HealthUpdateMetaObservation.from_text(_format_result(result))


class HealthUpdateMetaTool(ToolDefinition[HealthUpdateMetaAction, HealthUpdateMetaObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthUpdateMetaTool"]:
        return [cls(
            description=(
                "Update program metadata fields: comp_date, target maxes, body weight, weight_class_kg, "
                "federation, program_start, program_name. Pass only the fields you want to change."
            ),
            action_type=HealthUpdateMetaAction,
            observation_type=HealthUpdateMetaObservation,
            executor=HealthUpdateMetaExecutor(),
        )]


# --- health_update_phases ---

class HealthUpdatePhasesAction(Action):
    phases: List[Dict[str, Any]] = Field(
        description="Complete phases list. Each phase: {name (required), start_week (int), end_week (int), intent (str)}"
    )


class HealthUpdatePhasesObservation(Observation):
    pass


class HealthUpdatePhasesExecutor(ToolExecutor[HealthUpdatePhasesAction, HealthUpdatePhasesObservation]):
    def __call__(self, action: HealthUpdatePhasesAction, conversation=None) -> HealthUpdatePhasesObservation:
        from health import health_update_phases
        result = _run_async(health_update_phases(action.phases))
        return HealthUpdatePhasesObservation.from_text(_format_result(result))


class HealthUpdatePhasesTool(ToolDefinition[HealthUpdatePhasesAction, HealthUpdatePhasesObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthUpdatePhasesTool"]:
        return [cls(
            description="Replace the training phases array. Fetch current phases first, modify, then submit the full list.",
            action_type=HealthUpdatePhasesAction,
            observation_type=HealthUpdatePhasesObservation,
            executor=HealthUpdatePhasesExecutor(),
        )]


# --- health_update_current_maxes ---

class HealthUpdateCurrentMaxesAction(Action):
    squat_kg: Optional[float] = Field(default=None, description="New squat max in kg (omit to leave unchanged)")
    bench_kg: Optional[float] = Field(default=None, description="New bench max in kg (omit to leave unchanged)")
    deadlift_kg: Optional[float] = Field(default=None, description="New deadlift max in kg (omit to leave unchanged)")


class HealthUpdateCurrentMaxesObservation(Observation):
    pass


class HealthUpdateCurrentMaxesExecutor(ToolExecutor[HealthUpdateCurrentMaxesAction, HealthUpdateCurrentMaxesObservation]):
    def __call__(self, action: HealthUpdateCurrentMaxesAction, conversation=None) -> HealthUpdateCurrentMaxesObservation:
        from health import health_update_current_maxes
        result = _run_async(health_update_current_maxes(action.squat_kg, action.bench_kg, action.deadlift_kg))
        return HealthUpdateCurrentMaxesObservation.from_text(_format_result(result))


class HealthUpdateCurrentMaxesTool(ToolDefinition[HealthUpdateCurrentMaxesAction, HealthUpdateCurrentMaxesObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["HealthUpdateCurrentMaxesTool"]:
        return [cls(
            description="Update current competition maxes (squat_kg, bench_kg, deadlift_kg). Pass only the lifts that changed.",
            action_type=HealthUpdateCurrentMaxesAction,
            observation_type=HealthUpdateCurrentMaxesObservation,
            executor=HealthUpdateCurrentMaxesExecutor(),
        )]


# =============================================================================
# Register all SDK tools
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
register_tool("HealthGetCompetitionTool", HealthGetCompetitionTool)
register_tool("HealthListCompetitionsTool", HealthListCompetitionsTool)
register_tool("HealthGetDietNotesTool", HealthGetDietNotesTool)
register_tool("HealthGetSessionTool", HealthGetSessionTool)
register_tool("HealthGetSessionsRangeTool", HealthGetSessionsRangeTool)
register_tool("HealthGetSupplementsTool", HealthGetSupplementsTool)
register_tool("HealthGetMetaTool", HealthGetMetaTool)
register_tool("HealthGetPhasesTool", HealthGetPhasesTool)
register_tool("HealthGetCurrentMaxesTool", HealthGetCurrentMaxesTool)
register_tool("HealthGetOperatorPrefsTool", HealthGetOperatorPrefsTool)
register_tool("HealthGetBreaksTool", HealthGetBreaksTool)
register_tool("DaysUntilTool", DaysUntilTool)
register_tool("HealthUpdateCompetitionTool", HealthUpdateCompetitionTool)
register_tool("HealthUpdateDietNoteTool", HealthUpdateDietNoteTool)
register_tool("HealthUpdateSupplementsTool", HealthUpdateSupplementsTool)
register_tool("HealthCreateSessionTool", HealthCreateSessionTool)
register_tool("HealthDeleteSessionTool", HealthDeleteSessionTool)
register_tool("HealthRescheduleSessionTool", HealthRescheduleSessionTool)
register_tool("HealthAddExerciseTool", HealthAddExerciseTool)
register_tool("HealthRemoveExerciseTool", HealthRemoveExerciseTool)
register_tool("HealthCreateCompetitionTool", HealthCreateCompetitionTool)
register_tool("HealthDeleteCompetitionTool", HealthDeleteCompetitionTool)
register_tool("HealthDeleteDietNoteTool", HealthDeleteDietNoteTool)
register_tool("HealthUpdateMetaTool", HealthUpdateMetaTool)
register_tool("HealthUpdatePhasesTool", HealthUpdatePhasesTool)
register_tool("HealthUpdateCurrentMaxesTool", HealthUpdateCurrentMaxesTool)


# =============================================================================
# Plugin contract: get_tools()
# =============================================================================

def get_tools() -> List[Tool]:
    """Get all health SDK Tool objects (side effect: register_tool already called above)."""
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
        Tool(name="HealthGetCompetitionTool"),
        Tool(name="HealthListCompetitionsTool"),
        Tool(name="HealthGetDietNotesTool"),
        Tool(name="HealthGetSessionTool"),
        Tool(name="HealthGetSessionsRangeTool"),
        Tool(name="HealthGetSupplementsTool"),
        Tool(name="HealthGetMetaTool"),
        Tool(name="HealthGetPhasesTool"),
        Tool(name="HealthGetCurrentMaxesTool"),
        Tool(name="HealthGetOperatorPrefsTool"),
        Tool(name="HealthGetBreaksTool"),
        Tool(name="DaysUntilTool"),
        Tool(name="HealthUpdateCompetitionTool"),
        Tool(name="HealthUpdateDietNoteTool"),
        Tool(name="HealthUpdateSupplementsTool"),
        Tool(name="HealthCreateSessionTool"),
        Tool(name="HealthDeleteSessionTool"),
        Tool(name="HealthRescheduleSessionTool"),
        Tool(name="HealthAddExerciseTool"),
        Tool(name="HealthRemoveExerciseTool"),
        Tool(name="HealthCreateCompetitionTool"),
        Tool(name="HealthDeleteCompetitionTool"),
        Tool(name="HealthDeleteDietNoteTool"),
        Tool(name="HealthUpdateMetaTool"),
        Tool(name="HealthUpdatePhasesTool"),
        Tool(name="HealthUpdateCurrentMaxesTool"),
    ]


# =============================================================================
# Plugin contract: get_schemas() — JSON schemas for non-agentic specialist path
# =============================================================================

def get_schemas() -> Dict[str, Dict[str, Any]]:
    """Return snake_case tool name → JSON schema mapping."""
    return {
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
                    "date": {"type": "string", "description": "Session date (YYYY-MM-DD)"},
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
                    "date": {"type": "string", "description": "ISO8601 date string (YYYY-MM-DD) of the session to update"},
                    "patch": {"type": "object", "description": "Dict with session fields to update. Allowed keys: completed, session_rpe, body_weight_kg, session_notes, exercises"},
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
                    "change_reason": {"type": "string", "description": "Human-readable reason for the version change"},
                    "patches": {"type": "array", "items": {"type": "object"}, "description": "List of patches, each with 'path' and 'value' keys"},
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
                "properties": {"date": {"type": "string", "description": "Competition date (YYYY-MM-DD)"}},
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
                "properties": {"patch": {"type": "object", 'description': '{"supplements": [...]} or {"supplement_phases": [...]}'},},
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
                "properties": {"date": {"type": "string", "description": "Session date to delete (YYYY-MM-DD)"}},
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
                "properties": {"competition": {"type": "object", "description": "Competition dict: name, date, federation, status, weight_class_kg, location, targets, notes"}},
                "required": ["competition"],
            },
        },
        "health_delete_competition": {
            "name": "health_delete_competition",
            "description": "Delete a competition entry by date.",
            "parameters": {
                "type": "object",
                "properties": {"date": {"type": "string", "description": "Competition date to delete (YYYY-MM-DD)"}},
                "required": ["date"],
            },
        },
        "health_delete_diet_note": {
            "name": "health_delete_diet_note",
            "description": "Delete a diet note by date.",
            "parameters": {
                "type": "object",
                "properties": {"date": {"type": "string", "description": "Diet note date to delete (YYYY-MM-DD)"}},
                "required": ["date"],
            },
        },
        "health_update_meta": {
            "name": "health_update_meta",
            "description": "Update program metadata fields.",
            "parameters": {
                "type": "object",
                "properties": {"updates": {"type": "object", "description": "Dict of meta fields to update"}},
                "required": ["updates"],
            },
        },
        "health_update_phases": {
            "name": "health_update_phases",
            "description": "Replace the full phases list.",
            "parameters": {
                "type": "object",
                "properties": {"phases": {"type": "array", "items": {"type": "object"}, "description": "Complete phases list. Each: {name, start_week, end_week, intent}"}},
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
            "parameters": {"type": "object", "properties": {"kg": {"type": "number", "description": "Weight in kilograms"}}, "required": ["kg"]},
        },
        "lb_to_kg": {
            "name": "lb_to_kg",
            "description": "Convert pounds to kilograms.",
            "parameters": {"type": "object", "properties": {"lb": {"type": "number", "description": "Weight in pounds"}}, "required": ["lb"]},
        },
        "ipf_weight_classes": {
            "name": "ipf_weight_classes",
            "description": "Get IPF weight classes for a given sex.",
            "parameters": {"type": "object", "properties": {"sex": {"type": "string", "description": "Sex: 'M' or 'F'"}}, "required": ["sex"]},
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
# Plugin contract: execute() — async dispatcher for non-agentic specialist path
# =============================================================================

async def execute(name: str, args: Dict[str, Any]) -> str:
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

    ROUTES = {
        "health_get_program": lambda: health_get_program(),
        "health_get_session": lambda: health_get_session(args["date"]),
        "health_update_session": lambda: do_update_session(args["date"], args["patch"]),
        "health_new_version": lambda: do_new_version(args["change_reason"], args["patches"]),
        "health_rag_search": lambda: health_rag_search(args["query"], args.get("n_results", 4)),
        "health_get_competition": lambda: health_get_competition(args["date"]),
        "health_get_diet_notes": lambda: health_get_diet_notes(args.get("start_date"), args.get("end_date")),
        "health_get_sessions_range": lambda: health_get_sessions_range(args["start_date"], args["end_date"]),
        "health_get_supplements": lambda: health_get_supplements(),
        "health_get_meta": lambda: health_get_meta(),
        "health_get_phases": lambda: health_get_phases(),
        "health_get_current_maxes": lambda: health_get_current_maxes(),
        "health_update_competition": lambda: do_update_competition(args["date"], args["patch"]),
        "health_update_diet_note": lambda: do_update_diet_note(args["date"], args["notes"]),
        "health_update_supplements": lambda: do_update_supplements(args["patch"]),
        "health_create_session": lambda: do_create_session(args["date"], args["day"], args["week_number"], args.get("exercises"), args.get("session_notes", "")),
        "health_delete_session": lambda: do_delete_session(args["date"]),
        "health_reschedule_session": lambda: do_reschedule_session(args["old_date"], args["new_date"]),
        "health_add_exercise": lambda: do_add_exercise(args["date"], args["exercise"]),
        "health_remove_exercise": lambda: do_remove_exercise(args["date"], args["exercise_index"]),
        "health_create_competition": lambda: do_create_competition(args["competition"]),
        "health_delete_competition": lambda: do_delete_competition(args["date"]),
        "health_delete_diet_note": lambda: do_delete_diet_note(args["date"]),
        "health_update_meta": lambda: do_update_meta(args["updates"]),
        "health_update_phases": lambda: do_update_phases(args["phases"]),
        "health_update_current_maxes": lambda: do_update_current_maxes(args.get("squat_kg"), args.get("bench_kg"), args.get("deadlift_kg")),
        "kg_to_lb": lambda: kg_to_lb(args["kg"]),
        "lb_to_kg": lambda: lb_to_kg(args["lb"]),
        "ipf_weight_classes": lambda: ipf_weight_classes(args["sex"]),
        "pct_of_max": lambda: pct_of_max(args["max_kg"], args["pct"]),
        "calculate_attempts": lambda: calculate_attempts(args["lift"], args["opener_kg"], args.get("j1_override"), args.get("j2_override"), args.get("last_felt")),
        "days_until": lambda: days_until(args["target_date"], args.get("label", "target")),
    }

    handler = ROUTES.get(name)
    if not handler:
        return f"Unknown health tool: {name}"

    result = handler()
    if isinstance(result, str):
        return result
    return json.dumps(result, indent=2, default=str)
