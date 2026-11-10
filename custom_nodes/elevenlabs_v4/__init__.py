import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
import wave

import torch
from typing_extensions import override

import folder_paths
from comfy_api.latest import ComfyExtension, IO

MODEL_ID = "eleven_v4"
# pcm_44100 needs the Pro tier; pcm_48000 is tried first.
OUTPUT_FORMATS = ("pcm_48000", "pcm_44100")
TAIL_SILENCE_SEC = 0.4
SHOT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def lipsync_input_dir():
    return os.path.join(folder_paths.get_input_directory(), "lipsync")


def api_key():
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key and os.name == "nt":
        # setx only reaches processes started afterwards; Comfy Desktop's reboot keeps the old environment.
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                key = winreg.QueryValueEx(k, "ELEVENLABS_API_KEY")[0]
        except FileNotFoundError:
            pass
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set. Set it in the environment, then restart ComfyUI.")
    return key


def request_tts(text, voice_id, seed, voice_settings, output_format):
    key = api_key()
    body = json.dumps({"text": text, "model_id": MODEL_ID, "seed": seed, "voice_settings": voice_settings}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format={output_format}",
        data=body, method="POST", headers={"xi-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def synthesize(text, voice_id, seed, voice_settings):
    errors = []
    for fmt in OUTPUT_FORMATS:
        try:
            return fmt, request_tts(text, voice_id, seed, voice_settings, fmt)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            # A plan that can't use this output format answers 403; anything else is a real error.
            if e.code != 403:
                raise RuntimeError(f"ElevenLabs {MODEL_ID} request failed ({e.code}): {detail}")
            errors.append(f"{fmt}: {detail}")
    raise RuntimeError("No PCM output format is available on this ElevenLabs plan: " + " | ".join(errors))


def write_wav(path, pcm, sample_rate):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)


class ElevenLabsV4TTS(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="ElevenLabsV4TTS",
            display_name="ElevenLabs v4 TTS",
            category="audio/lipsync",
            description="Eleven v4 text to speech as 16-bit PCM with character timestamps and 400 ms trailing silence. Reads ELEVENLABS_API_KEY from the environment.",
            inputs=[
                IO.String.Input("text", multiline=True),
                IO.String.Input("voice_id"),
                IO.Int.Input("seed", default=1, min=0, max=4294967295, control_after_generate=True),
                IO.Float.Input("stability", default=0.5, min=0.0, max=1.0, step=0.01),
                IO.Float.Input("similarity_boost", default=0.75, min=0.0, max=1.0, step=0.01),
                IO.Float.Input("speed", default=1.0, min=0.7, max=1.2, step=0.01),
                IO.String.Input("shot_id", default="", optional=True,
                                tooltip="If set, writes audio.wav and alignment.json to input/lipsync/<shot_id>/."),
            ],
            outputs=[IO.Audio.Output(), IO.String.Output(display_name="alignment")],
        )

    @classmethod
    def validate_inputs(cls, shot_id=""):
        if shot_id and not SHOT_ID_RE.match(shot_id):
            return "shot_id may only contain letters, digits, '_' and '-'."
        return True

    @classmethod
    def execute(cls, text, voice_id, seed, stability, similarity_boost, speed, shot_id="") -> IO.NodeOutput:
        voice_settings = {"stability": stability, "similarity_boost": similarity_boost, "speed": speed}
        key = json.dumps({"text": text, "voice_id": voice_id, "model": MODEL_ID, "settings": voice_settings, "seed": seed}, sort_keys=True)
        digest = hashlib.sha256(key.encode()).hexdigest()[:24]
        cache_dir = os.path.join(lipsync_input_dir(), "_tts_cache")
        wav_path = os.path.join(cache_dir, digest + ".wav")
        align_path = os.path.join(cache_dir, digest + ".json")

        if not (os.path.exists(wav_path) and os.path.exists(align_path)):
            fmt, resp = synthesize(text, voice_id, seed, voice_settings)
            sample_rate = int(fmt.split("_")[1])
            pcm = base64.b64decode(resp["audio_base64"])
            pcm += b"\x00\x00" * round(sample_rate * TAIL_SILENCE_SEC)
            os.makedirs(cache_dir, exist_ok=True)
            write_wav(wav_path, pcm, sample_rate)
            meta = {"model_id": MODEL_ID, "voice_id": voice_id, "seed": seed, "voice_settings": voice_settings,
                    "output_format": fmt, "tail_silence_sec": TAIL_SILENCE_SEC, "text": text,
                    "alignment": resp.get("alignment"), "normalized_alignment": resp.get("normalized_alignment")}
            with open(align_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=1)

        with wave.open(wav_path, "rb") as w:
            sample_rate = w.getframerate()
            pcm = w.readframes(w.getnframes())
        with open(align_path, encoding="utf-8") as f:
            alignment = f.read()

        if shot_id:
            shot_dir = os.path.join(lipsync_input_dir(), shot_id)
            os.makedirs(shot_dir, exist_ok=True)
            write_wav(os.path.join(shot_dir, "audio.wav"), pcm, sample_rate)
            with open(os.path.join(shot_dir, "alignment.json"), "w", encoding="utf-8") as f:
                f.write(alignment)

        waveform = torch.frombuffer(bytearray(pcm), dtype=torch.int16).float().div(32768.0).reshape(1, 1, -1)
        return IO.NodeOutput({"waveform": waveform, "sample_rate": sample_rate}, alignment)


class ElevenLabsV4Extension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[IO.ComfyNode]]:
        return [ElevenLabsV4TTS]


async def comfy_entrypoint() -> ElevenLabsV4Extension:
    return ElevenLabsV4Extension()
