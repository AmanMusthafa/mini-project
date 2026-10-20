"""
Smart Traffic Signal Optimizer Module (Webster's Method)
Computes optimal cycle lengths and phase green allocations based on Passenger Car Units (PCU),
approach flow ratios, minimum pedestrian clearance, and saturation constraints.
Includes uniform delay calculation and before/after baseline comparison.
"""

DEFAULT_PCU_FACTORS = {
    "Car": 1.0,
    "Motorcycle": 0.5,
    "Bus": 2.5,
    "Truck": 2.5,
    "Bicycle": 0.3
}

def calculate_pcu(class_counts, pcu_factors=None):
    """Calculate total Passenger Car Units (PCU) from vehicle class counts."""
    factors = pcu_factors or DEFAULT_PCU_FACTORS
    total_pcu = 0.0
    for v_class, count in class_counts.items():
        total_pcu += count * factors.get(v_class, 1.0)
    return round(total_pcu, 2)

def optimize_traffic_signals(
    approaches,
    min_cycle=40,
    max_cycle=130,
    min_green=8,
    yellow_time=3,
    all_red=2,
    saturation_flow=1800,  # PCU/hr per lane
    fixed_baseline=None,
    cycle_time_window_sec=60  # observation window duration used to calculate hourly flow
):
    """
    Apply Webster's formula to compute optimal signal cycle and green time distribution.
    
    Parameters:
        approaches (list): List of approach dicts:
            [
                {
                    "name": "North (MG Road)",
                    "vehicle_counts": {"Car": 20, "Motorcycle": 15, "Bus": 3, "Truck": 1, "Bicycle": 2},
                    "lanes": 2
                }, ...
            ]
        min_cycle (int): Minimum permissible cycle length (seconds).
        max_cycle (int): Maximum permissible cycle length (seconds).
        min_green (int): Minimum green time per phase (seconds).
        yellow_time (int): Clearance amber interval (seconds).
        all_red (int): Clearance all-red interval (seconds).
        saturation_flow (int): Saturation flow per lane (PCU/hour).
        fixed_baseline (list or dict): Baseline fixed timing for comparison.
        cycle_time_window_sec (int): Observation period in seconds to scale counts to hourly flow.
        
    Returns:
        dict: Optimization results containing phase allocations, delays, and engineering rationale.
    """
    num_phases = len(approaches)
    if num_phases < 2:
        raise ValueError("At least 2 approaches/phases required for signal optimization.")

    lost_time_per_phase = yellow_time + all_red  # Total lost time per phase (seconds)
    total_lost_time = lost_time_per_phase * num_phases

    # 1. Compute PCU and hourly flow rate for each approach
    scale_factor = 3600.0 / max(cycle_time_window_sec, 1)
    phase_data = []
    flow_ratios = []
    
    for i, app in enumerate(approaches):
        name = app.get("name", f"Phase {i+1}")
        v_counts = app.get("vehicle_counts", {})
        lanes = max(int(app.get("lanes", 1)), 1)
        
        pcu = calculate_pcu(v_counts)
        hourly_flow_q = max(pcu * scale_factor, 10.0)  # Min flow guard
        approach_sat = saturation_flow * lanes
        y_i = hourly_flow_q / approach_sat
        flow_ratios.append(y_i)
        
        phase_data.append({
            "name": name,
            "counts": v_counts,
            "pcu": pcu,
            "hourly_flow_pcu": round(hourly_flow_q, 1),
            "lanes": lanes,
            "saturation_capacity": approach_sat,
            "flow_ratio": y_i
        })

    Y = sum(flow_ratios)
    is_oversaturated = Y >= 0.88
    
    # 2. Compute Webster's optimal cycle length: C0 = (1.5 * L + 5) / (1 - Y)
    if Y >= 0.95:
        # Heavily oversaturated - clamp to max cycle
        optimal_cycle = max_cycle
        rationale_warning = f"High demand detected (Y = {Y:.2f} >= 0.95). Intersection is oversaturated; maximizing cycle capacity at {max_cycle}s."
    else:
        computed_cycle = (1.5 * total_lost_time + 5.0) / max(1.0 - Y, 0.05)
        optimal_cycle = int(round(computed_cycle))
        optimal_cycle = max(min_cycle, min(optimal_cycle, max_cycle))
        rationale_warning = f"Balanced flow condition (Y = {Y:.2f}). Webster optimal cycle calculated at {optimal_cycle}s."

    # 3. Allocate Effective Green Time: G_total = C - L
    total_effective_green = optimal_cycle - total_lost_time
    min_required_green = min_green * num_phases
    
    if total_effective_green < min_required_green:
        optimal_cycle = min_required_green + total_lost_time
        total_effective_green = min_required_green

    # Allocate green proportional to flow ratio y_i
    raw_greens = []
    for y_i in flow_ratios:
        proportion = y_i / max(Y, 0.001)
        raw_g = round(total_effective_green * proportion)
        raw_greens.append(max(raw_g, min_green))

    # Adjust rounding differences so sum(greens) + lost_time == optimal_cycle
    allocated_green_sum = sum(raw_greens)
    diff = total_effective_green - allocated_green_sum
    # Apply difference to highest flow phase
    max_phase_idx = int(flow_ratios.index(max(flow_ratios)))
    raw_greens[max_phase_idx] = max(min_green, raw_greens[max_phase_idx] + diff)

    # 4. Construct Phase Details & Delay Estimates
    phases = []
    total_simulated_delay = 0.0
    for i, app in enumerate(phase_data):
        green = int(raw_greens[i])
        phase_time = green + yellow_time + all_red
        
        # Webster's uniform delay formula:
        # d = (C * (1 - lambda)^2) / (2 * (1 - lambda * x))
        # where lambda = green / C, x = degree of saturation = q / (s * lambda)
        lam = green / float(optimal_cycle)
        deg_sat = min(app["hourly_flow_pcu"] / (app["saturation_capacity"] * lam), 0.98)
        denom = 2.0 * (1.0 - lam * deg_sat)
        delay_sec = (optimal_cycle * ((1.0 - lam) ** 2)) / max(denom, 0.05)
        delay_sec = round(min(delay_sec, 120.0), 1)
        total_simulated_delay += delay_sec * (app["pcu"] / max(sum(p["pcu"] for p in phase_data), 1.0))

        phases.append({
            "phase_index": i + 1,
            "approach_name": app["name"],
            "green_seconds": green,
            "yellow_seconds": yellow_time,
            "all_red_seconds": all_red,
            "total_phase_seconds": phase_time,
            "pcu_count": app["pcu"],
            "degree_of_saturation": round(deg_sat, 2),
            "estimated_delay_seconds": delay_sec
        })

    # 5. Baseline Comparison (Fixed Time 90s: default [25, 30, 20, 15] or equal split)
    baseline_delays = []
    if not fixed_baseline or len(fixed_baseline) != num_phases:
        fixed_baseline = [25, 30, 20, 15][:num_phases]
        if len(fixed_baseline) < num_phases:
            fixed_baseline += [20] * (num_phases - len(fixed_baseline))

    baseline_cycle = sum(fixed_baseline) + total_lost_time
    total_baseline_delay = 0.0
    for i, app in enumerate(phase_data):
        b_green = fixed_baseline[i]
        b_lam = b_green / float(baseline_cycle)
        b_sat = min(app["hourly_flow_pcu"] / (app["saturation_capacity"] * b_lam), 1.2)
        b_denom = 2.0 * max(1.0 - b_lam * min(b_sat, 0.98), 0.05)
        b_delay = (baseline_cycle * ((1.0 - b_lam) ** 2)) / b_denom
        if b_sat > 1.0:
            b_delay += 30.0 * (b_sat - 1.0)  # Overflow delay penalty
        b_delay = round(min(b_delay, 150.0), 1)
        total_baseline_delay += b_delay * (app["pcu"] / max(sum(p["pcu"] for p in phase_data), 1.0))

    delay_reduction_pct = round(max((total_baseline_delay - total_simulated_delay) / max(total_baseline_delay, 1.0) * 100.0, 0.0), 1)

    return {
        "success": True,
        "is_simulation": True,
        "simulation_disclaimer": "SIMULATION ONLY: Calculated timings are for decision support and planning. Not connected to physical traffic signal controllers.",
        "cycle_length": optimal_cycle,
        "total_lost_time": total_lost_time,
        "total_effective_green": sum(raw_greens),
        "flow_ratio_sum_Y": round(Y, 3),
        "is_oversaturated": is_oversaturated,
        "phases": phases,
        "rationale": rationale_warning,
        "comparison": {
            "baseline_cycle": baseline_cycle,
            "baseline_phases": fixed_baseline,
            "baseline_avg_delay_sec": round(total_baseline_delay, 1),
            "optimized_avg_delay_sec": round(total_simulated_delay, 1),
            "estimated_delay_reduction_pct": delay_reduction_pct
        }
    }
