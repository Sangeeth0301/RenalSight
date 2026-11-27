"""Literature review: every reference is cited, every citation resolves, tables are complete and the LaTeX table is well formed."""
import re
from pathlib import Path

import pytest

pytest.importorskip("reportlab")
from forecast import review as rv  # noqa: E402


def test_citation_keys_and_reference_list_agree():
    src = Path(rv.__file__).read_text(encoding="utf-8")
    used = {k for grp in re.findall(r"\bc\(((?:['\"][a-z0-9]+['\"],?\s*)+)\)", src) for k in re.findall(r"['\"]([a-z0-9]+)['\"]", grp)}
    assert used <= set(rv.R)
    assert len(rv.R) == len(rv.REFS)
    cited = {rv.R[k] for k in used} | {int(n) for n in re.findall(r"\[(\d+)\]", " ".join(m[0] for m in rv.MATRIX))}
    assert cited == set(range(1, len(rv.REFS) + 1))


def test_tables_are_complete():
    assert all(len(r) == 5 for r in rv.ROWS) and len(rv.OURS) == 5
    assert all(len(v) == len(rv.CAPS) and set(v) <= {rv.Y, rv.P_, rv.N} for _, v in rv.MATRIX)


def test_latex_table_has_one_line_per_work(tmp_path, monkeypatch):
    monkeypatch.setattr(rv, "TEX", tmp_path / "t.tex")
    rv.write_tex()
    tex = (tmp_path / "t.tex").read_text(encoding="utf-8")
    assert tex.count(r" \\") == len(rv.ROWS) + 2 and "<b>" not in tex and "&gt;" not in tex
    assert tex.strip().endswith(r"\end{table*}")
