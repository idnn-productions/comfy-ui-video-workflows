"""Download the models the workflows need into your ComfyUI models folder.

  python tools/get_models.py --models-dir C:/ComfyUI/models --list                      # what each workflow needs
  python tools/get_models.py --models-dir C:/ComfyUI/models dialogue-ltx25distilled      # one workflow
  python tools/get_models.py --models-dir C:/ComfyUI/models dialogue-ltx25distilled sing-wan22-s2v --dry-run
  python tools/get_models.py --models-dir C:/ComfyUI/models --all

Files already present (any size) are skipped. Downloads resume from a .part file. Gated models (marked in
models.json) need their license accepted on Hugging Face and a token in the HF_TOKEN environment variable.
Stdlib only.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent.parent / "models.json"


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
    a = ap.parse_args()

    models = json.loads(MANIFEST.read_text(encoding="utf-8"))["models"]
    root = Path(a.models_dir)
    every = sorted({w for m in models.values() for w in m["workflows"]})

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
