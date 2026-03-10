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
    ]
