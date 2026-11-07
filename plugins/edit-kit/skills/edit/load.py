#!/usr/bin/env python3
"""Cache for the Edit Kit that Gen serves (tool `edit_kit`). Stdlib only.

  load.py version                 print the cached version (empty if none)
  load.py write BUNDLE.json|-     write a bundle from Gen into the cache ("-" reads stdin)

BUNDLE.json is the tool's answer: {"version", "files": {path: text}} or {"version", "current": true}.
`current` leaves the cache alone. A new bundle is written to a temp folder next to the cache and
renamed into place; absolute paths and `..` are refused before anything is written.
"""
import json, os, posixpath, shutil, sys, tempfile
from pathlib import Path

def cache_dir():
    return Path(os.environ.get("ADITOR_EDIT_KIT_CACHE") or Path.home() / ".cache" / "aditor-edit-kit")

def cached_version(cache):
    try:
        return (cache / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return ""

def safe_path(p):
    if not isinstance(p, str) or not p or "\0" in p or "\\" in p or p.startswith("/") or (len(p) > 1 and p[1] == ":"):
        raise ValueError(f"unsafe path in bundle: {p!r}")
    if ".." in p.split("/") or posixpath.normpath(p) != p or p in (".", "VERSION"):
        raise ValueError(f"unsafe path in bundle: {p!r}")
    return p

def write_bundle(bundle, cache):
    """Returns 'current' (cache untouched) or 'written'. Raises ValueError on a bad bundle; the cache stays as it was."""
    version = bundle.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("bundle has no version")
    if bundle.get("current") is True:
        if cached_version(cache) != version:
            raise ValueError("Gen says the cache is current, but the cache is empty or another version")
        return "current"
    files = bundle.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("bundle has no files")
    for p, text in files.items():
        safe_path(p)
        if not isinstance(text, str):
            raise ValueError(f"file is not text: {p!r}")
    cache.parent.mkdir(parents=True, exist_ok=True)
    for left in cache.parent.glob(cache.name + ".*-*"):  # leftovers of a killed run
        shutil.rmtree(left, ignore_errors=True)
    tmp = Path(tempfile.mkdtemp(prefix=cache.name + ".tmp-", dir=cache.parent))
    old = None
    try:
        for p, text in files.items():
            dest = tmp / p
            if not dest.resolve().is_relative_to(tmp.resolve()):
                raise ValueError(f"unsafe path in bundle: {p!r}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8", newline="")
            if p.endswith((".py", ".sh")):
                dest.chmod(0o755)
        (tmp / "VERSION").write_text(version + "\n", encoding="utf-8")
        if os.path.lexists(cache):
            old = cache.with_name(cache.name + ".old-" + tmp.name.rsplit("-", 1)[-1])
            cache.rename(old)
        tmp.rename(cache)
    except BaseException:
        if old is not None and not cache.exists():
            old.rename(cache)
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    if old is not None:
        shutil.rmtree(old, ignore_errors=True)
    return "written"

def main(argv):
    cache = cache_dir()
    if argv[:1] == ["version"]:
        print(cached_version(cache))
        return 0
    if len(argv) == 2 and argv[0] == "write":
        try:
            if argv[1] == "-":
                bundle = json.loads(sys.stdin.buffer.read().decode("utf-8"))
            else:
                with open(argv[1], encoding="utf-8") as f:
                    bundle = json.load(f)
            if not isinstance(bundle, dict):
                raise ValueError("bundle is not an object")
            print(f"{write_bundle(bundle, cache)} {bundle['version']} {cache}")
            return 0
        except (OSError, ValueError) as e:  # json.JSONDecodeError is a ValueError
            print(f"FAIL  {e}", file=sys.stderr)
            return 1
    print(__doc__, file=sys.stderr)
    return 2

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
