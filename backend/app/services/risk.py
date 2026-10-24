WEIGHTS = {"technical_severity": 0.40, "exposure": 0.25, "confidence": 0.20, "business_impact": 0.15}


def calculate_risk(technical_severity: float, exposure: float, confidence: float, business_impact: float) -> dict:
    factors = {
        "technical_severity": technical_severity,
        "exposure": exposure,
        "confidence": confidence,
        "business_impact": business_impact,
    }
    if any(not 0 <= value <= 100 for value in factors.values()):
        raise ValueError("Risk factors must be between 0 and 100.")
    score = round(sum(factors[key] * weight for key, weight in WEIGHTS.items()), 1)
    level = "Informational" if score < 20 else "Low" if score < 40 else "Medium" if score < 60 else "High" if score < 80 else "Critical"
    return {"score": score, "level": level, "factors": factors, "weights": WEIGHTS}