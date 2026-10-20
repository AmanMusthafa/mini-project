"""
Emergency Vehicle Signal Preemption Module
Calculates safe, clearance-compliant signal preemption plans for emergency vehicles.
Guarantees yellow amber and all-red clearance intervals, minimum green thresholds,
and orderly recovery to standard cycle rotation.
"""
import datetime
import sqlite3
from backend.config import Config

MIN_GREEN_BEFORE_TERMINATE = 7   # Minimum seconds a green must serve before premature truncation
YELLOW_CLEARANCE = 3             # Mandatory amber clearance (seconds)
ALL_RED_CLEARANCE = 2            # Mandatory all-red clearance (seconds)
MAX_PREEMPTION_DURATION = 60     # Maximum preemption window (seconds)

def compute_emergency_preemption(
    approaching_approach,
    eta_seconds,
    vehicle_type="Ambulance",
    current_active_phase="North",
    elapsed_green_seconds=12,
    all_approaches=None
):
    """
    Calculate an IRC / NEMA compliant signal preemption plan.
    
    Parameters:
        approaching_approach (str): The approach direction of the emergency vehicle (e.g. 'East')
        eta_seconds (int): Estimated time of arrival at the stop line in seconds.
        vehicle_type (str): 'Ambulance', 'Fire Brigade', 'Police Patrol'
        current_active_phase (str): The approach currently holding the green light.
        elapsed_green_seconds (int): How long current phase has been green.
        all_approaches (list): List of all approaches at the junction in cycle order.
        
    Returns:
        dict: Preemption sequence, timeline, safety constraints, and restore plan.
    """
    if all_approaches is None:
        all_approaches = ["North", "East", "South", "West"]

    eta = max(int(eta_seconds), 5)
    elapsed = max(int(elapsed_green_seconds), 0)
    approaching_norm = approaching_approach.strip().title()
    current_norm = current_active_phase.strip().title()

    timeline = []
    current_time_offset = 0

    # CASE 1: The approaching approach is ALREADY GREEN
    if approaching_norm == current_norm:
        extension_needed = max(eta + 10, 15)
        extension_needed = min(extension_needed, MAX_PREEMPTION_DURATION)
        
        timeline.append({
            "t_offset": 0,
            "phase": current_norm,
            "state": "GREEN_EXTENDED",
            "duration": extension_needed,
            "description": f"Approach {current_norm} is currently active. Extending green by {extension_needed}s to cover {vehicle_type} arrival (ETA {eta}s)."
        })
        current_time_offset += extension_needed
        
        decision = f"GREEN EXTENSION (+{extension_needed}s)"
        rationale = f"Emergency vehicle approaching on currently active approach ({current_norm}). Safe to extend green without conflicting phase transition."

    # CASE 2: The approaching approach is CONFLICTING (currently RED)
    else:
        # Check minimum green requirement
        rem_min_green = max(0, MIN_GREEN_BEFORE_TERMINATE - elapsed)
        if rem_min_green > 0:
            timeline.append({
                "t_offset": current_time_offset,
                "phase": current_norm,
                "state": "MIN_GREEN_HOLD",
                "duration": rem_min_green,
                "description": f"Serving {rem_min_green}s remaining minimum green on {current_norm} to avoid pedestrian/traffic trapping."
            })
            current_time_offset += rem_min_green

        # Mandatory Yellow Clearance
        timeline.append({
            "t_offset": current_time_offset,
            "phase": current_norm,
            "state": "YELLOW_CLEARANCE",
            "duration": YELLOW_CLEARANCE,
            "description": f"Transitioning {current_norm} to Yellow for {YELLOW_CLEARANCE}s clearance."
        })
        current_time_offset += YELLOW_CLEARANCE

        # Mandatory All-Red Clearance
        timeline.append({
            "t_offset": current_time_offset,
            "phase": "ALL_RED",
            "state": "ALL_RED_CLEARANCE",
            "duration": ALL_RED_CLEARANCE,
            "description": f"Holding junction in All-Red for {ALL_RED_CLEARANCE}s to completely clear intersection."
        })
        current_time_offset += ALL_RED_CLEARANCE

        # Preempt to Emergency Phase Green
        emergency_green_duration = max(eta - current_time_offset + 8, 15)
        emergency_green_duration = min(emergency_green_duration, MAX_PREEMPTION_DURATION)

        timeline.append({
            "t_offset": current_time_offset,
            "phase": approaching_norm,
            "state": "PREEMPTION_GREEN",
            "duration": emergency_green_duration,
            "description": f"Awarding prioritized Green to {approaching_norm} for {emergency_green_duration}s until {vehicle_type} clears stop line."
        })
        current_time_offset += emergency_green_duration

        decision = f"IMMEDIATE CLEARANCE & PREEMPTION TO {approaching_norm}"
        rationale = (
            f"Interrupted {current_norm} with mandatory {YELLOW_CLEARANCE}s yellow + "
            f"{ALL_RED_CLEARANCE}s all-red clearance. Priority green granted to {approaching_norm} "
            f"for {emergency_green_duration}s (ETA {eta}s)."
        )

    # Post-Preemption Clearance & Normal Restoration
    timeline.append({
        "t_offset": current_time_offset,
        "phase": approaching_norm,
        "state": "YELLOW_CLEARANCE",
        "duration": YELLOW_CLEARANCE,
        "description": f"Post-preemption {YELLOW_CLEARANCE}s Yellow clearance on {approaching_norm}."
    })
    current_time_offset += YELLOW_CLEARANCE

    timeline.append({
        "t_offset": current_time_offset,
        "phase": "ALL_RED",
        "state": "ALL_RED_CLEARANCE",
        "duration": ALL_RED_CLEARANCE,
        "description": f"Post-preemption {ALL_RED_CLEARANCE}s All-Red clearance."
    })
    current_time_offset += ALL_RED_CLEARANCE

    # Next restored phase in regular rotation
    try:
        cur_idx = all_approaches.index(approaching_norm)
        next_phase = all_approaches[(cur_idx + 1) % len(all_approaches)]
    except ValueError:
        next_phase = all_approaches[0]

    timeline.append({
        "t_offset": current_time_offset,
        "phase": next_phase,
        "state": "RESTORE_NORMAL_CYCLE",
        "duration": 25,
        "description": f"Restoring normal cycle operation at next scheduled phase: {next_phase}."
    })

    return {
        "success": True,
        "is_simulation": True,
        "simulation_disclaimer": "SIMULATION ONLY: Signal preemption operates in demonstration mode. Not linked to physical emergency beacon receivers or signal controllers.",
        "vehicle_type": vehicle_type,
        "approach": approaching_norm,
        "eta_seconds": eta,
        "decision": decision,
        "rationale": rationale,
        "total_plan_seconds": current_time_offset + 25,
        "timeline": timeline,
        "restoration_phase": next_phase,
        "safety_checks": {
            "yellow_clearance_met": True,
            "all_red_clearance_met": True,
            "minimum_green_enforced": True,
            "max_duration_capped": True
        }
    }

def log_emergency_event(event_data, db_path=None):
    """Persist emergency preemption event to database audit table."""
    if db_path is None:
        db_path = Config.DATABASE_PATH
        
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute(
        """
        INSERT INTO emergency_events 
        (timestamp, vehicle_type, approach, eta_seconds, decision, preemption_plan, source, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now_str,
            event_data.get("vehicle_type", "Ambulance"),
            event_data.get("approach", "North"),
            event_data.get("eta_seconds", 30),
            event_data.get("decision", "PREEMPTION_PLANNED"),
            str(event_data.get("rationale", "")),
            event_data.get("source", "simulated"),
            "COMPLETED"
        )
    )
    conn.commit()
    conn.close()
