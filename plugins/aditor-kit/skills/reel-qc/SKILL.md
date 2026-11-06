---
name: reel-qc
description: Use before calling any reel/short video final or uploading it for review — runs the deterministic QC (format, loudness, black frames, static stretches, lip-sync/TH offset, transcript vs script, contact sheet) on a vertical talking-head reel.
---

# reel-qc

`qc.py` sits next to this file (the skill's base directory, shown when it loads). Needs `ffmpeg` (`brew install ffmpeg`); the script check also needs `whisper-cli` (`brew install whisper-cpp`) and the large-v3-turbo model at `~/.cache/whisper-cpp/ggml-large-v3-turbo-q5_0.bin` or `REEL_QC_WHISPER_MODEL`, else it is skipped with a WARN.

A FAIL blocks hand-off. Run it on **every** final (Hook A and B), after the last render, not on an older file.

```
python3 <base dir>/qc.py FINAL.mp4 [--th th_X.mp4] [--script SCRIPT.md] [--src REMOTION_SRC_DIR] [--out DIR]
```
`--th` = the raw talking-head file the reel was built from (enables lip-sync + exact pauses/outro). `--script` = SCRIPT.md with numbered quoted lines (`1. "text" — …`). `--src` = Remotion `src/` (static `startFrom` check). Default `--out` = `qc/` next to FINAL. Exit code 1 on any FAIL. Takes ~15 s.

## Reading the result
- **FAIL**: fix and re-render; never ship around it. Each row names timestamps.
- **WARN**: look at it; fix or explain in the hand-off (e.g. script lines not heard = wrong cut or masked word; "speech not in script" = leftover tail).
- Then **Read `<out>/sheet.jpg`** (1 fps contact sheet) and confirm: frame 0 is moving, finished content (not a frozen/blank frame), no stock man on a phone, captions on the seam, no watermark. The script cannot judge taste.

## README (decisions and thresholds)
- Format 1080×1920, 30 fps, audio. Loudness −14 ±0.5 LUFS, true peak ≤ −1.2 dBTP.
- Black: `blackdetect d≥0.1 s`.
- Static: 108×192 gray @10 fps; a frame is static if <12 % of pixels changed by >14/255 vs 0.3 s earlier (median-filtered over 5 frames); span >3.0 s → FAIL. Calibrated on V4: known-good finals peak at 2.6–2.7 s, a plain 5 s talking-head stretch measures 5.0 s. Gesturing heads can exceed 12 % and slip through; the check targets "nothing changes".
- Lip-sync: pixel residual after subtracting the mean TH frame (locked-off camera), TH tried at zoom 1.0/1.07/1.14/1.25 (punch-ins), searched at TH t−3…+3 s (restart-at-0 bugs shift by seconds, not 0.5 s). 8 best-matching of 40 candidate times are judged; non-TH moments (b-roll, split screen) are skipped. FAIL if the best shift is ≥0.3 s and beats same-time by >0.08. Synthetic tests: ±0.5 s and restart-at-0 are caught.
- Transcript: full mix through highpass 200/lowpass 4000, whisper-cli large-v3-turbo; each script line is matched to its best window (order-independent, so Hook B works). WARN <95 % recall, lines not heard, or ≥4 extra words not in script. Known ASR confusions (servers/services, PTE/PDE/people, Martel) are mapped. Pauses >0.35 s and outro (0.3–0.8 s) come from TH audio (`silencedetect −35 dB`); without `--th` ASR timings are used (rough, word times are token-based).
- Code check: any `<OffthreadVideo src=…th…>` without `startFrom` → FAIL.
- Temp files live in a `mktemp` dir that is removed at the end.
