#!/usr/bin/env python3
"""reel-qc: deterministic QC for finished vertical talking-head reels.
Stdlib + ffmpeg/ffprobe/whisper-cli only.  Exit code 1 on any FAIL."""
import argparse, difflib, json, math, os, re, shutil, subprocess, sys, tempfile
from collections import Counter

WHISPER_MODEL = os.environ.get("REEL_QC_WHISPER_MODEL", os.path.expanduser("~/.cache/whisper-cpp/ggml-large-v3-turbo-q5_0.bin"))

# ---- thresholds (calibrated on ig-content-2026-11-04 v4; see SKILL.md) ----
LUFS_TARGET, LUFS_TOL, TP_MAX = -14.0, 0.5, -1.2
BLACK_MIN_D = 0.1
SW, SH, SFPS = 108, 192, 10          # analysis frames: 108x192 gray @10 fps
STATIC_LAG = 3                       # compare frame i with i-3 (0.3 s)
STATIC_PIX, STATIC_FRAC = 14, 0.12   # a pixel "changed" if |diff|>14/255 vs 0.3 s ago; frame is static if <12 % changed
STATIC_SMOOTH = 5                    # median filter over frames (ignores single lip/caption blips)
STATIC_MAX_S = 3.0
SYNC_N, SYNC_RANGE = 8, 3.0          # 8 samples, search TH at t-3 s .. t+3 s (restart-at-0 bugs shift by seconds)
SYNC_MIN_CORR = 0.5                  # best residual match below this = final isn't showing the TH here -> skip
SYNC_MARGIN = 0.08                   # shifted must beat same-time by this much
SYNC_ZOOMS, SYNC_CANDS = (1.0, 1.07, 1.14, 1.25), 40
SYNC_MIN_SHIFT = 0.3                 # shifts below 0.3 s are neighbouring frames, not an offset
RECALL_MIN, GAP_MAX = 0.95, 0.35
OUTRO_MIN, OUTRO_MAX = 0.3, 0.8
ASR = {"servers": "services", "pte": "people", "pde": "people", "martel": "martell", "whatsapp": "whatsapp"}


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, **kw)


def probe(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration",
             "-of", "json", path])
    return json.loads(r.stdout or b"{}")


def gray_frames(path, tmp, name, w=SW, h=SH, zoom=1.0):
    """All frames @10fps as list of bytes (w*h gray); zoom>1 = fill-crop around (50%, 36%) like the Reel's punch-in."""
    raw = os.path.join(tmp, name + ".raw")
    z = f",scale=iw*{zoom}:ih*{zoom}:flags=area,crop={w}:{h}:(iw-{w})/2:(ih-{h})*0.36" if zoom != 1.0 else ""
    run(["ffmpeg", "-v", "error", "-y", "-i", path, "-an", "-vf",
         f"fps={SFPS},scale={w}:{h}:flags=area{z},format=gray", "-f", "rawvideo", raw])
    d = open(raw, "rb").read()
    n = w * h
    return [d[i:i + n] for i in range(0, len(d) - n + 1, n)]


def mae(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sa = sb = sab = 0.0
    for x, y in zip(a, b):
        x -= ma; y -= mb
        sa += x * x; sb += y * y; sab += x * y
    return sab / math.sqrt(sa * sb) if sa > 0 and sb > 0 else 0.0


def ts(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def spans(flags, step, min_len):
    out, s = [], None
    for i, f in enumerate(flags + [False]):
        if f and s is None:
            s = i
        if not f and s is not None:
            if (i - s) * step >= min_len:
                out.append((s * step, i * step))
            s = None
    return out


class Report:
    def __init__(self):
        self.rows = []

    def add(self, name, status, evidence, data=None):
        self.rows.append({"check": name, "status": status, "evidence": evidence, **({"data": data} if data else {})})


# ---------------- checks ----------------
def check_format(rep, path, info):
    v = next((s for s in info.get("streams", []) if s["codec_type"] == "video"), {})
    a = any(s["codec_type"] == "audio" for s in info.get("streams", []))
    num, den = (v.get("r_frame_rate", "0/1").split("/") + ["1"])[:2]
    fps = float(num) / float(den or 1)
    ok = v.get("width") == 1080 and v.get("height") == 1920 and abs(fps - 30) < 0.01 and a
    rep.add("format", "PASS" if ok else "FAIL",
            f"{v.get('width')}x{v.get('height')} @ {fps:.2f} fps, audio={'yes' if a else 'NO'} (need 1080x1920, 30 fps, audio)")
    return float(info.get("format", {}).get("duration", 0))


def check_loudness(rep, path):
    r = run(["ffmpeg", "-nostats", "-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"])
    txt = r.stderr.decode(errors="replace")
    summ = txt[txt.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summ)
    p = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ)
    if not i or not p:
        rep.add("loudness", "FAIL", "could not measure (no audio?)")
        return
    I, P = float(i.group(1)), float(p.group(1))
    ok = abs(I - LUFS_TARGET) <= LUFS_TOL and P <= TP_MAX
    rep.add("loudness", "PASS" if ok else "FAIL",
            f"{I:.1f} LUFS (need {LUFS_TARGET}±{LUFS_TOL}), true peak {P:.1f} dBTP (need ≤ {TP_MAX})")


def check_black(rep, path):
    r = run(["ffmpeg", "-nostats", "-i", path, "-an", "-vf", f"blackdetect=d={BLACK_MIN_D}:pix_th=0.10", "-f", "null", "-"])
    found = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr.decode(errors="replace"))
    if found:
        rep.add("black frames", "FAIL", "black at " + ", ".join(f"{ts(float(a))}-{ts(float(b))}" for a, b in found))
    else:
        rep.add("black frames", "PASS", f"none ≥ {BLACK_MIN_D} s")


def changed_frac(a, b):
    return sum(1 for x, y in zip(a, b) if abs(x - y) > STATIC_PIX) / len(a)


def check_static(rep, fr, debug=False):
    cf = [changed_frac(fr[i], fr[i - STATIC_LAG]) for i in range(STATIC_LAG, len(fr))]
    h = STATIC_SMOOTH // 2
    sm = [sorted(cf[max(0, i - h):i + h + 1])[len(cf[max(0, i - h):i + h + 1]) // 2] for i in range(len(cf))]
    flags = [v < STATIC_FRAC for v in sm]
    step = 1.0 / SFPS
    bad = [(s, e + STATIC_LAG * step) for s, e in spans(flags, step, STATIC_MAX_S)]
    if debug:
        print("changed%:", " ".join(f"{v * 100:.0f}" for v in sm), file=sys.stderr)
    longest = max((e - s for s, e in spans(flags, step, 0.1)), default=0.0)
    if bad:
        rep.add("static stretches", "FAIL",
                f"no cut/zoom/motion for > {STATIC_MAX_S:.0f} s: " + ", ".join(f"{ts(s)}-{ts(e)} ({e - s:.1f} s)" for s, e in bad),
                {"spans": bad})
    else:
        rep.add("static stretches", "PASS", f"longest static run {longest:.1f} s (limit {STATIC_MAX_S:.0f} s; static = <{STATIC_FRAC * 100:.0f}% pixels changed per 0.3 s)")
    if len(fr) > 4:
        d0 = max(changed_frac(fr[0], fr[k]) for k in (1, 2, 3))
        rep.add("frame 0 moving", "PASS" if d0 >= 0.03 else "WARN",
                f"{d0 * 100:.0f}% of pixels change over first 0.3 s" + ("" if d0 >= 0.03 else " (frame 0 looks frozen; LOOK at sheet.jpg)"))


def check_sync(rep, final, thp, tmp):
    """Static head => raw frames correlate ~equally at any shift. So: subtract the mean TH frame (locked-off
    camera), try the TH at a few punch-in zooms, search the TH timeline t-3 s..t+3 s. Candidates that don't
    show the TH (b-roll, split screen) match nothing and are skipped; the 8 best-matching candidates are judged."""
    w, h = 54, 96
    fr = gray_frames(final, tmp, "fs", w, h)
    ths = {z: gray_frames(thp, tmp, f"ts{z}", w, h, z) for z in SYNC_ZOOMS}
    n = len(ths[1.0])
    bgs, resz = {}, {}
    for z, th in ths.items():
        ks = range(0, n, 5)
        bgs[z] = [sum(th[k][p] for k in ks) / len(ks) for p in range(w * h)]
        resz[z] = {}

    def r_th(z, j):
        if j not in resz[z]:
            resz[z][j] = [x - b for x, b in zip(ths[z][j], bgs[z])]
        return resz[z][j]

    dur = min(len(fr), n) / SFPS
    R = int(SYNC_RANGE * SFPS)
    cands = []
    for k in range(SYNC_CANDS):
        t = dur * (k + 0.5) / SYNC_CANDS
        i = int(t * SFPS)
        if i >= len(fr) or i >= n:
            continue
        # cheap pre-check (coarse lags, any zoom): does the final show the TH here at all?
        pre = max(corr([x - b for x, b in zip(fr[i], bgs[z])], r_th(z, i + L))
                  for z in ths for L in range(-R, R + 1, 5) if 0 <= i + L < n)
        cands.append((pre, t, i))
    cands.sort(reverse=True)
    judged = sorted(cands[:SYNC_N], key=lambda c: c[1])
    ok_n, bad, skipped, detail = 0, [], 0, []
    for pre, t, i in judged:
        best_all = (-2, 0, 1.0, -2)
        for z in ths:
            rf = [x - b for x, b in zip(fr[i], bgs[z])]
            prof = {L: corr(rf, r_th(z, i + L)) for L in range(-R, R + 1) if 0 <= i + L < n}
            same = prof.get(0, -2)
            bL, best = max(prof.items(), key=lambda kv: kv[1])
            if best > best_all[0]:
                best_all = (best, bL, z, same)
        best, bL, z, same = best_all
        detail.append({"t": round(t, 2), "zoom": z, "same": round(same, 3), "best_shift_s": bL / SFPS, "best": round(best, 3)})
        if best < SYNC_MIN_CORR:
            skipped += 1
        elif abs(bL) / SFPS >= SYNC_MIN_SHIFT and best > same + SYNC_MARGIN:
            bad.append((t, bL / SFPS, same, best))
        else:
            ok_n += 1
    if bad:
        rep.add("lip-sync (TH offset)", "FAIL", "TH offset at " + ", ".join(
            f"{ts(t)} (matches TH {d:+.1f} s: r={b:.2f} vs same-time {s:.2f})" for t, d, s, b in bad), {"samples": detail})
    elif ok_n == 0:
        rep.add("lip-sync (TH offset)", "WARN", f"no sample clearly shows the TH ({skipped} skipped); check lips manually on the sheet", {"samples": detail})
    else:
        rep.add("lip-sync (TH offset)", "PASS", f"{ok_n} TH samples in sync (best-match r>={SYNC_MIN_CORR}), {skipped} skipped as non-TH", {"samples": detail})


def check_src(rep, src):
    probs, n = [], 0
    for root, _, files in os.walk(src):
        for fn in files:
            if not fn.endswith((".tsx", ".jsx", ".ts", ".js")):
                continue
            p = os.path.join(root, fn)
            txt = open(p, errors="replace").read()
            for m in re.finditer(r"<OffthreadVideo\b(.*?)/>", txt, re.S):
                tag = m.group(1)
                s = re.search(r"src=\{?([^\s]*?th[^\s]*?)\}?\s", tag + " ")
                if not s:
                    continue
                n += 1
                if "startFrom" not in tag:
                    probs.append(f"{fn}:{txt[:m.start()].count(chr(10)) + 1}")
    if probs:
        rep.add("TH startFrom (code)", "FAIL", "OffthreadVideo of TH without startFrom at " + ", ".join(probs))
    else:
        rep.add("TH startFrom (code)", "PASS" if n else "WARN", f"{n} TH OffthreadVideo instance(s), all with startFrom" if n else "no TH OffthreadVideo found in --src")


def norm_words(s):
    out = []
    for w in re.findall(r"[a-z0-9']+", s.lower().replace("’", "'")):
        w = ASR.get(w, w)
        if len(w) > 3 and w.endswith("s"):
            w = w[:-1]
        out.append(w)
    return out


def script_lines(path):
    lines = []
    for ln in open(path, errors="replace"):
        m = re.match(r"\s*\d+\.\s+\"(.+?)\"", ln)
        if m:
            lines.append(m.group(1))
    return lines


def transcribe(path, tmp):
    wav = os.path.join(tmp, "mix.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vn", "-af", "highpass=200,lowpass=4000", "-ar", "16000", "-ac", "1", wav])
    run(["whisper-cli", "-m", WHISPER_MODEL, "-l", "en", "-mc", "0", "-ml", "1", "-sow", "-oj", "-of", os.path.join(tmp, "w"), "-f", wav])
    words = []
    for t in json.load(open(os.path.join(tmp, "w.json")))["transcription"]:
        w = t["text"].strip()
        if re.search(r"[A-Za-z0-9]", w) and not w.startswith("["):
            for part in norm_words(w) or []:
                words.append((part, t["offsets"]["from"] / 1000, t["offsets"]["to"] / 1000))
    return words


def voice_gaps(path, dur):
    """Pauses > GAP_MAX inside the speech, from a clean voice track (TH) via silencedetect."""
    r = run(["ffmpeg", "-nostats", "-i", path, "-vn", "-af", f"silencedetect=n=-35dB:d={GAP_MAX}", "-f", "null", "-"])
    txt = r.stderr.decode(errors="replace")
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", txt)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", txt)]
    sil = [(max(0, s), en[i] if i < len(en) else dur) for i, s in enumerate(st)]
    voice_end = sil[-1][0] if sil and sil[-1][1] >= dur - 0.05 else dur
    inner = [(s, e) for s, e in sil if s > 0.05 and e < dur - 0.05]
    return inner, voice_end


def check_transcript(rep, path, script, th, dur, tmp):
    words = transcribe(path, tmp)
    tw = [w for w, _, _ in words]
    total = matched = 0
    missing, absent, covered = [], [], set()
    for ln in script_lines(script):
        ew = norm_words(ln)
        n = len(ew)
        best = (-1, 0, [])
        for i in range(0, max(1, len(tw) - n // 2)):
            sm = difflib.SequenceMatcher(None, ew, tw[i:i + n + 3], autojunk=False)
            blocks = sm.get_matching_blocks()
            c = sum(b.size for b in blocks)
            if c > best[0]:
                best = (c, i, blocks)
        c, i, blocks = best
        total += n
        matched += c
        if c < n * 0.5:
            absent.append(" ".join(ln.split()[:6]) + " …")
            continue
        hit = set()
        for b in blocks:
            hit.update(range(b.a, b.a + b.size))
            covered.update(range(i + b.b, i + b.b + b.size))
        for k, w in enumerate(ew):
            if k not in hit:
                nxt = next((blocks_b for blocks_b in sorted(x.b for x in blocks if x.a > k and x.size)), None)
                j = min(len(words) - 1, i + (nxt if nxt is not None else n))
                missing.append((w, words[j][1]))
    recall = matched / total if total else 0
    ev = f"word recall {recall * 100:.0f}% of {total} script words ({len(words)} transcribed)"
    if absent:
        ev += "; script lines NOT heard: " + " | ".join(f"\"{a}\"" for a in absent)
    if missing:
        ev += "; missing words: " + ", ".join(f"'{w}' ~{ts(t)}" for w, t in missing[:10]) + (" …" if len(missing) > 10 else "")
    extra, run_ = [], []
    for i in range(len(words) + 1):
        if i < len(words) and i not in covered:
            run_.append(i)
        else:
            if len(run_) >= 4:
                extra.append((words[run_[0]][1], " ".join(words[k][0] for k in run_)))
            run_ = []
    if extra:
        ev += "; speech NOT in script: " + " | ".join(f"~{ts(t)} \"{x[:60]}\"" for t, x in extra[:4])
    rep.add("transcript vs script", "PASS" if recall >= RECALL_MIN and not extra else "WARN", ev,
            {"recall": recall, "missing": missing, "absent_lines": absent, "extra": extra})

    if th:
        thd = float(probe(th).get("format", {}).get("duration", dur))
        gaps, voice_end = voice_gaps(th, thd)
        src = "TH audio"
    else:
        gaps = [(words[i - 1][2], words[i][1]) for i in range(1, len(words)) if words[i][1] - words[i - 1][2] > GAP_MAX]
        voice_end = words[-1][2] if words else dur
        src = "ASR timings, rough"
    rep.add("word gaps", "WARN" if gaps else "PASS",
            (f"pauses > {GAP_MAX} s ({src}): " + ", ".join(f"{ts(s)}-{ts(e)} ({e - s:.2f} s)" for s, e in gaps)) if gaps
            else f"no pause > {GAP_MAX} s ({src})")
    outro = dur - voice_end
    rep.add("outro", "PASS" if OUTRO_MIN <= outro <= OUTRO_MAX else "WARN",
            f"voice ends {ts(voice_end)}, outro {outro:.2f} s (want {OUTRO_MIN}-{OUTRO_MAX} s); last ASR word '{words[-1][0] if words else '-'}' at {ts(words[-1][1]) if words else '-'}")


def contact_sheet(rep, path, out, dur):
    sheet = os.path.join(out, "sheet.jpg")
    n = max(1, int(math.ceil(dur)))
    cols = 10
    rows = int(math.ceil(n / cols))
    r = run(["ffmpeg", "-v", "error", "-y", "-i", path, "-an", "-vf",
             f"fps=1,scale=216:384,drawtext=text='%{{pts\\:hms}}':x=4:y=4:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6,tile={cols}x{rows}",
             "-frames:v", "1", "-q:v", "3", sheet])
    if not os.path.exists(sheet):  # drawtext may be missing in some ffmpeg builds
        run(["ffmpeg", "-v", "error", "-y", "-i", path, "-an", "-vf", f"fps=1,scale=216:384,tile={cols}x{rows}",
             "-frames:v", "1", "-q:v", "3", sheet])
    rep.add("contact sheet", "PASS" if os.path.exists(sheet) else "FAIL",
            f"{sheet} (1 fps, {cols} per row) - LOOK at it: frame 0 must be moving content" if os.path.exists(sheet) else "could not render")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("final")
    ap.add_argument("--th"), ap.add_argument("--script"), ap.add_argument("--src"), ap.add_argument("--out")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()
    final = os.path.abspath(a.final)
    out = os.path.abspath(a.out) if a.out else os.path.join(os.path.dirname(final), "qc")
    os.makedirs(out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="reelqc.")
    rep = Report()
    try:
        info = probe(final)
        dur = check_format(rep, final, info)
        check_loudness(rep, final)
        check_black(rep, final)
        fr = gray_frames(final, tmp, "final")
        check_static(rep, fr, a.debug)
        if a.th:
            check_sync(rep, final, a.th, tmp)
        if a.src:
            check_src(rep, a.src)
        if a.script and not (shutil.which("whisper-cli") and os.path.isfile(WHISPER_MODEL)):
            rep.add("transcript vs script", "WARN", "skipped: needs whisper-cli + model (brew install whisper-cpp; model at REEL_QC_WHISPER_MODEL)", {})
        elif a.script:
            check_transcript(rep, final, a.script, a.th, dur, tmp)
        contact_sheet(rep, final, out, dur)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    fails = [r for r in rep.rows if r["status"] == "FAIL"]
    json.dump({"file": final, "result": "FAIL" if fails else "PASS", "checks": rep.rows}, open(os.path.join(out, "qc.json"), "w"), indent=2, default=str)
    print(f"\nreel-qc: {os.path.basename(final)}")
    for r in rep.rows:
        print(f"  {r['status']:<5} {r['check']:<22} {r['evidence']}")
    print(f"\n=> {'FAIL (blocks hand-off)' if fails else 'PASS'}   [{out}/qc.json, sheet.jpg]")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
