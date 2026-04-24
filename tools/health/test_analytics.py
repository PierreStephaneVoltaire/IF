from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analytics  # noqa: E402


TODAY = date(2026, 4, 24)


class FrozenDate(date):
    @classmethod
    def today(cls) -> "FrozenDate":
        return cls(TODAY.year, TODAY.month, TODAY.day)


@pytest.fixture(autouse=True)
def freeze_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(analytics, "date", FrozenDate)


def make_exercise(name: str, kg: float, reps: int, sets: int = 1) -> dict:
    return {
        "name": name,
        "kg": kg,
        "reps": reps,
        "sets": sets,
    }


def make_session(
    days_ago: int,
    exercises: list[dict],
    *,
    session_rpe: float | None = None,
    week_number: int | None = None,
    body_weight_kg: float | None = None,
    wellness: dict | None = None,
    status: str = "completed",
    completed: bool = True,
) -> dict:
    d = TODAY - timedelta(days=days_ago)
    session = {
        "date": d.isoformat(),
        "week_number": week_number if week_number is not None else max(1, days_ago // 7 + 1),
        "completed": completed,
        "status": status,
        "session_rpe": session_rpe,
        "exercises": exercises,
    }
    if body_weight_kg is not None:
        session["body_weight_kg"] = body_weight_kg
    if wellness is not None:
        session["wellness"] = wellness
    return session


def make_wellness(sleep: int, soreness: int, mood: int, stress: int, energy: int) -> dict:
    return {
        "sleep": sleep,
        "soreness": soreness,
        "mood": mood,
        "stress": stress,
        "energy": energy,
        "recorded_at": TODAY.isoformat(),
    }


def make_sbd_session(
    days_ago: int,
    squat_kg: float,
    bench_kg: float,
    deadlift_kg: float,
    *,
    session_rpe: float,
    week_number: int | None = None,
    completed: bool = True,
) -> dict:
    return make_session(
        days_ago,
        [
            make_exercise("Squat", squat_kg, 1),
            make_exercise("Bench Press", bench_kg, 1),
            make_exercise("Deadlift", deadlift_kg, 1),
        ],
        session_rpe=session_rpe,
        week_number=week_number,
        completed=completed,
    )


def test_fatigue_physics_is_nonlinear() -> None:
    profile = {"axial": 1.0, "neural": 1.0, "peripheral": 1.0, "systemic": 1.0}

    neural_90 = analytics._per_set_fatigue(180, 1, profile, 200)["neural"]
    neural_95 = analytics._per_set_fatigue(190, 1, profile, 200)["neural"]
    axial_70x3 = analytics._per_set_fatigue(140, 3, profile, 200)["axial"]
    axial_90x3 = analytics._per_set_fatigue(180, 3, profile, 200)["axial"]
    systemic_70 = analytics._per_set_fatigue(140, 1, profile, 200)["systemic"]
    systemic_90 = analytics._per_set_fatigue(180, 1, profile, 200)["systemic"]

    assert neural_95 > neural_90
    assert axial_90x3 > axial_70x3
    assert systemic_90 > systemic_70


@pytest.mark.parametrize(
    ("avg_rpe", "expected"),
    [
        (7.5, 0.0),
        (8.0, 0.2),
        (8.5, 0.4),
        (9.0, 0.6),
        (9.5, 0.8),
        (10.0, 1.0),
    ],
)
def test_fatigue_index_rpe_stress_mapping(avg_rpe: float, expected: float) -> None:
    sessions = [
        make_session(1, [make_exercise("Squat", 100, 1)], session_rpe=avg_rpe),
        make_session(0, [make_exercise("Squat", 100, 1)], session_rpe=avg_rpe),
    ]

    result = analytics.fatigue_index(sessions, days=14)

    assert result["components"]["rpe_stress"] == pytest.approx(expected, abs=1e-3)
    assert result["score"] == pytest.approx(expected * 0.25, abs=1e-3)


def test_progression_rate_returns_fit_metrics() -> None:
    sessions = [
        make_session(21, [make_exercise("Squat", 100, 1)], session_rpe=10, week_number=1),
        make_session(14, [make_exercise("Squat", 110, 1)], session_rpe=10, week_number=2),
        make_session(7, [make_exercise("Squat", 120, 1)], session_rpe=10, week_number=3),
    ]

    result = analytics.progression_rate(sessions, "Squat", "2026-03-01")

    assert result["slope_kg_per_week"] == pytest.approx(10.0, abs=1e-6)
    assert result["kendall_tau"] == pytest.approx(1.0, abs=1e-6)
    assert result["fit_quality"] == pytest.approx(1.0, abs=1e-6)
    assert result["r2"] == pytest.approx(1.0, abs=1e-6)
    assert result["r_squared"] == pytest.approx(1.0, abs=1e-6)


def test_rpe_drift_returns_fit_metrics() -> None:
    sessions = [
        make_session(21, [make_exercise("Squat", 100, 1)], session_rpe=7, week_number=1),
        make_session(14, [make_exercise("Squat", 100, 1)], session_rpe=8, week_number=2),
        make_session(7, [make_exercise("Squat", 100, 1)], session_rpe=9, week_number=3),
    ]

    result = analytics.rpe_drift(sessions, "Squat", "2026-03-01")

    assert result["slope"] == pytest.approx(1.0, abs=1e-6)
    assert result["kendall_tau"] == pytest.approx(1.0, abs=1e-6)
    assert result["fit_quality"] == pytest.approx(1.0, abs=1e-6)
    assert result["r2"] == pytest.approx(1.0, abs=1e-6)
    assert result["r_squared"] == pytest.approx(1.0, abs=1e-6)


def test_compute_inol_uses_per_lift_thresholds_and_smoothing() -> None:
    sessions = [
        make_session(
            0,
            [
                make_exercise("Squat", 120, 10, 10),
                make_exercise("Bench Press", 120, 10, 10),
                make_exercise("Deadlift", 80, 5, 5),
            ],
        )
    ]
    lift_profiles = [
        {
            "lift": "squat",
            "stimulus_coefficient": 1.0,
            "inol_low_threshold": 0.1,
            "inol_high_threshold": 0.2,
        }
    ]

    result = analytics.compute_inol(
        sessions,
        program_start=TODAY.isoformat(),
        current_maxes={"squat": 200, "bench": 200, "deadlift": 200},
        lift_profiles=lift_profiles,
    )

    assert result["avg_inol"]["squat"] == pytest.approx(2.50, abs=0.02)
    assert result["avg_inol"]["bench"] == pytest.approx(2.50, abs=0.02)
    assert result["avg_inol"]["deadlift"] == pytest.approx(0.42, abs=0.02)
    assert result["thresholds"]["squat"] == {"low": 0.1, "high": 0.2}
    assert result["thresholds"]["bench"] == {"low": 2.0, "high": 5.0}
    assert result["thresholds"]["deadlift"] == {"low": 1.0, "high": 2.5}
    assert "overreaching_risk_squat" in result["flags"]
    assert "low_stimulus_deadlift" in result["flags"]
    assert "overreaching_risk_bench" not in result["flags"]
    assert "low_stimulus_bench" not in result["flags"]


def test_compute_acwr_daily_ewma_and_labels() -> None:
    sessions: list[dict] = []
    for day_index in range(35):
        days_ago = 34 - day_index
        kg = 50 if day_index < 28 else 300
        sessions.append(
            make_session(
                days_ago,
                [make_exercise("Squat", kg, 1)],
                week_number=day_index // 7 + 1,
            )
        )

    glossary = [
        {
            "name": "Squat",
            "fatigue_profile": {
                "axial": 1.0,
                "neural": 1.0,
                "peripheral": 1.0,
                "systemic": 1.0,
            },
        }
    ]

    result = analytics.compute_acwr(
        sessions,
        glossary=glossary,
        program_start=(TODAY - timedelta(days=34)).isoformat(),
        current_maxes={"squat": 300},
        phases=[
            {
                "name": "Overreach",
                "intent": "planned overreach block",
                "start_week": 1,
                "end_week": 8,
                "target_rpe_max": 9,
            }
        ],
        current_week=5,
        ref_date=TODAY,
    )

    assert result["composite_zone"] == "load_spike"
    assert result["composite_label"] == "Load spike (expected during planned overreach)"
    assert result["dimensions"]["axial"]["zone"] == "load_spike"
    assert result["dimensions"]["axial"]["label"] == "Load spike (expected during planned overreach)"
    assert result["dimensions"]["neural"]["label"].endswith("(expected during planned overreach)")
    assert math.isfinite(result["composite"])


def test_weekly_analysis_respects_requested_window() -> None:
    sessions = [
        make_session(
            83 - (idx * 7),
            [
                make_exercise("Squat", 100, 1),
                make_exercise("Bench Press", 80, 1),
                make_exercise("Deadlift", 120, 1),
            ],
            week_number=idx + 1,
        )
        for idx in range(12)
    ]
    program = {
        "meta": {
            "program_start": (TODAY - timedelta(days=83)).isoformat(),
        },
        "phases": [],
        "competitions": [],
    }
    glossary = [
        {
            "name": "Squat",
            "fatigue_profile": {
                "axial": 1.0,
                "neural": 1.0,
                "peripheral": 1.0,
                "systemic": 1.0,
            },
        },
        {
            "name": "Bench Press",
            "fatigue_profile": {
                "axial": 1.0,
                "neural": 1.0,
                "peripheral": 1.0,
                "systemic": 1.0,
            },
        },
        {
            "name": "Deadlift",
            "fatigue_profile": {
                "axial": 1.0,
                "neural": 1.0,
                "peripheral": 1.0,
                "systemic": 1.0,
            },
        },
    ]

    result_4 = analytics.weekly_analysis(program, sessions, weeks=4, block="current", glossary=glossary)
    result_8 = analytics.weekly_analysis(program, sessions, weeks=8, block="current", glossary=glossary)
    result_12 = analytics.weekly_analysis(program, sessions, weeks=12, block="current", glossary=glossary)

    assert result_4["sessions_analyzed"] == 4
    assert result_4["compliance"]["planned"] == 4
    assert result_4["compliance"]["completed"] == 4

    assert result_8["sessions_analyzed"] == 8
    assert result_8["compliance"]["planned"] == 8
    assert result_8["compliance"]["completed"] == 8

    assert result_12["sessions_analyzed"] == 12
    assert result_12["compliance"]["planned"] == 12
    assert result_12["compliance"]["completed"] == 12


def test_compute_acwr_requires_25_calendar_days() -> None:
    sessions = [
        make_session(
            days_ago,
            [make_exercise("Squat", 100, 1)],
        )
        for days_ago in range(23, -1, -1)
    ]

    result = analytics.compute_acwr(
        sessions,
        glossary=[{"name": "Squat", "fatigue_profile": {"axial": 1.0, "neural": 1.0, "peripheral": 1.0, "systemic": 1.0}}],
        program_start=(TODAY - timedelta(days=23)).isoformat(),
        current_maxes={"squat": 200},
        ref_date=TODAY,
    )

    assert result["status"] == "insufficient_data"
    assert "25 calendar days" in result["reason"]


def test_compute_acwr_accepts_25_calendar_days() -> None:
    sessions = [
        make_session(
            days_ago,
            [make_exercise("Squat", 100, 1)],
        )
        for days_ago in range(24, -1, -1)
    ]

    result = analytics.compute_acwr(
        sessions,
        glossary=[{"name": "Squat", "fatigue_profile": {"axial": 1.0, "neural": 1.0, "peripheral": 1.0, "systemic": 1.0}}],
        program_start=(TODAY - timedelta(days=24)).isoformat(),
        current_maxes={"squat": 200},
        ref_date=TODAY,
    )

    assert "status" not in result
    assert result["composite"] is not None
    assert math.isfinite(result["composite"])


def test_compute_banister_ffm_constant_load_stays_balanced() -> None:
    sessions = [
        make_sbd_session(
            days_ago,
            100,
            80,
            120,
            session_rpe=7,
            week_number=days_ago // 7 + 1,
        )
        for days_ago in range(19, -1, -1)
    ]

    result = analytics.compute_banister_ffm(
        sessions,
        glossary=[{"name": "Squat", "fatigue_profile": {"axial": 1.0, "neural": 1.0, "peripheral": 1.0, "systemic": 1.0}}],
        program_start=(TODAY - timedelta(days=19)).isoformat(),
        current_maxes={"squat": 200, "bench": 160, "deadlift": 240},
        ref_date=TODAY,
    )

    assert result["tsb_today"] == pytest.approx(0.0, abs=1e-6)
    assert result["tsb_label"] == "Building"
    assert len(result["series"]) == 20
    assert result["series"][0]["ctl"] == pytest.approx(result["series"][-1]["ctl"], abs=1e-6)
    assert result["series"][0]["atl"] == pytest.approx(result["series"][-1]["atl"], abs=1e-6)


def test_compute_monotony_strain_flags_high_monotony_and_strain_spike() -> None:
    sessions = []
    for week_idx in range(5):
        kg = 100 if week_idx < 4 else 200
        for day_offset in range(7):
            days_ago = 34 - (week_idx * 7 + day_offset)
            sessions.append(
                make_session(
                    days_ago,
                    [make_exercise("Squat", kg, 1)],
                    session_rpe=7,
                    week_number=week_idx + 1,
                )
            )

    result = analytics.compute_monotony_strain(
        sessions,
        glossary=[{"name": "Squat", "fatigue_profile": {"axial": 1.0, "neural": 1.0, "peripheral": 1.0, "systemic": 1.0}}],
        program_start=(TODAY - timedelta(days=34)).isoformat(),
        current_maxes={"squat": 200},
        ref_date=TODAY,
    )

    assert len(result["weekly"]) >= 5
    assert result["weekly"][0]["monotony"] > 2.0
    assert "high_monotony" in result["weekly"][0]["flags"]
    assert "strain_spike" in result["weekly"][-1]["flags"]


def test_compute_decoupling_flags_fatigue_dominant_streak() -> None:
    sessions = []
    week_payloads = [
        (100, 80, 120, 6),
        (102.5, 82.5, 122.5, 6),
        (105, 85, 125, 6),
        (100, 80, 120, 10),
        (95, 75, 115, 10),
        (90, 70, 110, 10),
    ]

    for week_idx, (squat, bench, deadlift, rpe) in enumerate(week_payloads):
        base_day = 41 - week_idx * 7
        sessions.append(
            make_sbd_session(
                base_day,
                squat,
                bench,
                deadlift,
                session_rpe=rpe,
                week_number=week_idx + 1,
            )
        )
        sessions.append(
            make_sbd_session(
                base_day - 2,
                squat,
                bench,
                deadlift,
                session_rpe=rpe,
                week_number=week_idx + 1,
            )
        )

    result = analytics.compute_decoupling(
        sessions,
        glossary=[{"name": "Squat", "fatigue_profile": {"axial": 1.0, "neural": 1.0, "peripheral": 1.0, "systemic": 1.0}}],
        program_start=(TODAY - timedelta(days=41)).isoformat(),
        current_maxes={"squat": 200, "bench": 160, "deadlift": 240},
        ref_date=TODAY,
    )

    assert result["current"] is not None
    assert result["current"]["decoupling"] < 0
    assert "decoupling_fatigue_dominant" in result["flags"]
    assert len(result["series"]) >= 3


def test_compute_taper_quality_gates_and_scores_inside_window() -> None:
    sessions = []
    program_start = (TODAY - timedelta(days=55)).isoformat()
    comp_date = (TODAY + timedelta(days=14)).isoformat()

    for week_idx in range(8):
        days_from_start = week_idx * 7
        if week_idx < 4:
            payloads = [
                (180, 135, 225, 9),
                (175, 132.5, 220, 9),
            ]
        else:
            payloads = [
                (170, 127.5, 212.5, 7),
            ]
        for offset, (squat, bench, deadlift, rpe) in enumerate(payloads):
            days_ago = 55 - days_from_start - (offset * 2)
            sessions.append(
                make_sbd_session(
                    days_ago,
                    squat,
                    bench,
                    deadlift,
                    session_rpe=rpe,
                    week_number=week_idx + 1,
                )
            )

    program = {
        "meta": {
            "program_start": program_start,
        },
        "phases": [
            {
                "name": "Taper",
                "intent": "taper and sharpen",
                "start_week": 5,
                "end_week": 8,
            }
        ],
        "competitions": [
            {
                "name": "Meet",
                "date": comp_date,
                "status": "confirmed",
                "weight_class_kg": 93,
            }
        ],
    }

    too_far_program = {
        **program,
        "competitions": [
            {
                "name": "Meet",
                "date": (TODAY + timedelta(days=28)).isoformat(),
                "status": "confirmed",
                "weight_class_kg": 93,
            }
        ],
    }

    gated = analytics.compute_taper_quality(
        too_far_program,
        sessions,
        glossary=[{"name": "Squat", "fatigue_profile": {"axial": 1.0, "neural": 1.0, "peripheral": 1.0, "systemic": 1.0}}],
        program_start=program_start,
        current_maxes={"squat": 200, "bench": 160, "deadlift": 240},
        ref_date=TODAY,
    )
    assert gated is None

    result = analytics.compute_taper_quality(
        program,
        sessions,
        glossary=[{"name": "Squat", "fatigue_profile": {"axial": 1.0, "neural": 1.0, "peripheral": 1.0, "systemic": 1.0}}],
        program_start=program_start,
        current_maxes={"squat": 200, "bench": 160, "deadlift": 240},
        ref_date=TODAY,
    )

    assert result["weeks_to_comp"] == pytest.approx(2.0, abs=1e-6)
    assert result["score"] >= 60
    assert result["label"] in {"good", "excellent"}
    assert set(result["components"].keys()) == {"volume_reduction", "intensity_maintained", "fatigue_trend", "tsb"}


def test_weekly_analysis_includes_peaking_layer_payloads() -> None:
    sessions = []
    for week_idx in range(8):
        base_day = 55 - (week_idx * 7)
        if week_idx < 4:
            payloads = [
                (180, 135, 225, 9),
                (175, 132.5, 220, 9),
            ]
        else:
            payloads = [
                (170, 127.5, 212.5, 7),
            ]
        for offset, (squat, bench, deadlift, rpe) in enumerate(payloads):
            sessions.append(
                make_sbd_session(
                    base_day - (offset * 2),
                    squat,
                    bench,
                    deadlift,
                    session_rpe=rpe,
                    week_number=week_idx + 1,
                )
            )

    program = {
        "meta": {
            "program_start": (TODAY - timedelta(days=55)).isoformat(),
        },
        "phases": [
            {
                "name": "Taper",
                "intent": "taper and sharpen",
                "start_week": 5,
                "end_week": 8,
            }
        ],
        "competitions": [
            {
                "name": "Meet",
                "date": (TODAY + timedelta(days=14)).isoformat(),
                "status": "confirmed",
                "weight_class_kg": 93,
            }
        ],
    }
    glossary = [
        {
            "name": "Squat",
            "fatigue_profile": {
                "axial": 1.0,
                "neural": 1.0,
                "peripheral": 1.0,
                "systemic": 1.0,
            },
        }
    ]

    result = analytics.weekly_analysis(program, sessions, weeks=8, block="current", glossary=glossary)

    assert "banister" in result
    assert result["banister"] is not None
    assert result["banister"]["tsb_label"]
    assert "series" in result["banister"]
    assert "monotony_strain" in result
    assert len(result["monotony_strain"]["weekly"]) > 0
    assert "decoupling" in result
    assert result["decoupling"] is not None
    assert result["decoupling"]["current"] is not None
    assert "taper_quality" in result
    assert result["taper_quality"] is not None
    assert result["taper_quality"]["score"] >= 60


def test_readiness_wellness_penalty_and_fallback() -> None:
    sessions = [
        make_session(0, [], wellness=make_wellness(5, 5, 5, 5, 5)),
        make_session(3, [], wellness=make_wellness(1, 1, 1, 1, 1)),
    ]

    result = analytics._readiness_wellness_component(sessions, reference_date=TODAY)
    assert result["mean"] == pytest.approx(3.0, abs=1e-6)
    assert result["penalty"] == pytest.approx(0.4, abs=1e-6)

    fallback = analytics._readiness_wellness_component([make_session(0, [])], reference_date=TODAY)
    assert fallback["mean"] is None
    assert fallback["penalty"] == pytest.approx(0.5, abs=1e-6)


def test_readiness_performance_trend_penalizes_negative_slope_only() -> None:
    current_maxes = {"squat": 100, "bench": 100, "deadlift": 100}
    negative_sessions = [
        make_session(14, [make_exercise("Squat", 100, 1)], session_rpe=10, week_number=1),
        make_session(7, [make_exercise("Squat", 95, 1)], session_rpe=10, week_number=2),
        make_session(0, [make_exercise("Squat", 90, 1)], session_rpe=10, week_number=3),
    ]
    negative = analytics._readiness_performance_trend_component(
        negative_sessions,
        current_maxes=current_maxes,
        reference_date=TODAY,
    )
    assert negative["slope_kg_per_week"] == pytest.approx(-5.0, abs=1e-6)
    assert negative["penalty"] == pytest.approx(1.0, abs=1e-6)

    positive_sessions = [
        make_session(14, [make_exercise("Squat", 90, 1)], session_rpe=10, week_number=1),
        make_session(7, [make_exercise("Squat", 95, 1)], session_rpe=10, week_number=2),
        make_session(0, [make_exercise("Squat", 100, 1)], session_rpe=10, week_number=3),
    ]
    positive = analytics._readiness_performance_trend_component(
        positive_sessions,
        current_maxes=current_maxes,
        reference_date=TODAY,
    )
    assert positive["slope_kg_per_week"] == pytest.approx(5.0, abs=1e-6)
    assert positive["penalty"] == pytest.approx(0.0, abs=1e-6)


def test_readiness_bodyweight_component_is_cut_aware_and_falls_back_without_series() -> None:
    program = {
        "meta": {
            "program_start": (TODAY - timedelta(days=28)).isoformat(),
            "comp_date": (TODAY + timedelta(days=28)).isoformat(),
            "weight_class_kg": 86,
            "current_body_weight_kg": 90,
        },
        "competitions": [
            {
                "date": (TODAY + timedelta(days=28)).isoformat(),
                "status": "confirmed",
                "weight_class_kg": 86,
            }
        ],
    }
    cut_sessions = [
        make_session(14, [], body_weight_kg=92),
        make_session(7, [], body_weight_kg=91),
        make_session(0, [], body_weight_kg=90),
    ]

    cut_result = analytics._readiness_bodyweight_component(cut_sessions, program, reference_date=TODAY)
    assert cut_result["mode"] == "cut"
    assert cut_result["expected_weekly_change_kg"] == pytest.approx(-1.0, abs=1e-6)
    assert cut_result["actual_weekly_change_kg"] == pytest.approx(-1.0, abs=1e-6)
    assert cut_result["penalty"] == pytest.approx(0.0, abs=1e-6)

    fallback = analytics._readiness_bodyweight_component([make_session(0, [], body_weight_kg=None)], program, reference_date=TODAY)
    assert fallback["mode"] == "fallback"
    assert fallback["penalty"] == pytest.approx(0.5, abs=1e-6)


def test_compute_readiness_score_uses_new_components(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(analytics, "fatigue_index", lambda *args, **kwargs: {"score": 0.2})
    monkeypatch.setattr(analytics, "_readiness_wellness_component", lambda *args, **kwargs: {"penalty": 0.4})
    monkeypatch.setattr(analytics, "_readiness_performance_trend_component", lambda *args, **kwargs: {"penalty": 0.3})
    monkeypatch.setattr(analytics, "_readiness_bodyweight_component", lambda *args, **kwargs: {"penalty": 0.1})

    program = {
        "meta": {
            "program_start": (TODAY - timedelta(days=14)).isoformat(),
            "weight_class_kg": 86,
            "current_body_weight_kg": 90,
        },
        "phases": [
            {
                "name": "Base",
                "intent": "build",
                "start_week": 1,
                "end_week": 12,
                "target_rpe_min": 7,
                "target_rpe_max": 9,
            }
        ],
    }
    sessions = [
        make_session(
            0,
            [make_exercise("Squat", 100, 1)],
            session_rpe=9,
            body_weight_kg=90,
            wellness=make_wellness(4, 4, 4, 4, 4),
            week_number=3,
        )
    ]

    result = analytics.compute_readiness_score(sessions, program, program_start=program["meta"]["program_start"])

    assert result["score"] == pytest.approx(68.0, abs=1e-6)
    assert result["zone"] == "yellow"
    assert result["components"]["fatigue_norm"] == pytest.approx(0.2, abs=1e-6)
    assert result["components"]["rpe_drift"] == pytest.approx(0.5, abs=1e-6)
    assert result["components"]["wellness"] == pytest.approx(0.4, abs=1e-6)
    assert result["components"]["performance_trend"] == pytest.approx(0.3, abs=1e-6)
    assert result["components"]["bw_deviation"] == pytest.approx(0.1, abs=1e-6)
    assert "miss_rate" not in result["components"]
    assert "compliance_pct" not in result["components"]
