---
name: broll
description: Use when an editor wants b-roll placed over a talking head or rough cut — "put b-roll on it", "b-roll drauf", "place these clips", "cover the cuts" — with a folder of b-roll clips.
---

# broll

Script next to this file: `<base dir>/br.py`. Works on a job from `rough-cut` (`$JOB/rough.mp4` + `$JOB/rough/words.json`). For any other talking head first run `python3 <rough-cut base dir>/rc.py words TH.mp4 $JOB/rough`.

1. **Look at the clips:** `python3 <base dir>/br.py frames BROLL_DIR $JOB`, then **Read every `$JOB/broll/<id>.jpg`** (3 frames per clip) and `$JOB/broll.json` (durations). Note per clip, for yourself: what it shows, and its bucket: `pain` (the problem), `product`, `application` (product in use), `result` (after).
2. **Place clips on words.** Read `$JOB/rough/transcript.txt`. Write `$JOB/edl.json`:
   `[{"clip": "03", "from": 12, "to": 18, "src_in": 0.0}]` — the clip covers words 12–18; `src_in` = seconds into the clip.
   - The clip must show what is said in that span (pain on the problem, product on its name, result on the promise).
   - 1–2 s per insert, something new every ~1.5 s, 60–70 % coverage. A sentence of 2 s+ gets two clips, not one (Alan 07.11.: "cut frequency higher"). Keep the face on the hook's first words and on the call to action.
   - A calm clip (person barely moving) longer than ~2.5 s fails reel-qc's static check: split the span over two clips.
   - No clip twice in a row; no overlaps; a clip must be at least as long as its span (the script refuses otherwise).
3. **Render:** `python3 <base dir>/br.py render $JOB/rough.mp4 $JOB` → `$JOB/broll.mp4`. Full-frame, voice copied bit-for-bit; it fails loudly on sync drift.
4. **Look at it:** take frames at 3–4 insert times (`ffmpeg -ss T -i $JOB/broll.mp4 -frames:v 1 /tmp/x.jpg`) and Read them; a clip that doesn't match its words → change edl.json, render again.
5. Report: number of inserts, coverage, one line per insert ("02 product shot on 'this serum'"). Next: `reel-qc` (vertical) then `autoreview` (aditor-kit).
