# Aditor Kit for Claude Code

What we run every day at Aditor, in one install.

| Piece | What it does |
|---|---|
| `/orchestrate` | One session becomes the lead. It cuts a spec into lanes, runs sub-agents in parallel (build → review → fix → verify per task) and hands you one PR. |
| `/nightshift` | Builds the roadmap items marked ready while you're away. Morning: one PR you can judge in five minutes. |
| `/promise-loop` | Write goals into `PROMISES.md`. The session won't stop until every one is done with proof. |
| Auto-learn | Whenever you correct Claude ("no, never…", "always…"), it writes the rule into `CLAUDE.md` before it stops. Every mistake becomes a rule, without you doing anything. |

## Install

Open Claude Code and paste these two lines, one after the other:

```
/plugin marketplace add aditor/aditor-kit
/plugin install aditor-kit@aditor
```

Restart Claude Code. Done. Auto-learn is on from now on. The skills show up when you type `/`.

Needs `python3` (preinstalled on every Mac). Orchestrate works best with the `superpowers` plugin installed.

## Turn things off

- Promise loop: only runs in folders that have a `PROMISES.md`.
- Everything: `/plugin disable aditor-kit@aditor`.
