"""Turn lab values into the 'Living Kidney' state: stage, severity and which wounds to draw.

Each wound level is 0..1 and has a code the frontend maps to an animation and a translated explanation.
"""
from __future__ import annotations

import math

from clinical import albuminuria_category, gfr_stage


def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def kidney_state(egfr, acr=None, sbp=None, hgb=None, potassium=None, male=True):
    stage_g = gfr_stage(egfr)
    stage_num = int(stage_g[1])
    a_cat = albuminuria_category(acr) if acr is not None else None
    visual_stage = stage_num
    if a_cat == "A3" and stage_num == 3:
        visual_stage = 4                                # heavy protein leak makes a stage-3 kidney look wounded; "destroyed" is reserved for eGFR < 15

    cracks = _clip((90.0 - egfr) / 75.0)
    leak = 0.0 if acr is None or acr < 30 else _clip(0.2 + 0.8 * math.log10(max(acr, 30) / 30.0) / 2.0)
    veins = 0.0 if sbp is None else _clip((sbp - 120.0) / 60.0)
    low_hgb = 12.0 if not male else 13.0
    pallor = 0.0 if hgb is None else _clip((low_hgb - hgb) / 5.0)
    flicker = 0.0 if potassium is None else _clip((potassium - 5.0) / 1.5)

    wounds = [
        {"code": "cracks", "level": round(cracks, 2), "cause": "low_egfr", "value": round(float(egfr), 1)},
        {"code": "leak", "level": round(leak, 2), "cause": "albuminuria", "value": None if acr is None else round(float(acr), 1)},
        {"code": "veins", "level": round(veins, 2), "cause": "high_bp", "value": sbp},
        {"code": "pallor", "level": round(pallor, 2), "cause": "anaemia", "value": hgb},
        {"code": "flicker", "level": round(flicker, 2), "cause": "high_potassium", "value": potassium},
    ]
    severity = 100.0 * _clip(0.7 * cracks + 0.15 * leak + 0.15 * max(veins, pallor, flicker))
    if visual_stage == 5:
        severity = max(severity, 90.0)
    theme = {1: "healthy", 2: "healthy", 3: "watch", 4: "critical", 5: "critical"}[visual_stage]
    return {
        "g_stage": stage_g,
        "a_category": a_cat,
        "visual_stage": visual_stage,
        "stage_name": {1: "healthy", 2: "stressed", 3: "scarred", 4: "wounded", 5: "destroyed"}[visual_stage],
        "severity": round(severity, 1),
        "theme": theme,
        "shrink": round(1.0 - 0.07 * (visual_stage - 1), 2),
        "pulse": {1: "calm", 2: "calm", 3: "slow", 4: "irregular", 5: "flatline"}[visual_stage],
        "wounds": wounds,
        "urgent": visual_stage >= 4 or (potassium is not None and potassium >= 6.0),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(kidney_state(32, acr=450, sbp=155, hgb=10.2, potassium=5.4), indent=1))
