"""Download the models the workflows need into your ComfyUI models folder.

  python tools/get_models.py --models-dir C:/ComfyUI/models --list                      # what each workflow needs
  python tools/get_models.py --models-dir C:/ComfyUI/models dialogue-ltx25distilled      # one workflow
  python tools/get_models.py --models-dir C:/ComfyUI/models dialogue-ltx25distilled sing-wan22-s2v --dry-run
  python tools/get_models.py --models-dir C:/ComfyUI/models --all

Files already present (any size) are skipped. Downloads resume from a .part file. Gated models (marked in
models.json) need their license accepted on Hugging Face and a token in the HF_TOKEN environment variable.

Verify (downloads nothing, changes nothing; exit code 1 if anything drifted):
  python tools/get_models.py --models-dir C:/ComfyUI/models --verify [workflows...]
         [--comfy-dir C:/ComfyUI] [--comfy-url http://127.0.0.1:8188] [--deep --hash-cache hashes.json]
  - models: missing files, and size differences against models.json (--deep: full SHA-256, cached by size+mtime)
  - stack: ComfyUI core/frontend/templates, Python and pinned packages against pins.json (the stack the workflows
    were tested on; read from the running ComfyUI and from the install's site-packages)
  - node packs: present, at the pinned version/commit, and patched files carrying their patch
Stdlib only.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "models.json"
PINS = ROOT / "pins.json"


def sha256_of(path, cache):
    st = path.stat()
    key = str(path.resolve())
    hit = cache.get(key)
    if hit and hit["size"] == st.st_size and hit["mtime"] == int(st.st_mtime):
        return hit["sha256"]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    cache[key] = {"size": st.st_size, "mtime": int(st.st_mtime), "sha256": h.hexdigest()}
    return cache[key]["sha256"]


def site_packages(comfy_dir):
    for cand in (comfy_dir / ".venv" / "Lib" / "site-packages", *sorted((comfy_dir / ".venv" / "lib").glob("python3*/site-packages")),
                 comfy_dir.parent / "python_embeded" / "Lib" / "site-packages"):
        if cand.is_dir():
            return cand
    return None


def dist_versions(sp):
    out = {}
    for d in sp.glob("*.dist-info"):
        m = re.match(r"(.+?)-(\d[^-]*)\.dist-info$", d.name)
        if m:
            out[m.group(1).lower().replace("_", "-")] = m.group(2)
    return out


def pack_state(pack_dir):
    v = None
    py = pack_dir / "pyproject.toml"
    if py.exists():
        m = re.search(r'^version\s*=\s*"([^"]+)"', py.read_text(encoding="utf-8", errors="replace"), re.M)
        v = m.group(1) if m else None
    commit = None
    if (pack_dir / ".git").exists():
        r = subprocess.run(["git", "-C", str(pack_dir), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
        commit = r.stdout.strip() or None
    return v, commit


def verify(a, models, wanted):
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    problems, notes = [], []
    root = Path(a.models_dir)
    cache_path = Path(a.hash_cache) if a.hash_cache else None
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path and cache_path.exists() else {}
    names = [n for n, m in sorted(models.items()) if not wanted or set(m["workflows"]) & wanted]
    for n in names:
        m = models[n]
        p = root / m["folder"] / n
        if not p.exists():
            problems.append(f"MISSING  model {m['folder']}/{n}")
            continue
        size = p.stat().st_size
        if m.get("bytes") and size != m["bytes"]:
            problems.append(f"SIZE     model {m['folder']}/{n}: {size} bytes, expected {m['bytes']}")
            continue
        if a.deep and m.get("sha256"):
            if sha256_of(p, cache) != m["sha256"]:
                problems.append(f"HASH     model {m['folder']}/{n}: SHA-256 differs from models.json")
    if cache_path:
        cache_path.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    notes.append(f"models: {len(names)} checked ({'size + SHA-256' if a.deep else 'presence + size'})")

    # stack
    try:
        with urllib.request.urlopen(a.comfy_url.rstrip("/") + "/system_stats", timeout=5) as r:
            sysd = json.load(r)["system"]
        have = {"comfyui": sysd.get("comfyui_version"), "frontend": sysd.get("required_frontend_version"),
                "templates": sysd.get("installed_templates_version"),
                "python": (sysd.get("python_version") or "").split(" ")[0]}
        for k, want in (("comfyui", pins["comfyui"]["version"]), ("frontend", pins["comfyui"]["frontend"]),
                        ("templates", pins["comfyui"]["templates"]), ("python", pins["python"])):
            if have[k] and have[k] != want:
                problems.append(f"STACK    {k} {have[k]} (tested on {want})")
        notes.append(f"stack: ComfyUI {have['comfyui']} at {a.comfy_url}")
    except (OSError, ValueError, KeyError) as e:
        notes.append(f"stack: ComfyUI not reachable at {a.comfy_url} ({e.__class__.__name__}); core version not checked")
    if a.comfy_dir:
        cd = Path(a.comfy_dir)
        sp = site_packages(cd)
        if sp:
            dv = dist_versions(sp)
            for pkg, want in pins["packages"].items():
                got = dv.get(pkg.lower())
                if got is None:
                    problems.append(f"STACK    package {pkg} not installed (tested with {want})")
                elif got != want:
                    problems.append(f"STACK    package {pkg} {got} (tested with {want})")
        else:
            notes.append("packages: no site-packages found under --comfy-dir; not checked")
        for pack, pin in pins["node_packs"].items():
            if wanted and not set(pin.get("workflows", [])) & wanted:
                continue
            d = cd / "custom_nodes" / pack
            if not d.is_dir():
                problems.append(f"PACK     {pack} missing (needed by {', '.join(pin.get('workflows', []))})")
                continue
            v, commit = pack_state(d)
            if pin.get("version") and v != pin["version"]:
                problems.append(f"PACK     {pack} version {v} (tested with {pin['version']})")
            if pin.get("commit") and commit and not commit.startswith(pin["commit"]) and not pin["commit"].startswith(commit):
                problems.append(f"PACK     {pack} commit {commit} (tested at {pin['commit']})")
            for fn, h in pin.get("files", {}).items():
                fp = d / fn
                got = hashlib.sha256(fp.read_bytes()).hexdigest() if fp.exists() else None
                if got == h["patched_sha256"]:
                    continue
                if got == h.get("stock_sha256"):
                    problems.append(f"PATCH    {pack}/{fn} is the stock file: apply {pin['patch']}")
                else:
                    problems.append(f"PATCH    {pack}/{fn} differs from both the stock and the patched file")
        notes.append(f"node packs and packages checked in {cd}")
    else:
        notes.append("node packs and packages: pass --comfy-dir to check them")
    for n in notes:
        print("  " + n)
    for p in problems:
        print(p)
    print("verify:", "clean" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


def human(n):
    return f"{n / 1e9:.1f} GB"


def download(url, dest, token=None):
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url, headers={"User-Agent": "comfy-ui-video-workflows/get_models"})
    if have:
        req.add_header("Range", f"bytes={have}-")
    if token and "huggingface.co" in url:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        r = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise SystemExit(f"{dest.name}: HTTP {e.code}. Gated model: accept its license on Hugging Face and set "
                             "HF_TOKEN to a token with read access.") from e
        if e.code == 416:  # already complete
            part.replace(dest)
            return
        raise
    with r:
        if have and r.status != 206:  # server ignored the range: start over
            have = 0
        total = have + int(r.headers.get("Content-Length") or 0)
        t0, done = time.time(), have
        with open(part, "ab" if have else "wb") as f:
            while True:
                chunk = r.read(1 << 22)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                rate = (done - have) / max(time.time() - t0, 1e-6)
                print(f"\r  {human(done)} / {human(total)}  {rate / 1e6:5.1f} MB/s", end="", flush=True)
    print()
    part.replace(dest)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workflows", nargs="*", help="workflow names (file names without .json)")
    ap.add_argument("--models-dir", required=True, help="ComfyUI's models folder")
    ap.add_argument("--all", action="store_true", help="every model for every workflow")
    ap.add_argument("--list", action="store_true", help="show workflows with their download size and exit")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true", help="check the install against models.json and pins.json")
    ap.add_argument("--comfy-dir", help="ComfyUI folder (holds custom_nodes/ and .venv/) for --verify")
    ap.add_argument("--comfy-url", default="http://127.0.0.1:8188", help="running ComfyUI for --verify")
    ap.add_argument("--deep", action="store_true", help="--verify: full SHA-256 of every model file")
    ap.add_argument("--hash-cache", help="--verify --deep: JSON file caching hashes by size and mtime")
    a = ap.parse_args()

    models = json.loads(MANIFEST.read_text(encoding="utf-8"))["models"]
    root = Path(a.models_dir)
    every = sorted({w for m in models.values() for w in m["workflows"]})

    if a.verify:
        unknown = set(a.workflows) - set(every)
        if unknown:
            sys.exit(f"unknown workflow(s): {', '.join(sorted(unknown))}. Use --list.")
        sys.exit(verify(a, models, set(a.workflows)))

    if a.list:
        for w in every:
            need = [n for n, m in models.items() if w in m["workflows"]]
            missing = [n for n in need if not (root / models[n]["folder"] / n).exists()]
            gb = sum(models[n]["gb"] for n in missing)
            print(f"{w:32} {len(need):2} files, {len(missing):2} missing ({gb:5.1f} GB to download)")
        return

    unknown = set(a.workflows) - set(every)
    if unknown:
        sys.exit(f"unknown workflow(s): {', '.join(sorted(unknown))}. Use --list.")
    if not a.workflows and not a.all:
        sys.exit("name one or more workflows, or --all. Use --list to see them.")
    want = [n for n, m in sorted(models.items()) if a.all or set(m["workflows"]) & set(a.workflows)]
    todo = [n for n in want if not (root / models[n]["folder"] / n).exists()]
    print(f"{len(want)} files needed, {len(want) - len(todo)} already present, "
          f"{len(todo)} to download ({sum(models[n]['gb'] for n in todo):.1f} GB)")
    token = os.environ.get("HF_TOKEN")
    for i, n in enumerate(todo, 1):
        m = models[n]
        dest = root / m["folder"] / n
        flag = "  [gated: needs HF_TOKEN]" if m.get("gated") else ""
        print(f"[{i}/{len(todo)}] {m['folder']}/{n}  {m['gb']} GB{flag}")
        if a.dry_run:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        download(m["url"], dest, token)


if __name__ == "__main__":
    main()
