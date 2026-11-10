# Our setup: RTX 4090 (24 GB), Windows 11

This is the exact machine these workflows were built and tested on. Copy it and every workflow here runs as
described, with the render times below.

## Hardware

| part | ours | notes |
|---|---|---|
| GPU | RTX 4090, 24 GB | Every workflow peaks at 22-24 GB. ComfyUI offloads the rest to system RAM. |
| RAM | 64 GB | The 20-30 GB text encoders and 14-21 GB video models are swapped through RAM. 32 GB is not enough for the LTX and H3 workflows. |
| Disk | NVMe SSD, ~350 GB free | All models together are 306 GB (`models.json`); one workflow needs 24-46 GB. |
| OS | Windows 11 Pro | Linux works the same; only the paths differ. |

## Software

| | version |
|---|---|
| ComfyUI | 0.44.2, commit `e6515b16` (Comfy Desktop 1.1.9, standalone NVIDIA bundle `v0.42.1-env1`) |
| frontend / templates | 1.57.6 / 0.11.103 |
| ComfyUI-Manager | 3.42 |
| Python | 3.13.12 (the one bundled with ComfyUI) |
| PyTorch | 2.12.1+cu130, CUDA 13.0 (torchaudio 2.11.0+cu130, torchvision 0.27.1+cu130) |
| NVIDIA driver | 617.42 (any driver with CUDA 13 support) |
| SageAttention (optional) | sageattention 2.2.0+cu130torch2.10.0andhigher.post6, triton-windows 3.8.0.post29 |
| node packs | ComfyUI-KJNodes 1.5.3, ComfyUI-LTXVideo 1.1.0, comfyui-latentsync-enhanced 1.0.5 (+ patch), Sphere-Light-Render-ComfyUI 1.0.0 (`cc89da6`) |

The same list is machine-readable in `pins.json`; `tools/get_models.py --verify` compares an install against it.

Older ComfyUI versions lack nodes these workflows use (LTX-2.5, MiniMax H3, Wan-Animate-2, Wan-Dancer, HunyuanVideo 1.5
nodes, subgraphs). Update first.

## Step by step

1. **Install ComfyUI.** Comfy Desktop (https://www.comfy.org/download) or the portable NVIDIA build. Update to 0.44.x
   or newer.
2. **Launch flags: none.** We run with no extra launch arguments, apart from ComfyUI-Manager being enabled.
   **Do not add `--use-sage-attention` globally**: it turns Wan-Dancer output solid black (NaNs) on the 4090. See
   "Speed-ups" for using Sage on the models where it is safe.
3. **Get the workflows.** Clone this repo, then drag a file from `workflows/` onto the canvas. To have them in the
   workflow browser, copy them into `ComfyUI/user/default/workflows/`.
4. **Download the models** for the workflows you want:
   ```bash
   python tools/get_models.py --models-dir "C:/path/to/ComfyUI/models" --list
   python tools/get_models.py --models-dir "C:/path/to/ComfyUI/models" dialogue-ltx25distilled sing-wan22-s2v
   ```
   Files land in the right subfolders. Downloads resume if interrupted. `dialogue-ltx25dev-latentsync` uses the gated
   LTX-2.5 dev model: accept its license at https://huggingface.co/Lightricks/LTX-2.5 and set `HF_TOKEN` first.
5. **Install node packs**, only for the workflows that need them (ComfyUI-Manager > Custom Nodes Manager):

   | pack | version tested | needed by |
   |---|---|---|
   | ComfyUI-KJNodes | 1.5.3 | LatentSync and relight workflows |
   | comfyui-latentsync-enhanced | 1.0.5 | `*-latentsync` workflows (see below) |
   | ComfyUI-LTXVideo | 1.1.0 | `relight-ltx23` |
   | Sphere-Light-Render-ComfyUI | 1.0.0 | `relight-ltx23` |
   | elevenlabs_v4 (this repo) | | `tts-elevenlabs-v4` |

   Installing a pack makes ComfyUI-Manager restart ComfyUI, so don't install while something renders.
6. **LatentSync setup** (only for `*-latentsync`):
   - `pip install insightface` into ComfyUI's Python (the pack's requirements leave it out).
   - Weights in `models/checkpoints/LatentSync-1.6/`: `latentsync_unet.pt` (5 GB) and `whisper/tiny.pt` from
     https://huggingface.co/ByteDance/LatentSync-1.6, plus `vae/` = https://huggingface.co/stabilityai/sd-vae-ft-mse.
   - Face detector: insightface `buffalo_l` unpacked to `ComfyUI/checkpoints/auxiliary/models/buffalo_l/`, so it
     doesn't download at run time.
   - On torch 2.12 / torchaudio 2.11 / torchvision 0.27 the pack's `nodes.py` needs three one-line fixes:
     call `read_video(..., change_fps=False, use_decord=False)` (otherwise 24 fps input plays about 4% slow), write
     audio with `soundfile` instead of `torchaudio.save`, and read the result with the pack's own cv2 `read_video`
     instead of the removed `torchvision.io.read_video`. They are in `patches/comfyui-latentsync-enhanced-1.0.5.patch`:
     from the pack's folder, `patch -p1 < <this repo>/patches/comfyui-latentsync-enhanced-1.0.5.patch` (Git Bash on
     Windows). A pack update overwrites the fixes; `--verify` reports it.
7. **ElevenLabs voice** (only for `tts-elevenlabs-v4`): copy `custom_nodes/elevenlabs_v4/` into
   `ComfyUI/custom_nodes/`, set `ELEVENLABS_API_KEY` as a user environment variable (`setx ELEVENLABS_API_KEY ...`),
   restart ComfyUI, and put your voice id in the node.

## Keep it pinned

Workflows behave the way they were tested only on the tested stack, so stop things changing under you:

- **Turn off automatic updates for the install.** In Comfy Desktop, auto-update is a per-install setting
  (`autoUpdateComfyUI` in the install's record, on by default). With it on, Desktop moves the ComfyUI core and
  frontend forward on its own: ours went from 0.44.2 to 0.45.1 between two sessions. Turn it off in the install's
  settings in the app, and update on purpose.
- **Check after any update or node install:**
  ```bash
  python tools/get_models.py --models-dir "C:/path/to/ComfyUI/models" --verify --comfy-dir "C:/path/to/ComfyUI"
  ```
  It reports missing or changed model files, a core, frontend, Python or package version that differs from
  `pins.json`, node packs at a different version, and patched files that lost their patch. `--deep` adds a full
  SHA-256 of every model (cache it with `--hash-cache hashes.json`; about 5 minutes for all 306 GB, seconds after).
- **Rollback:** Comfy Desktop keeps a snapshot before and after each update and node install
  (`<install>/.launcher/snapshots/`); restore from the app.

## Render times on the 4090

Measured on this machine (median of our logged runs, default settings in each workflow, no Sage):

| workflow | output | time | peak VRAM |
|---|---|---|---|
| `dialogue-ltx25distilled` | 704x1280, 265 frames (11 s) | ~2 min | 23.9 GB |
| `wide-ltx25distilled` | 704x1280, 265 frames | ~2 min | 23.7 GB |
| `dialogue-ltx23` | 704x1280, 265 frames | ~1-1.5 min | 24.0 GB |
| `dialogue-ltx23-latentsync` | LTX-2.3 + LatentSync on a 7 s clip | ~1.5 + 2.5 min | 24.0 GB |
| `dialogue-ltx25dev-latentsync` | 30-step dev + LatentSync | ~7-10 + 2.5 min | 24 GB |
| `movement-ltx25distilled-flf` | 121 frames (5 s) | ~1 min | 23.7 GB |
| `movement-ltx25distilled-i2v` | 121 frames | ~0.5-1 min | 23.9 GB |
| `movement-pikah3` | 124 frames (5 s), 6 steps | ~1-1.5 min | 23.8 GB |
| `relight-ltx23` | 121 frames | ~2.5 min | 23.7 GB |
| `sing-wan22-s2v` | 832x480, one ~5 s chunk | ~2 min | 23.1 GB |
| `dance-wandancer` | 480x832, 15 s | ~8 min | 22.1 GB |
| `broll-wan22-flf` | 704x1280, 81 frames (5 s), 20 steps | ~12.5 min | 23.0 GB |
| `i2v-hunyuan15` | 720p, 121 frames, 20 steps | ~14 min | 24.1 GB |
| `motion-wananimate2*` | 482x854 | not logged | |

The first run of a workflow is slower: models load from disk (20-60 s each on NVMe).

## Speed-ups (optional)

- **SageAttention per model, not globally.** With sageattention 2.2 + triton-windows installed, add KJNodes'
  **Patch Sage Attention KJ** (`sage_attention: auto`) right after the model loader in the LTX and MiniMax H3 / Pika
  workflows. Leave it off for Wan-Dancer (black frames) and test before using it on other Wan workflows.
- **Drafts.** Wan 2.2 has 4-step lightx2v templates (`video_wan2_2_14B_flf2v`, ~2 min instead of ~12) for blocking
  out motion; HunyuanVideo 1.5 has EasyCache (bypassed in the workflow).

## Things that bit us

- **One heavy model at a time.** Switching between LTX, Wan and H3 workflows leaves the old model in VRAM/RAM.
  Use ComfyUI-Manager's "Unload models" (or `POST /free` with `{"unload_models": true, "free_memory": true}`)
  between them.
- **Out of system RAM looks like a hang.** If Windows runs out of RAM, or the GPU spills into "shared GPU memory",
  a step that took a minute takes hours while the GPU still shows 100%. Close other apps, and in NVIDIA Control
  Panel set **CUDA - Sysmem Fallback Policy** to **Prefer No Sysmem Fallback** for ComfyUI's python.exe so it fails
  fast instead.
- **Max length.** LTX-2.3: 10 s per clip. LTX-2.5: 20 s. Wan 2.2: 81 frames (5 s at 16 fps); longer loops or drifts.
  Wan renders 16 fps: interpolate (RIFE in comfyui-frame-interpolation) for a 24 fps edit.
- **Wan-Dancer size.** 720x1280 at 15 s crashed the GPU driver on our 4090. Stay at the default 480x832, or test 5 s
  first at a larger size.
- **Validator false positive.** Some checkers report `'center' not in scale_method` / missing `resize_type.crop` on
  `ResizeImageMaskNode`. ComfyUI itself accepts the workflow; ignore it.
- **MiniMax H3 text encoder** on disk is the NVFP4 build (`qwen3vl_32b_minimax_h3_nvfp4_awq`); it runs on the 4090.

## Folder layout we use

```
ComfyUI/models/
  diffusion_models/   LTX-2.5, MiniMax H3, Wan 2.2, Wan-Dancer, Wan-Animate-2, HunyuanVideo 1.5
  checkpoints/        ltx-2.3-22b-dev-fp8, LatentSync-1.6/
  text_encoders/      gemma 3 / gemma 4, umt5, qwen VL, byt5
  vae/  loras/  latent_upscale_models/  clip_vision/  audio_encoders/
```

Comfy Desktop can keep models outside the install (Settings > model folders); the workflows only use file names.
