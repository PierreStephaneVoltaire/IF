"""Proposal tools for agent-proposed directives and tools.

Provides tools for:
- create_proposal(): Agent creates a proposal (capped at 3 per summarization)
- list_proposals(): Query proposals with optional status filter
- resolve_proposal(): User approves/rejects a proposal
- generate_implementation_plan(): Generate step-by-step plan for approved proposals

Design principle: Agent proposes, user approves.
"""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Sequence, Literal

from pydantic import Field

from openhands.sdk import (
    Action,
    Observation,
    Tool,
    ToolDefinition,
    register_tool,
)
from openhands.sdk.tool import ToolExecutor

logger = logging.getLogger(__name__)


# =============================================================================
# Helper functions
# =============================================================================

def _run_async(coro):
    """Run an async coroutine in a sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
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
# Core async functions
# =============================================================================

async def _get_table(table_name: str):
    """Get DynamoDB table reference."""
    import boto3
    from config import AWS_REGION
    return boto3.resource("dynamodb", region_name=AWS_REGION).Table(table_name)


ProposalType = Literal[
    "new_directive",
    "rewrite_directive",
    "deprecate_directive",
    "new_tool",
    "system_observation",
]

ProposalStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "implemented",
]


async def create_proposal(
    type: ProposalType,
    title: str,
    rationale: str,
    content: str,
    target_id: Optional[str] = None,
    user_pk: str = "operator",
) -> Dict[str, Any]:
    """Create a new proposal.

    Args:
        type: Type of proposal (new_directive, rewrite_directive, etc.)
        title: Short title for the proposal
        rationale: Why this proposal is needed
        content: Full proposal content (directive text, tool spec, etc.)
        target_id: For rewrite/deprecate, the SK of the target directive
        user_pk: User partition key

    Returns:
        Dict with success status and proposal metadata
    """
    from config import IF_PROPOSALS_TABLE_NAME

    table = await _get_table(IF_PROPOSALS_TABLE_NAME)

    now = datetime.now(timezone.utc)
    sk = f"proposal#{now.isoformat()}"

    item = {
        "pk": user_pk,
        "sk": sk,
        "type": type,
        "status": "pending",
        "author": "agent",
        "title": title,
        "rationale": rationale,
        "content": content,
        "target_id": target_id if target_id else "null",
        "implementation_plan": "null",
        "created_at": now.isoformat(),
        "resolved_at": "null",
        "resolved_by": "null",
        "rejection_reason": "null",
    }

    try:
        table.put_item(Item=item)
        logger.info(f"[proposals] Created proposal {sk}: {type} - {title}")

        return {
            "success": True,
            "proposal_sk": sk,
            "type": type,
            "title": title,
            "status": "pending",
            "created_at": now.isoformat(),
        }
    except Exception as e:
        logger.error(f"[proposals] Failed to create proposal: {e}")
        return {"success": False, "error": str(e)}


async def list_proposals(
    status: Optional[ProposalStatus] = None,
    user_pk: str = "operator",
    limit: int = 20,
) -> Dict[str, Any]:
    """List proposals, optionally filtered by status.

    Args:
        status: Filter by status (pending, approved, rejected, implemented)
        user_pk: User partition key
        limit: Maximum number of proposals to return

    Returns:
        Dict with list of proposals sorted by created_at desc
    """
    from config import IF_PROPOSALS_TABLE_NAME
    from boto3.dynamodb.conditions import Attr

    table = await _get_table(IF_PROPOSALS_TABLE_NAME)

    try:
        # Query all proposals for user
        response = table.query(
            KeyConditionExpression="pk = :pk AND begins_with(sk, :prefix)",
            ExpressionAttributeValues={
                ":pk": user_pk,
                ":prefix": "proposal#",
            },
            Limit=limit,
            ScanIndexForward=False,  # Sort descending (newest first)
        )

        proposals = response.get("Items", [])

        # Filter by status if provided
        if status:
            proposals = [p for p in proposals if p.get("status") == status]

        # Clean up null strings for display
        for p in proposals:
            for key in ["target_id", "implementation_plan", "resolved_at", "resolved_by", "rejection_reason"]:
                if p.get(key) == "null":
                    p[key] = None

        return {
            "success": True,
            "count": len(proposals),
            "proposals": proposals,
        }
    except Exception as e:
        logger.error(f"[proposals] Failed to list proposals: {e}")
        return {"success": False, "error": str(e), "proposals": []}


async def resolve_proposal(
    sk: str,
    decision: Literal["approved", "rejected"],
    reason: Optional[str] = None,
    user_pk: str = "operator",
) -> Dict[str, Any]:
    """Resolve a proposal (approve or reject).

    Args:
        sk: Sort key of the proposal
        decision: "approved" or "rejected"
        reason: Optional reason for rejection
        user_pk: User partition key

    Returns:
        Dict with success status and updated proposal
    """
    from config import IF_PROPOSALS_TABLE_NAME

    table = await _get_table(IF_PROPOSALS_TABLE_NAME)

    now = datetime.now(timezone.utc)

    try:
        # Update the proposal
        update_expr = "SET #status = :status, resolved_at = :resolved_at, resolved_by = :resolved_by"
        expr_attr_names = {
            "#status": "status",
        }
        expr_attr_values = {
            ":status": decision,
            ":resolved_at": now.isoformat(),
            ":resolved_by": "user",
        }

        if decision == "rejected" and reason:
            update_expr += ", rejection_reason = :reason"
            expr_attr_values[":reason"] = reason
        elif decision == "rejected":
            update_expr += ", rejection_reason = :reason"
            expr_attr_values[":reason"] = reason or "No reason provided"

        response = table.update_item(
            Key={"pk": user_pk, "sk": sk},
            UpdateStatement=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
            ReturnValues="ALL_NEW",
        )

        updated = response.get("Attributes", {})
        logger.info(f"[proposals] Resolved proposal {sk}: {decision}")

        # If approved, trigger implementation plan generation
        if decision == "approved":
            # Queue async task to generate implementation plan
            asyncio.create_task(generate_implementation_plan(sk, user_pk))

        return {
            "success": True,
            "proposal_sk": sk,
            "decision": decision,
            "resolved_at": now.isoformat(),
        }
    except Exception as e:
        logger.error(f"[proposals] Failed to resolve proposal: {e}")
        return {"success": False, "error": str(e)}


async def generate_implementation_plan(
    proposal_sk: str,
    user_pk: str = "operator",
) -> Dict[str, Any]:
    """Generate an implementation plan for an approved proposal.

    Reads the proposal content and existing directives, then calls a heavy
    model to generate a step-by-step implementation plan.

    Args:
        proposal_sk: Sort key of the proposal
        user_pk: User partition key

    Returns:
        Dict with success status and implementation plan
    """
    from config import (
        IF_PROPOSALS_TABLE_NAME,
        IF_CORE_TABLE_NAME,
        OPENROUTER_API_KEY,
        DIRECTIVE_REWRITE_MODEL,
    )

    proposals_table = await _get_table(IF_PROPOSALS_TABLE_NAME)

    try:
        # Get the proposal
        proposal = proposals_table.get_item(Key={"pk": user_pk, "sk": proposal_sk})
        if "Item" not in proposal:
            return {"success": False, "error": "Proposal not found"}

        prop = proposal["Item"]

        if prop.get("status") != "approved":
            return {"success": False, "error": "Proposal must be approved first"}

        # Get existing directives for context
        core_table = await _get_table(IF_CORE_TABLE_NAME)
        directives_response = core_table.query(
            KeyConditionExpression="pk = :pk AND begins_with(sk, :prefix)",
            ExpressionAttributeValues={
                ":pk": "DIR",
                ":prefix": "",
            },
            Limit=50,
        )
        existing_directives = directives_response.get("Items", [])

        # Build prompt for implementation plan
        prompt = f"""Generate a step-by-step implementation plan for the following approved proposal.

PROPOSAL:
Type: {prop.get('type')}
Title: {prop.get('title')}
Rationale: {prop.get('rationale')}
Content: {prop.get('content')}
Target ID: {prop.get('target_id')}

EXISTING DIRECTIVES (for context):
{json.dumps([{"sk": d.get("sk"), "label": d.get("label")} for d in existing_directives[:20]], indent=2)}

Generate a practical, actionable implementation plan with clear steps.
Format as a numbered list with:
1. What needs to be done
2. Who/what should do it
3. Any dependencies or prerequisites
4. Verification steps

Keep it concise but complete. Maximum 10 steps.
"""

        # Call the model
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": DIRECTIVE_REWRITE_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()

        plan = result["choices"][0]["message"]["content"]

        # Update the proposal with the implementation plan
        proposals_table.update_item(
            Key={"pk": user_pk, "sk": proposal_sk},
            UpdateExpression="SET implementation_plan = :plan",
            ExpressionAttributeValues={":plan": plan},
        )

        logger.info(f"[proposals] Generated implementation plan for {proposal_sk}")

        return {
            "success": True,
            "proposal_sk": proposal_sk,
            "implementation_plan": plan,
        }

    except Exception as e:
        logger.error(f"[proposals] Failed to generate implementation plan: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# Tool Definitions
# =============================================================================

class CreateProposalAction(Action):
    type: ProposalType = Field(description="Type: new_directive, rewrite_directive, deprecate_directive, new_tool, system_observation")
    title: str = Field(description="Short title for the proposal")
    rationale: str = Field(description="Why this proposal is needed")
    content: str = Field(description="Full proposal content (directive text, tool spec, etc.)")
    target_id: Optional[str] = Field(default=None, description="For rewrite/deprecate, the SK of target directive")
    user_pk: str = Field(default="operator", description="User partition key")


class CreateProposalObservation(Observation):
    pass


class CreateProposalExecutor(ToolExecutor[CreateProposalAction, CreateProposalObservation]):
    def __call__(self, action: CreateProposalAction, conversation=None) -> CreateProposalObservation:
        result = _run_async(create_proposal(
            type=action.type,
            title=action.title,
            rationale=action.rationale,
            content=action.content,
            target_id=action.target_id,
            user_pk=action.user_pk,
        ))
        return CreateProposalObservation.from_text(_format_result(result))


class CreateProposalTool(ToolDefinition[CreateProposalAction, CreateProposalObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["CreateProposalTool"]:
        return [cls(
            description=(
                "Create a proposal for a new directive, tool, or system change. "
                "Proposals require user approval before implementation. "
                "Capped at 3 proposals per summarization run."
            ),
            action_type=CreateProposalAction,
            observation_type=CreateProposalObservation,
            executor=CreateProposalExecutor(),
        )]


class ListProposalsAction(Action):
    status: Optional[ProposalStatus] = Field(default=None, description="Filter by status: pending, approved, rejected, implemented")
    user_pk: str = Field(default="operator", description="User partition key")
    limit: int = Field(default=20, description="Maximum number of proposals to return")


class ListProposalsObservation(Observation):
    pass


class ListProposalsExecutor(ToolExecutor[ListProposalsAction, ListProposalsObservation]):
    def __call__(self, action: ListProposalsAction, conversation=None) -> ListProposalsObservation:
        result = _run_async(list_proposals(
            status=action.status,
            user_pk=action.user_pk,
            limit=action.limit,
        ))
        return ListProposalsObservation.from_text(_format_result(result))


class ListProposalsTool(ToolDefinition[ListProposalsAction, ListProposalsObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["ListProposalsTool"]:
        return [cls(
            description=(
                "List proposals, optionally filtered by status. "
                "Use to show pending proposals for user review."
            ),
            action_type=ListProposalsAction,
            observation_type=ListProposalsObservation,
            executor=ListProposalsExecutor(),
        )]


class ResolveProposalAction(Action):
    sk: str = Field(description="Sort key of the proposal (e.g., proposal#2026-03-14T10:00:00Z)")
    decision: Literal["approved", "rejected"] = Field(description="Decision: approved or rejected")
    reason: Optional[str] = Field(default=None, description="Reason for rejection (required if rejected)")
    user_pk: str = Field(default="operator", description="User partition key")


class ResolveProposalObservation(Observation):
    pass


class ResolveProposalExecutor(ToolExecutor[ResolveProposalAction, ResolveProposalObservation]):
    def __call__(self, action: ResolveProposalAction, conversation=None) -> ResolveProposalObservation:
        result = _run_async(resolve_proposal(
            sk=action.sk,
            decision=action.decision,
            reason=action.reason,
            user_pk=action.user_pk,
        ))
        return ResolveProposalObservation.from_text(_format_result(result))


class ResolveProposalTool(ToolDefinition[ResolveProposalAction, ResolveProposalObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["ResolveProposalTool"]:
        return [cls(
            description=(
                "Resolve a proposal by approving or rejecting it. "
                "If approved, an implementation plan will be automatically generated."
            ),
            action_type=ResolveProposalAction,
            observation_type=ResolveProposalObservation,
            executor=ResolveProposalExecutor(),
        )]


class GenerateImplementationPlanAction(Action):
    proposal_sk: str = Field(description="Sort key of the approved proposal")
    user_pk: str = Field(default="operator", description="User partition key")


class GenerateImplementationPlanObservation(Observation):
    pass


class GenerateImplementationPlanExecutor(ToolExecutor[GenerateImplementationPlanAction, GenerateImplementationPlanObservation]):
    def __call__(self, action: GenerateImplementationPlanAction, conversation=None) -> GenerateImplementationPlanObservation:
        result = _run_async(generate_implementation_plan(
            proposal_sk=action.proposal_sk,
            user_pk=action.user_pk,
        ))
        return GenerateImplementationPlanObservation.from_text(_format_result(result))


class GenerateImplementationPlanTool(ToolDefinition[GenerateImplementationPlanAction, GenerateImplementationPlanObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["GenerateImplementationPlanTool"]:
        return [cls(
            description=(
                "Generate an implementation plan for an approved proposal. "
                "Usually called automatically after approval, but can be called manually."
            ),
            action_type=GenerateImplementationPlanAction,
            observation_type=GenerateImplementationPlanObservation,
            executor=GenerateImplementationPlanExecutor(),
        )]


# =============================================================================
# Register all tools
# =============================================================================

register_tool("CreateProposalTool", CreateProposalTool)
register_tool("ListProposalsTool", ListProposalsTool)
register_tool("ResolveProposalTool", ResolveProposalTool)
register_tool("GenerateImplementationPlanTool", GenerateImplementationPlanTool)


# =============================================================================
# Getter function
# =============================================================================

def get_proposal_tools() -> List[Tool]:
    """Get all proposal tools for session initialization."""
    return [
        Tool(name="CreateProposalTool"),
        Tool(name="ListProposalsTool"),
        Tool(name="ResolveProposalTool"),
        Tool(name="GenerateImplementationPlanTool"),
    ]
