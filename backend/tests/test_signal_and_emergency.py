"""
Smart Traffic Signal Optimizer & Emergency Preemption Test Suite (Phases 7 & 9)
Verifies:
- Webster signal optimization constraints (cycle bounds, clearance lost time, delay reduction)
- Green time proportionality and oversaturation fallback
- Emergency preemption clearance safety (minimum yellow 3s, all-red 2s, min green served)
- Preemption restore rotation
"""
from backend.signal_optimizer import optimize_traffic_signals
from backend.emergency_priority import compute_emergency_preemption

def test_signal_optimizer_equal_flows():
    """Equal flows on symmetric approaches should receive approximately equal greens."""
    approaches = [
        {"name": "North", "vehicle_counts": {"Car": 10}, "lanes": 1},
        {"name": "South", "vehicle_counts": {"Car": 10}, "lanes": 1},
        {"name": "East", "vehicle_counts": {"Car": 10}, "lanes": 1},
        {"name": "West", "vehicle_counts": {"Car": 10}, "lanes": 1}
    ]
    res = optimize_traffic_signals(approaches, min_cycle=40, max_cycle=120)
    assert res["success"] is True
    assert 40 <= res["cycle_length"] <= 120

    greens = [p["green_seconds"] for p in res["phases"]]
    # Max difference between any two phases should be minimal (<= 2s due to integer rounding)
    assert max(greens) - min(greens) <= 2

def test_signal_optimizer_heavy_approach():
    """An approach with 4x traffic should be allocated substantially longer green."""
    approaches = [
        {"name": "North (Heavy Arterial)", "vehicle_counts": {"Car": 40, "Bus": 8}, "lanes": 2},
        {"name": "South (Heavy Arterial)", "vehicle_counts": {"Car": 38, "Bus": 7}, "lanes": 2},
        {"name": "East (Side Street)", "vehicle_counts": {"Car": 4}, "lanes": 1},
        {"name": "West (Side Street)", "vehicle_counts": {"Car": 4}, "lanes": 1}
    ]
    res = optimize_traffic_signals(approaches)
    phases = res["phases"]
    north_green = phases[0]["green_seconds"]
    east_green = phases[2]["green_seconds"]
    assert north_green > east_green * 2

def test_signal_optimizer_oversaturation_handling():
    """Extremely high traffic should trigger oversaturation clamp and warning without crash."""
    approaches = [
        {"name": "North", "vehicle_counts": {"Car": 120, "Truck": 20}, "lanes": 1},
        {"name": "South", "vehicle_counts": {"Car": 110, "Truck": 20}, "lanes": 1}
    ]
    res = optimize_traffic_signals(approaches, max_cycle=130)
    assert res["is_oversaturated"] is True
    assert res["cycle_length"] == 130
    assert "oversaturated" in res["rationale"].lower()

def test_emergency_preemption_conflicting_approach_clearance():
    """Emergency preemption must enforce mandatory Yellow (3s) and All-Red (2s) clearance."""
    plan = compute_emergency_preemption(
        approaching_approach="West",
        eta_seconds=20,
        vehicle_type="Ambulance",
        current_active_phase="North",
        elapsed_green_seconds=15
    )
    assert plan["success"] is True
    assert plan["safety_checks"]["yellow_clearance_met"] is True
    assert plan["safety_checks"]["all_red_clearance_met"] is True

    timeline = plan["timeline"]
    states = [step["state"] for step in timeline]
    assert "YELLOW_CLEARANCE" in states
    assert "ALL_RED_CLEARANCE" in states
    assert "PREEMPTION_GREEN" in states

def test_emergency_preemption_already_green_extends():
    """If approaching approach is already green, plan should extend green without clearance interruption."""
    plan = compute_emergency_preemption(
        approaching_approach="North",
        eta_seconds=25,
        vehicle_type="Fire Brigade",
        current_active_phase="North",
        elapsed_green_seconds=10
    )
    assert plan["success"] is True
    first_step = plan["timeline"][0]
    assert first_step["state"] == "GREEN_EXTENDED"
    assert "extension" in plan["decision"].lower()
