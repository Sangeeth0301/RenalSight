"""Download the open datasets used by the forecast work (run once; files go to data/raw, which is git-ignored).

    python -m forecast.datasets

* MIMIC-IV Clinical Database Demo 2.2 (PhysioNet, ODbL): 100 patients with real, time-stamped creatinine, diagnoses and demographics.
* Human chronic-kidney-disease images from Wikimedia Commons (ultrasound, CT, histology; CC BY, CC BY-SA or CC0), with author and licence recorded.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
UA = "RenalSight-research/1.0 (student project)"

MIMIC = "https://physionet.org/files/mimic-iv-demo/2.2/"
MIMIC_FILES = ["hosp/labevents.csv.gz", "hosp/d_labitems.csv.gz", "hosp/patients.csv.gz", "hosp/admissions.csv.gz", "hosp/diagnoses_icd.csv.gz", "hosp/d_icd_diagnoses.csv.gz", "LICENSE.txt"]

KIDNEY_IMAGES = [
    ("Ultrasonography of chronic renal disease caused by glomerulonephritis.jpg", "Ultrasound: chronic kidney disease (glomerulonephritis)"),
    ("Ultrasonography of end-stage chronic kidney disease.jpg", "Ultrasound: end-stage chronic kidney disease"),
    ("Ultrasonography of chronic pyelonephritis with reduced kidney size and focal cortical thinning.jpg", "Ultrasound: chronic pyelonephritis, small kidney"),
    ("Advanced polycystic kidney disease with multiple cysts.jpg", "Advanced polycystic kidney disease"),
    ("CT scan autosomal dominant polycystic kidney disease.jpg", "CT: polycystic kidney disease"),
    ("Histopathology of arcuate artery nephrosclerosis.jpg", "Histology: nephrosclerosis (arcuate artery)"),
    ("Histopathology of hypertensive glomerular lesion of hypertensive nephropathy.jpg", "Histology: hypertensive glomerular lesion"),
    ("Histopathology of renal interstitial fibrosis of hypertensive nephropathy.jpg", "Histology: interstitial fibrosis"),
    ("Diabetic glomerulosclerosis (1) HE.jpg", "Histology: diabetic glomerulosclerosis (HE)"),
    ("Diabetic glomerulosclerosis (4) PAS.jpg", "Histology: diabetic glomerulosclerosis (PAS)"),
]


def _curl(url: str, out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["curl", "-sSL", "-m", "120", "-A", UA, "-o", str(out), "-w", "%{http_code}", url], capture_output=True, text=True)
    return int(r.stdout or 0)


def fetch_mimic() -> None:
    for f in MIMIC_FILES:
        out = RAW / "physionet" / "mimic_demo" / f
        if out.exists() and out.stat().st_size > 0:
            continue
        print("download", f, _curl(MIMIC + f, out))


def fetch_images() -> list[dict]:
    meta = []
    d = RAW / "kidney_images"
    for title, caption in KIDNEY_IMAGES:
        q = urllib.parse.urlencode({"action": "query", "titles": "File:" + title, "prop": "imageinfo", "iiprop": "url|extmetadata", "iiextmetadatafilter": "LicenseShortName|Artist|LicenseUrl", "format": "json"})
        r = subprocess.run(["curl", "-sS", "-m", "30", "-A", UA, "https://commons.wikimedia.org/w/api.php?" + q], capture_output=True, text=True)
        page = next(iter(json.loads(r.stdout)["query"]["pages"].values()))
        ii = page["imageinfo"][0]
        m = ii.get("extmetadata", {})
        artist = m.get("Artist", {}).get("value", "")
        artist = __import__("re").sub(r"<[^>]+>", "", artist).strip()
        fn = title.replace(" ", "_")
        path = d / fn
        if not path.exists() or path.stat().st_size == 0:
            code = _curl("https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(fn) + "?width=900", path)
            print("download", title, code)
        meta.append({"file": fn, "caption": caption, "author": artist, "license": m.get("LicenseShortName", {}).get("value", ""), "page": ii.get("descriptionurl", "")})
    (d / "attribution.json").write_text(json.dumps(meta, indent=1))
    return meta


if __name__ == "__main__":
    fetch_mimic()
    meta = fetch_images()
    print(len(meta), "images;", sum(1 for m in meta if m["license"]), "with a licence recorded")
