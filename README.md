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

---

# Agentic Editing Kit (`edit-kit`)

For video editors. Drop raw footage into Claude Code, get a tight rough cut with b-roll on the right words, checked and ready for review. No API keys: Claude makes the editing calls, Whisper runs on your Mac.

| Piece | What it does |
|---|---|
| `edit-setup` | Say "set up my workspace". Installs ffmpeg, whisper-cpp and the speech model, creates `~/aditor-edits/` with the house editing rules, checks the Gen connection. |
| `rough-cut` | Drag in a raw talking head, say "cut this". Claude reads the word-level transcript, removes false starts, stutters, retakes and empty sentences, shrinks every pause, speeds up 1.15× (lessons 1.1×), normalises to −14 LUFS, then re-transcribes the result to prove nothing doubled is left. |
| `broll` | Drag in a folder of clips, say "put b-roll on it". Claude looks at every clip, places each on the words it matches, renders full-frame at 1080×1920/30 fps with the voice untouched. |

QC (`reel-qc`) and delivery (`autoreview`) come from `aditor-kit`, so install both:

```
/plugin marketplace add videoaditor/aditor-kit
/plugin install aditor-kit@aditor
/plugin install edit-kit@aditor
```

Restart Claude Code, then say **"set up my workspace"**. macOS only for now. Homebrew must be installed (the setup tells you the one command if it isn't).
