"""Granular finance tools for the agent.

Replaces the monolithic GetFinancialContextTool with targeted per-section
tools. Each read tool returns only the relevant slice of the finance snapshot.
Write tools create new versioned snapshots via the same copy→mutate→PUT
pattern used by the finance portal backend.

All tools use the same DynamoDB pointer chain:
  finance#current → ref_sk → actual snapshot
"""
from __future__ import annotations
import asyncio
import copy
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import boto3
from pydantic import Field

from config import IF_FINANCE_TABLE_NAME, IF_USER_PK, AWS_REGION
from openhands.sdk import Action, Observation, Tool, ToolDefinition, register_tool
from openhands.sdk.tool import ToolExecutor

logger = logging.getLogger(__name__)

_USER_PK = IF_USER_PK


# =============================================================================
# Core DynamoDB helpers
# =============================================================================

def _run_async(coro):
    """Run async coroutine in sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _fmt(result: Any) -> str:
    if isinstance(result, str):
        return result
    return json.dumps(result, indent=2, default=str)


async def _get_snapshot() -> Dict[str, Any]:
    """Fetch the current finance snapshot from DynamoDB.

    Returns:
        Full snapshot dict

    Raises:
        RuntimeError: If snapshot not found
    """
    table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(IF_FINANCE_TABLE_NAME)

    pointer = table.get_item(Key={"pk": _USER_PK, "sk": "finance#current"})
    if "Item" not in pointer:
        raise RuntimeError("Finance snapshot pointer not found. Run seed_finance.sh first.")

    ref_sk = pointer["Item"].get("ref_sk")
    if not ref_sk:
        raise RuntimeError("Finance pointer has no ref_sk.")

    item = table.get_item(Key={"pk": _USER_PK, "sk": ref_sk})
    if "Item" not in item:
        raise RuntimeError(f"Finance snapshot {ref_sk} not found.")

    return item["Item"]


async def _write_snapshot(snapshot: Dict[str, Any], change_entry: str = "") -> Dict[str, Any]:
    """Write a new versioned snapshot and update the pointer.

    Args:
        snapshot: The full snapshot dict to persist
        change_entry: Human-readable description of what changed

    Returns:
        The written snapshot with updated version metadata
    """
    table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(IF_FINANCE_TABLE_NAME)

    # Read current pointer to determine next version number
    pointer = table.get_item(Key={"pk": _USER_PK, "sk": "finance#current"})
    current_version = 1
    if "Item" in pointer:
        current_ref = pointer["Item"].get("ref_sk", "finance#v000")
        try:
            current_version = int(current_ref.split("#v")[-1]) + 1
        except (ValueError, IndexError):
            current_version = 1

    new_sk = f"finance#v{current_version:03d}"
    now = datetime.now(timezone.utc).isoformat()

    # Update metadata in snapshot
    new_snapshot = copy.deepcopy(snapshot)
    new_snapshot["pk"] = _USER_PK
    new_snapshot["sk"] = new_sk

    # Append change log entry
    if change_entry:
        change_log = new_snapshot.get("change_log", [])
        change_log.append(f"{now[:10]}: {change_entry}")
        new_snapshot["change_log"] = change_log

    new_snapshot["updated_at"] = now

    # Write new version
    table.put_item(Item=new_snapshot)

    # Update pointer
    table.put_item(Item={
        "pk": _USER_PK,
        "sk": "finance#current",
        "ref_sk": new_sk,
        "version": current_version,
        "updated_at": now,
    })

    logger.info(f"[finance_tools] Wrote snapshot {new_sk}")
    return new_snapshot


# =============================================================================
# Granular Read Functions
# =============================================================================

async def finance_get_profile() -> Dict[str, Any]:
    """Get operator profile: age, employment, income, tax brackets."""
    snap = await _get_snapshot()
    return snap.get("profile", {})


async def finance_get_goals() -> Dict[str, Any]:
    """Get all financial goals by time horizon."""
    snap = await _get_snapshot()
    return snap.get("goals", {"short_term": [], "medium_term": [], "long_term": []})


async def finance_get_risk_profile() -> Dict[str, Any]:
    """Get risk profile: tolerance, time horizon, philosophy, max drawdown."""
    snap = await _get_snapshot()
    return snap.get("risk_profile", {})


async def finance_get_net_worth() -> Dict[str, Any]:
    """Get net worth snapshot: total_assets, total_liabilities, net_worth, as_of."""
    snap = await _get_snapshot()
    return snap.get("net_worth_snapshot", {})


async def finance_get_accounts() -> Dict[str, Any]:
    """Get all accounts: chequing, savings, credit_cards, lines_of_credit, loans."""
    snap = await _get_snapshot()
    return snap.get("accounts", {})


async def finance_get_investments() -> Dict[str, Any]:
    """Get investment accounts with holdings, allocation, and global watchlist."""
    snap = await _get_snapshot()
    return {
        "investment_accounts": snap.get("investment_accounts", []),
        "watchlist": snap.get("watchlist", []),
    }


async def finance_get_cashflow() -> Dict[str, Any]:
    """Get monthly cashflow: income, fixed expenses, debt payments, savings, variable budget, computed totals."""
    snap = await _get_snapshot()
    return snap.get("monthly_cashflow", {})


async def finance_get_tax() -> Dict[str, Any]:
    """Get tax situation: brackets, RRSP room/contributions, TFSA room, filing status."""
    snap = await _get_snapshot()
    return snap.get("tax", {})


async def finance_get_insurance() -> List[Dict[str, Any]]:
    """Get all insurance policies."""
    snap = await _get_snapshot()
    return snap.get("insurance", [])


async def finance_get_agent_context() -> Dict[str, Any]:
    """Get agent context: known biases, recurring questions, notes."""
    snap = await _get_snapshot()
    return snap.get("agent_context", {})


# =============================================================================
# Granular Write Functions
# =============================================================================

async def finance_update_profile(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update profile fields (age, employment, income, tax brackets).

    Args:
        updates: Dict of profile fields to update

    Returns:
        Updated profile dict
    """
    snap = await _get_snapshot()
    new_snap = copy.deepcopy(snap)
    profile = new_snap.setdefault("profile", {})

    # Deep merge employment if provided
    if "employment" in updates and isinstance(updates["employment"], dict):
        profile.setdefault("employment", {}).update(updates.pop("employment"))

    profile.update(updates)
    await _write_snapshot(new_snap, f"Updated profile: {list(updates.keys())}")
    return profile


async def finance_update_goals(
    short_term: Optional[List[Dict]] = None,
    medium_term: Optional[List[Dict]] = None,
    long_term: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Replace one or more goal arrays.

    Pass only the arrays you want to update; omitted arrays are unchanged.

    Args:
        short_term: New short-term goals list (< 1 year)
        medium_term: New medium-term goals list (1-5 years)
        long_term: New long-term goals list (5+ years)

    Returns:
        Updated goals dict
    """
    snap = await _get_snapshot()
    new_snap = copy.deepcopy(snap)
    goals = new_snap.setdefault("goals", {})

    changed = []
    if short_term is not None:
        goals["short_term"] = short_term
        changed.append("short_term")
    if medium_term is not None:
        goals["medium_term"] = medium_term
        changed.append("medium_term")
    if long_term is not None:
        goals["long_term"] = long_term
        changed.append("long_term")

    if not changed:
        raise ValueError("At least one goal array must be provided.")

    await _write_snapshot(new_snap, f"Updated goals: {changed}")
    return goals


async def finance_update_risk_profile(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update risk profile fields.

    Allowed fields: tolerance, time_horizon_years, investment_philosophy,
    max_drawdown_comfort_pct, notes.

    Args:
        updates: Dict of risk profile fields to update

    Returns:
        Updated risk_profile dict
    """
    snap = await _get_snapshot()
    new_snap = copy.deepcopy(snap)
    new_snap.setdefault("risk_profile", {}).update(updates)
    await _write_snapshot(new_snap, f"Updated risk profile: {list(updates.keys())}")
    return new_snap["risk_profile"]


async def finance_update_net_worth(
    total_assets: Optional[float] = None,
    total_liabilities: Optional[float] = None,
    as_of: Optional[str] = None,
) -> Dict[str, Any]:
    """Update net worth snapshot.

    Args:
        total_assets: Total assets in dollars
        total_liabilities: Total liabilities in dollars
        as_of: Date of snapshot (YYYY-MM-DD)

    Returns:
        Updated net_worth_snapshot dict
    """
    if total_assets is None and total_liabilities is None:
        raise ValueError("At least one of total_assets or total_liabilities must be provided.")

    snap = await _get_snapshot()
    new_snap = copy.deepcopy(snap)
    nw = new_snap.setdefault("net_worth_snapshot", {})

    if total_assets is not None:
        nw["total_assets"] = total_assets
    if total_liabilities is not None:
        nw["total_liabilities"] = total_liabilities
    if as_of is not None:
        nw["as_of"] = as_of

    # Recompute net worth
    assets = nw.get("total_assets", 0) or 0
    liabilities = nw.get("total_liabilities", 0) or 0
    nw["net_worth"] = assets - liabilities

    await _write_snapshot(new_snap, f"Updated net worth: assets={total_assets}, liabilities={total_liabilities}")
    return nw


async def finance_update_account(
    account_type: str,
    account_id: str,
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    """Patch a specific account by type and id.

    Args:
        account_type: One of: chequing, savings, credit_cards, lines_of_credit, loans
        account_id: The account's id field
        updates: Fields to update on that account

    Returns:
        The updated account dict

    Raises:
        ValueError: If account type invalid or account not found
    """
    valid_types = {"chequing", "savings", "credit_cards", "lines_of_credit", "loans"}
    if account_type not in valid_types:
        raise ValueError(f"account_type must be one of {valid_types}")

    snap = await _get_snapshot()
    new_snap = copy.deepcopy(snap)
    accounts = new_snap.setdefault("accounts", {})
    account_list = accounts.setdefault(account_type, [])

    target_idx = next((i for i, a in enumerate(account_list) if str(a.get("id")) == str(account_id)), None)
    if target_idx is None:
        raise ValueError(f"Account {account_id} not found in {account_type}")

    account_list[target_idx].update(updates)

    # Recompute utilization for credit accounts
    if account_type == "credit_cards":
        acct = account_list[target_idx]
        balance = acct.get("balance_owing", 0) or 0
        limit = acct.get("credit_limit", 0) or 0
        if limit > 0:
            acct["utilization_pct"] = round((balance / limit) * 100, 1)

    await _write_snapshot(new_snap, f"Updated {account_type} account {account_id}: {list(updates.keys())}")
    return account_list[target_idx]


async def finance_add_holding(
    account_id: str,
    ticker: str,
    shares: float,
    avg_cost: float,
    current_price: Optional[float] = None,
    notes: str = "",
) -> Dict[str, Any]:
    """Add a new holding to an investment account.

    Args:
        account_id: Investment account id
        ticker: Ticker symbol (e.g. "AAPL", "VFV.TO")
        shares: Number of shares held
        avg_cost: Average cost per share
        current_price: Current market price per share (optional)
        notes: Optional notes

    Returns:
        The new holding dict

    Raises:
        ValueError: If account not found or ticker already exists
    """
    snap = await _get_snapshot()
    new_snap = copy.deepcopy(snap)
    accounts = new_snap.get("investment_accounts", [])

    acct_idx = next((i for i, a in enumerate(accounts) if str(a.get("id")) == str(account_id)), None)
    if acct_idx is None:
        raise ValueError(f"Investment account {account_id} not found")

    holdings = accounts[acct_idx].setdefault("holdings", [])
    if any(h.get("ticker", "").upper() == ticker.upper() for h in holdings):
        raise ValueError(f"Holding {ticker} already exists in account {account_id}. Use finance_update_holding to update it.")

    now = datetime.now(timezone.utc).isoformat()
    new_holding = {
        "ticker": ticker.upper(),
        "shares": shares,
        "avg_cost": avg_cost,
        "current_price": current_price,
        "last_price_update": now if current_price is not None else None,
        "notes": notes,
    }
    holdings.append(new_holding)

    await _write_snapshot(new_snap, f"Added holding {ticker} to account {account_id}")
    return new_holding


async def finance_update_holding(
    account_id: str,
    ticker: str,
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    """Update an existing holding in an investment account.

    Allowed fields: shares, avg_cost, current_price, notes.

    Args:
        account_id: Investment account id
        ticker: Ticker symbol
        updates: Fields to update

    Returns:
        The updated holding dict

    Raises:
        ValueError: If account or holding not found
    """
    snap = await _get_snapshot()
    new_snap = copy.deepcopy(snap)
    accounts = new_snap.get("investment_accounts", [])

    acct_idx = next((i for i, a in enumerate(accounts) if str(a.get("id")) == str(account_id)), None)
    if acct_idx is None:
        raise ValueError(f"Investment account {account_id} not found")

    holdings = accounts[acct_idx].get("holdings", [])
    holding_idx = next((i for i, h in enumerate(holdings) if h.get("ticker", "").upper() == ticker.upper()), None)
    if holding_idx is None:
        raise ValueError(f"Holding {ticker} not found in account {account_id}")

    holdings[holding_idx].update(updates)
    if "current_price" in updates:
        holdings[holding_idx]["last_price_update"] = datetime.now(timezone.utc).isoformat()

    await _write_snapshot(new_snap, f"Updated holding {ticker} in account {account_id}: {list(updates.keys())}")
    return holdings[holding_idx]


async def finance_update_watchlist(watchlist: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Replace the global watchlist.

    Args:
        watchlist: New watchlist array (list of {ticker, notes} dicts)

    Returns:
        Updated watchlist
    """
    snap = await _get_snapshot()
    new_snap = copy.deepcopy(snap)
    new_snap["watchlist"] = watchlist
    await _write_snapshot(new_snap, f"Updated watchlist ({len(watchlist)} items)")
    return watchlist


async def finance_update_cashflow(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update monthly cashflow sections.

    Allowed keys: net_monthly_income (number), fixed_expenses (array),
    debt_payments (array), savings_and_investments (array),
    variable_expense_budget (array).

    Totals are recomputed server-side after update.

    Args:
        updates: Dict of cashflow sections to replace

    Returns:
        Updated monthly_cashflow dict with recomputed totals
    """
    allowed = {"net_monthly_income", "fixed_expenses", "debt_payments",
               "savings_and_investments", "variable_expense_budget"}
    unknown = set(updates.keys()) - allowed
    if unknown:
        raise ValueError(f"Unknown cashflow fields: {unknown}")

    snap = await _get_snapshot()
    new_snap = copy.deepcopy(snap)
    cf = new_snap.setdefault("monthly_cashflow", {})
    cf.update(updates)

    # Recompute totals
    def sum_amounts(items):
        return sum(float(i.get("amount", 0) or 0) for i in (items or []))

    income = float(cf.get("net_monthly_income", 0) or 0)
    total_fixed = sum_amounts(cf.get("fixed_expenses", []))
    total_debt = sum_amounts(cf.get("debt_payments", []))
    total_savings = sum_amounts(cf.get("savings_and_investments", []))
    total_variable = sum_amounts(cf.get("variable_expense_budget", []))
    total_outflow = total_fixed + total_debt + total_savings + total_variable

    cf.update({
        "total_fixed": total_fixed,
        "total_debt_payments": total_debt,
        "total_savings_investments": total_savings,
        "total_variable_budget": total_variable,
        "total_outflow": total_outflow,
        "monthly_surplus": income - total_outflow,
        "as_of": datetime.now(timezone.utc).isoformat()[:10],
    })

    await _write_snapshot(new_snap, f"Updated cashflow: {list(updates.keys())}")
    return cf


async def finance_update_tax(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update tax situation fields.

    Args:
        updates: Dict of tax fields to update (rrsp_room, rrsp_ytd_contributions,
                 tfsa_room, tfsa_used_this_year, filing_status, etc.)

    Returns:
        Updated tax dict
    """
    snap = await _get_snapshot()
    new_snap = copy.deepcopy(snap)
    new_snap.setdefault("tax", {}).update(updates)
    await _write_snapshot(new_snap, f"Updated tax: {list(updates.keys())}")
    return new_snap["tax"]


async def finance_update_insurance(policies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Replace the insurance policies array.

    Args:
        policies: New insurance policies list

    Returns:
        Updated insurance list
    """
    snap = await _get_snapshot()
    new_snap = copy.deepcopy(snap)
    new_snap["insurance"] = policies
    await _write_snapshot(new_snap, f"Updated insurance ({len(policies)} policies)")
    return policies


# =============================================================================
# OpenHands Tool Wrappers — Reads
# =============================================================================

class FinanceGetProfileAction(Action):
    pass

class FinanceGetProfileObservation(Observation):
    pass

class FinanceGetProfileExecutor(ToolExecutor[FinanceGetProfileAction, FinanceGetProfileObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_get_profile())
        return FinanceGetProfileObservation.from_text(_fmt(result))

class FinanceGetProfileTool(ToolDefinition[FinanceGetProfileAction, FinanceGetProfileObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Get operator profile: age, employment (role, company, income, trajectory), "
                        "secondary income, tax brackets. Use instead of GetFinancialContextTool for profile queries.",
            action_type=FinanceGetProfileAction,
            observation_type=FinanceGetProfileObservation,
            executor=FinanceGetProfileExecutor(),
        )]


class FinanceGetGoalsAction(Action):
    pass

class FinanceGetGoalsObservation(Observation):
    pass

class FinanceGetGoalsExecutor(ToolExecutor[FinanceGetGoalsAction, FinanceGetGoalsObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_get_goals())
        return FinanceGetGoalsObservation.from_text(_fmt(result))

class FinanceGetGoalsTool(ToolDefinition[FinanceGetGoalsAction, FinanceGetGoalsObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Get all financial goals grouped by time horizon: short_term (<1yr), "
                        "medium_term (1-5yr), long_term (5yr+). Each goal has title, target_amount, "
                        "current_amount, deadline, priority, category.",
            action_type=FinanceGetGoalsAction,
            observation_type=FinanceGetGoalsObservation,
            executor=FinanceGetGoalsExecutor(),
        )]


class FinanceGetRiskProfileAction(Action):
    pass

class FinanceGetRiskProfileObservation(Observation):
    pass

class FinanceGetRiskProfileExecutor(ToolExecutor[FinanceGetRiskProfileAction, FinanceGetRiskProfileObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_get_risk_profile())
        return FinanceGetRiskProfileObservation.from_text(_fmt(result))

class FinanceGetRiskProfileTool(ToolDefinition[FinanceGetRiskProfileAction, FinanceGetRiskProfileObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Get risk profile: tolerance (conservative/moderate/aggressive), time_horizon_years, "
                        "investment_philosophy, max_drawdown_comfort_pct, notes.",
            action_type=FinanceGetRiskProfileAction,
            observation_type=FinanceGetRiskProfileObservation,
            executor=FinanceGetRiskProfileExecutor(),
        )]


class FinanceGetNetWorthAction(Action):
    pass

class FinanceGetNetWorthObservation(Observation):
    pass

class FinanceGetNetWorthExecutor(ToolExecutor[FinanceGetNetWorthAction, FinanceGetNetWorthObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_get_net_worth())
        return FinanceGetNetWorthObservation.from_text(_fmt(result))

class FinanceGetNetWorthTool(ToolDefinition[FinanceGetNetWorthAction, FinanceGetNetWorthObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Get net worth snapshot: total_assets, total_liabilities, net_worth, as_of date.",
            action_type=FinanceGetNetWorthAction,
            observation_type=FinanceGetNetWorthObservation,
            executor=FinanceGetNetWorthExecutor(),
        )]


class FinanceGetAccountsAction(Action):
    pass

class FinanceGetAccountsObservation(Observation):
    pass

class FinanceGetAccountsExecutor(ToolExecutor[FinanceGetAccountsAction, FinanceGetAccountsObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_get_accounts())
        return FinanceGetAccountsObservation.from_text(_fmt(result))

class FinanceGetAccountsTool(ToolDefinition[FinanceGetAccountsAction, FinanceGetAccountsObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Get all accounts: chequing, savings, credit_cards (with utilization), "
                        "lines_of_credit, loans. Use for debt/balance questions.",
            action_type=FinanceGetAccountsAction,
            observation_type=FinanceGetAccountsObservation,
            executor=FinanceGetAccountsExecutor(),
        )]


class FinanceGetInvestmentsAction(Action):
    pass

class FinanceGetInvestmentsObservation(Observation):
    pass

class FinanceGetInvestmentsExecutor(ToolExecutor[FinanceGetInvestmentsAction, FinanceGetInvestmentsObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_get_investments())
        return FinanceGetInvestmentsObservation.from_text(_fmt(result))

class FinanceGetInvestmentsTool(ToolDefinition[FinanceGetInvestmentsAction, FinanceGetInvestmentsObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Get investment accounts (RRSP, TFSA, non-reg) with holdings, target allocation, "
                        "and global watchlist.",
            action_type=FinanceGetInvestmentsAction,
            observation_type=FinanceGetInvestmentsObservation,
            executor=FinanceGetInvestmentsExecutor(),
        )]


class FinanceGetCashflowAction(Action):
    pass

class FinanceGetCashflowObservation(Observation):
    pass

class FinanceGetCashflowExecutor(ToolExecutor[FinanceGetCashflowAction, FinanceGetCashflowObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_get_cashflow())
        return FinanceGetCashflowObservation.from_text(_fmt(result))

class FinanceGetCashflowTool(ToolDefinition[FinanceGetCashflowAction, FinanceGetCashflowObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Get monthly cashflow: income, fixed expenses, debt payments, savings/investments, "
                        "variable budget, and computed totals (surplus, outflow).",
            action_type=FinanceGetCashflowAction,
            observation_type=FinanceGetCashflowObservation,
            executor=FinanceGetCashflowExecutor(),
        )]


class FinanceGetTaxAction(Action):
    pass

class FinanceGetTaxObservation(Observation):
    pass

class FinanceGetTaxExecutor(ToolExecutor[FinanceGetTaxAction, FinanceGetTaxObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_get_tax())
        return FinanceGetTaxObservation.from_text(_fmt(result))

class FinanceGetTaxTool(ToolDefinition[FinanceGetTaxAction, FinanceGetTaxObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Get tax situation: federal/provincial brackets, RRSP room and YTD contributions, "
                        "TFSA room and used amount, filing status, capital gains.",
            action_type=FinanceGetTaxAction,
            observation_type=FinanceGetTaxObservation,
            executor=FinanceGetTaxExecutor(),
        )]


class FinanceGetInsuranceAction(Action):
    pass

class FinanceGetInsuranceObservation(Observation):
    pass

class FinanceGetInsuranceExecutor(ToolExecutor[FinanceGetInsuranceAction, FinanceGetInsuranceObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_get_insurance())
        return FinanceGetInsuranceObservation.from_text(_fmt(result))

class FinanceGetInsuranceTool(ToolDefinition[FinanceGetInsuranceAction, FinanceGetInsuranceObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Get all insurance policies: type, provider, coverage amount, premium, "
                        "deductible, renewal date, beneficiaries.",
            action_type=FinanceGetInsuranceAction,
            observation_type=FinanceGetInsuranceObservation,
            executor=FinanceGetInsuranceExecutor(),
        )]


class FinanceGetAgentContextAction(Action):
    pass

class FinanceGetAgentContextObservation(Observation):
    pass

class FinanceGetAgentContextExecutor(ToolExecutor[FinanceGetAgentContextAction, FinanceGetAgentContextObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_get_agent_context())
        return FinanceGetAgentContextObservation.from_text(_fmt(result))

class FinanceGetAgentContextTool(ToolDefinition[FinanceGetAgentContextAction, FinanceGetAgentContextObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Get agent context about this operator's financial behaviour: known biases, "
                        "recurring questions, and advisory notes.",
            action_type=FinanceGetAgentContextAction,
            observation_type=FinanceGetAgentContextObservation,
            executor=FinanceGetAgentContextExecutor(),
        )]


# =============================================================================
# OpenHands Tool Wrappers — Writes
# =============================================================================

class FinanceUpdateProfileAction(Action):
    updates: Dict[str, Any] = Field(
        description="Profile fields to update. Supports: age, net_monthly_income, "
                    "tax_bracket_federal, tax_bracket_provincial, "
                    "employment (dict with role/company/tenure_years/gross_annual_income/trajectory/near_term_change_risk), "
                    "secondary_income (list)."
    )

class FinanceUpdateProfileObservation(Observation):
    pass

class FinanceUpdateProfileExecutor(ToolExecutor[FinanceUpdateProfileAction, FinanceUpdateProfileObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_update_profile(action.updates))
        return FinanceUpdateProfileObservation.from_text(_fmt(result))

class FinanceUpdateProfileTool(ToolDefinition[FinanceUpdateProfileAction, FinanceUpdateProfileObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Update operator profile fields: age, income, employment details, tax brackets.",
            action_type=FinanceUpdateProfileAction,
            observation_type=FinanceUpdateProfileObservation,
            executor=FinanceUpdateProfileExecutor(),
        )]


class FinanceUpdateGoalsAction(Action):
    short_term: Optional[List[Dict[str, Any]]] = Field(default=None, description="Replace short-term goals array (<1yr)")
    medium_term: Optional[List[Dict[str, Any]]] = Field(default=None, description="Replace medium-term goals array (1-5yr)")
    long_term: Optional[List[Dict[str, Any]]] = Field(default=None, description="Replace long-term goals array (5yr+)")

class FinanceUpdateGoalsObservation(Observation):
    pass

class FinanceUpdateGoalsExecutor(ToolExecutor[FinanceUpdateGoalsAction, FinanceUpdateGoalsObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_update_goals(action.short_term, action.medium_term, action.long_term))
        return FinanceUpdateGoalsObservation.from_text(_fmt(result))

class FinanceUpdateGoalsTool(ToolDefinition[FinanceUpdateGoalsAction, FinanceUpdateGoalsObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description=(
                "Create, update, or delete financial goals. Fetch current goals first, "
                "modify the relevant array, then submit. Each goal: {id, title, description, "
                "target_amount, current_amount, deadline, priority, category, notes}."
            ),
            action_type=FinanceUpdateGoalsAction,
            observation_type=FinanceUpdateGoalsObservation,
            executor=FinanceUpdateGoalsExecutor(),
        )]


class FinanceUpdateRiskProfileAction(Action):
    updates: Dict[str, Any] = Field(
        description="Risk profile fields: tolerance (conservative/moderate/aggressive), "
                    "time_horizon_years, investment_philosophy, max_drawdown_comfort_pct, notes."
    )

class FinanceUpdateRiskProfileObservation(Observation):
    pass

class FinanceUpdateRiskProfileExecutor(ToolExecutor[FinanceUpdateRiskProfileAction, FinanceUpdateRiskProfileObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_update_risk_profile(action.updates))
        return FinanceUpdateRiskProfileObservation.from_text(_fmt(result))

class FinanceUpdateRiskProfileTool(ToolDefinition[FinanceUpdateRiskProfileAction, FinanceUpdateRiskProfileObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Update risk profile: tolerance, time horizon, investment philosophy, max drawdown comfort.",
            action_type=FinanceUpdateRiskProfileAction,
            observation_type=FinanceUpdateRiskProfileObservation,
            executor=FinanceUpdateRiskProfileExecutor(),
        )]


class FinanceUpdateNetWorthAction(Action):
    total_assets: Optional[float] = Field(default=None, description="Total assets in dollars")
    total_liabilities: Optional[float] = Field(default=None, description="Total liabilities in dollars")
    as_of: Optional[str] = Field(default=None, description="Snapshot date (YYYY-MM-DD)")

class FinanceUpdateNetWorthObservation(Observation):
    pass

class FinanceUpdateNetWorthExecutor(ToolExecutor[FinanceUpdateNetWorthAction, FinanceUpdateNetWorthObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_update_net_worth(action.total_assets, action.total_liabilities, action.as_of))
        return FinanceUpdateNetWorthObservation.from_text(_fmt(result))

class FinanceUpdateNetWorthTool(ToolDefinition[FinanceUpdateNetWorthAction, FinanceUpdateNetWorthObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Update net worth snapshot. Net worth is auto-computed as assets - liabilities.",
            action_type=FinanceUpdateNetWorthAction,
            observation_type=FinanceUpdateNetWorthObservation,
            executor=FinanceUpdateNetWorthExecutor(),
        )]


class FinanceUpdateAccountAction(Action):
    account_type: str = Field(description="Account type: chequing, savings, credit_cards, lines_of_credit, loans")
    account_id: str = Field(description="Account id field value")
    updates: Dict[str, Any] = Field(description="Fields to update on the account")

class FinanceUpdateAccountObservation(Observation):
    pass

class FinanceUpdateAccountExecutor(ToolExecutor[FinanceUpdateAccountAction, FinanceUpdateAccountObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_update_account(action.account_type, action.account_id, action.updates))
        return FinanceUpdateAccountObservation.from_text(_fmt(result))

class FinanceUpdateAccountTool(ToolDefinition[FinanceUpdateAccountAction, FinanceUpdateAccountObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description=(
                "Patch a specific account by type and id. Fetch accounts first to get ids. "
                "Credit card utilization is auto-recomputed. "
                "Types: chequing, savings, credit_cards, lines_of_credit, loans."
            ),
            action_type=FinanceUpdateAccountAction,
            observation_type=FinanceUpdateAccountObservation,
            executor=FinanceUpdateAccountExecutor(),
        )]


class FinanceAddHoldingAction(Action):
    account_id: str = Field(description="Investment account id")
    ticker: str = Field(description="Ticker symbol (e.g. AAPL, VFV.TO)")
    shares: float = Field(description="Number of shares held")
    avg_cost: float = Field(description="Average cost per share")
    current_price: Optional[float] = Field(default=None, description="Current market price per share")
    notes: str = Field(default="", description="Optional notes")

class FinanceAddHoldingObservation(Observation):
    pass

class FinanceAddHoldingExecutor(ToolExecutor[FinanceAddHoldingAction, FinanceAddHoldingObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_add_holding(
            action.account_id, action.ticker, action.shares,
            action.avg_cost, action.current_price, action.notes
        ))
        return FinanceAddHoldingObservation.from_text(_fmt(result))

class FinanceAddHoldingTool(ToolDefinition[FinanceAddHoldingAction, FinanceAddHoldingObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Add a new investment holding to an account. Fails if ticker already exists — use finance_update_holding instead.",
            action_type=FinanceAddHoldingAction,
            observation_type=FinanceAddHoldingObservation,
            executor=FinanceAddHoldingExecutor(),
        )]


class FinanceUpdateHoldingAction(Action):
    account_id: str = Field(description="Investment account id")
    ticker: str = Field(description="Ticker symbol to update")
    updates: Dict[str, Any] = Field(description="Fields: shares, avg_cost, current_price, notes")

class FinanceUpdateHoldingObservation(Observation):
    pass

class FinanceUpdateHoldingExecutor(ToolExecutor[FinanceUpdateHoldingAction, FinanceUpdateHoldingObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_update_holding(action.account_id, action.ticker, action.updates))
        return FinanceUpdateHoldingObservation.from_text(_fmt(result))

class FinanceUpdateHoldingTool(ToolDefinition[FinanceUpdateHoldingAction, FinanceUpdateHoldingObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Update an existing holding: shares, avg_cost, current_price, notes. last_price_update is set automatically when current_price changes.",
            action_type=FinanceUpdateHoldingAction,
            observation_type=FinanceUpdateHoldingObservation,
            executor=FinanceUpdateHoldingExecutor(),
        )]


class FinanceUpdateWatchlistAction(Action):
    watchlist: List[Dict[str, Any]] = Field(description="New watchlist array. Each item: {ticker, notes}")

class FinanceUpdateWatchlistObservation(Observation):
    pass

class FinanceUpdateWatchlistExecutor(ToolExecutor[FinanceUpdateWatchlistAction, FinanceUpdateWatchlistObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_update_watchlist(action.watchlist))
        return FinanceUpdateWatchlistObservation.from_text(_fmt(result))

class FinanceUpdateWatchlistTool(ToolDefinition[FinanceUpdateWatchlistAction, FinanceUpdateWatchlistObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Replace the global investment watchlist. Fetch current first, add/remove tickers, submit full list.",
            action_type=FinanceUpdateWatchlistAction,
            observation_type=FinanceUpdateWatchlistObservation,
            executor=FinanceUpdateWatchlistExecutor(),
        )]


class FinanceUpdateCashflowAction(Action):
    updates: Dict[str, Any] = Field(
        description="Cashflow sections to update. Keys: net_monthly_income (number), "
                    "fixed_expenses (array), debt_payments (array), "
                    "savings_and_investments (array), variable_expense_budget (array). "
                    "Omit sections you don't want to change. Totals are recomputed automatically."
    )

class FinanceUpdateCashflowObservation(Observation):
    pass

class FinanceUpdateCashflowExecutor(ToolExecutor[FinanceUpdateCashflowAction, FinanceUpdateCashflowObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_update_cashflow(action.updates))
        return FinanceUpdateCashflowObservation.from_text(_fmt(result))

class FinanceUpdateCashflowTool(ToolDefinition[FinanceUpdateCashflowAction, FinanceUpdateCashflowObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description=(
                "Update monthly cashflow sections. Surplus and totals are recomputed automatically. "
                "Fetch current cashflow first, modify the relevant sections, submit only changed keys."
            ),
            action_type=FinanceUpdateCashflowAction,
            observation_type=FinanceUpdateCashflowObservation,
            executor=FinanceUpdateCashflowExecutor(),
        )]


class FinanceUpdateTaxAction(Action):
    updates: Dict[str, Any] = Field(
        description="Tax fields to update: rrsp_room, rrsp_ytd_contributions, "
                    "tfsa_room, tfsa_used_this_year, filing_status, "
                    "capital_gains_ytd, tax_refund_owing, or others."
    )

class FinanceUpdateTaxObservation(Observation):
    pass

class FinanceUpdateTaxExecutor(ToolExecutor[FinanceUpdateTaxAction, FinanceUpdateTaxObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_update_tax(action.updates))
        return FinanceUpdateTaxObservation.from_text(_fmt(result))

class FinanceUpdateTaxTool(ToolDefinition[FinanceUpdateTaxAction, FinanceUpdateTaxObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Update tax situation: RRSP room/contributions, TFSA room, filing status, capital gains.",
            action_type=FinanceUpdateTaxAction,
            observation_type=FinanceUpdateTaxObservation,
            executor=FinanceUpdateTaxExecutor(),
        )]


class FinanceUpdateInsuranceAction(Action):
    policies: List[Dict[str, Any]] = Field(
        description="Full insurance policies list. Each policy: "
                    "{type, provider, coverage_amount, premium, deductible, renewal_date, beneficiaries, notes}."
    )

class FinanceUpdateInsuranceObservation(Observation):
    pass

class FinanceUpdateInsuranceExecutor(ToolExecutor[FinanceUpdateInsuranceAction, FinanceUpdateInsuranceObservation]):
    def __call__(self, action, conversation=None):
        result = _run_async(finance_update_insurance(action.policies))
        return FinanceUpdateInsuranceObservation.from_text(_fmt(result))

class FinanceUpdateInsuranceTool(ToolDefinition[FinanceUpdateInsuranceAction, FinanceUpdateInsuranceObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="Replace insurance policies list. Fetch current first, add/modify/remove entries, submit full list.",
            action_type=FinanceUpdateInsuranceAction,
            observation_type=FinanceUpdateInsuranceObservation,
            executor=FinanceUpdateInsuranceExecutor(),
        )]


# =============================================================================
# Register all tools
# =============================================================================

# Reads
register_tool("FinanceGetProfileTool", FinanceGetProfileTool)
register_tool("FinanceGetGoalsTool", FinanceGetGoalsTool)
register_tool("FinanceGetRiskProfileTool", FinanceGetRiskProfileTool)
register_tool("FinanceGetNetWorthTool", FinanceGetNetWorthTool)
register_tool("FinanceGetAccountsTool", FinanceGetAccountsTool)
register_tool("FinanceGetInvestmentsTool", FinanceGetInvestmentsTool)
register_tool("FinanceGetCashflowTool", FinanceGetCashflowTool)
register_tool("FinanceGetTaxTool", FinanceGetTaxTool)
register_tool("FinanceGetInsuranceTool", FinanceGetInsuranceTool)
register_tool("FinanceGetAgentContextTool", FinanceGetAgentContextTool)

# Writes
register_tool("FinanceUpdateProfileTool", FinanceUpdateProfileTool)
register_tool("FinanceUpdateGoalsTool", FinanceUpdateGoalsTool)
register_tool("FinanceUpdateRiskProfileTool", FinanceUpdateRiskProfileTool)
register_tool("FinanceUpdateNetWorthTool", FinanceUpdateNetWorthTool)
register_tool("FinanceUpdateAccountTool", FinanceUpdateAccountTool)
register_tool("FinanceAddHoldingTool", FinanceAddHoldingTool)
register_tool("FinanceUpdateHoldingTool", FinanceUpdateHoldingTool)
register_tool("FinanceUpdateWatchlistTool", FinanceUpdateWatchlistTool)
register_tool("FinanceUpdateCashflowTool", FinanceUpdateCashflowTool)
register_tool("FinanceUpdateTaxTool", FinanceUpdateTaxTool)
register_tool("FinanceUpdateInsuranceTool", FinanceUpdateInsuranceTool)


# =============================================================================
# Getter
# =============================================================================

def get_finance_tools() -> List[Tool]:
    """Get all finance tools for session initialization."""
    return [
        # Reads
        Tool(name="FinanceGetProfileTool"),
        Tool(name="FinanceGetGoalsTool"),
        Tool(name="FinanceGetRiskProfileTool"),
        Tool(name="FinanceGetNetWorthTool"),
        Tool(name="FinanceGetAccountsTool"),
        Tool(name="FinanceGetInvestmentsTool"),
        Tool(name="FinanceGetCashflowTool"),
        Tool(name="FinanceGetTaxTool"),
        Tool(name="FinanceGetInsuranceTool"),
        Tool(name="FinanceGetAgentContextTool"),
        # Writes
        Tool(name="FinanceUpdateProfileTool"),
        Tool(name="FinanceUpdateGoalsTool"),
        Tool(name="FinanceUpdateRiskProfileTool"),
        Tool(name="FinanceUpdateNetWorthTool"),
        Tool(name="FinanceUpdateAccountTool"),
        Tool(name="FinanceAddHoldingTool"),
        Tool(name="FinanceUpdateHoldingTool"),
        Tool(name="FinanceUpdateWatchlistTool"),
        Tool(name="FinanceUpdateCashflowTool"),
        Tool(name="FinanceUpdateTaxTool"),
        Tool(name="FinanceUpdateInsuranceTool"),
    ]
