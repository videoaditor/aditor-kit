#!/usr/bin/env python3
"""Auto-learn — every correction becomes a rule in CLAUDE.md.

`learn.py capture` (UserPromptSubmit): a prompt that sounds like a correction is queued for this session.
`learn.py stop` (Stop): queued corrections -> block once and have Claude write them as rules, then clear.
Run with --selftest for the check.
"""
import json, os, re, sys

QUEUE_DIR = os.path.expanduser("~/.claude/aditor-kit/learn")
MAX_RULES = 30

# ponytail: keyword heuristic, Claude itself filters out what isn't a lasting rule
CORRECTION = re.compile(
    r"\b(no|nope|wrong|don'?t|do not|never|always|stop|instead|not like that|i told you|again|"
    r"nein|falsch|nicht so|nie|immer|stattdessen|lass das|hör auf|hab doch gesagt|schon wieder|bitte nicht)\b",
    re.I)


def is_correction(prompt):
    return bool(CORRECTION.search(prompt or ""))


def reason_for(items):
    lines = "\n".join(f"- “{i}”" for i in items)
    return (
        "Auto-learn: the user said this in this session, it may be a correction:\n"
        f"{lines}\n\n"
        "For each one that is a lasting rule (how you should work, a preference, an always/never), add ONE line "
        "under `## Learned rules` in the right CLAUDE.md: about this project -> CLAUDE.md in the repo root; "
        "about how the user works in general -> ~/.claude/CLAUDE.md. Format: `- <rule> — why: <reason>`. "
        "Skip one-off instructions. No duplicates; if a new rule contradicts an old one, replace the old one. "
        f"If the section has more than {MAX_RULES} rules, merge similar ones. "
        "Then end your turn with one line naming the rule you added, or nothing if none qualified."
    )


def queue_path(session_id):
    return os.path.join(QUEUE_DIR, f"{session_id or 'x'}.jsonl")


def capture(data):
    prompt = (data.get("prompt") or "").strip()
    if not is_correction(prompt):
        return
    os.makedirs(QUEUE_DIR, exist_ok=True)
    with open(queue_path(data.get("session_id")), "a", encoding="utf-8") as f:
        f.write(json.dumps(prompt[:500]) + "\n")


def stop(data):
    p = queue_path(data.get("session_id"))
    if not os.path.isfile(p):
        return
    items = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    os.remove(p)  # consumed: the next stop goes through
    if items:
        print(json.dumps({"decision": "block", "reason": reason_for(items[-10:])}))


def selftest():
    assert is_correction("Nein, nicht so — mach die Hooks kürzer")
    assert is_correction("don't use the Desktop folder")
    assert is_correction("always render 9:16")
    assert not is_correction("make me three hook variants for glow25")
    global QUEUE_DIR
    import io, tempfile, contextlib
    QUEUE_DIR = tempfile.mkdtemp()
    capture({"session_id": "s", "prompt": "make a cut"})
    assert not os.path.exists(queue_path("s"))
    capture({"session_id": "s", "prompt": "no, never use stock footage"})
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        stop({"session_id": "s"})
    r = json.loads(out.getvalue())
    assert r["decision"] == "block" and "stock footage" in r["reason"]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        stop({"session_id": "s"})
    assert out.getvalue() == ""  # queue consumed, no loop
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        {"capture": capture, "stop": stop}[sys.argv[1]](json.load(sys.stdin))
