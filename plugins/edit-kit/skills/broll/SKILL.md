---
name: broll
description: Use when an editor wants a talking head or rough cut finished — b-roll on the words, split screens, before/after, the speaker cut out over b-roll (green-screen look), captions, sound effects. Triggers: "put b-roll on it", "finish it", "b-roll drauf", "split screen", "green screen", "freistellen", "captions", "SFX".
---

# broll (compose)

Script: `<base dir>/br.py` (`<base dir>` = this skill's folder). Works on a job from `rough-cut` (`$JOB/rough.mp4` + `$JOB/rough/words.json`). Any other talking head: first `python3 <rough-cut base dir>/rc.py words TH.mp4 $JOB/rough`. Uses only macOS frameworks (a Swift helper compiles itself on first use).

## 0. Read the brief first
If the editor gives a script or brief, its markers win over your own taste: `[SPLIT SCREEN: …]` → `split`/`compare`, "green screen" / "speaker over …" → `cutout`, sound-design notes → `sfx.json`. Quote each marker you followed in the report.

## 1. Look at the clips
`python3 <base dir>/br.py frames BROLL_DIR $JOB`, then **Read every `$JOB/broll/<id>.jpg`** (3 frames per clip) and `$JOB/broll.json` (durations). Note per clip what it shows and its bucket: `pain`, `product`, `application`, `result`.

## 2. Proofread the words (captions come from them)
Read `$JOB/rough/transcript.txt`. Whisper mishears brand names and rare words ("wear and tager"). Fix the `w` field in `$JOB/rough/words.json` (spelling only, never `t`/`d`), from the script or brand name if given. Add `"hl": true` to the words that should pop (pain words, numbers, product name).

## 3. Write `$JOB/edl.json`: shots on words
`{"from": 12, "to": 18, "layout": "full", "clip": "03", "src_in": 0.0}` covers words 12–18 and runs until word 19 starts.

| layout | what | when |
|---|---|---|
| `full` | b-roll fills the frame | showing what is said |
| `split` | b-roll top, speaker bottom (left/right on 16:9) | explaining while showing; keeps the face |
| `compare` | `clip` top vs `clip2` bottom | before/after, problem vs solution, old vs new |
| `cutout` | speaker cut out, over the b-roll | green-screen look; the speaker stands in the scene |

`cutout` options: `"scale"` 0.4–1.0 (default 0.62; 1.0 = full-size background swap), `"place"` `auto|left|right|center`. `auto` finds what the eye goes to in the b-roll and puts the speaker on the other side; the body always sits on the bottom edge.

Rhythm (house rules): every shot **at least 1 s** (the script refuses shorter ones: widen the word range); something new every ~1.5 s; 60–70 % covered; face on the hook's first words and on the call to action. Speaker gaps under 1 s between shots close automatically (no flash frames). A calm clip over ~2.5 s fails reel-qc's static check: split it over two clips. No clip twice in a row; the clip must be at least as long as the shot.

## 4. Sound effects (optional): `$JOB/sfx.json`
`[{"word": 2, "file": "Suspense:Hits/Sub Stress Boom sfx.wav", "db": -10}]`, files under `~/aditor-edits/sfx/` (one folder per kind; list it to see what exists). Hits/booms on pain words, whooshes on layout changes, pops on product or price reveals, risers into the payoff. Sparse: 5–8 per 45 s. The voice keeps its timing; the mix is normalised to −14 LUFS.

## 5. Captions: pick the look by niche
Reverse-engineered from 39 long-running winning ads in 5 niches. `--captions <style>`:

| style | look | default for |
|---|---|---|
| `highlight` | CAPS, heavy, thin outline, one key word on a colour block | health, supplements, telehealth/medical (DR) |
| `native` | TikTok-native, sentence case, semibold, soft shadow, 4–7 words | beauty, home, fashion, creator UGC |
| `boxed` | black on white bubble per line | native UGC; also the `--hook` line |
| `editorial` | serif, sentence case | premium brands, doctors, testimonials |
| `pop` | one big word, shadow | fast montage passages |

`--accent "#FFD60A"` sets the highlight colour (brand colour; yellow and purple are the most common in winners). Mark the key word yourself with `"hl": true` on a word in `rough/words.json` (pain word, number, product name); otherwise a number or the longest meaningful word is taken. `--hook "Every Man Over 40 Needs to Hear This"` pins the hook as a boxed line at the top for the whole ad (common in health winners). Captions sit on the seam in split/compare and on the chest of a small cutout.

## 6. Render and look
`python3 <base dir>/br.py render $JOB/rough.mp4 $JOB --captions highlight` → `$JOB/final.mp4`, 1080×1920 (or 1920×1080) at 30 fps.
Then take frames at 4–6 shot times (`ffmpeg -ss T -i $JOB/final.mp4 -frames:v 1 -vf scale=-2:640 /tmp/x.jpg`) and Read them. Speaker covering the b-roll's subject, caption over a face, clip not matching its words → change edl.json, render again.

## 7. Hand-off
`reel-qc` on `final.mp4` (vertical), then `autoreview` (aditor-kit). Report: shots per layout, coverage, SFX count, one line per shot ("05 cutout over medicine cabinet on 'raw material'").
