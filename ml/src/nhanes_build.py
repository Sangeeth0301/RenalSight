"""Build one analysis table from NHANES 2005-2014 (cycles D-H) + CDC linked mortality (to 2019).

Output: data/processed/nhanes_adults.csv  (adults 20+ with creatinine and urine ACR)
"""
from pathlib import Path

import numpy as np
import pandas as pd

from clinical import albuminuria_category, egfr_ckdepi_2021, gfr_stage

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "nhanes"
OUT = ROOT / "data" / "processed"
CYCLES = {"D": "2005_2006", "E": "2007_2008", "F": "2009_2010", "G": "2011_2012", "H": "2013_2014"}


def xpt(name, letter):
    return pd.read_sas(RAW / f"{name}_{letter}.xpt", format="xport")


def load_cycle(letter, years):
    demo = xpt("DEMO", letter)[["SEQN", "RIAGENDR", "RIDAGEYR", "RIDRETH1", "WTMEC2YR", "INDFMPIR"]]
    bio = xpt("BIOPRO", letter)[["SEQN", "LBXSCR", "LBXSAL", "LBXSBU", "LBXSKSI", "LBXSNASI"]]
    alb = xpt("ALB_CR", letter)[["SEQN", "URXUMA", "URXUCR"]]
    bp = xpt("BPX", letter)
    sy = [c for c in bp.columns if c.startswith("BPXSY")]
    di = [c for c in bp.columns if c.startswith("BPXDI")]
    bp = bp.assign(sbp=bp[sy].mean(axis=1), dbp=bp[di].mean(axis=1))[["SEQN", "sbp", "dbp"]]
    ghb = xpt("GHB", letter)[["SEQN", "LBXGH"]]
    diq = xpt("DIQ", letter)[["SEQN", "DIQ010"]]
    cbc = xpt("CBC", letter)[["SEQN", "LBXHGB"]]
    bmx = xpt("BMX", letter)[["SEQN", "BMXBMI"]]
    df = demo
    for t in (bio, alb, bp, ghb, diq, cbc, bmx):
        df = df.merge(t, on="SEQN", how="left")
    # linked mortality (fixed width, positions from the CDC read-in program)
    cs = [(0, 6), (14, 15), (15, 16), (16, 19), (42, 45), (45, 48)]
    mort = pd.read_fwf(RAW / f"mort_{years}.dat", colspecs=cs, header=None,
                       names=["SEQN", "eligstat", "mortstat", "ucod", "permth_int", "permth_exm"])
    for c in mort.columns:
        mort[c] = pd.to_numeric(mort[c], errors="coerce")
    df = df.merge(mort, on="SEQN", how="left")
    df["cycle"] = years
    return df


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.concat([load_cycle(k, v) for k, v in CYCLES.items()], ignore_index=True)
    df = df.rename(columns={
        "SEQN": "seqn", "RIAGENDR": "sex_code", "RIDAGEYR": "age", "RIDRETH1": "race_code", "WTMEC2YR": "weight_2yr",
        "INDFMPIR": "income_ratio", "LBXSCR": "scr", "LBXSAL": "serum_albumin", "LBXSBU": "bun", "LBXSKSI": "potassium",
        "LBXSNASI": "sodium", "URXUMA": "uma", "URXUCR": "ucr", "LBXGH": "hba1c", "DIQ010": "diq010", "LBXHGB": "hgb", "BMXBMI": "bmi",
    })
    df = df[df["age"] >= 20].copy()
    df = df.dropna(subset=["scr", "uma", "ucr"])
    df["male"] = (df["sex_code"] == 1).astype(int)
    df["acr"] = df["uma"] / df["ucr"] * 100.0          # mg/g
    df["egfr"] = egfr_ckdepi_2021(df["scr"], df["age"], df["male"] == 0)
    df["g_stage"] = df["egfr"].apply(gfr_stage)
    df["a_cat"] = df["acr"].apply(albuminuria_category)
    df["ckd"] = ((df["egfr"] < 60) | (df["acr"] >= 30)).astype(int)
    df["diabetes"] = ((df["diq010"] == 1) | (df["hba1c"] >= 6.5)).astype(int)
    df["event"] = (df["mortstat"] == 1).astype(int)
    df["months"] = df["permth_exm"]
    keep = ["seqn", "cycle", "age", "male", "race_code", "weight_2yr", "scr", "egfr", "g_stage", "acr", "a_cat", "ckd",
            "sbp", "dbp", "hba1c", "diabetes", "hgb", "bmi", "serum_albumin", "bun", "potassium", "sodium",
            "eligstat", "mortstat", "event", "months", "ucod"]
    df = df[keep]
    df.to_csv(OUT / "nhanes_adults.csv", index=False)
    print("rows", len(df), "| CKD prevalence (single visit) %.1f%%" % (100 * df.ckd.mean()))
    print(df["g_stage"].value_counts().sort_index().to_dict())
    elig = df[df.eligstat == 1]
    print("mortality-eligible", len(elig), "deaths", int(elig.event.sum()), "median follow-up months", float(elig.months.median()))
    print(elig.groupby("ckd").event.mean().round(3).to_dict(), "(death rate: no CKD vs CKD)")


if __name__ == "__main__":
    main()
