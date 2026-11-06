#!/usr/bin/env python3
"""Compose a talking head: b-roll in four layouts, captions, SFX. One ffmpeg render.

  br.py frames BROLL_DIR JOBDIR        -> JOBDIR/broll/<id>.jpg (3-frame strip per clip) + broll.json
  br.py render TH.mp4 JOBDIR [--no-captions]
        reads JOBDIR/edl.json (+ sfx.json), JOBDIR/rough/words.json -> JOBDIR/final.mp4

edl.json  [{"from": 12, "to": 18, "layout": "full", "clip": "03", "src_in": 0.0}, ...]
          layout: full (b-roll covers all) | split (b-roll top, speaker bottom) |
                  cutout (speaker cut out over b-roll) | compare (clip top, clip2 bottom)
          cutout options: "place": auto|left|right|center (auto = away from the b-roll's focal point),
                          "scale": 0.4-1.0 (default 0.62; 1.0 = full size, background swap)
sfx.json  [{"word": 12, "file": "Whooshes/Swoosh_04.wav", "db": -12}, ...]  (file under $EDIT_SFX)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}
MIN_SHOT = 1.0          # Alan 07.11.: nothing on screen for less than ~1 s, else it stutters
LAYOUTS = {"full", "split", "cutout", "compare"}
SFX_DIR = Path(os.environ.get("EDIT_SFX", Path.home() / "aditor-edits/sfx")).expanduser()
KIT = Path.home() / ".cache/edit-kit/kit"
HERE = Path(__file__).parent


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def probe(video: str) -> dict:
    out = json.loads(sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                         "stream=width,height,r_frame_rate:format=duration", "-of", "json", video]))
    s = out["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return {"w": s["width"], "h": s["height"], "fps": float(num) / float(den),
            "dur": float(out["format"]["duration"])}


def kit() -> str:
    """Compile the native helper once (Xcode command line tools come with Homebrew)."""
    src = HERE / "kit.swift"
    if not KIT.exists() or KIT.stat().st_mtime < src.stat().st_mtime:
        KIT.parent.mkdir(parents=True, exist_ok=True)
        sh(["swiftc", "-O", str(src), "-o", str(KIT)])
    return str(KIT)


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


def plan(edl: list[dict], words: list[dict], inv: dict, th_dur: float) -> tuple[list[dict], list[str]]:
    """Word ranges -> timed shots. A shot runs until the next word starts (no gap).
    Speaker stretches under MIN_SHOT between shots are closed by letting the earlier shot run on.
    Refuses unknown clips/layouts, overlaps, shots under MIN_SHOT and clips shorter than their shot."""
    shots, notes = [], []
    for e in edl:
        lay = e.get("layout", "full")
        if lay not in LAYOUTS:
            raise SystemExit(f"unknown layout {lay}")
        i, j = e["from"], e["to"]
        if not (0 <= i <= j < len(words)):
            raise SystemExit(f"bad word range {i}-{j}")
        ids = [e["clip"]] + ([e["clip2"]] if lay == "compare" else [])
        for cid in ids:
            if cid not in inv:
                raise SystemExit(f"unknown clip {cid}")
        end = words[j + 1]["t"] if j + 1 < len(words) else th_dur
        shots.append({"layout": lay, "paths": [inv[c]["path"] for c in ids], "durs": [inv[c]["dur"] for c in ids],
                      "at": words[i]["t"], "end": min(end, th_dur), "src_in": float(e.get("src_in", 0.0)),
                      "words": f"{i}-{j}", "place": e.get("place", "auto"), "scale": e.get("scale", 0.62)})
    shots.sort(key=lambda s: s["at"])
    for a, b in zip(shots, shots[1:]):
        if a["end"] > b["at"] + 1e-3:
            raise SystemExit(f"overlap: words {a['words']} and {b['words']}")
        if 0 < b["at"] - a["end"] < MIN_SHOT:
            notes.append(f"closed {b['at'] - a['end']:.2f}s speaker flash before words {b['words']}")
            a["end"] = b["at"]
    if shots and 0 < th_dur - shots[-1]["end"] < MIN_SHOT:
        shots[-1]["end"] = th_dur
    for s in shots:
        s["dur"] = s["end"] - s["at"]
        if s["dur"] < MIN_SHOT - 1e-3:
            raise SystemExit(f"words {s['words']}: {s['dur']:.2f}s on screen, minimum {MIN_SHOT}s - widen the range")
        if min(s["durs"]) - s["src_in"] < s["dur"] - 0.01:
            raise SystemExit(f"words {s['words']}: clip has {min(s['durs']) - s['src_in']:.2f}s, needs {s['dur']:.2f}s")
    return shots, notes


def caption_groups(words: list[dict], th_dur: float) -> list[dict]:
    """1-3 words per caption, max ~16 characters, break after punctuation."""
    groups, cur = [], []
    for w in words:
        if cur and (len(cur) == 3 or len(" ".join(x["w"] for x in cur + [w])) > 16):
            groups.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.,?!;:]$", w["w"]):
            groups.append(cur)
            cur = []
    groups += [cur] if cur else []
    out = []
    for k, g in enumerate(groups):
        t1 = groups[k + 1][0]["t"] if k + 1 < len(groups) else min(th_dur, g[-1]["t"] + g[-1]["d"] + 0.4)
        out.append({"text": re.sub(r"[.,;:]+$", "", " ".join(x["w"] for x in g)).upper(), "t0": g[0]["t"], "t1": t1})
    return out


def between(spans: list[tuple[float, float]]) -> str:
    return "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in spans) or "0"


def cutout_spot(path: str, src_in: float, dur: float, place: str, scale: float, W: int, H: int) -> tuple[int, int, str]:
    """Where the scaled speaker goes: bottom-anchored, on the side the b-roll's focal point is NOT."""
    if scale >= 0.99:
        return 0, 0, "full"
    if place == "auto":
        x, _, w, _ = (float(v) for v in sh([kit(), "focus", path, f"{src_in + dur / 2:.2f}"]).split())
        place = "left" if x + w / 2 > 0.5 else "right"
    pw, ph = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
    xs = {"left": -int(pw * 0.12), "right": W - pw + int(pw * 0.12), "center": (W - pw) // 2}
    return xs[place], H - ph, place


def body_bottom(mask: Path, t: float) -> float:
    """Lowest row (0..1) where the speaker's mask still covers >4 % of the width, at time t.
    A desk or counter in the talking head ends the body early; the cutout gets pushed down by the rest."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(mask), "-frames:v", "1",
                          "-vf", "scale=90:160,format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    rows = [raw[r * 90:(r + 1) * 90] for r in range(len(raw) // 90)]
    hit = [r for r, row in enumerate(rows) if sum(b > 128 for b in row) > 4]
    return (hit[-1] + 1) / len(rows) if hit else 1.0


def make_mask(th: str, info: dict, job: Path) -> Path:
    """Person mask of the whole talking head (Apple Vision), cached per job."""
    mask = job / "mask.mp4"
    if mask.exists() and mask.stat().st_mtime > Path(th).stat().st_mtime:
        return mask
    mw, mh = info["w"] // 2 * 2, info["h"] // 2 * 2
    p = subprocess.Popen([kit(), "mask", th, str(mw), str(mh)], stdout=subprocess.PIPE)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{mw}x{mh}",
                    "-r", f"{info['fps']:g}", "-i", "-", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
                    str(mask)], stdin=p.stdout, check=True)
    if p.wait():
        raise SystemExit("person mask failed")
    return mask


def cmd_render(th: str, jobdir: str, captions: bool = True) -> None:
    job = Path(jobdir)
    info = probe(th)
    words = json.loads((job / "rough/words.json").read_text())
    inv = {c["id"]: c for c in json.loads((job / "broll.json").read_text())} if (job / "broll.json").exists() else {}
    edl = json.loads((job / "edl.json").read_text()) if (job / "edl.json").exists() else []
    shots, notes = plan(edl, words, inv, info["dur"])
    vertical = info["h"] >= info["w"]
    W, H, fps = (1080, 1920, 30) if vertical else (1920, 1080, 30)
    hw, hh = (W, H // 2) if vertical else (W // 2, H)            # one split panel
    stack = "vstack" if vertical else "hstack"

    def fit(w: int, h: int) -> str:
        return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},setsar=1"

    inputs, fc = ["-i", th], []

    def add(path: str, *pre: str) -> int:
        inputs.extend([*pre, "-i", path])
        return inputs.count("-i") - 1

    n_cut = sum(s["layout"] == "cutout" for s in shots)
    copies = 1 + sum(s["layout"] in ("split", "cutout") for s in shots)
    fc.append(f"[0:v]{fit(W, H)},split={copies}" + "".join(f"[th{k}]" for k in range(copies)))
    mask = make_mask(th, info, job) if n_cut else None
    if n_cut:
        mi = add(str(mask))
        fc.append(f"[{mi}:v]{fit(W, H)},format=gray,split={n_cut}" + "".join(f"[mk{k}]" for k in range(n_cut)))

    base, thk, mkk = "th0", 1, 0
    for k, s in enumerate(shots):
        a, d, si = s["at"], s["dur"], s["src_in"]
        win = f"trim=start={a:.3f}:duration={d:.3f}"

        def clip(path: str, w: int, h: int, tag: str) -> None:
            fc.append(f"[{add(path)}:v]trim=start={si:.3f}:duration={d:.3f},setpts=PTS-STARTPTS+{a:.3f}/TB,"
                      f"{fit(w, h)}[{tag}]")

        if s["layout"] == "full":
            clip(s["paths"][0], W, H, f"p{k}")
        elif s["layout"] == "compare":
            clip(s["paths"][0], hw, hh, f"x{k}")
            clip(s["paths"][1], hw, hh, f"y{k}")
            fc.append(f"[x{k}][y{k}]{stack}[p{k}]")
        elif s["layout"] == "split":
            clip(s["paths"][0], hw, hh, f"x{k}")
            # speaker panel keeps the face (upper-middle of a selfie frame)
            crop = f"crop={hw}:{hh}:0:{int(H * 0.12)}" if vertical else f"crop={hw}:{hh}:{W // 4}:0"
            fc.append(f"[th{thk}]{win},{crop}[y{k}]")
            fc.append(f"[x{k}][y{k}]{stack}[p{k}]")
            thk += 1
        else:  # cutout: speaker without background, over the b-roll, clear of its focal point
            clip(s["paths"][0], W, H, f"x{k}")
            scale = min(1.0, max(0.4, float(s.get("scale", 0.62))))
            px, py, s["place"] = cutout_spot(s["paths"][0], si, d, s.get("place", "auto"), scale, W, H)
            pw, ph = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
            py += int((1 - body_bottom(mask, a + d / 2)) * ph)      # body sits on the bottom edge
            fc.append(f"[th{thk}]{win},format=rgba[c{k}];[mk{mkk}]{win}[m{k}];[c{k}][m{k}]alphamerge,scale={pw}:{ph}[y{k}]")
            fc.append(f"[x{k}][y{k}]overlay={px}:{py}:eof_action=pass[p{k}]")
            thk, mkk = thk + 1, mkk + 1
        fc.append(f"[{base}][p{k}]overlay=0:0:enable='between(t,{a:.3f},{a + d:.3f})':eof_action=pass[o{k}]")
        base = f"o{k}"

    if captions and words:
        cdir = job / "captions"
        cdir.mkdir(exist_ok=True)
        groups = caption_groups(words, info["dur"])
        size = {"w": W - 80, "h": 320, "size": 88 if vertical else 72}
        spec = [{"text": g["text"], "file": f"c{k:03d}.png", **size} for k, g in enumerate(groups)]
        spec.append({"text": "", "file": "blank.png", **size})
        (cdir / "captions.json").write_text(json.dumps(spec))
        sh([kit(), "captions", str(cdir / "captions.json"), str(cdir)])
        lines, t = ["ffconcat version 1.0"], 0.0
        for k, g in enumerate(groups):
            if g["t0"] > t + 1e-3:
                lines += ["file blank.png", f"duration {g['t0'] - t:.3f}"]
            lines += [f"file c{k:03d}.png", f"duration {g['t1'] - g['t0']:.3f}"]
            t = g["t1"]
        lines += ["file blank.png", f"duration {max(0.1, info['dur'] - t):.3f}", "file blank.png"]
        (cdir / "track.ffconcat").write_text("\n".join(lines) + "\n")
        ci = add(str(cdir / "track.ffconcat"), "-f", "concat", "-safe", "0")
        # on the seam in split/compare, on the chest of a small cutout (never over its face), lower third otherwise
        seam = [(s["at"], s["end"]) for s in shots if s["layout"] in ("split", "compare")]
        chest = [(s["at"], s["end"]) for s in shots if s["layout"] == "cutout" and float(s["scale"]) < 0.99]
        y = (f"if({between(seam)},{H // 2}-h/2,if({between(chest)},{int(H * 0.86)}-h/2,{int(H * 0.66)}-h/2))"
             if vertical else f"{int(H * 0.8)}-h/2")
        fc.append(f"[{ci}:v]fps={fps},format=rgba[cap];[{base}][cap]overlay=(W-w)/2:'{y}':eof_action=pass[ocap]")
        base = "ocap"

    sfx = json.loads((job / "sfx.json").read_text()) if (job / "sfx.json").exists() else []
    amap = ["-map", "0:a", "-c:a", "copy"]
    if sfx:
        mix = ["[0:a]aresample=48000[vo]"]
        for k, e in enumerate(sfx):
            f = Path(e["file"]).expanduser()
            f = f if f.is_absolute() else SFX_DIR / f
            if not f.exists():
                raise SystemExit(f"sfx not found: {f}")
            ms = max(0, int((words[e["word"]]["t"] + float(e.get("offset", 0.0))) * 1000))
            mix.append(f"[{add(str(f))}:a]aresample=48000,volume={float(e.get('db', -12))}dB,adelay={ms}|{ms}[s{k}]")
        mix.append("[vo]" + "".join(f"[s{k}]" for k in range(len(sfx)))
                   + f"amix=inputs={len(sfx) + 1}:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")
        fc += mix
        amap = ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]   # voice level and timing unchanged

    out = job / "final.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", f"[{base}]",
                    *amap, "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-r", str(fps),
                    "-t", f"{info['dur']:.3f}", "-movflags", "+faststart", str(out)], check=True)
    drift = abs(probe(str(out))["dur"] - info["dur"])
    if drift > 1.5 / fps:
        raise SystemExit(f"SYNC FAIL: duration drift {drift:.3f}s")
    cover = sum(s["dur"] for s in shots) / info["dur"] * 100
    lay = ", ".join(f"{n} {l}" for l in sorted(LAYOUTS) if (n := sum(s["layout"] == l for s in shots)))
    print(f"{len(shots)} shots ({lay or 'none'}), {cover:.0f}% covered, {len(sfx)} sfx, "
          f"captions {'on' if captions else 'off'}, drift {drift * 1000:.0f} ms -> {out}")
    for s in shots:
        if s["layout"] == "cutout":
            print(f"  cutout words {s['words']}: speaker {s['place']}")
    for n in notes:
        print("  note:", n)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "frames":
        cmd_frames(a[1], a[2])
    elif len(a) >= 3 and a[0] == "render":
        cmd_render(a[1], a[2], captions="--no-captions" not in a)
    else:
        raise SystemExit(__doc__)
