#!/usr/bin/env python3
"""AutoReview setup and requests (stdlib only).

  ar.py pair CODE [--name NAME]      trade the 8-character pairing code for a key, store it in the macOS Keychain
  ar.py whoami                        which project (brand) this machine delivers to
  ar.py request TITLE REF             open a review request (same REF = same request); prints request_id, upload_token, review_url

The key never leaves the Keychain (service aditor-autoreview-agent) and is never printed.
"""
import argparse, json, platform, subprocess, sys

import push

SERVICE = "aditor-autoreview-agent"


def store_key(key):
    # stdin, not argv: the key never shows up in the process list. -U replaces the key of an earlier pairing.
    # ponytail: one key per machine (one brand); per-brand accounts when someone delivers to several brands from one Mac.
    cmd = f'add-generic-password -U -s {SERVICE} -a autoreview -l "AutoReview agent key" -w "{key}"\n'
    out = subprocess.run(["security", "-i"], input=cmd, capture_output=True, text=True, timeout=15)
    if out.returncode != 0:
        sys.exit("Could not write to the Keychain: " + (out.stderr or out.stdout).strip()[:200])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default=push.DEFAULT_API)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pair"); p.add_argument("code"); p.add_argument("--name", default=f"Claude Code on {platform.node()}")
    sub.add_parser("whoami")
    r = sub.add_parser("request"); r.add_argument("title"); r.add_argument("ref")
    a = ap.parse_args(argv)
    api = a.api.rstrip("/")
    if a.cmd == "pair":
        _, d = push.call(f"{api}/agents/pair", None, {"code": a.code.strip(), "agent_name": a.name, "program": "claude-code"})
        store_key(d["agent_key"])
        return print(f"Paired as \"{a.name}\" with project \"{d['project_name']}\". Key stored in the Keychain ({SERVICE}).")
    key = push.agent_key()
    if a.cmd == "whoami":
        _, d = push.call(f"{api}/agent/me", key)
        return print(json.dumps(d, indent=1))
    _, d = push.call(f"{api}/agent/requests", key, {"title": a.title, "external_ref": a.ref})
    print(json.dumps({k: d[k] for k in ("request_id", "upload_token", "review_url")}, indent=1))


if __name__ == "__main__":
    sys.exit(main())
