# AI Builder Starter Kit for Claude Code

For people who build with AI: what we run every day at Aditor, in one install. Claude plans, builds in parallel, keeps working while you're away, learns from every correction, and hands finished work to a human reviewer.

| Piece | What it does |
|---|---|
| `/orchestrate` | One session becomes the lead. It cuts a spec into lanes, runs sub-agents in parallel (build → review → fix → verify per task) and hands you one PR. |
| `/nightshift` | Builds the roadmap items marked ready while you're away. Morning: one PR you can judge in five minutes. |
| `/promise-loop` | Write goals into `PROMISES.md`. The session won't stop until every one is done with proof. |
| `autoreview` | Hands finished videos to a human on AutoReview and fixes them until approved. Type `Pair with AutoReview: CODE` once (code from the brand's project); after that every upload lands with that brand, the key sits in the macOS Keychain, and the session wakes up by itself when the reviewer presses Send. |
| `reel-qc` | Checks a vertical reel before it goes out: format, loudness, black frames, frozen stretches, lip-sync, transcript vs script, contact sheet. A FAIL blocks the upload. Needs `ffmpeg`; the script check also `whisper-cpp`. |
| Auto-learn | Whenever you correct Claude ("no, never…", "always…"), it writes the rule into `CLAUDE.md` before it stops. Every mistake becomes a rule, without you doing anything. |

## Install

Open Claude Code and paste these two lines, one after the other:

```
/plugin marketplace add videoaditor/aditor-kit
/plugin install aditor-kit@aditor
```

Restart Claude Code. Done. Auto-learn is on from now on. The skills show up when you type `/`.

Needs `python3` (preinstalled on every Mac). Orchestrate works best with the `superpowers` plugin installed.

## Turn things off

- Promise loop: only runs in folders that have a `PROMISES.md`.
- Everything: `/plugin disable aditor-kit@aditor`.
