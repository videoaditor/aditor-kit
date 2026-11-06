#!/usr/bin/env python3
"""Rough cut for a talking head: local whisper word timings -> Claude picks word ranges to
drop -> pause-cut + speed-up + loudnorm in one render.

  rc.py words VIDEO OUTDIR                 -> OUTDIR/words.json + OUTDIR/transcript.txt
  rc.py cut VIDEO JOBDIR [--drop 12-14,40-52] [--pace ad|lesson|natural]
        reads JOBDIR/raw/words.json, writes JOBDIR/rough.mp4
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tighten_core import PACE_PRESETS, TightenConfig, _merge_cuts, _snap, render_tightened  # noqa: E402

MODEL = os.environ.get("EDIT_WHISPER_MODEL",
                       str(Path.home() / ".cache/whisper-cpp/ggml-large-v3-turbo-q5_0.bin"))
PACES = {
    "ad": PACE_PRESETS["social"],                                     # ~2-frame gaps, 1.15x
    "lesson": TightenConfig(pausecut_trigger_s=0.08, pausecut_floor_s=0.05,
                            sentence_floor_s=0.14, speed_factor=1.1),  # Alan: lessons 1.1x
    "natural": PACE_PRESETS["natural"],
}
END = re.compile(r"[.?!]$")


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def probe(video: str) -> tuple[float, float]:
    out = json.loads(sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                         "stream=r_frame_rate:format=duration", "-of", "json", video]))
    num, den = out["streams"][0]["r_frame_rate"].split("/")
    return float(num) / float(den), float(out["format"]["duration"])


def parse_whisper(segments: list[dict]) -> list[dict]:
    """whisper-cli -ml 1 segments -> [{i,w,t,d}]; punctuation-only tokens glue onto the word before."""
    words: list[dict] = []
    for s in segments:
        txt = s["text"].strip()
        if not txt:
            continue
        t0, t1 = s["offsets"]["from"] / 1000, s["offsets"]["to"] / 1000
        if words and not re.search(r"\w", txt):
            words[-1]["w"] += txt
            continue
        words.append({"i": len(words), "w": txt, "t": round(t0, 3), "d": round(max(0.0, t1 - t0), 3)})
    return words


def sentences(words: list[dict]) -> list[list[dict]]:
    out, cur = [], []
    for w in words:
        cur.append(w)
        if END.search(w["w"]):
            out.append(cur)
            cur = []
    return out + ([cur] if cur else [])


def repeats(words: list[dict]) -> list[str]:
    """Hints only: adjacent identical words or bigrams. Claude decides (lists/punchlines stay)."""
    norm = [re.sub(r"[^\w']", "", w["w"].lower()) for w in words]
    hits = []
    for i in range(len(norm) - 1):
        if norm[i] and norm[i] == norm[i + 1]:
            hits.append(f"[{i}-{i + 1}] {words[i]['w']} {words[i + 1]['w']}")
    for i in range(len(norm) - 3):
        if norm[i] and norm[i:i + 2] == norm[i + 2:i + 4]:
            hits.append(f"[{i}-{i + 3}] " + " ".join(w["w"] for w in words[i:i + 4]))
    # retakes: the same 3 words again within the next 12 (e.g. "...your biology, not against it. Get 20 biology, not against it")
    for i in range(len(norm) - 3):
        for k in range(i + 3, min(i + 15, len(norm) - 2)):
            if all(norm[i:i + 3]) and norm[i:i + 3] == norm[k:k + 3]:
                hits.append(f"retake? [{i}-{i + 2}] and [{k}-{k + 2}] " + " ".join(w["w"] for w in words[i:i + 3]))
                break
    return hits


def cmd_words(video: str, outdir: str) -> None:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        wav = f"{tmp}/a.wav"
        sh(["ffmpeg", "-v", "error", "-y", "-i", video, "-ar", "16000", "-ac", "1", wav])
        sh(["whisper-cli", "-m", MODEL, "-f", wav, "-ml", "1", "-sow", "-ojf", "-of", f"{tmp}/w", "-np"])
        segs = json.load(open(f"{tmp}/w.json"))["transcription"]
    words = parse_whisper(segs)
    (out / "words.json").write_text(json.dumps(words))
    lines = [f"{s[0]['t']:7.2f}s  " + " ".join(f"{w['i']}:{w['w']}" for w in s) for s in sentences(words)]
    hits = repeats(words)
    if hits:
        lines += ["", "POSSIBLE REPEATS (check, don't blindly cut):"] + hits
    (out / "transcript.txt").write_text("\n".join(lines) + "\n")
    print(f"{len(words)} words -> {out}/transcript.txt ({len(hits)} possible repeats)")


def drop_spans(words: list[dict], spec: str) -> list[tuple[float, float]]:
    """'12-14,40' -> source time spans; a range runs from word i's start to word j+1's start."""
    spans = []
    for part in filter(None, (p.strip() for p in spec.split(","))):
        a, _, b = part.partition("-")
        i, j = int(a), int(b or a)
        if not (0 <= i <= j < len(words)):
            raise SystemExit(f"bad word range {part} (0..{len(words) - 1})")
        end = words[j + 1]["t"] if j + 1 < len(words) else words[j]["t"] + words[j]["d"]
        spans.append((words[i]["t"], end))
    return spans


def silences(video: str, db: int = -35, min_s: float = 0.06) -> list[tuple[float, float]]:
    """Pauses from the audio itself: whisper.cpp word timings butt up against each other."""
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-af", f"silencedetect=n={db}dB:d={min_s}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    return list(zip(starts, ends))


def plan_keeps(words, sil, dur, fps, cfg, drops) -> list[tuple[float, float]]:
    """Every pause longer than the trigger shrinks to its floor (sentence ends keep a longer one);
    dropped word ranges go entirely. Pause floors are split evenly around the seam."""
    ends = [(w["t"] + w["d"], bool(END.search(w["w"]))) for w in words]
    cuts = []
    for a, b in sil:
        if b - a <= cfg.pausecut_trigger_s:
            continue
        sentence_end = min(ends, key=lambda e: abs(e[0] - a), default=(0, True))[1]
        floor = cfg.sentence_floor_s if sentence_end and cfg.sentence_floor_s is not None else cfg.pausecut_floor_s
        c0, c1 = _snap(a + floor / 2, fps), _snap(b - floor / 2, fps)
        if c1 > c0:
            cuts.append((c0, c1))
    cuts = _merge_cuts(cuts + [(_snap(a, fps), _snap(b, fps)) for a, b in drops])
    keeps, cur = [], 0.0
    for c0, c1 in cuts:
        if c0 > cur:
            keeps.append((cur, min(c0, dur)))
        cur = max(cur, c1)
    if cur < dur:
        keeps.append((cur, dur))
    return [k for k in keeps if k[1] - k[0] > 0.5 / fps] or [(0.0, dur)]


def cmd_cut(video: str, jobdir: str, drop: str, pace: str) -> None:
    job = Path(jobdir)
    words = json.loads((job / "raw/words.json").read_text())
    fps, dur = probe(video)
    cfg = PACES[pace]
    keeps = plan_keeps(words, silences(video), dur, fps, cfg, drop_spans(words, drop))
    raw = job / "rough_raw.mp4"
    render_tightened(video, keeps, fps, cfg.pausecut_fade_frames, str(raw), speed=cfg.speed_factor)
    out = job / "rough.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-c:v", "copy", "-af",
        "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(out)])
    raw.unlink()
    print(f"{dur:.1f}s -> {probe(str(out))[1]:.1f}s, {len(keeps)} pieces -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("words"); w.add_argument("video"); w.add_argument("outdir")
    c = sub.add_parser("cut"); c.add_argument("video"); c.add_argument("jobdir")
    c.add_argument("--drop", default=""); c.add_argument("--pace", choices=PACES, default="ad")
    a = ap.parse_args()
    cmd_words(a.video, a.outdir) if a.cmd == "words" else cmd_cut(a.video, a.jobdir, a.drop, a.pace)
