#!/usr/bin/env python3
"""Wait for the reviewer's feedback on AutoReview, then print it and exit (stdlib only).

  watch.py [--request REQUEST_ID] [--every 60]    block until a feedback round is closed, print it, exit 0
  watch.py --ack ROUND_ID                          mark a round as handled (after the fix is pushed)

A round opens with the first human comment and closes when the reviewer presses Send or after 5 idle minutes (server side).
Run it with run_in_background: its exit wakes the session. Full JSON lands in ./feedback-<round>.json.
Several sessions share one agent key, so pass --request (request_id from POST /agent/requests) to take only yours.
"""
import argparse, json, sys, time

import push


def tc(s):
    return "--:--" if s is None else f"{int(s // 60)}:{s % 60:04.1f}"


def bbox(drawing):
    pts = [p for m in ((drawing or {}).get("drawing_data") or {}).get("marks") or [] for p in m.get("points") or []]
    if not pts:
        return ""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return f"  [drawn at x {min(xs):.2f}-{max(xs):.2f}, y {min(ys):.2f}-{max(ys):.2f} of the frame]"


def summary(rnd):
    out = [f"ROUND {rnd['round_id']}  request {rnd['request_id']}  \"{rnd.get('briefing') or ''}\"  closed by {rnd.get('closed_by')}"]
    for f in rnd.get("files") or []:
        out.append(f"  FILE {f.get('name')} v{f.get('version_number')}  asset {f.get('asset_id')}")
        for c in f.get("comments") or []:
            out.append(f"    {tc(c.get('t_start'))}  {(c.get('text') or '').strip()}{bbox(c.get('drawing'))}")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--request", help="only rounds of this request_id")
    ap.add_argument("--ack", metavar="ROUND_ID")
    ap.add_argument("--every", type=int, default=60, help="seconds between polls (rate limit: keep >= 60)")
    ap.add_argument("--api", default=push.DEFAULT_API)
    a = ap.parse_args(argv)
    key, api = push.agent_key(), a.api.rstrip("/")
    if a.ack:
        push.call(f"{api}/agent/feedback/{a.ack}/ack", key, raw=b"", method="POST")
        return print("acked", a.ack)
    while True:
        _, d = push.call(f"{api}/agent/feedback", key)
        rounds = [r for r in d.get("rounds") or [] if not a.request or r.get("request_id") == a.request]
        if rounds:
            for r in rounds:
                path = f"feedback-{r['round_id']}.json"
                json.dump(r, open(path, "w"), indent=1)
                print(summary(r), f"\n  full: {path}\n")
            return
        time.sleep(a.every)


if __name__ == "__main__":
    sys.exit(main())
