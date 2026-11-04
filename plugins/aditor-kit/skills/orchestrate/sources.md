# Where the rules come from

Read only if you want the "why". The skill works without it.

## Field run — "Newsletter system structure" (Oct 2026)
- 3 specs (CRM spine / call loop / ranked newsletter) → 3 lane agents in worktrees → 12 implementers + 11 reviewers. 29 agents, ~4 h 15 min build, 1 PR, 1,904 tests green (baseline 1,532), zero user input after kickoff.
- What made it work: specs with `Verified:` + `Done` blocks written first; `SCHEMA.md` as binding contract; `DECISIONS.md` with "what would the owner decide" rules instead of mid-run questions; dependency lane A first, then B ∥ C; migration numbers pre-assigned per lane; fix via SendMessage to the same implementer; lane verifies itself; integration + seam check by the orchestrator.
- What hurt: two network drops (ENOTFOUND) killed a lane mid-task → rule "push after every task" + resume-with-exact-state message. 72 worktree-guard refusals from `git -C`/variables/pipes → rule "git as plain single commands". A credential grep was refused → turn it into a manual step, never route around.

## Japanese agent-team practitioners
- **Jun Ito** (note.com, Feb 2026): Phase A = contract only → B1–B5 disjoint file sets in parallel → C integrate. Dependency checkers (dependency-cruiser / ArchUnit / import-linter) enforce boundaries. DDD vocabulary "functions as a shared language with the LLM". $809 in 2 days, 85 % input tokens → keep always-on context short. When output stops matching intent, drop from parallel back to one session.
- **Agent Teams video (Sura × Asura)**: Agent Teams buy collision-free parallelism, not fast parallelism. Separate the head that builds from the head that breaks; reviewer gets no edit rights. Grow team size only with a one-line reason per role.
- **Classmethod**: each teammate owns a directory exclusively; side effects (MCP sends) marked "Team Lead only"; set the teammate model explicitly. Supervision ceiling ≈ 3 agent-driven work streams per lead.
- **t_wada (Takuto Wada)**: TDD is the fence that keeps agents from running wild. Red agent writes failing tests → Green agent implements, may not edit tests → review agent.
- **laiso** control experiment: a named authority ("t-wada style") works only halfway and unreliably; a precise term works fully; an invented name not at all → write the rule, not the name.
- **mizchi**: global CLAUDE.md is one line; procedures live in skills. Precondition for scaling agents: lint, tests and docs exist and don't contradict each other.
- **Yuya Takeyama (LayerX)**: an agent that keeps drifting needs a narrower job, not a stronger instruction.
- **ZOZO**: adversarial review loops; resumable `/dev-init` + `/dev-resume` with progress files.
- **suna**: 2 worktrees, 11 PRs in under 2 h, zero conflicts — "isolation is largely solved; coordination remains."
- Contract-mutation rule, lockfile/migration rule and the `comm -12` overlap check: sound engineering added, not practitioner quotes.

## Loop doctrine
- Briefs need objective, output format, tool guidance and boundaries — vague briefs cause duplicate work and gaps.
- Expect specification gaming: agents satisfy the letter of a check. Treat the eval as the contract.
- Anthropic's multi-agent research system: +90 % quality at ~15× tokens → use when the work is worth the tokens.
- Unattended runs need an iteration cap, a heartbeat (silent ≠ healthy) and a tested stop.
