---
name: edit
description: Use when an editor wants to set up their editing workspace, cut a raw talking head or finish it with b-roll. Triggers: "set up my workspace", "install the edit kit", "einrichten", "cut this", "rough cut", "tighten", "schneid das", "Rohschnitt", "put b-roll on it", "finish it", "b-roll drauf", "split screen", "green screen", "freistellen", "captions", "SFX". Loads the Edit Kit from Gen (gen.aditor.ai) and follows its skills.
---

# edit (loader)

The skills, scripts and house rules live in Gen and are loaded here. Cutting, transcription and rendering then run on this machine. `<load>` = `${CLAUDE_SKILL_DIR}` (this skill's folder, where `load.py` sits). The cache is `~/.cache/aditor-edit-kit/`.

**Hard stop rule.** Every step below must succeed in this run. If one does not (tool missing, error, 401, no network, `load.py` exits non-zero), STOP, show the message verbatim and do nothing else. Never read or use `~/.cache/aditor-edit-kit/` after a failure: an old cache means old rules.

## 1. Gen connected?
Call the Gen tool `whoami`. If the tool does not exist or fails, stop and tell the editor: open https://gen.aditor.ai, click **Connect Claude**, paste the command into a terminal, restart Claude Code.

## 2. Load the kit
1. `python3 <load>/load.py version` prints the cached version (empty the first time).
2. Call the Gen tool `edit_kit` with `have` = that version (leave `have` out when empty).
3. Answer `{version, current: true}`: run `python3 <load>/load.py write -` with that answer on stdin, it must exit 0 (it checks the cache really has that version).
4. Answer with `files`: write the answer verbatim to a temp file (absolute path, e.g. `$HOME/aditor-edit-kit.bundle.json`) or, if the tool result was saved to a file, use that file. Run `python3 <load>/load.py write <that file>`. It checks the paths and replaces the cache in one step. Delete your temp file afterwards.
5. Step 2 is done only when `load.py write` printed `written` or `current` and exited 0.

## 3. Rules, for every job
A job is each new cut or finish request. Call the Gen tool `edit_rules` (with `brand` and `card` when the editor names them) and follow it; it is always fetched fresh, never cached. Its `script` is the briefing: the markers in it are binding. If it fails, stop.

## 4. Follow the skill (only after step 2 succeeded in this run)
Read `~/.cache/aditor-edit-kit/skills/<skill>/SKILL.md` and follow it; its `<base dir>` is `~/.cache/aditor-edit-kit/skills/<skill>/`.
- workspace, install, "set up my workspace": `edit-setup`
- raw talking head, "cut this": `rough-cut`
- "finish it", b-roll, split screen, cutout, captions, SFX: `broll`
- `gen-session`: works with the editor's Telegram session, only if the editor asks for it.
