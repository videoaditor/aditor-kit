---
name: orchestrate
description: Use when a spec or plan exists and the user wants it built with sub-agents — "orchestrate this", "build all phases", "build this with sub-agents", "I'm away, build it through" — or when a build spans 2+ specs or 4+ tasks and should run unattended for hours without the user intervening.
---

# Orchestrate

**This session becomes the orchestrator: it writes the contract, dispatches, waits, judges and integrates. It does not type feature code.** Agents type. The orchestrator keeps the four things that decide whether parallel work is fast or a pile-up: the contract, the decisions, the lane cut, and the final verdict.

Announce at start: "Using the orchestrate skill — this session is now the orchestrator."

Proven run (Oct 2026): 3 specs → 29 agents → 1 PR, 1,904 tests green, ~4 h build, zero user input after "lets go". Rules below come from that run plus Japanese agent-team practitioners (Jun Ito, t_wada, mizchi, Classmethod, ZOZO) — see `sources.md`.

## When NOT to use

- No spec yet → write one first (Phase 0 checklist). A vague spec burns a night.
- One small task (<1 h, one file area) → just do it. Multi-agent costs many times the tokens of one session; use it when the work is worth more than the tokens.
- Exploration / "what should we build" → that's planning, not orchestration.

## Phase 0 — Gate (before any agent exists)

Read the spec, the repo's `CLAUDE.md`/`AGENTS.md`, and `git status` / `git log`. Stop and fix before Phase 1 if any is missing:

- [ ] Every task names its **files**, a **`Verified:`** command line, and the spec has a machine-checkable **`Done`** block + **Stop & escalate** section.
- [ ] **What is actually left?** Specs are often half-built. Check spec revisions, ROADMAP status, existing branches/PRs. Build only the remainder.
- [ ] **Whose work is in the dirty tree?** Uncommitted files may belong to another session. Never mix them in — branch or worktree off clean `origin`.
- [ ] Test baseline recorded (test count + typecheck) so "after" has something to compare to.
- [ ] **Target repo(s) known.** If the code lives in another repo than the spec, lanes get worktrees in *that* repo.
- [ ] **Time window known.** Note when the user returns; wrap-up (Phase 4) starts at ~80 % of it, done or not.

**Gate fails → three exits, pick one:**
1. **Product decisions are in the spec, only the task breakdown is missing** → write the plan yourself (`docs/superpowers/plans/<date>-<slug>.md`: tasks with files, `Verified:`, `Done`, Stop & escalate). An orchestrator-written plan is valid input.
2. **Nothing left to build** → don't invent work. Report "spec is built; open: X" and stop.
3. **A product decision is missing that you can't default safely** (money, customer-facing copy, irreversible data) → build what doesn't depend on it, report the decision as the ONE question.

## Phase 1 — Contract, decisions, lane cut (orchestrator does this itself)

1. **Ask the user ONE batched round** (AskUserQuestion, ≤4 questions) for decisions only they can make — **only if they're still there.** Already gone ("I'm away")? Don't ask; take the smallest reversible default and list it as a veto point in the report. After this point you never ask again.
2. **Write `DECISIONS.md`** next to the spec (template: `templates.md`): decisions verbatim, house rules, hard no's, and 5–7 *"if nothing fits, the owner would decide…"* rules. This file replaces asking the user mid-run.
3. **Write the contract** (`SCHEMA.md` or the interface section): exact public interfaces, types, names, table/column names, error taxonomy. Phase A = contract only, no implementation.
4. **Cut lanes by file ownership** — a table: lane → files it owns exclusively.
   - Shared-by-construction files (lockfile, DB migrations, barrel/index files, routing tables, config) get ONE owner or happen only in the contract/integration phase. Number migrations per lane up front (A=0001, B=0002…).
   - Dependent lanes wait; independent lanes run in parallel. "B and C read A's tables" → A alone first, then B ∥ C from A's pushed branch.
   - Max **3 parallel lanes** — the limit is your routing capacity, not the machine.
   - Tasks share the same few files? Then they're sequential in ONE lane. One lane is a fine answer.
5. **Commit + push** spec, contract and DECISIONS to a feature branch (never `main`) before spawning. Agents branch from that SHA.

## Phase 2 — Topology

```
orchestrator (this session — contract, dispatch, judge, integrate)
└─ lane agent per spec   general-purpose · isolation:"worktree" · run_in_background · named
   ├─ implementer per task   general-purpose · foreground · test-first · 1 commit
   └─ reviewer per task      superpowers:code-reviewer (fallback: general-purpose, told read-only)
```

- **One spec only?** Skip the lane level — this session is the lane and spawns implementer/reviewer directly.
- **Model routing:** strongest model implements; a cheaper model (e.g. Sonnet) can review and explore. Set it explicitly — teammates default to the expensive one.
- Lane agent first writes a short **design note** (module layout, exact signatures) and may pre-write task prompts to files, so later implementer prompts are just "your brief is in `<file>`".

## Phase 3 — The per-task loop (inside each lane)

```
implement (test-first, 1 commit, no push)
  → review (separate agent, read-only, vs spec + contract + checklist → Critical/Important/Minor with file:line + fix)
  → fix (SendMessage to the SAME implementer — it keeps its context)
  → lane runs the task's Verified: commands ITSELF (never trusts reported numbers)
  → push after every task (a network drop must lose nothing)
```

- Fix all Critical + Important. Minor = optional. One review round is the norm; a 2nd only if a fix touched new logic.
- **3 attempts per task, then stop it**: mark `not-done` + diagnosis in the report, continue other tasks.
- Same task fails review twice for the same reason → the spec is unclear, not the agent. Drop that task back to one focused session; give the agent a *narrower* job, not a louder instruction.

## Prompts — what every agent prompt contains

Full copy-paste templates (lane, implementer, reviewer, fix, resume): `templates.md`. Non-negotiable parts:

- **Objective + "work unattended, nobody answers questions — decide per DECISIONS.md, log `Decision: X because Y`".**
- **Read-first list in order** (CLAUDE.md, contract, spec task, design note, one house-style example file).
- **Scope = only this task**, owned files listed, *"report any file you touch outside them"*.
- **Prohibitions, not preferences** (prohibitions survive summarization):
  never bypass hooks / `--no-verify` · never skip, delete or edit existing tests to pass · never widen a lint/architecture rule to silence an error · never add a dependency or migration you don't own · never deploy, send, pay, merge, set secrets or write remote data (lead-only) · **contract wrong? stop and report — never patch the contract.**
- **Git as plain single commands** (no `git -C`, variables, pipes) — worktree guards refuse complex forms.
- **Verification commands with expected numbers** ("expect 88 files, 1532 + new tests").
- **Final answer ≤300 words**: SHA, files, signatures, verification numbers, decisions, blockers. Details go into a report file, not into your context.
- Use precise terms instead of paragraphs (*idempotent, bounded context, invariant, pure function, deny by default*) and state rules, not names ("write the failing test first", not "do it like t_wada").

## Orchestrator conduct

- **Dispatch → wait → judge → ship.** Wait on task notifications; don't poll with sleep loops; post one-line status updates.
- **Context hygiene:** read lane reports, not whole diffs. Spot-check seams and run the tests yourself.
- **Open questions from agents:** answer from DECISIONS.md, apply, and record under *"Taste questions — answered by orchestrator (veto anytime)"* in the final report.
- **Crash / network drop:** inspect the worktree (`git status`, `git log`), then SendMessage the lane its exact state ("T1 committed abc123, T2 diff uncommitted in files X — inspect, test, finish, continue"). If it can't resume, spawn a fresh agent with that state summary.
- **Side issues** (a bug, a leaked token) → `spawn_task` / separate session. Never widen a lane.
- Permission denied on a check → don't route around it; turn it into a manual step for the user.

## Phase 4 — Integrate, verify, report

1. Integration branch from the dependency tip; merge lanes in order; merge `origin/main`.
2. Predict conflicts before merging: `comm -12 <(git diff --name-only main...lane-a | sort) <(git diff --name-only main...lane-b | sort)` — empty = any order is safe.
3. **Check the seams**: does C read exactly what B writes? Contract tests across lanes.
4. Full suite + typecheck vs the Phase 0 baseline; every `Done` check with its real output. **UI touched?** Screenshot it (desktop + mobile) via the preview/browser tool and look at it before calling it done.
5. **One PR.** If merging = going live, don't merge.
6. Report file `reviews/<date>-<slug>.md`: what works now (table), verification baseline → after, decisions taken, taste answers, manual steps as one copy-paste block with exact links, and ONE next action for the user.

## Red flags — you are drifting

| Thought | Reality |
|---|---|
| "I'll just fix this quickly myself" | Fine for an integration seam. Feature code → an implementer. You are the judge; judges who type miss their own bugs. |
| "The agent reported tests pass" | Run them. Reports are claims. |
| "They'll figure out the file overlap" | They won't. No ownership table = merge conflicts at hour 4. |
| "More agents = faster" | Undesigned parallelism jams. If you can't say in one line why a lane exists, cut it. |
| "Quick question to the user mid-run" | The user is away. DECISIONS.md + default to the smaller, reversible option. |
| "The reviewer can just fix it" | Builder and breaker stay separate heads. Reviewer reports; implementer fixes. |
| "Contract is slightly off, the agent adjusted it" | A contract edited mid-flight is a collision no file list predicts. Stop, decide, restart affected lanes. |
| "Spec is clear enough, let's go" | Every hour of build is bought with minutes of spec. Run Phase 0. |
| "One review at the end is enough" | Per-task review catches bugs while the implementer still holds the context. End-only review = rework across files. |
| "The change is tiny, skip the design note / overlap check" | Skip them only with a single lane. With 2+ lanes they are the whole point. |
| "Most of it is built, I'll find something to do" | Exit 2: report what's built and what's open. Invented work is waste with a PR attached. |
