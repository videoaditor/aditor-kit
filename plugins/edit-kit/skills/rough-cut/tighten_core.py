"""Pause-cut + speed-up engine — ported from Aditor Branding/video-pipeline/ads
(tighten.py + speed.py + contracts Word/Sentence), decoupled from the AdCut/
blackdetect machinery. Operates on a plain word list; pure functions unit-tested,
render shells out to ffmpeg.

The upstream lib segmented a reel via blackdetect + whisper-cli; here we tighten a
single talking-head over its whole length (copied from editing-agent; rc.py now feeds it silencedetect pauses + whisper.cpp words)
(see runner.tighten.flow). The keep/remap/render math is identical to upstream.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class Word:
    w: str
    t: float   # absolute start time in seconds
    d: float   # duration in seconds


@dataclass
class Sentence:
    idx: int
    start: float
    end: float
    text: str


@dataclass
class TightenConfig:
    pausecut_trigger_s: float = 0.12       # gaps longer than this get cut
    pausecut_floor_s: float = 0.06         # leave this much pause in on each cut
    pausecut_preserve_sentence_pauses: bool = True
    sentence_floor_s: float | None = None  # if set, inter-sentence gaps ARE cut, to this floor
    pausecut_fade_frames: int = 1          # audio de-click fade at each seam
    speed_factor: float = 1.15             # 1.0 = no speed-up


# Pace presets. All cut points snap to frame boundaries (_snap), so the floors
# below land frame-exact; comments give the ~frame count at 30fps.
# ponytail: values eyeballed against DR-social pacing — tune after Alan hears
# rendered A/B samples, not before.
PACE_PRESETS: dict[str, TightenConfig] = {
    # natural: breathe — only clearly dead air goes; sentence pauses kept but capped.
    "natural": TightenConfig(pausecut_trigger_s=0.20, pausecut_floor_s=0.12,  # ~4 fr
                             sentence_floor_s=0.40,                           # ~12 fr
                             speed_factor=1.0),
    # social: every gap collapses to a beat — ~2 frames in-sentence, ~4 between.
    "social": TightenConfig(pausecut_trigger_s=0.08, pausecut_floor_s=0.05,   # ~2 fr
                            sentence_floor_s=0.14,                            # ~4 fr
                            speed_factor=1.15),
}


# --- pure helpers (faithful port) ----------------------------------------

def _snap(t: float, fps: float) -> float:
    return round(t * fps) / fps


def _find_sentence(t: float, sentences: list[Sentence]) -> Sentence | None:
    for s in sentences:
        if s.start <= t <= s.end:
            return s
    return None


def _same_sentence(t1: float, t2: float, sentences: list[Sentence]) -> bool:
    """True if both times fall in the same sentence. No sentences ⇒ treat as one."""
    if not sentences:
        return True
    s1 = _find_sentence(t1, sentences)
    s2 = _find_sentence(t2, sentences)
    return s1 is not None and s1 is s2


def remap_time(t: float, keeps: list[tuple[float, float]]) -> float:
    """Map a source time onto the tightened (0-based) timeline defined by keeps."""
    elapsed = 0.0
    for k_start, k_end in keeps:
        if t <= k_end:
            return elapsed + max(0.0, t - k_start)
        elapsed += k_end - k_start
    return elapsed


def _merge_cuts(cuts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Sort cuts and merge overlapping/touching spans."""
    merged: list[tuple[float, float]] = []
    for c_in, c_out in sorted(cuts):
        if merged and c_in <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], c_out))
        else:
            merged.append((c_in, c_out))
    return merged


def plan_keep_intervals(words, sentences, seg_start, seg_end, fps, cfg,
                        drop_spans=None):
    """Return (keep_intervals, remapped_words).

    keep_intervals: [(start, end), ...] in SOURCE absolute time — spans that survive.
    remapped_words: words with `t` rebased to the tightened clip (0-based); `d` unchanged.
    drop_spans: [(t0, t1), ...] source spans to remove unconditionally (duplicate
    takes from dedup) — they bypass the sentence-pause protection.
    """
    trigger = cfg.pausecut_trigger_s
    floor = cfg.pausecut_floor_s
    preserve = cfg.pausecut_preserve_sentence_pauses
    sentence_floor = cfg.sentence_floor_s

    cuts: list[tuple[float, float]] = []
    for i in range(len(words) - 1):
        w0, w1 = words[i], words[i + 1]
        gap = w1.t - (w0.t + w0.d)
        if gap <= trigger:
            continue
        gap_floor = floor
        if preserve and not _same_sentence(w0.t, w1.t, sentences):
            if sentence_floor is None:
                continue                    # legacy: sentence pauses untouchable
            gap_floor = sentence_floor      # pace preset: cap the sentence pause
        cut_in = _snap(w0.t + w0.d, fps)
        cut_out = _snap(w1.t - gap_floor, fps)
        if cut_out <= cut_in:
            continue
        cuts.append((cut_in, cut_out))

    for d0, d1 in drop_spans or []:
        d0, d1 = _snap(d0, fps), _snap(d1, fps)
        if d1 > d0:
            cuts.append((d0, d1))
    cuts = _merge_cuts(cuts)

    keeps: list[tuple[float, float]] = []
    cursor = seg_start
    for c_in, c_out in cuts:
        c_in = max(seg_start, min(seg_end, c_in))
        c_out = max(seg_start, min(seg_end, c_out))
        if c_in > cursor:
            keeps.append((cursor, c_in))
        cursor = max(cursor, c_out)
    if cursor < seg_end:
        keeps.append((cursor, seg_end))
    if not keeps:
        keeps = [(seg_start, seg_end)]

    remapped = [Word(w=w.w, t=round(remap_time(w.t, keeps), 6), d=w.d) for w in words]
    return keeps, remapped


def build_speed_filter(factor, v_in, a_in, v_out, a_out):
    """Speed up video (setpts) + audio (atempo, pitch-preserved)."""
    return (f"[{v_in}]setpts=PTS/{factor:.6f}[{v_out}];"
            f"[{a_in}]atempo={factor:.6f}[{a_out}]")


def scale_words(words, factor):
    return [Word(w=w.w, t=round(w.t / factor, 6), d=round(w.d / factor, 6)) for w in words]


def scale_sentences(sentences, factor):
    return [Sentence(idx=s.idx, start=round(s.start / factor, 6),
                     end=round(s.end / factor, 6), text=s.text) for s in sentences]


def build_filter_complex(keeps, fps, fade_frames, speed=1.0):
    """ffmpeg filter_complex: trim each keep (v+a), de-click fade each audio seam,
    concat. First piece has no fade-in; last no fade-out. speed!=1.0 → sped up same pass."""
    fade = fade_frames / fps
    n = len(keeps)
    parts: list[str] = []
    for i, (start, end) in enumerate(keeps):
        length = end - start
        parts.append(
            f"[0:v]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS[v{i}]"
        )
        af = [f"[0:a]atrim=start={start:.6f}:end={end:.6f}", "asetpts=PTS-STARTPTS"]
        if i != 0:
            af.append(f"afade=t=in:st=0:d={fade:.6f}")
        if i != n - 1:
            af.append(f"afade=t=out:st={max(0.0, length - fade):.6f}:d={fade:.6f}")
        parts.append(",".join(af) + f"[a{i}]")
    concat_in = "".join(f"[v{i}][a{i}]" for i in range(n))
    if speed == 1.0:
        parts.append(f"{concat_in}concat=n={n}:v=1:a=1[outv][outa]")
    else:
        parts.append(f"{concat_in}concat=n={n}:v=1:a=1[cv][ca]")
        parts.append(build_speed_filter(speed, "cv", "ca", "outv", "outa"))
    return ";".join(parts)


def render_tightened(src, keeps, fps, fade_frames, dest, speed=1.0, run=subprocess.run):
    """One ffmpeg call: trim/concat keeps with de-click audio fades, optional speed → dest."""
    fc = build_filter_complex(keeps, fps, fade_frames, speed)
    cmd = ["ffmpeg", "-y", "-i", src, "-filter_complex", fc,
           "-map", "[outv]", "-map", "[outa]", "-r", str(fps),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-c:a", "aac", dest]
    run(cmd, check=True, capture_output=True, text=True)
