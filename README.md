# comfy-ui-video-workflows

Production ComfyUI workflows for AI video from IDNN Productions: dialogue with lip sync, singing, dance, motion and
B-roll, relighting, and voice. All video models are open weights and run locally (tested on an RTX 4090, 24 GB,
ComfyUI 0.44). Each workflow carries a **how to use** note on the canvas with its inputs, limits and timings.

Companion tool: [comfy-ui-agentic-storyboard](https://github.com/idnn-productions/comfy-ui-agentic-storyboard) plans
the shots these workflows render.

## Workflows

### Dialogue and lip sync (voice-driven, start + end frame)

| workflow | what it is for |
|---|---|
| [`dialogue-ltx25distilled`](workflows/dialogue-ltx25distilled.json) | LTX-2.5 distilled, audio-driven first/last frame. Close-up and medium dialogue on clean, high-res start frames. Best default: ~3 min per render. |
| [`dialogue-ltx23`](workflows/dialogue-ltx23.json) | LTX-2.3 audio-driven first/last frame. Better on soft or low-res start frames. |
| [`dialogue-ltx23-latentsync`](workflows/dialogue-ltx23-latentsync.json) | LTX-2.3, then LatentSync 1.6 redraws the mouth. Close-ups; paints over anything in front of the mouth (stage A clip saved for layering). |
| [`dialogue-ltx25dev-latentsync`](workflows/dialogue-ltx25dev-latentsync.json) | LTX-2.5 dev (30 steps) for identity, then LatentSync 1.6. Calm lines only; slow (~10 min). |
| [`wide-ltx25distilled`](workflows/wide-ltx25distilled.json) | LTX-2.5 distilled for wide shots (small face in frame). Seed-fragile: render 3 and keep one. |
| [`wide-ltx23-latentsync`](workflows/wide-ltx23-latentsync.json) | LTX-2.3 + LatentSync on wide shots. Experimental: LatentSync hurts small faces. |

### Singing and dance (music-driven)

| workflow | what it is for |
|---|---|
| [`sing-wan22-s2v`](workflows/sing-wan22-s2v.json) | Wan 2.2 S2V: a start frame + a vocal stem -> a singing performance (no end frame, ~5 s per chunk). |
| [`dance-wandancer`](workflows/dance-wandancer.json) | Wan-Dancer 14B: a reference image + music -> a dance video, up to 30 s (global keyframe pass, then local segments). |

### Motion and B-roll (no lip sync)

| workflow | what it is for |
|---|---|
| [`movement-ltx25distilled-flf`](workflows/movement-ltx25distilled-flf.json) | LTX-2.5 distilled first/last frame, with generated audio. Camera moves and action. |
| [`movement-ltx25distilled-i2v`](workflows/movement-ltx25distilled-i2v.json) | LTX-2.5 distilled image-to-video with the x2 latent upscaler. |
| [`movement-pikah3`](workflows/movement-pikah3.json) | MiniMax H3 first/last frame with the Pika H3 Flex LoRA (6 steps). Strong motion and camera direction. |
| [`broll-wan22-flf`](workflows/broll-wan22-flf.json) | Wan 2.2 14B first/last frame, 20 steps, no audio. Walking shots and wides. |
| [`i2v-hunyuan15`](workflows/i2v-hunyuan15.json) | HunyuanVideo 1.5 image-to-video at 720p/24 fps, optional 1080p super-resolution pass. |
| [`motion-wananimate2`](workflows/motion-wananimate2.json) | Wan-Animate-2: a reference character performs the motion of a driving video (loops over the whole clip). |
| [`motion-wananimate2-distilled`](workflows/motion-wananimate2-distilled.json) | Wan-Animate-2 distilled model, one 81-frame segment per subgraph. |

### Look and audio

| workflow | what it is for |
|---|---|
| [`relight-ltx23`](workflows/relight-ltx23.json) | LTX-2.3 relight IC-LoRA: relight an existing video from a light-sphere control. |
| [`tts-elevenlabs-v4`](workflows/tts-elevenlabs-v4.json) | ElevenLabs Eleven v4 text to speech (PCM wav, character timestamps, 400 ms tail) for the dialogue workflows. |

## Inputs and outputs

Every workflow exposes its inputs as nodes titled `in_*` (`in_start_image`, `in_end_image`, `in_audio`, `in_prompt`,
`in_seed`, ...) and its result as `out_video` (some also save a `_stageA`, `_global` or `_compare` clip). The titles
make them easy to find on the canvas and to drive from scripts through ComfyUI's API.

Load nodes point at placeholder files (`start.png`, `end.png`, `audio.wav`, `reference.png`): pick your own files in
them. Outputs go to `output/video/`.

Dialogue workflows take the voice as the plain wav and a measured length: set `in_speech_seconds` to the voice length;
`in_lead_in_seconds` (1.0) and `in_tail_seconds` (0.75) pad it with silence so the face settles before the first word
and the cut has a handle. Frame counts are computed for you.

## Setup

**Have an RTX 4090?** [SETUP-RTX4090.md](SETUP-RTX4090.md) is our exact machine: versions, launch settings, node packs, measured render times and the pitfalls we hit. `tools/get_models.py` downloads the models for the workflows you pick (list in `models.json`).

1. Update ComfyUI (these use recent core nodes: LTX-2.5, MiniMax H3, Wan-Animate-2, Wan-Dancer, HunyuanVideo 1.5,
   subgraphs, DynamicCombo widgets).
2. Drag a workflow onto the canvas, or copy `workflows/` into `ComfyUI/user/default/workflows/`.
3. Download the models it lists (below), or run `python tools/get_models.py --models-dir <ComfyUI>/models <workflow>`.
4. Install the extra node packs a workflow needs (most need none).

### Extra node packs

| pack | used by |
|---|---|
| Sphere-Light-Render-ComfyUI | `relight-ltx23` |
| [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo) | `relight-ltx23` |
| [KJNodes](https://github.com/kijai/ComfyUI-KJNodes) | `dialogue-ltx23-latentsync`, `dialogue-ltx25dev-latentsync`, `relight-ltx23`, `wide-ltx23-latentsync` |
| comfyui-latentsync-enhanced (LatentSync 1.6) | `dialogue-ltx23-latentsync`, `dialogue-ltx25dev-latentsync`, `wide-ltx23-latentsync` |
| elevenlabs_v4 (in this repo) | `tts-elevenlabs-v4` |

**comfyui-latentsync-enhanced** (registry id `comfyui-latentsync-enhanced`): its requirements leave out `insightface`
(install it into ComfyUI's Python), it needs the LatentSync 1.6 weights under `models/checkpoints/LatentSync-1.6/`
(`latentsync_unet.pt`, `whisper/tiny.pt`, `vae/` = `stabilityai/sd-vae-ft-mse`) and insightface `buffalo_l` under
`ComfyUI/checkpoints/auxiliary/models/`. On torch 2.12 / torchaudio 2.11 / torchvision 0.27 its `nodes.py` needs three
small fixes: call `read_video(..., change_fps=False, use_decord=False)` (otherwise 24 fps input plays ~4% slow),
write audio with `soundfile` instead of `torchaudio.save`, and read the result back with the pack's own cv2
`read_video` instead of the removed `torchvision.io.read_video`.

**elevenlabs_v4**: copy `custom_nodes/elevenlabs_v4/` into `ComfyUI/custom_nodes/`, set the environment variable
`ELEVENLABS_API_KEY`, restart ComfyUI, then put your voice id in the node. The key is never stored in the workflow.

### Models

- **dialogue-ltx25distilled**: `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors`, `gemma4_e2b_it_int8_convrot.safetensors`, `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors`, `ltx-2.5-audio-vae-bf16.safetensors`, `ltx-2.5-video-vae-bf16.safetensors`
- **dialogue-ltx23**: `gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors`, `gemma_3_12B_it_fp4_mixed.safetensors`, `ltx-2.3-22b-dev-fp8.safetensors`, `ltx-2.3-spatial-upscaler-x2-1.1.safetensors`, `ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16.safetensors`
- **dialogue-ltx23-latentsync**: `gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors`, `gemma_3_12B_it_fp4_mixed.safetensors`, `ltx-2.3-22b-dev-fp8.safetensors`, `ltx-2.3-spatial-upscaler-x2-1.1.safetensors`, `ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16.safetensors`
- **dialogue-ltx25dev-latentsync**: `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors`, `gemma4_e2b_it_int8_convrot.safetensors`, `ltx-2.5-22b-dev-transformer-comfy-int8-convrot.safetensors`, `ltx-2.5-audio-vae-bf16.safetensors`, `ltx-2.5-video-vae-bf16.safetensors`
- **wide-ltx25distilled**: `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors`, `gemma4_e2b_it_int8_convrot.safetensors`, `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors`, `ltx-2.5-audio-vae-bf16.safetensors`, `ltx-2.5-video-vae-bf16.safetensors`
- **wide-ltx23-latentsync**: `gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors`, `gemma_3_12B_it_fp4_mixed.safetensors`, `ltx-2.3-22b-dev-fp8.safetensors`, `ltx-2.3-spatial-upscaler-x2-1.1.safetensors`, `ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16.safetensors`
- **sing-wan22-s2v**: `umt5_xxl_fp8_e4m3fn_scaled.safetensors`, `wan2.2_s2v_14B_fp8_scaled.safetensors`, `wan_2.1_vae.safetensors`, `wav2vec2_large_english_fp16.safetensors`
- **dance-wandancer**: `Wan2_1_VAE_bf16.safetensors`, `clip_vision_h.safetensors`, `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors`, `umt5_xxl_fp8_e4m3fn_scaled.safetensors`, `wan2.2_dancer_14b_global_fp8_scaled.safetensors`, `wan2.2_dancer_14b_local_fp8_scaled.safetensors`
- **movement-ltx25distilled-flf**: `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors`, `gemma4_e2b_it_int8_convrot.safetensors`, `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors`, `ltx-2.5-audio-vae-bf16.safetensors`, `ltx-2.5-video-vae-bf16.safetensors`
- **movement-ltx25distilled-i2v**: `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors`, `gemma4_e2b_it_int8_convrot.safetensors`, `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors`, `ltx-2.5-audio-vae-bf16.safetensors`, `ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors`, `ltx-2.5-video-vae-bf16.safetensors`
- **movement-pikah3**: `minimax_h3_audio_vae_fp32.safetensors`, `minimax_h3_fl2va_pruned_int8_convrot.safetensors`, `minimax_h3_video_vae_int8_convrot.safetensors`, `pika_h3_flex_fl2va_v1_bf16.safetensors`, `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`
- **broll-wan22-flf**: `umt5_xxl_fp8_e4m3fn_scaled.safetensors`, `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors`, `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors`, `wan_2.1_vae.safetensors`
- **i2v-hunyuan15**: `byt5_small_glyphxl_fp16.safetensors`, `hunyuanvideo1.5_720p_i2v_fp16.safetensors`, `hunyuanvideo15_vae_fp16.safetensors`, `qwen_2.5_vl_7b_fp8_scaled.safetensors`, `sigclip_vision_patch14_384.safetensors`
- **motion-wananimate2**: `Wan2_1_VAE_bf16.safetensors`, `clip_vision_h.safetensors`, `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors`, `umt5_xxl_fp8_e4m3fn_scaled.safetensors`, `wan_animate_2_int8_convrot.safetensors`
- **motion-wananimate2-distilled**: `Wan2_1_VAE_bf16.safetensors`, `clip_vision_h.safetensors`, `umt5_xxl_fp8_e4m3fn_scaled.safetensors`, `wan_animate_2_distill_int8_convrot.safetensors`
- **relight-ltx23**: `gemma_3_12B_it_fp4_mixed.safetensors`, `ltx-2.3-22b-dev-fp8.safetensors`, `ltx-2.3-22b-ic-lora-relight-1.0.safetensors`, `ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16.safetensors`

Model files go in the usual ComfyUI folders (`diffusion_models`, `checkpoints`, `text_encoders`, `vae`, `loras`,
`latent_upscale_models`, `clip_vision`, `audio_encoders`). Each model has its own license; check it before commercial
use.

## Prompting notes that held up in testing

- Describe the camera like an operator (lens, light source, handheld or locked off) and the delivery (pace, emotion,
  where the eyes go). Let the start and end frames carry the appearance.
- Avoid beautifying words ("flawless skin", "perfect", "8k", "masterpiece"): they push the models toward a plastic look.
  The dialogue workflows ship a negative prompt against plastic skin and bad teeth.
- End frames with a closed or neutral mouth pair with the silent tail and give a clean cut.
- Keep CFG moderate; high CFG overcooks skin and color.

## License

The workflow files and the `elevenlabs_v4` node are MIT licensed (see LICENSE). Models, node packs and the ElevenLabs
API have their own terms.
