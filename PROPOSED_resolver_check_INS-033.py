#!/usr/bin/env python3
"""PROPOSED - NOT APPLIED. A resolver check for INS-033 (register row INS-033, ruled by Anupam 2026-10-14).

A patch proposal for ~/command-center/council/resolver.py, deliberately NOT applied: resolver.py and council/issues.json are
owned by the Mac session that commits command-center. To adopt, paste the function into resolver.py and register it, e.g.
    CHECKS.update({"ins033_preregistered": check_ins033_preregistered})

It passes when (1) the evolution ledger holds exactly one INS-033/v1 entry; (2) research/PREREG_INS-033.md carries that entry's
spec_sha256; (3) the RULE literal in ins033_floor_test.py hashes to it (read with ast, not imported); (4) the entry's ir_commit was
committed before 2026-10-15 13:30 UTC (06:30 PT, before the first cohort call can be written), is on origin/main, and the PREREG file
is byte-identical to that commit's. It does NOT require the scorer's code to be unchanged: RULE is hashed, behaviour is pinned by tests.

Returns (ok: bool, evidence: str). Standalone run prints the current result, read-only:
    /opt/anaconda3/bin/python ~/insider-radar/PROPOSED_resolver_check_INS-033.py
"""


def check_ins033_preregistered():
    import ast, datetime as dt, hashlib, json, os, subprocess
    home = os.path.expanduser("~")
    ir, led = f"{home}/insider-radar", f"{home}/command-center/council/evolution_ledger.json"
    try:
        ents = [v for g in json.load(open(led)).get("generations") or [] for v in g.get("variants") or [] if v.get("id") == "INS-033/v1"]
    except (OSError, ValueError) as e:
        return False, f"evolution_ledger.json unreadable ({type(e).__name__}): INS-033/v1 cannot be verified"
    if len(ents) != 1:
        return False, f"INS-033/v1 appears {len(ents)} time(s) in the evolution ledger (need exactly 1)"
    sha, commit = ents[0].get("spec_sha256"), ents[0].get("ir_commit")
    prereg, code = f"{ir}/research/PREREG_INS-033.md", f"{ir}/ins033_floor_test.py"
    if not (sha and commit and os.path.exists(prereg) and os.path.exists(code)):
        return False, "the ledger entry lacks spec_sha256/ir_commit, or PREREG_INS-033.md / ins033_floor_test.py is missing"
    if sha not in open(prereg).read():
        return False, "PREREG_INS-033.md does not carry the ledger's spec_sha256"
    try:
        node = next(n for n in ast.parse(open(code).read()).body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "RULE" for t in n.targets))
        calc = hashlib.sha256(json.dumps(ast.literal_eval(node.value), sort_keys=True).encode()).hexdigest()
    except (StopIteration, ValueError, SyntaxError) as e:
        return False, f"RULE could not be read from ins033_floor_test.py ({type(e).__name__})"
    if calc != sha:
        return False, f"RULE hashes to {calc[:16]}, the ledger says {sha[:16]}: the rule was edited after registration"
    git = lambda *a: subprocess.run(["git", "-C", ir, *a], capture_output=True, text=True, timeout=30, env=dict(os.environ, DEVELOPER_DIR="/Library/Developer/CommandLineTools"))
    r = git("show", "-s", "--format=%cI", commit)
    if r.returncode != 0:
        return False, f"insider-radar has no commit {commit[:8]}"
    when = dt.datetime.fromisoformat(r.stdout.strip())
    if when >= dt.datetime(2026, 10, 15, 13, 30, tzinfo=dt.timezone.utc):
        return False, f"insider-radar {commit[:8]} was committed {when.isoformat()}, not before 2026-10-15 13:30 UTC (06:30 PT)"
    if git("merge-base", "--is-ancestor", commit, "origin/main").returncode != 0:
        return False, f"insider-radar {commit[:8]} is not on origin/main: committed but not pushed"
    if git("rev-parse", f"{commit}:research/PREREG_INS-033.md").stdout.strip() != git("hash-object", prereg).stdout.strip():
        return False, f"PREREG_INS-033.md has changed since the registered commit {commit[:8]}"
    return True, f"INS-033/v1: PREREG + RULE hash {sha[:16]} match the ledger; insider-radar {commit[:8]} committed {when.isoformat()} (before 06:30 PT 2026-10-15), on origin/main, PREREG unchanged since"


if __name__ == "__main__":
    print(check_ins033_preregistered())
