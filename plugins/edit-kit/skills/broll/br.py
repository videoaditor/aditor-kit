#!/usr/bin/env python3
"""B-roll over a talking head: full-frame overlays placed on spoken words, voice untouched.

  br.py frames BROLL_DIR JOBDIR   -> JOBDIR/broll/<id>.jpg (3-frame strip per clip) + broll.json
  br.py render TH.mp4 JOBDIR      -> reads JOBDIR/edl.json + JOBDIR/rough/words.json,
                                     writes JOBDIR/broll.mp4 (duration == TH, audio stream copied)
edl.json: [{"clip": "03", "from": 12, "to": 18, "src_in": 0.0}, ...]  (word indices, inclusive)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def probe(video: str) -> dict:
    out = json.loads(sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                         "stream=width,height,r_frame_rate:format=duration", "-of", "json", video]))
    s = out["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return {"w": s["width"], "h": s["height"], "fps": float(num) / float(den),
            "dur": float(out["format"]["duration"])}


def cmd_frames(broll_dir: str, jobdir: str) -> None:
    out = Path(jobdir) / "broll"
    out.mkdir(parents=True, exist_ok=True)
    clips = sorted(p for p in Path(broll_dir).expanduser().rglob("*") if p.suffix.lower() in VIDEO_EXT)
    inv = []
    for n, p in enumerate(clips, 1):
        cid, dur = f"{n:02d}", probe(str(p))["dur"]
        # 3 frames at 15/50/85 % side by side: enough to see what moves
        sh(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-vf",
            f"fps=3/{max(dur, 0.1):.3f},scale=-2:360,tile=3x1", "-frames:v", "1", str(out / f"{cid}.jpg")])
        inv.append({"id": cid, "path": str(p.resolve()), "dur": round(dur, 2)})
    (Path(jobdir) / "broll.json").write_text(json.dumps(inv, indent=1))
    print(f"{len(inv)} clips -> {out}/<id>.jpg; inventory {jobdir}/broll.json")


def plan(edl: list[dict], words: list[dict], inv: dict, th_dur: float) -> list[dict]:
    """Word ranges -> [{path, at, dur, src_in}]; refuses overlaps, too-short clips, bad ids."""
    placed = []
    for e in edl:
        c = inv.get(e["clip"])
        if c is None:
            raise SystemExit(f"unknown clip {e['clip']}")
        i, j = e["from"], e["to"]
        if not (0 <= i <= j < len(words)):
            raise SystemExit(f"bad word range {i}-{j}")
        at = words[i]["t"]
        end = min(words[j]["t"] + words[j]["d"], th_dur)
        src_in = float(e.get("src_in", 0.0))
        if c["dur"] - src_in < end - at - 0.01:
            raise SystemExit(f"clip {e['clip']} has {c['dur'] - src_in:.2f}s, span {i}-{j} needs {end - at:.2f}s")
        placed.append({"path": c["path"], "at": at, "dur": end - at, "src_in": src_in})
    placed.sort(key=lambda p: p["at"])
    for a, b in zip(placed, placed[1:]):
        if a["at"] + a["dur"] > b["at"] + 1e-3:
            raise SystemExit(f"overlap at {b['at']:.2f}s")
    return placed


def cmd_render(th: str, jobdir: str) -> None:
    job = Path(jobdir)
    info = probe(th)
    words = json.loads((job / "rough/words.json").read_text())
    inv = {c["id"]: c for c in json.loads((job / "broll.json").read_text())}
    placed = plan(json.loads((job / "edl.json").read_text()), words, inv, info["dur"])
    # delivery format: 1080x1920 (or 1920x1080) @ 30 fps, whatever the source was
    W, H, fps = (1080, 1920, 30.0) if info["h"] >= info["w"] else (1920, 1080, 30.0)
    cmd, fc, base = ["ffmpeg", "-v", "error", "-y", "-i", th], [], "v0"
    fc.append(f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps:g},setsar=1[v0]")
    for k, p in enumerate(placed, 1):
        cmd += ["-i", p["path"]]
        fc.append(f"[{k}:v]trim=start={p['src_in']:.3f}:duration={p['dur']:.3f},setpts=PTS-STARTPTS+{p['at']:.3f}/TB,"
                  f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps:g},setsar=1[b{k}]")
        fc.append(f"[{base}][b{k}]overlay=enable='between(t,{p['at']:.3f},{p['at'] + p['dur']:.3f})':eof_action=pass[o{k}]")
        base = f"o{k}"
    out = job / "broll.mp4"
    cmd += ["-filter_complex", ";".join(fc), "-map", f"[{base}]",
            "-map", "0:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy",
            "-t", f"{info['dur']:.3f}", "-movflags", "+faststart", str(out)]
    sh(cmd)
    drift = abs(probe(str(out))["dur"] - info["dur"])
    if drift > 1.5 / fps:
        raise SystemExit(f"SYNC FAIL: duration drift {drift:.3f}s")
    cover = sum(p["dur"] for p in placed) / info["dur"] * 100
    print(f"{len(placed)} inserts, {cover:.0f}% covered, drift {drift * 1000:.0f} ms -> {out}")


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("frames", "render"):
        raise SystemExit(__doc__)
    (cmd_frames if sys.argv[1] == "frames" else cmd_render)(sys.argv[2], sys.argv[3])
