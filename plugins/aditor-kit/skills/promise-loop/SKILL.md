---
name: promise-loop
description: Use when the user states goals, wishes or requirements that must not get lost — a long list "before the night", "build it all until it's done", "don't forget this", "promise loop" — and whenever the Stop hook says "Promise Loop". Tracks every promise in PROMISES.md and keeps the session working through open items until each one is done with proof.
---

# Promise Loop

Ideas die in the session context. `PROMISES.md` is the memory, the Stop hook is the guard: while the file has open items, the session is not allowed to stop.

The guard only runs where a `PROMISES.md` exists (repo root or current folder). No file, no loop.

## 1. Write it down

The user names a goal, wish or requirement → one line in `PROMISES.md`, right away. Short, in their words, their intent, not your reinterpretation.

```markdown
# Promises
max-rounds: 8
<!-- promise-loop: off   ← this line without the comment = guard off -->

- [ ] Magic-link login
- [~] CSV export — running, spec docs/specs/…
- [x] Dark mode — Proof: screenshot /tmp/…png, test_theme green
- [?] Pricing page — Question: $29 or $39? (my pick: $29)
```

Status: `[ ]` open · `[~]` running · `[x]` done with proof · `[?]` waiting for the user. Only `[ ]` and `[~]` keep the session going.

## 2. Every round (when the hook blocks)

1. **Sweep** (first round only): read the whole session for wishes that are missing → add them.
2. Take the next open item. Read any context that already exists (spec, PR, roadmap) first.
3. Big? → write a short spec, then `orchestrate` with sub-agents. Small? → build it directly.
4. Tick it only with `Proof:` — test output, a screenshot you looked at, a live URL. "I did it" is not proof.

## 3. Decide open questions yourself

Before asking the user, look in `CLAUDE.md`, `AGENTS.md`, the roadmap and earlier decisions. Estimate how likely the user would decide the same way:

- **≥ 80 %** → decide, keep building, note it in the line: `Assumed: X (85 %, source: CLAUDE.md) — reversible`.
- **< 80 %** → `[?]` with the question and your recommendation, take the next item. Never block.

## 4. Brakes (never break these)

- Irreversible or outward-facing (deploy, push to main, send mail or messages, money, delete) → never on your own. `[?]` plus the ready-to-run command.
- No progress possible → `[?]` with the reason instead of going in circles. The hook lets go after 2 rounds without a change to `PROMISES.md`, and after `max-rounds`.
- Never invent new wishes. Only what the user said or what follows directly from it.

## 5. Hand-over

When nothing is open, end with ONE block for the user: done (with proof links) · assumed (reversible) · `[?]` questions, one line each, your recommendation first.
