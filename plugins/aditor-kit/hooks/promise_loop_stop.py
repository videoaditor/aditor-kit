#!/usr/bin/env python3
"""Promise Loop — Stop hook. Blocks the session from stopping while PROMISES.md has open items.

Opt-in per project: does nothing unless PROMISES.md exists in cwd or the git root.
Brakes: max rounds per session, stall detection (file unchanged), `promise-loop: off`.
Run with --selftest for the check.
"""
import hashlib, json, os, re, subprocess, sys

STATE_DIR = os.path.expanduser("~/.claude/promise-loop")
DEFAULT_MAX = 8
STALL_LIMIT = 2  # blocks in a row without any change to PROMISES.md -> let it stop


def find_promises(cwd):
    roots = [cwd]
    try:
        top = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        if top:
            roots.append(top)
    except Exception:
        pass
    for r in roots:
        p = os.path.join(r, "PROMISES.md")
        if os.path.isfile(p):
            return p
    return None


def decide(text, state):
    """Pure decision. Returns (reason or None, new_state)."""
    if re.search(r"^promise-loop:\s*off\b", text, re.M | re.I):
        return None, state
    m = re.search(r"^max-rounds:\s*(\d+)", text, re.M | re.I)
    max_rounds = int(m.group(1)) if m else DEFAULT_MAX
    open_items = re.findall(r"^\s*- \[[ ~]\] (.+)$", text, re.M)
    digest = hashlib.md5(text.encode()).hexdigest()

    rounds = state.get("rounds", 0)
    stall = state.get("stall", 0) + 1 if digest == state.get("hash") else 0
    if rounds >= max_rounds or stall >= STALL_LIMIT:
        return None, state

    swept = state.get("swept", False)
    if swept and not open_items:
        return None, state

    new = {"rounds": rounds + 1, "stall": stall, "hash": digest, "swept": True}
    head = f"Promise Loop (round {rounds + 1}/{max_rounds}) — follow the `promise-loop` skill."
    if not swept:
        body = ("SWEEP first: read this whole session and add every goal or wish of the user "
                "that is not in PROMISES.md yet as `- [ ]`. Then continue with the next open item.")
    else:
        body = ("Still open:\n" + "\n".join(f"- {i}" for i in open_items[:5])
                + (f"\n…and {len(open_items) - 5} more" if len(open_items) > 5 else ""))
    tail = ("\nTake the next item and work it until you have proof. If it can't move without the user "
            "(a question you can't answer with 80 % confidence, or an irreversible action), mark it `- [?]` with the reason and take the next one. "
            "Only tick an item with `Proof:`.")
    return f"{head}\n{body}{tail}", new


def main():
    data = json.load(sys.stdin)
    path = find_promises(data.get("cwd") or os.getcwd())
    if not path:
        return
    os.makedirs(STATE_DIR, exist_ok=True)
    sf = os.path.join(STATE_DIR, f"{data.get('session_id', 'x')}.json")
    try:
        state = json.load(open(sf))
    except Exception:
        state = {}
    reason, new = decide(open(path, encoding="utf-8").read(), state)
    if reason:
        json.dump(new, open(sf, "w"))
        print(json.dumps({"decision": "block", "reason": f"[{path}]\n{reason}"}))


def selftest():
    f = "# P\n- [ ] A\n- [~] B\n- [x] C — Beweis: ok\n- [?] D — Frage\n"
    r, s = decide(f, {})
    assert r and "SWEEP" in r and s["rounds"] == 1
    r, s2 = decide(f + "- [ ] E\n", s)
    assert r and "- A" in r and "- B" in r and "- E" in r and "- C" not in r and "- D" not in r
    r, s3 = decide(f + "- [ ] E\n", s2)  # unchanged once -> still blocks
    assert r and s3["stall"] == 1
    assert decide(f + "- [ ] E\n", s3)[0] is None  # stalled twice -> stop
    assert decide("- [x] A — Beweis: y\n", s)[0] is None  # all done after sweep
    assert decide(f + "promise-loop: off\n", {})[0] is None
    assert decide(f + "max-rounds: 1\n", {"rounds": 1, "swept": True})[0] is None
    print("selftest ok")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else main()
