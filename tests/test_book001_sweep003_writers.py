"""SWEEP-003 / BOOK-001 (2026-10-09, second wave): the insider collector's writers no longer truncate a published file in place.

collector_edgar.py wrote docs/data/insiders.json (the file the Pages viewer and the desk read, replaced every pass) with Path.write_text, plus agent/exclusions.csv and the SEC ticker cache;
backfill_edgar.py checkpointed docs/data/events.json per day; attribution.py wrote agent/attribution.csv. Path.write_text truncates first: a reader arriving mid-write saw an empty feed.
The Sweep could not see them (Path constants, no open()); it now follows constants. insider-radar had no atomicio: ./atomicio.py is the byte-identical mirror of stock-radar's.

Pinned: the mirror is byte-identical (where stock-radar is on this machine); none of the three files truncates in place; the new write equals the old byte for byte; the real
collector_edgar.write_exclusions() on a scratch path writes the same bytes as the frozen pre-conversion version and leaves no .tmp.
Run: python -m pytest -q tests/test_book001_sweep003_writers.py
"""
import ast
import csv
import json
import os
import sys
from pathlib import Path

import pytest

IR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(IR))
import atomicio

FILES = ["collector_edgar.py", "backfill_edgar.py", "attribution.py"]


def test_the_mirror_is_byte_identical_to_stock_radar():
    src = Path.home() / "stock-radar" / "atomicio.py"
    if not src.exists():
        pytest.skip("stock-radar is not on this machine")
    assert (IR / "atomicio.py").read_bytes() == src.read_bytes()


def truncating_calls(src):
    out = []
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id == "open":
                mode = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == "mode"), None)
                if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and mode.value.startswith("w") and "tmp" not in ast.unparse(n.args[0]):
                    out.append(n.lineno)
            elif isinstance(f, ast.Attribute) and f.attr in ("write_text", "write_bytes"):
                out.append(n.lineno)
            elif isinstance(f, ast.Attribute) and f.attr == "open" and n.args and isinstance(n.args[0], ast.Constant) and str(n.args[0].value).startswith("w"):
                out.append(n.lineno)
    return out


@pytest.mark.parametrize("name", FILES)
def test_no_converted_file_truncates_in_place(name):
    assert truncating_calls((IR / name).read_text()) == []


DOC = {"updated_utc": "2026-10-09 17:00 UTC", "purchases": [{"t": "ABC", "who": "José \"CEO\"", "value": 12345.6}], "seen": ["a", "b"], "note": "x\ny"}


def test_atomic_write_text_equals_path_write_text(tmp_path):
    Path(tmp_path / "old").write_text(json.dumps(DOC, indent=1))
    atomicio.atomic_write_text(str(tmp_path / "new"), json.dumps(DOC, indent=1))
    assert (tmp_path / "old").read_bytes() == (tmp_path / "new").read_bytes()
    assert sorted(os.listdir(tmp_path)) == ["new", "old"]


def test_atomic_csv_equals_the_dictwriter_loop(tmp_path):
    cols = ["a", "b"]
    rows = [{"a": "x,y", "b": 'q"q', "c": "dropped"}, {"a": "café"}]
    with open(tmp_path / "old", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(rows)
    atomicio.atomic_csv(str(tmp_path / "new"), cols, rows, extrasaction="ignore", restval="")
    assert (tmp_path / "old").read_bytes() == (tmp_path / "new").read_bytes()


def test_write_exclusions_writes_the_same_bytes_as_the_old_loop(tmp_path, monkeypatch):
    pytest.importorskip("requests")
    import collector_edgar
    monkeypatch.setattr(collector_edgar, "EXCLUSIONS", tmp_path / "exclusions.csv")
    clusters = [{"ticker": "ACME, INC. (CIK 1234567)", "total_value": 5000.0, "insiders": 2}, {"ticker": "ZED CORP (CIK 7654321)", "total_value": 9000.5, "insiders": 3}]
    n = collector_edgar.write_exclusions(clusters, today="2026-10-09")
    assert n == 2
    got = (tmp_path / "exclusions.csv").read_bytes()
    assert not [p for p in os.listdir(tmp_path) if ".tmp." in p]
    rows = list(csv.DictReader(got.decode().splitlines(True)))
    assert len(rows) == n
    # the old loop, replayed over the rows the function itself produced: header + rows sorted by -total_value, "\r\n" line ends, no BOM
    cols = list(rows[0].keys()) if rows else []
    with open(tmp_path / "old.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(rows, key=lambda x: -float(x["total_value"] or 0)):
            w.writerow({k: r.get(k, "") for k in cols})
    assert got == (tmp_path / "old.csv").read_bytes()

ROOT_DIR = IR
LOADABLE = ["collector_edgar.py", "attribution.py"]


def test_each_converted_module_loads_by_path_from_any_cwd(tmp_path):
    """a resolver check, a bin script or another repo may load these with spec_from_file_location and no sys.path help: the atomicio import must not depend on the
    caller's path (found by loading every converted module from cwd=/ on 2026-10-09; a bare `from atomicio import` failed for most of them)."""
    import subprocess
    code = "import importlib.util as u,sys; s=u.spec_from_file_location('probe', sys.argv[1]); m=u.module_from_spec(s); s.loader.exec_module(m)"
    for name in LOADABLE:
        r = subprocess.run([sys.executable, "-c", code, str(ROOT_DIR / name)], cwd=tmp_path, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (name, r.stderr[-300:])
