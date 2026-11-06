#!/usr/bin/env python3
"""Push a local video to AutoReview as a new request file or a new version (stdlib only).

  push.py <file> --request <upload_token> [--asset <asset_id>] [--api https://feedback.aditor.ai/api]

Key: env AUTOREVIEW_AGENT_KEY, else macOS Keychain (service aditor-autoreview-agent). Never printed.
Resumes after an interruption from <file>.arupload.json; deleted on success.
"""
import argparse, json, mimetypes, os, subprocess, sys, urllib.error, urllib.request

PART = 10 * 1024 * 1024
UA = "autoreview-push/1.0"  # Cloudflare blocks the default Python-urllib agent (error 1010)
DEFAULT_API = "https://feedback.aditor.ai/api"


def plan_parts(size, part=PART):
    """[(part_number, offset, length)] covering `size` bytes; empty for an empty file."""
    return [(i + 1, off, min(part, size - off)) for i, off in enumerate(range(0, size, part))]


def fingerprint(path, request, asset):
    st = os.stat(path)
    return {"file": os.path.abspath(path), "size": st.st_size, "mtime": int(st.st_mtime), "request": request, "asset": asset or None}


def merge_state(saved, fp):
    """Reuse saved upload progress only if it is for the same file, request and asset; else start fresh."""
    if not isinstance(saved, dict) or saved.get("fp") != fp or not saved.get("upload_id"):
        return {"fp": fp, "parts": {}}
    return {**saved, "parts": {str(k): v for k, v in (saved.get("parts") or {}).items()}}


def agent_key():
    key = os.environ.get("AUTOREVIEW_AGENT_KEY", "").strip()
    if key:
        return key
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", "aditor-autoreview-agent", "-w"],
                             capture_output=True, text=True, timeout=15)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    sys.exit("No agent key: set AUTOREVIEW_AGENT_KEY or store it in the Keychain "
             "(security add-generic-password -s aditor-autoreview-agent -a $USER -w <key>).")


def call(url, key, body=None, method=None, raw=None, headers=None):
    h = {"User-Agent": UA, **(headers or {})}
    if key:
        h["Authorization"] = "Bearer " + key
    data = raw
    if body is not None:
        data, h["Content-Type"] = json.dumps(body).encode(), "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method or ("POST" if data is not None else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            text = r.read().decode() or "null"
            return r.headers, (json.loads(text) if "json" in (r.headers.get("content-type") or "") else None)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        sys.exit(f"{e.code} {url.split('?')[0].split('/')[-1]}: {detail}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--request", required=True, help="upload_token of the request")
    ap.add_argument("--asset", help="asset_id: upload as a new version of this asset")
    ap.add_argument("--api", default=DEFAULT_API)
    a = ap.parse_args(argv)
    if not os.path.isfile(a.file) or os.path.getsize(a.file) == 0:
        sys.exit("File missing or empty: " + a.file)
    key, api = agent_key(), a.api.rstrip("/")
    base = f"{api}/r/{a.request}/upload"
    size, state_path = os.path.getsize(a.file), a.file + ".arupload.json"
    try:
        saved = json.load(open(state_path))
    except (OSError, ValueError):
        saved = None
    st = merge_state(saved, fingerprint(a.file, a.request, a.asset))
    if not st.get("upload_id"):
        mime = mimetypes.guess_type(a.file)[0] or "video/mp4"
        _, init = call(base + "/initiate", key, {"original_filename": os.path.basename(a.file), "mime_type": mime,
                                                 "file_size_bytes": size, **({"asset_id": a.asset} if a.asset else {})})
        st.update({k: init[k] for k in ("upload_id", "s3_key", "asset_id", "version_id", "version_number")})
    else:
        print("Resuming upload", file=sys.stderr)
    save = lambda: json.dump(st, open(state_path, "w"))
    save()
    plan = plan_parts(size)
    with open(a.file, "rb") as f:
        for n, off, length in plan:
            if str(n) in st["parts"]:
                continue
            _, pre = call(base + "/presign-part", key, {"s3_key": st["s3_key"], "upload_id": st["upload_id"], "part_number": n})
            f.seek(off)
            chunk = f.read(length)
            etag = None
            for attempt in range(3):
                try:  # presigned S3 URL: no Authorization header
                    req = urllib.request.Request(pre["presigned_url"], data=chunk, method="PUT", headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=300) as r:
                        etag = r.headers.get("ETag")
                    break
                except (urllib.error.URLError, OSError):
                    if attempt == 2:
                        sys.exit(f"Part {n} failed; run the same command again to resume.")
            if not etag:
                sys.exit(f"Part {n}: no ETag from storage; run again to resume.")
            st["parts"][str(n)] = etag
            save()
            print(f"part {n}/{len(plan)} done", file=sys.stderr)
    parts = [{"PartNumber": n, "ETag": st["parts"][str(n)]} for n, _, _ in plan]
    _, done = call(base + "/complete", key, {"s3_key": st["s3_key"], "upload_id": st["upload_id"], "parts": parts})
    os.remove(state_path)
    print(f"uploaded asset_id={st['asset_id']} version_id={st['version_id']} version={st['version_number']} status={(done or {}).get('status', 'processing')}")


if __name__ == "__main__":
    main()
