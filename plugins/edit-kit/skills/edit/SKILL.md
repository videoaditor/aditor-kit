---
name: edit
description: Use when an editor wants to set up their editing workspace, cut a raw talking head or finish it with b-roll. Triggers: "set up my workspace", "install the edit kit", "einrichten", "cut this", "rough cut", "tighten", "schneid das", "Rohschnitt", "put b-roll on it", "finish it", "b-roll drauf", "split screen", "green screen", "freistellen", "captions", "SFX". Loads the Edit Kit from Gen (gen.aditor.ai) and follows its skills.
---

# edit (loader)

The skills, scripts and house rules live in Gen and are loaded here. Cutting, transcription and rendering then run on this machine. Cache: `~/.cache/aditor-edit-kit/`. `<load>` = this skill's folder, `load.py` sits in it.

## 1. Gen connected?
Call the Gen tool `whoami`. If the tool does not exist or fails with 401, stop and tell the editor: open https://gen.aditor.ai, click **Connect Claude**, paste the command into a terminal, restart Claude Code. Do not continue.

## 2. Load the kit
1. `python3 <load>/load.py version` prints the cached version (empty the first time).
2. Call the Gen tool `edit_kit` with `have` = that version (leave `have` out when empty).
3. Answer `{version, current: true}`: the cache is up to date, go on.
4. Answer with `files`: save the answer as JSON to `~/.cache/aditor-edit-kit.bundle.json`, then run `python3 <load>/load.py write ~/.cache/aditor-edit-kit.bundle.json`. It checks the paths and replaces the cache in one step.
5. `edit_kit_not_enabled`, 401 or no network: stop, show the message as it is. Never work from the old cache then.

## 3. Rules, once per job
Call the Gen tool `edit_rules` (with `brand` and `card` when the editor names them) and follow it. Its `script` is the briefing: the markers in it are binding.

## 4. Follow the skill
Read `~/.cache/aditor-edit-kit/skills/<skill>/SKILL.md` and follow it; its `<base dir>` is `~/.cache/aditor-edit-kit/skills/<skill>/`.
- workspace, install, "set up my workspace": `edit-setup`
- raw talking head, "cut this": `rough-cut`
- "finish it", b-roll, split screen, cutout, captions, SFX: `broll`
- `gen-session`: works with the editor's Telegram session, only if the editor asks for it.
