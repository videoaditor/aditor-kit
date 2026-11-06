#!/usr/bin/env python3
"""AutoReview setup and requests (stdlib only).

  ar.py pair CODE [--name NAME]      trade the 8-character pairing code for a key, store it in the macOS Keychain
  ar.py whoami                        which project (brand) this machine delivers to
  ar.py check                         what reel-qc still needs on this Mac (install lines)
  ar.py request TITLE REF             open a review request (same REF = same request); prints request_id, upload_token, review_url

The key never leaves the Keychain (service aditor-autoreview-agent) and is never printed.
"""
import argparse, json, os, platform, shutil, subprocess, sys

import push

SERVICE = "aditor-autoreview-agent"


def store_key(key):
    # stdin, not argv: the key never shows up in the process list. -U replaces the key of an earlier pairing.
    # ponytail: one key per machine (one brand); per-brand accounts when someone delivers to several brands from one Mac.
    cmd = f'add-generic-password -U -s {SERVICE} -a autoreview -l "AutoReview agent key" -w "{key}"\n'
    out = subprocess.run(["security", "-i"], input=cmd, capture_output=True, text=True, timeout=15)
    if out.returncode != 0:
        sys.exit("Could not write to the Keychain: " + (out.stderr or out.stdout).strip()[:200])


def missing_tools():
    """What reel-qc still needs on this Mac, as (what, install line). Empty = ready."""
    out = []
    if not shutil.which("ffmpeg"):
        out.append(("ffmpeg (video checks)", "brew install ffmpeg"))
    if not shutil.which("whisper-cli"):
        out.append(("whisper-cpp (script check)", "brew install whisper-cpp"))
    model = os.environ.get("REEL_QC_WHISPER_MODEL", os.path.expanduser("~/.cache/whisper-cpp/ggml-large-v3-turbo-q5_0.bin"))
    if not os.path.isfile(model):
        out.append(("speech model (script check)", f"mkdir -p {os.path.dirname(model)} && curl -L -o {model} "
                    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin"))
    if out and not shutil.which("brew") and any(cmd.startswith("brew") for _, cmd in out):
        out.insert(0, ("Homebrew", '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default=push.DEFAULT_API)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pair"); p.add_argument("code"); p.add_argument("--name", default=f"Claude Code on {platform.node()}")
    sub.add_parser("whoami"); sub.add_parser("check")
    r = sub.add_parser("request"); r.add_argument("title"); r.add_argument("ref")
    a = ap.parse_args(argv)
    api = a.api.rstrip("/")
    if a.cmd == "pair":
        _, d = push.call(f"{api}/agents/pair", None, {"code": a.code.strip(), "agent_name": a.name, "program": "claude-code"})
        store_key(d["agent_key"])
        print(f"Paired as \"{a.name}\" with project \"{d['project_name']}\". Key stored in the Keychain ({SERVICE}).")
        todo = missing_tools()
        if todo:
            print("\nBefore the first upload, reel-qc needs (paste each line into Terminal):")
            for what, cmd in todo:
                print(f"  {what}:\n    {cmd}")
        return
    if a.cmd == "check":
        todo = missing_tools()
        for what, cmd in todo:
            print(f"{what}:\n  {cmd}")
        return print("All set: reel-qc has everything it needs.") if not todo else None
    key = push.agent_key()
    if a.cmd == "whoami":
        _, d = push.call(f"{api}/agent/me", key)
        return print(json.dumps(d, indent=1))
    _, d = push.call(f"{api}/agent/requests", key, {"title": a.title, "external_ref": a.ref})
    print(json.dumps({k: d[k] for k in ("request_id", "upload_token", "review_url")}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
