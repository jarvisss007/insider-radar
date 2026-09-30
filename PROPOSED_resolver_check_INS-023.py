#!/usr/bin/env python3
"""PROPOSED — NOT APPLIED. A resolver check for INS-023 (prereg-reviewer: APPROVE option (x), 2026-09-29).

A patch proposal for ~/command-center/council/resolver.py, deliberately NOT applied: resolver.py and
council/issues.json are owned by another session. To adopt, paste the function into resolver.py and register it,
e.g.   CHECKS.update({"insider_step2_check_date_text": check_insider_step2_check_date_text})

INS-023 corrected insider AGENT.md step 2: "`check_date` is never rewritten." contradicted the SESSION-001 /
write-time roll of a non-session check_date. The corrected text says check_date is never rewritten BY THIS
SUBSTITUTION (the INS-012 missing-bar roll-forward) and names the one exception (a non-session check_date,
rolled at write time by stale_quote.append_call or, as a backstop, by the grader under SESSION-001). The check
holds the text: both phrases present, the old bare sentence gone, and the survivorship sentence kept verbatim.

Returns (ok: bool, evidence: str). Standalone run prints the current result, read-only:
    /opt/anaconda3/bin/python ~/insider-radar/PROPOSED_resolver_check_INS-023.py
"""
import os

HOME = os.path.expanduser("~")
_AGENT = f"{HOME}/insider-radar/agent/AGENT.md"
_SURVIVORSHIP_SENTENCE = ("A delisted or unfetchable ticker is scored `wrong` — clusters in stocks that vanish are "
                          "part of the signal's real-world record.")


def check_insider_step2_check_date_text():
    """INS-023: insider AGENT.md step 2 says check_date is never rewritten *by this substitution* and names the
    SESSION-001 non-session exception; the survivorship sentence survives verbatim."""
    if not os.path.exists(_AGENT):
        return False, "insider-radar/agent/AGENT.md missing"
    t = open(_AGENT).read()
    i = t.find("2. **Score due calls")
    j = t.find("3. **Update lessons**", i)
    if i < 0 or j <= i:
        return False, "AGENT.md step 2 ('2. **Score due calls' .. '3. **Update lessons**') not found — cannot verify"
    s2 = t[i:j]
    bad = []
    if "by this substitution" not in s2:
        bad.append("step 2 lacks 'by this substitution' (INS-023)")
    if "SESSION-001" not in s2:
        bad.append("step 2 does not name the SESSION-001 non-session exception (INS-023)")
    if "`check_date` is never rewritten." in s2:
        bad.append("step 2 still carries the bare '`check_date` is never rewritten.' that INS-023 corrected")
    if _SURVIVORSHIP_SENTENCE not in s2:
        bad.append("step 2 lost the survivorship sentence verbatim")
    if bad:
        return False, "; ".join(bad)
    return True, ("step 2: check_date never rewritten 'by this substitution', SESSION-001 non-session exception named, "
                  "survivorship sentence verbatim")


if __name__ == "__main__":
    print(check_insider_step2_check_date_text())
