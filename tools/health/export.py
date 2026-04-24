"""Excel export builder for training programs.

Uses openpyxl to produce a multi-sheet .xlsx workbook from a program dict.
"""
from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


# Shared styles
_HEADER_FONT = Font(bold=True, size=11)
_SECTION_FONT = Font(bold=True, size=11, color="1F3864")
_HEADER_FILL = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
_SECTION_FILL = PatternFill(start_color="E7ECF5", end_color="E7ECF5", fill_type="solid")
_WRAP = Alignment(wrap_text=True, vertical="top")

# openpyxl cell content limit
_CELL_CHAR_LIMIT = 32000


def _num(v: Any) -> Any:
    """Coerce a value to an Excel-compatible scalar."""
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (dict, list)):
        return str(v)
    return v


def _extract_phase_name(phase: Any) -> str:
    """Extract phase name from either a string or a phase dict."""
    if isinstance(phase, dict):
        return phase.get("name", "")
    return phase if isinstance(phase, str) else str(phase)


def _truncate(val: Any, limit: int = _CELL_CHAR_LIMIT) -> Any:
    if isinstance(val, str) and len(val) > limit:
        return val[: limit - 30] + "... [truncated]"
    return val


def _write_sheet(ws, headers: list[str], rows: list[list[Any]], col_widths: dict[int, int] | None = None):
    """Write a header row + data rows to a worksheet."""
    # Header
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _WRAP

    # Data
    for row_idx, row_data in enumerate(rows, 2):
        for col_idx, value in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col_idx, value=_truncate(_num(value)))

    # Column widths
    max_col = len(headers)
    for col_idx in range(1, max_col + 1):
        if col_widths and col_idx in col_widths:
            width = col_widths[col_idx]
        else:
            # Auto-width from header + data
            max_len = len(str(headers[col_idx - 1]))
            for row_idx in range(2, len(rows) + 2):
                val = ws.cell(row=row_idx, column=col_idx).value
                if val is not None:
                    max_len = max(max_len, len(str(val)))
            width = min(max_len + 2, 50)
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Freeze top row
    ws.freeze_panes = "A2"


def _write_section_label(ws, row_idx: int, label: str, width: int = 1):
    """Write a bold, filled section label row starting at column A."""
    cell = ws.cell(row=row_idx, column=1, value=label)
    cell.font = _SECTION_FONT
    cell.fill = _SECTION_FILL
    if width > 1:
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=width)


def _autosize_columns(ws, max_cols: int, min_width: int = 10, max_width: int = 60):
    """Size columns based on longest value in any row."""
    for col_idx in range(1, max_cols + 1):
        max_len = min_width
        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx, values_only=True):
            val = row[0]
            if val is None:
                continue
            s = str(val)
            longest_line = max((len(line) for line in s.splitlines()), default=len(s))
            if longest_line > max_len:
                max_len = longest_line
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, max_width)


def _fmt(val: Any) -> Any:
    """Format a value for a key-value cell: join lists, coerce numbers, truncate."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "Yes" if val else "No"
    if isinstance(val, list):
        return "; ".join(str(_num(v)) for v in val)
    return _truncate(_num(val))


def build_program_xlsx(program: dict, out_path: str, analysis: dict | None = None) -> str:
    """Build a multi-sheet Excel workbook from a program dict.

    Args:
        program: Full program dict from ProgramStore.
        out_path: Absolute path to write the .xlsx file.
        analysis: Optional analysis bundle with keys:
            - "weekly": output of analytics.weekly_analysis()
            - "correlation": cached correlation report dict (or None if not generated)
            - "program_evaluation": cached program evaluation dict (or None)
            - "lift_profiles": normalized lift profiles list (from summarize_lift_profiles)
            When provided, appends Lift Profiles, Weekly Analysis, Per-Lift Metrics,
            ROI Correlation, and Program Evaluation sheets.

    Returns:
        Absolute path to the written file.
    """
    wb = Workbook()

    meta = program.get("meta", {})
    phases = program.get("phases", [])
    sessions = program.get("sessions", [])
    competitions = program.get("competitions", [])
    maxes = program.get("current_maxes", {})

    # ---- Sheet 1: Meta ----
    ws_meta = wb.active
    ws_meta.title = "Meta"
    meta_rows = [
        ["Program Name", meta.get("program_name", "")],
        ["Creator", meta.get("creator", "")],
        ["Program Start", meta.get("program_start", "")],
        ["Competition Date", meta.get("comp_date", "")],
        ["Target Total (kg)", meta.get("target_total_kg", "")],
        ["Weight Class (kg)", meta.get("weight_class_kg", "")],
        ["Equipment", meta.get("equipment", "")],
        ["Last Updated", meta.get("updated_at", "")],
    ]
    _write_sheet(ws_meta, ["Field", "Value"], meta_rows)

    # ---- Sheet 2: Current Maxes ----
    ws_maxes = wb.create_sheet("Current Maxes")
    maxes_rows = []
    for lift, val in maxes.items():
        maxes_rows.append([lift.replace("_", " ").title(), val])
    _write_sheet(ws_maxes, ["Lift", "Current Max (kg)"], maxes_rows)

    # ---- Sheet 3: Phases ----
    ws_phases = wb.create_sheet("Phases")
    phase_rows = []
    for phase in phases:
        phase_rows.append([
            phase.get("name", ""),
            phase.get("start_week", ""),
            phase.get("end_week", ""),
            phase.get("intent", ""),
            phase.get("target_rpe_min", ""),
            phase.get("target_rpe_max", ""),
            phase.get("days_per_week", ""),
            phase.get("notes", ""),
        ])
    _write_sheet(
        ws_phases,
        ["Phase", "Start Week", "End Week", "Intent", "Target RPE Min", "Target RPE Max", "Days/Week", "Notes"],
        phase_rows,
    )

    # ---- Sheet 4: Sessions ----
    ws_sessions = wb.create_sheet("Sessions")
    session_rows = []
    for s in sessions:
        session_rows.append([
            s.get("id", ""),
            s.get("date", ""),
            s.get("week", ""),
            s.get("week_number", ""),
            _extract_phase_name(s.get("phase", "")),
            s.get("day", ""),
            s.get("status", ""),
            s.get("completed", ""),
            s.get("body_weight_kg", ""),
            s.get("session_rpe", ""),
            s.get("session_notes", ""),
        ])
    _write_sheet(
        ws_sessions,
        ["ID", "Date", "Week", "Week #", "Phase", "Day", "Status", "Completed", "Body Weight (kg)", "Session RPE", "Notes"],
        session_rows,
    )

    # ---- Sheet 5: Exercises (flattened) ----
    ws_exercises = wb.create_sheet("Exercises")
    ex_rows = []
    for s in sessions:
        s_date = s.get("date", "")
        s_week = s.get("week", "")
        s_phase = _extract_phase_name(s.get("phase", ""))
        for ex in s.get("exercises", []):
            def _to_float(v):
                if v is None or v == "":
                    return 0.0
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return 0.0
            sets_f = _to_float(ex.get("sets"))
            reps_f = _to_float(ex.get("reps"))
            kg_f = _to_float(ex.get("kg"))
            volume = sets_f * reps_f * kg_f
            ex_rows.append([
                s_date,
                s_week,
                s_phase,
                ex.get("name", ""),
                ex.get("sets", ""),
                ex.get("reps", ""),
                ex.get("kg", ""),
                ex.get("failed", False),
                ex.get("rpe", ""),
                round(volume, 1),
            ])
    _write_sheet(
        ws_exercises,
        ["Date", "Week", "Phase", "Exercise", "Sets", "Reps", "Weight (kg)", "Failed", "RPE", "Volume"],
        ex_rows,
    )

    # ---- Sheet 6: Competitions ----
    ws_comps = wb.create_sheet("Competitions")
    comp_rows = []
    for c in competitions:
        attempts = c.get("attempts", {})
        comp_rows.append([
            c.get("name", ""),
            c.get("date", ""),
            c.get("federation", ""),
            c.get("weight_class_kg", ""),
            c.get("equipment", ""),
            attempts.get("squat", {}).get("best", ""),
            attempts.get("bench", {}).get("best", ""),
            attempts.get("deadlift", {}).get("best", ""),
            attempts.get("total", ""),
            c.get("dots", ""),
            c.get("place", ""),
        ])
    _write_sheet(
        ws_comps,
        ["Meet", "Date", "Federation", "Weight Class", "Equipment",
         "Squat", "Bench", "Deadlift", "Total", "DOTS", "Place"],
        comp_rows,
    )

    if analysis is not None:
        _write_lift_profiles_sheet(wb, analysis.get("lift_profiles") or [])
        _write_per_lift_metrics_sheet(wb, analysis.get("weekly") or {})
        _write_correlation_sheet(wb, analysis.get("correlation"))
        _write_program_evaluation_sheet(wb, analysis.get("program_evaluation"))

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    wb.save(out_path)
    return out_path


# ---------------------------------------------------------------------------
# Analysis sheet builders
# ---------------------------------------------------------------------------

_MISSING_NOTE = "Not yet generated — open the Analysis page and let the report render before exporting."


def _write_lift_profiles_sheet(wb: Workbook, lift_profiles: list[dict]) -> None:
    ws = wb.create_sheet("Lift Profiles")
    headers = ["Lift", "Style Notes", "Sticking Points", "Primary Muscle", "Volume Tolerance"]
    rows = []
    for p in lift_profiles:
        rows.append([
            (p.get("lift") or "").title(),
            p.get("style_notes") or "",
            p.get("sticking_points") or "",
            p.get("primary_muscle") or "",
            p.get("volume_tolerance") or "",
        ])
    if not rows:
        rows.append(["—", "No lift profiles recorded on this program.", "", "", ""])
    _write_sheet(ws, headers, rows, col_widths={2: 40, 3: 40})


def _write_weekly_analysis_sheet(wb: Workbook, weekly: dict) -> None:
    ws = wb.create_sheet("Weekly Analysis")
    if not weekly:
        _write_sheet(ws, ["Field", "Value"], [["Status", _MISSING_NOTE]])
        return

    compliance = weekly.get("compliance") or {}
    deload = weekly.get("deload_info") or {}
    current_maxes = weekly.get("current_maxes") or {}
    readiness = weekly.get("readiness_score") or {}
    flags = weekly.get("flags") or []

    rows = [
        ["Current Week", weekly.get("week", "")],
        ["Block", weekly.get("block", "")],
        ["Sessions Analyzed", weekly.get("sessions_analyzed", "")],
        ["Compliance — Planned", compliance.get("planned", "")],
        ["Compliance — Completed", compliance.get("completed", "")],
        ["Compliance — %", compliance.get("pct", "")],
        ["Fatigue Index", weekly.get("fatigue_index", "")],
        ["Estimated DOTS", weekly.get("estimated_dots", "")],
        ["Current Max — Squat (kg)", current_maxes.get("squat", "")],
        ["Current Max — Bench (kg)", current_maxes.get("bench", "")],
        ["Current Max — Deadlift (kg)", current_maxes.get("deadlift", "")],
        ["Current Maxes Method", current_maxes.get("method", "")],
        ["Deload Weeks", _fmt(deload.get("deload_weeks"))],
        ["Break Weeks", _fmt(deload.get("break_weeks"))],
        ["Effective Training Weeks", deload.get("effective_training_weeks", "")],
        ["Readiness Score", readiness.get("score", "") if isinstance(readiness, dict) else ""],
        ["Readiness Zone", readiness.get("zone", "") if isinstance(readiness, dict) else ""],
        ["Readiness - Fatigue", readiness.get("components", {}).get("fatigue_norm", "") if isinstance(readiness, dict) else ""],
        ["Readiness - RPE Drift", readiness.get("components", {}).get("rpe_drift", "") if isinstance(readiness, dict) else ""],
        ["Readiness - Wellness", readiness.get("components", {}).get("wellness", "") if isinstance(readiness, dict) else ""],
        ["Readiness - Trend", readiness.get("components", {}).get("performance_trend", "") if isinstance(readiness, dict) else ""],
        ["Readiness - BW Deviation", readiness.get("components", {}).get("bw_deviation", "") if isinstance(readiness, dict) else ""],
        ["Flags", _fmt(flags)],
    ]
    _write_sheet(ws, ["Field", "Value"], rows, col_widths={1: 32, 2: 60})


def _write_per_lift_metrics_sheet(wb: Workbook, weekly: dict) -> None:
    ws = wb.create_sheet("Per-Lift Metrics")

    lifts = (weekly or {}).get("lifts") or {}
    projections = (weekly or {}).get("projections") or []

    headers = [
        "Lift", "Progression (kg/wk)", "Fit Quality", "Kendall τ", "Volume Change %",
        "Intensity Change %", "Failed Sets", "RPE Trend",
    ]
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _WRAP

    row_idx = 2
    if lifts:
        for name, data in lifts.items():
            values = [
                name,
                _fmt(data.get("progression_rate_kg_per_week")),
                _fmt(data.get("fit_quality", data.get("r_squared", data.get("r2")))),
                _fmt(data.get("kendall_tau")),
                _fmt(data.get("volume_change_pct")),
                _fmt(data.get("intensity_change_pct")),
                _fmt(data.get("failed_sets")),
                _fmt(data.get("rpe_trend")),
            ]
            for col_idx, v in enumerate(values, 1):
                ws.cell(row=row_idx, column=col_idx, value=v)
            row_idx += 1
    else:
        ws.cell(row=row_idx, column=1, value="No tracked lifts in the window.")
        row_idx += 1

    # Projections sub-section
    row_idx += 1
    _write_section_label(ws, row_idx, "Projections", width=len(headers))
    row_idx += 1
    proj_headers = ["Comp", "Weeks Out", "Projected Total (kg)", "Confidence", "Method"]
    for col_idx, h in enumerate(proj_headers, 1):
        cell = ws.cell(row=row_idx, column=col_idx, value=h)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _WRAP
    row_idx += 1

    if projections:
        for p in projections:
            values = [
                p.get("comp_name") or "(unscheduled)",
                _fmt(p.get("weeks_to_comp")),
                _fmt(p.get("total")),
                _fmt(p.get("confidence")),
                _fmt(p.get("method")),
            ]
            for col_idx, v in enumerate(values, 1):
                ws.cell(row=row_idx, column=col_idx, value=v)
            row_idx += 1
    else:
        reason = (weekly or {}).get("projection_reason") or "No upcoming competitions to project."
        ws.cell(row=row_idx, column=1, value=reason)

    _autosize_columns(ws, max_cols=len(headers))
    ws.freeze_panes = "A2"


def _write_correlation_sheet(wb: Workbook, correlation: dict | None) -> None:
    ws = wb.create_sheet("ROI Correlation")

    if not correlation:
        _write_sheet(ws, ["Field", "Value"], [["Status", _MISSING_NOTE]])
        return

    # Header block
    header_rows = [
        ["Summary", _fmt(correlation.get("summary"))],
        ["Generated At", _fmt(correlation.get("generated_at"))],
        ["Window Start", _fmt(correlation.get("window_start"))],
        ["Weeks", _fmt(correlation.get("weeks"))],
        ["Cached", _fmt(correlation.get("cached"))],
    ]
    for row_idx, (k, v) in enumerate(header_rows, 1):
        c1 = ws.cell(row=row_idx, column=1, value=k)
        c1.font = _HEADER_FONT
        c1.fill = _HEADER_FILL
        c1.alignment = _WRAP
        c2 = ws.cell(row=row_idx, column=2, value=v)
        c2.alignment = _WRAP

    next_row = len(header_rows) + 2

    if correlation.get("insufficient_data"):
        ws.cell(row=next_row, column=1, value="Insufficient data").font = _SECTION_FONT
        ws.cell(row=next_row, column=2, value=_fmt(correlation.get("insufficient_data_reason")))
        _autosize_columns(ws, max_cols=6)
        return

    _write_section_label(ws, next_row, "Findings", width=6)
    next_row += 1

    finding_headers = ["Exercise", "Lift", "Direction", "Strength", "Reasoning", "Caveat"]
    for col_idx, h in enumerate(finding_headers, 1):
        cell = ws.cell(row=next_row, column=col_idx, value=h)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _WRAP
    next_row += 1

    findings = correlation.get("findings") or []
    if findings:
        for f in findings:
            values = [
                _fmt(f.get("exercise")),
                _fmt(f.get("lift")),
                _fmt(f.get("correlation_direction")),
                _fmt(f.get("strength")),
                _fmt(f.get("reasoning")),
                _fmt(f.get("caveat")),
            ]
            for col_idx, v in enumerate(values, 1):
                c = ws.cell(row=next_row, column=col_idx, value=v)
                c.alignment = _WRAP
            next_row += 1
    else:
        ws.cell(row=next_row, column=1, value="No findings reported.")

    _autosize_columns(ws, max_cols=6)


def _write_program_evaluation_sheet(wb: Workbook, evaluation: dict | None) -> None:
    ws = wb.create_sheet("Program Evaluation")

    if not evaluation:
        _write_sheet(ws, ["Field", "Value"], [["Status", _MISSING_NOTE]])
        return

    header_rows = [
        ["Stance", _fmt(evaluation.get("stance"))],
        ["Summary", _fmt(evaluation.get("summary"))],
        ["Conclusion", _fmt(evaluation.get("conclusion"))],
        ["Generated At", _fmt(evaluation.get("generated_at"))],
        ["Window Start", _fmt(evaluation.get("window_start"))],
        ["Weeks", _fmt(evaluation.get("weeks"))],
        ["Cached", _fmt(evaluation.get("cached"))],
    ]
    for row_idx, (k, v) in enumerate(header_rows, 1):
        c1 = ws.cell(row=row_idx, column=1, value=k)
        c1.font = _HEADER_FONT
        c1.fill = _HEADER_FILL
        c1.alignment = _WRAP
        c2 = ws.cell(row=row_idx, column=2, value=v)
        c2.alignment = _WRAP

    next_row = len(header_rows) + 2

    if evaluation.get("insufficient_data"):
        ws.cell(row=next_row, column=1, value="Insufficient data").font = _SECTION_FONT
        ws.cell(row=next_row, column=2, value=_fmt(evaluation.get("insufficient_data_reason")))
        _autosize_columns(ws, max_cols=4)
        return

    # String-list sections
    for label, key in (("What's Working", "what_is_working"),
                       ("What's Not Working", "what_is_not_working"),
                       ("Monitoring Focus", "monitoring_focus")):
        _write_section_label(ws, next_row, label, width=4)
        next_row += 1
        items = evaluation.get(key) or []
        if items:
            for item in items:
                c = ws.cell(row=next_row, column=1, value=_truncate(str(item)))
                c.alignment = _WRAP
                ws.merge_cells(start_row=next_row, start_column=1, end_row=next_row, end_column=4)
                next_row += 1
        else:
            ws.cell(row=next_row, column=1, value="(none)")
            next_row += 1
        next_row += 1

    # Competition Alignment
    _write_section_label(ws, next_row, "Competition Alignment", width=4)
    next_row += 1
    ca_headers = ["Competition", "Role", "Alignment", "Reason"]
    for col_idx, h in enumerate(ca_headers, 1):
        cell = ws.cell(row=next_row, column=col_idx, value=h)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
    next_row += 1
    alignment_items = evaluation.get("competition_alignment") or []
    if alignment_items:
        for item in alignment_items:
            values = [
                _fmt(item.get("competition")),
                _fmt(item.get("role")),
                _fmt(item.get("alignment")),
                _fmt(item.get("reason")),
            ]
            for col_idx, v in enumerate(values, 1):
                c = ws.cell(row=next_row, column=col_idx, value=v)
                c.alignment = _WRAP
            next_row += 1
    else:
        ws.cell(row=next_row, column=1, value="(none)")
        next_row += 1
    next_row += 1

    # Small Changes
    _write_section_label(ws, next_row, "Small Changes", width=4)
    next_row += 1
    sc_headers = ["Change", "Why", "Risk", "Priority"]
    for col_idx, h in enumerate(sc_headers, 1):
        cell = ws.cell(row=next_row, column=col_idx, value=h)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
    next_row += 1
    changes = evaluation.get("small_changes") or []
    if changes:
        for item in changes:
            values = [
                _fmt(item.get("change")),
                _fmt(item.get("why")),
                _fmt(item.get("risk")),
                _fmt(item.get("priority")),
            ]
            for col_idx, v in enumerate(values, 1):
                c = ws.cell(row=next_row, column=col_idx, value=v)
                c.alignment = _WRAP
            next_row += 1
    else:
        ws.cell(row=next_row, column=1, value="(none)")

    _autosize_columns(ws, max_cols=4, max_width=70)
