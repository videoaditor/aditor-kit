---
name: rough-cut
description: Use when an editor drops a raw talking-head / A-roll / lesson recording and says "cut this", "rough cut", "tighten", "schneid das", "Rohschnitt", or wants false starts, stutters and pauses removed.
---

# rough-cut

Scripts sit next to this file (`<base dir>` = this skill's folder). Needs ffmpeg + whisper-cli + model; if missing, run the `edit-setup` skill first.

1. **Job folder.** `JOB=~/aditor-edits/jobs/<short-name>` (from the file name). Never touch the raw file.
2. **Transcribe:** `python3 <base dir>/rc.py words RAW.mp4 $JOB/raw` → read `$JOB/raw/transcript.txt`. Every word carries its index (`12:word`); one line per sentence; repeat hints at the bottom.
3. **Decide what goes**, reading the whole transcript like an outside editor (workspace `CLAUDE.md` rules win):
   - false starts and stutters: drop the earlier, broken take, keep the later complete one;
   - doubled takes of a whole sentence: keep the last good one;
   - null sentences ("you know", "but yeah", "so here we go");
   - never drop lists, parallels, punchlines or deliberate repetition. Never rephrase.
   Write the ranges as `--drop i-j,k-l` (inclusive word indices).
4. **Cut:** `python3 <base dir>/rc.py cut RAW.mp4 $JOB --drop … --pace ad` (`ad` = 1.15×, `lesson` = 1.1×, `natural` = 1.0× only dead air). Output `$JOB/rough.mp4`, −14 LUFS.
5. **Check — required:** `python3 <base dir>/rc.py words $JOB/rough.mp4 $JOB/rough` and read `$JOB/rough/transcript.txt`. Leftover stutters or a cut mid-word → widen the range in step 4 and re-cut (the indices refer to the raw transcript). Repeat until clean.
6. Report to the editor: old → new length, what you removed (one line each, quoted), path to `rough.mp4`. Next step: "put b-roll on it" (`broll` skill) or `reel-qc`.
