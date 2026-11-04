---
name: nightshift
description: Use when the user wants work done unattended — "nightshift", "build this while I sleep", "work on the roadmap tonight", before stepping away for hours. Picks the items marked ready, builds and verifies each one, and ends in one pull request plus a short report for the morning review.
---

# Nightshift

You work alone while the user is away. Morning = one pull request they can judge in five minutes.

## 1. What to build

- Read `CLAUDE.md`, `AGENTS.md` and `ROADMAP.md` (or the file the user names).
- Build only items explicitly marked ready (a `## Ready` section, status `ready`, or `#ready`). Unticked checkboxes are NOT a go.
- No ready item? Write a proposal instead (max 5 items: title, 2–3 sentences scope, open questions) to `reviews/<date>-proposal.md` and stop. No building without an approved roadmap.
- Big item (4+ tasks or several areas)? Use the `orchestrate` skill. Long wish list? Put it in `PROMISES.md` (`promise-loop` skill).

## 2. How to build

- New branch per night, never commit to `main`.
- Each item: write the failing test or the check first, build, run the check yourself. Never report a skipped check as passed.
- 3 attempts per item, then mark it `not done` with a diagnosis and take the next one.
- Taste or product decision open → don't guess. Write it down as a question for the morning.

## 3. Never

Force-push, commits on `main`, deploys, sending anything, spending money, deleting other branches, dependency upgrades nobody asked for.

## 4. Morning hand-over

Pull request body, in this order:
1. Demo link or screenshots first.
2. Three sentences: what and why.
3. Open questions for the user, one line each, your recommendation first.
4. The full report only inside `<details>`, plus `reviews/<date>-<slug>.md` in the branch.

No remote to push to? Same report into `reviews/`, leave the branch local, and say so.
