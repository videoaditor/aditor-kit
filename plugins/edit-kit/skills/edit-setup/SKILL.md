---
name: edit-setup
description: Use when an editor wants to set up their editing workspace, says "set up my workspace", "install the edit kit", "einrichten", or when rough-cut / broll fail because ffmpeg, whisper-cli or the whisper model is missing.
---

# edit-setup

Run `bash <base dir>/setup.sh` (base dir = this skill's folder, shown when it loads). It takes 1–5 minutes the first time (model download ~550 MB). Every line starts with a status:

- `OK` — done.
- `NEEDS_EDITOR` (exit 2) — Homebrew is missing and needs the Mac password. Tell the editor to type `!` followed by the printed command into this chat, then run setup.sh again. Do not try to install Homebrew yourself.
- `TODO gen` — optional. Gen (gen.aditor.ai) makes AI shots. To connect: open gen.aditor.ai → **Connect Claude** → copy the command → paste it in a terminal, then restart Claude Code.
- `FAIL` — show the line, stop.

Afterwards tell the editor, in three lines:
1. The workspace is `~/aditor-edits/`. Start Claude Code there next time (`cd ~/aditor-edits && claude`) so the house rules in its `CLAUDE.md` apply.
2. Drag a raw talking-head video into the chat and say **"cut this"**.
3. Then drag a folder of b-roll clips in and say **"put b-roll on it"**.
