from tools.health.analytics import fatigue_index, compute_readiness_score, compute_banister_ffm, compute_volume_landmarks
from datetime import date

def test_fatigue_index_empty():
    sessions = []
    res = fatigue_index(sessions)
    assert res.get("status") == "insufficient_data" or "reason" in res

def test_fatigue_index_basic():
    sessions = [
        {"date": "2024-01-01", "completed": True, "exercises": [
            {"name": "squat", "kg": 100, "reps": 5, "sets": 3}
        ]},
        {"date": "2024-01-08", "completed": True, "exercises": [
            {"name": "squat", "kg": 110, "reps": 5, "sets": 3}
        ]},
        {"date": "2024-01-15", "completed": True, "exercises": [
            {"name": "squat", "kg": 120, "reps": 5, "sets": 3}
        ]}
    ]
    res = fatigue_index(sessions, ref_date=date(2024, 1, 16))
    assert "score" in res
    assert "components" in res
    comps = res["components"]
    assert "failure_stress" in comps

def test_readiness_missing_data():
    sessions = [
        {"date": "2024-01-01", "completed": True, "session_rpe": 8, "exercises": []},
        {"date": "2024-01-08", "completed": True, "session_rpe": 9, "exercises": []}
    ]
    res = compute_readiness_score(sessions, program={})
    assert "score" in res
    assert "readiness_confidence" in res

def test_banister():
    sessions = [
        {"date": f"2024-01-{i:02d}", "completed": True, "exercises": [
            {"name": "squat", "kg": 100, "reps": 5, "sets": 3}
        ]} for i in range(1, 20)
    ]
    res = compute_banister_ffm(sessions, ref_date=date(2024, 1, 20))
    assert "tsb_today" in res or "reason" in res

def test_volume_landmarks():
    sessions = [
        {"date": f"2024-01-{i:02d}", "completed": True, "exercises": [
            {"name": "squat", "kg": 100, "reps": 5, "sets": 3}
        ]} for i in range(1, 30)
    ]
    res = compute_volume_landmarks(sessions, ref_date=date(2024, 1, 30))
    assert "squat" in res
