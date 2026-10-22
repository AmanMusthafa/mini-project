"""
Explainable Decision-Support Recommendations Module
Derives mitigation suggestions directly from SHAP feature contributions
for high-severity (Major/Fatal) crash predictions.
"""

# Curated recommendation catalog mapped by feature name and context
RECOMMENDATION_CATALOG = {
    "cause": {
        "overspeeding": {
            "title": "Dynamic Speed Feedback & Automated Speed Enforcement",
            "category": "Speed Management",
            "description": "Deploy automated speed enforcement radars and dynamic driver feedback signs to calm traffic and reduce impact velocity.",
            "action": "Calibrate radar enforcement cameras and install speed cushions on high-speed approach zones."
        },
        "drunk driving": {
            "title": "Targeted Sobriety Checkpoints & Night-Time Patrols",
            "category": "Enforcement & Surveillance",
            "description": "Increase randomized breathalyzer checkpoints during peak risk hours (21:00 - 04:00) and weekend corridors.",
            "action": "Deploy mobile interception teams along key arterial connectors."
        },
        "poor road": {
            "title": "Pavement Resurfacing & Hazard Remediation",
            "category": "Infrastructure Maintenance",
            "description": "Immediate surface restoration, pothole filling, and installation of high-friction anti-skid overlays.",
            "action": "Schedule emergency municipal road repair with Kerala PWD / Kochi Corporation."
        },
        "weather": {
            "title": "Monsoon Safety Measures & Variable Message Displays",
            "category": "Environmental Mitigation",
            "description": "Activate wet-weather speed limit reductions on Variable Message Signs (VMS) and clear road drainage channels.",
            "action": "Clear storm drains, clean road markings with retroreflective paint, and increase patrol visibility."
        },
        "distraction": {
            "title": "Distracted Driving Interception & Awareness",
            "category": "Driver Behavior",
            "description": "Enforce mobile phone usage prohibitions using AI CCTV analytics and intersection monitoring.",
            "action": "Deploy high-definition surveillance cameras at junction stop lines."
        }
    },
    "traffic_signal": {
        "0": {
            "title": "Intersection Signalization & Conflict Separation",
            "category": "Traffic Engineering",
            "description": "Install actuated or smart traffic control signals to eliminate unmanaged cross-traffic conflict points.",
            "action": "Conduct junction warrants study for adaptive traffic signal installation."
        }
    },
    "visibility": {
        "low": {
            "title": "High-Intensity LED Street Lighting & Road Delineators",
            "category": "Visibility & Lighting",
            "description": "Upgrade junction illumination with high-lumen solar/LED lights and reflective road studs (cat's eyes).",
            "action": "Install reflective lane delineators and verify luminaire lux levels along the corridor."
        }
    },
    "weather": {
        "rain": {
            "title": "Hydroplaning Mitigation & Stormwater Drainage Inspection",
            "category": "Road Surface",
            "description": "Cut micro-grooves into asphalt surface to enhance tire drainage and avoid hydroplaning during heavy rainfall.",
            "action": "Inspect stormwater runoff channels and add anti-skid friction layers."
        },
        "fog": {
            "title": "Fog Warning Signs & Active Roadway Guidance",
            "category": "Adverse Weather",
            "description": "Activate amber fog flashers and pulsed LED road stud guidance along low-visibility stretches.",
            "action": "Install illuminated edge-lines and warning flashers."
        }
    },
    "road_type": {
        "highway": {
            "title": "Highway Median Barrier & Access Management",
            "category": "Corridor Safety",
            "description": "Reinforce central median crash barriers (W-beam) and regulate unregulated side-road entries to prevent head-on crashes.",
            "action": "Install crash cushions at diverging points and close unauthorized median openings."
        }
    },
    "lanes": {
        "multi": {
            "title": "Lane Discipline & Channelized Turning Pockets",
            "category": "Road Geometry",
            "description": "Paint clear lane arrows, install physical channelizers, and provide dedicated right-turning storage pockets.",
            "action": "Mark continuous edge lines and separate lane conflicts using rumble strips."
        }
    }
}

def generate_shap_recommendations(predicted_severity, top_shap_features, input_data):
    """
    Generate decision-support recommendations strictly derived from SHAP contributions.
    
    Parameters:
        predicted_severity (str): 'minor', 'major', or 'fatal'
        top_shap_features (list): list of dicts with keys {'feature', 'original_feature', 'value', 'shap_value', 'direction'}
        input_data (dict): raw user input fields
        
    Returns:
        list of recommendation objects
    """
    if predicted_severity == "minor":
        return [
            {
                "title": "Routine Safety Monitoring",
                "category": "Preventive Maintenance",
                "description": "No high-severity drivers identified. Standard conditions observed with low collision probability.",
                "action": "Maintain routine corridor speed monitoring and quarterly pavement maintenance.",
                "trigger": "Model predicted Minor severity; low risk profile",
                "triggered_by": "Model predicted Minor severity; low risk profile",
                "priority": "Low",
                "disclaimer": "Decision-support suggestion based on feature attribution; requires engineering site survey."
            },
            {
                "title": "Defensive Driving & Speed Awareness",
                "category": "Driver Safety",
                "description": "Keep approach speeds within designated limits and maintain adequate headway in traffic.",
                "action": "Display standard road safety reminders on dynamic message signs.",
                "trigger": "Preventive tip for urban corridors",
                "triggered_by": "Preventive tip for urban corridors",
                "priority": "Low",
                "disclaimer": "Decision-support suggestion based on feature attribution; requires engineering site survey."
            }
        ]

    recommendations = []
    seen_titles = set()

    for feat in top_shap_features:
        # Only consider factors that support the severe prediction (positive contribution)
        if feat.get("direction") != "supports" or feat.get("shap_value", 0) <= 0:
            continue

        orig = feat.get("original_feature", "")
        val = str(feat.get("value", "")).lower()
        shap_val = feat.get("shap_value", 0.0)

        item = None
        evidence = f"Triggered by: {orig.replace('_', ' ').title()} = '{val}' (+{shap_val:.2f} SHAP contribution)"

        if orig == "cause" and val in RECOMMENDATION_CATALOG["cause"]:
            item = RECOMMENDATION_CATALOG["cause"][val]
        elif orig == "traffic_signal" and str(input_data.get("traffic_signal", 1)) in ["0", 0]:
            item = RECOMMENDATION_CATALOG["traffic_signal"]["0"]
        elif orig == "visibility" and val == "low":
            item = RECOMMENDATION_CATALOG["visibility"]["low"]
        elif orig == "weather" and val in ["rain", "fog"]:
            item = RECOMMENDATION_CATALOG["weather"][val]
        elif orig == "road_type" and val == "highway":
            item = RECOMMENDATION_CATALOG["road_type"]["highway"]
        elif orig == "lanes" and int(input_data.get("lanes", 2)) >= 4:
            item = RECOMMENDATION_CATALOG["lanes"]["multi"]

        if item and item["title"] not in seen_titles:
            seen_titles.add(item["title"])
            priority = "Critical" if predicted_severity == "fatal" else "High"
            recommendations.append({
                "title": item["title"],
                "category": item["category"],
                "description": item["description"],
                "action": item["action"],
                "trigger": evidence,
                "triggered_by": evidence,
                "priority": priority,
                "disclaimer": "Decision-support suggestion based on feature attribution; requires engineering site survey."
            })

        if len(recommendations) >= 4:
            break

    # If no specific catalog match was found but severity is high
    if not recommendations:
        recommendations.append({
            "title": "Comprehensive Junction Safety Audit",
            "category": "Engineering Audit",
            "description": "High accident severity anticipated from combined multi-factor conditions. Conduct an IRC-compliant road safety inspection.",
            "action": "Deploy traffic safety engineers to assess sight distance, signs, and speed calming.",
            "trigger": f"Composite risk factors elevated for {predicted_severity.title()} severity",
            "triggered_by": f"Composite risk factors elevated for {predicted_severity.title()} severity",
            "priority": "High",
            "disclaimer": "Decision-support suggestion based on feature attribution; requires engineering site survey."
        })

    return recommendations
