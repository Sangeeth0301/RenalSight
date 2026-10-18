"""Checks that ta/bn/te have exactly the same keys and {{placeholders}} as en.json.

doctor.* and admin.* are professional-portal strings: English only by policy (i18next falls back to English),
so they are skipped here.  Run:  python check_i18n.py
Also verifies every care-plan code produced by the backend rule engine has a translation.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
SKIP = ("doctor", "admin", "_meta")
PH = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flat(v, key))
        else:
            out[key] = v
    return out


def load(lang):
    data = json.loads((HERE / f"{lang}.json").read_text(encoding="utf-8"))
    return {k: v for k, v in flat(data).items() if k.split(".")[0] not in SKIP}


def main():
    en = load("en")
    problems = 0
    for lang in ("ta", "bn", "te"):
        tr = load(lang)
        missing = sorted(set(en) - set(tr))
        extra = sorted(set(tr) - set(en))
        bad_ph = [k for k in en if k in tr and set(PH.findall(en[k])) != set(PH.findall(tr[k]))]
        empty = [k for k, v in tr.items() if not str(v).strip()]
        same = [k for k in en if k in tr and tr[k] == en[k] and re.search(r"[A-Za-z]{4,}", en[k]) and k not in ("app.name",) and not k.startswith(("lang.", "buddy.toolNames.compute", "labs.hba1c", "labs.egfr", "forecast.hba1c"))]
        print(f"{lang}: {len(tr)} keys | missing {len(missing)} | extra {len(extra)} | placeholder mismatches {len(bad_ph)} | empty {len(empty)} | untranslated-looking {len(same)}")
        for name, lst in (("missing", missing), ("extra", extra), ("placeholder mismatch", bad_ph), ("empty", empty)):
            for k in lst[:10]:
                print(f"   {name}: {k}")
        problems += len(missing) + len(extra) + len(bad_ph) + len(empty)
        for k in same[:8]:
            print(f"   (check) identical to English: {k}")

    # every backend care-plan code must be translated
    src = (ROOT / "backend" / "app" / "modules" / "rx" / "engine.py").read_text(encoding="utf-8")
    codes = set(re.findall(r'_item\("([a-z_0-9]+)"', src)) | set(re.findall(r'\(\("(warn_[a-z]+)"', src)) | {"warn_swelling", "warn_breath", "warn_urine", "warn_vomit", "warn_chest"}
    for lang in ("en", "ta", "bn", "te"):
        have = set(k.split(".", 2)[2] for k in load(lang) if k.startswith("carePlan.items."))
        miss = sorted(codes - have)
        print(f"{lang}: backend care-plan codes {len(codes)} | untranslated {miss}")
        problems += len(miss)
    sections = ("urgent", "diet", "fluids", "blood_pressure", "blood_sugar", "medicines", "activity", "monitoring", "warning_signs")
    for lang in ("en", "ta", "bn", "te"):
        have = {k.split(".")[2] for k in load(lang) if k.startswith("carePlan.sections.")}
        problems += len(set(sections) - have)
    print("RESULT:", "OK" if problems == 0 else f"{problems} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
