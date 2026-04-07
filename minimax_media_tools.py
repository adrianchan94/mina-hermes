#!/usr/bin/env python3
"""
MiniMax Media Tools — Native media generation tools included in MiniMax Token Plan.

Tools:
- minimax_image_understand: Analyze images using MiniMax VLM
- minimax_image_generate: Generate images from text prompts
- minimax_speech: Text-to-speech with emotion/voice control
- minimax_music: Generate music with lyrics and style
- minimax_video: Generate videos from text or images (async)

All tools use MINIMAX_API_KEY — no extra API keys needed.
"""

import base64
import json
import logging
import os
import time
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_API_HOST = None
_API_KEY = None
_OUTPUT_DIR = "/opt/data/media"


def _get_api():
    global _API_HOST, _API_KEY
    if _API_KEY is None:
        _API_KEY = os.getenv("MINIMAX_API_KEY", "").strip()
        _API_HOST = os.getenv("MINIMAX_API_HOST", "https://api.minimax.io").strip().rstrip("/")
    return _API_HOST, _API_KEY


def _ensure_output_dir():
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    return _OUTPUT_DIR


def _check_minimax_key() -> bool:
    _, key = _get_api()
    return bool(key)


# ─── Image Understanding ────────────────────────────────────────────────────

def minimax_image_understand(image_source: str, prompt: str = "Describe this image in detail.") -> str:
    host, key = _get_api()
    if not key:
        return json.dumps({"error": "MINIMAX_API_KEY not set"})

    # Convert file path or URL to base64 data URL
    if image_source.startswith("data:"):
        image_url = image_source
    elif os.path.isfile(image_source):
        ext = Path(image_source).suffix.lower().lstrip(".")
        if ext == "jpg":
            ext = "jpeg"
        with open(image_source, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        image_url = f"data:image/{ext};base64,{b64}"
    elif image_source.startswith("http"):
        # Download and convert to base64
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(image_source)
                resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")
            b64 = base64.b64encode(resp.content).decode()
            image_url = f"data:{content_type};base64,{b64}"
        except Exception as e:
            return json.dumps({"error": f"Failed to download image: {e}"})
    else:
        return json.dumps({"error": f"Invalid image source: {image_source}"})

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{host}/v1/coding_plan/vlm",
                json={"prompt": prompt, "image_url": image_url},
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "MM-API-Source": "Minimax-MCP",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return json.dumps({
            "success": True,
            "analysis": data.get("content", ""),
        })
    except Exception as e:
        logger.error("MiniMax image understand failed: %s", e)
        return json.dumps({"error": str(e)})


# ─── Image Generation ────────────────────────────────────────────────────────

def minimax_image_generate(prompt: str, aspect_ratio: str = "1:1", n: int = 1) -> str:
    host, key = _get_api()
    if not key:
        return json.dumps({"error": "MINIMAX_API_KEY not set"})

    out_dir = _ensure_output_dir()

    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{host}/v1/image_generation",
                json={
                    "model": "image-01",
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "n": min(n, 4),
                    "response_format": "url",
                    "prompt_optimizer": True,
                },
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        image_urls = data.get("data", {}).get("image_urls", [])
        if not image_urls:
            return json.dumps({"error": "No images generated", "raw": data})

        # Download images locally for Telegram sending
        local_paths = []
        for i, url in enumerate(image_urls):
            with httpx.Client(timeout=60) as client:
                img_resp = client.get(url)
                img_resp.raise_for_status()
            ts = int(time.time())
            path = os.path.join(out_dir, f"generated_{ts}_{i}.png")
            with open(path, "wb") as f:
                f.write(img_resp.content)
            local_paths.append(path)

        media_tags = "\n".join(f"MEDIA:{p}" for p in local_paths)
        return json.dumps({
            "success": True,
            "images": local_paths,
            "urls": image_urls,
            "media_tag": media_tags,
        })
    except Exception as e:
        logger.error("MiniMax image generation failed: %s", e)
        return json.dumps({"error": str(e)})


# ─── Speech / TTS ────────────────────────────────────────────────────────────

def minimax_speech(
    text: str,
    voice_id: str = "English_aussie_buddy_vv2",
    emotion: str = "happy",
    speed: float = 1.0,
) -> str:
    host, key = _get_api()
    if not key:
        return json.dumps({"error": "MINIMAX_API_KEY not set"})

    out_dir = _ensure_output_dir()

    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{host}/v1/t2a_v2",
                json={
                    "model": "speech-2.8-hd",
                    "text": text[:10000],
                    "stream": False,
                    "voice_setting": {
                        "voice_id": voice_id,
                        "speed": speed,
                        "emotion": emotion,
                    },
                    "audio_setting": {
                        "format": "mp3",
                        "sample_rate": 32000,
                    },
                },
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        audio_hex = data.get("data", {}).get("audio", "")
        if not audio_hex:
            return json.dumps({"error": "No audio generated", "raw": data})

        audio_bytes = bytes.fromhex(audio_hex)
        ts = int(time.time())
        path = os.path.join(out_dir, f"speech_{ts}.mp3")
        with open(path, "wb") as f:
            f.write(audio_bytes)

        return json.dumps({
            "success": True,
            "file_path": path,
            "media_tag": f"[[audio_as_voice]]\nMEDIA:{path}",
            "duration": data.get("extra_info", {}).get("audio_length", 0),
        })
    except Exception as e:
        logger.error("MiniMax speech failed: %s", e)
        return json.dumps({"error": str(e)})


# ─── Music Generation ────────────────────────────────────────────────────────

def minimax_music(
    prompt: str,
    lyrics: str = "",
    instrumental: bool = False,
) -> str:
    host, key = _get_api()
    if not key:
        return json.dumps({"error": "MINIMAX_API_KEY not set"})

    out_dir = _ensure_output_dir()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    # Try music-2.5+ first (supports instrumental), fall back to music-2.5
    body = {
        "model": "music-2.5+",
        "prompt": prompt[:2000],
        "output_format": "url",  # URL instead of hex — avoids massive response
        "audio_setting": {
            "format": "mp3",
            "sample_rate": 44100,
        },
    }
    if instrumental:
        body["is_instrumental"] = True
    if lyrics and not instrumental:
        body["lyrics"] = lyrics[:3500]

    try:
        # First attempt: music-2.5+
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{host}/v1/music_generation", json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        status = data.get("base_resp", {}).get("status_code", -1)
        status_msg = data.get("base_resp", {}).get("status_msg", "")

        # Fallback to music-2.5 if plan rejects music-2.5+
        if status != 0 and "not support model" in status_msg:
            body_25 = {
                "model": "music-2.5",
                "prompt": prompt[:2000],
                "output_format": "url",
                "audio_setting": body["audio_setting"],
            }
            if lyrics:
                body_25["lyrics"] = lyrics[:3500]
            elif instrumental:
                # music-2.5 can't do instrumental, need lyrics
                return json.dumps({"error": "Instrumental requires music-2.5+ (not in plan). Provide lyrics instead."})
            else:
                # lyrics_optimizer also not in plan — require explicit lyrics
                return json.dumps({"error": "Music-2.5 requires lyrics. Please provide lyrics with [Verse], [Chorus] tags."})

            # Music gen takes 60-120s — use long timeout
            with httpx.Client(timeout=httpx.Timeout(connect=30, read=300, write=30, pool=30)) as client:
                resp = client.post(f"{host}/v1/music_generation", json=body_25, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            status = data.get("base_resp", {}).get("status_code", -1)
            status_msg = data.get("base_resp", {}).get("status_msg", "")
        elif status == 0:
            pass  # music-2.5+ worked
        else:
            # music-2.5+ failed for another reason, try music-2.5
            pass

        if status != 0:
            return json.dumps({"error": f"Music generation failed: {status_msg}", "raw": data})

        # Handle URL response format
        audio_url = data.get("data", {}).get("audio", "")
        if not audio_url:
            return json.dumps({"error": "No audio in response", "raw": data})

        # If output_format was url, audio field contains a URL
        if audio_url.startswith("http"):
            with httpx.Client(timeout=120) as client:
                dl = client.get(audio_url)
                dl.raise_for_status()
            ts = int(time.time())
            path = os.path.join(out_dir, f"music_{ts}.mp3")
            with open(path, "wb") as f:
                f.write(dl.content)
        else:
            # Hex format fallback
            audio_bytes = bytes.fromhex(audio_url)
            ts = int(time.time())
            path = os.path.join(out_dir, f"music_{ts}.mp3")
            with open(path, "wb") as f:
                f.write(audio_bytes)

        duration = data.get("extra_info", {}).get("music_duration", 0)
        return json.dumps({
            "success": True,
            "file_path": path,
            "media_tag": f"MEDIA:{path}",
            "duration": duration,
        })
    except Exception as e:
        logger.error("MiniMax music generation failed: %s", e)
        return json.dumps({"error": str(e)})


# ─── Video Generation (async 3-step) ─────────────────────────────────────────

def minimax_video(
    prompt: str,
    image_path: str = "",
    duration: int = 6,
) -> str:
    host, key = _get_api()
    if not key:
        return json.dumps({"error": "MINIMAX_API_KEY not set"})

    out_dir = _ensure_output_dir()
    model = "MiniMax-Hailuo-2.3"

    body = {
        "model": model,
        "prompt": prompt[:2000],
        "duration": duration,
    }

    # Image-to-video: encode first frame
    if image_path and os.path.isfile(image_path):
        ext = Path(image_path).suffix.lower().lstrip(".")
        if ext == "jpg":
            ext = "jpeg"
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        body["first_frame_image"] = f"data:image/{ext};base64,{b64}"

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    try:
        # Step 1: Submit
        with httpx.Client(timeout=60) as client:
            resp = client.post(f"{host}/v1/video_generation", json=body, headers=headers)
            resp.raise_for_status()
            submit_data = resp.json()

        task_id = submit_data.get("task_id")
        if not task_id:
            return json.dumps({"error": "No task_id returned", "raw": submit_data})

        # Step 2: Poll (max 5 minutes)
        file_id = None
        for _ in range(60):
            time.sleep(5)
            with httpx.Client(timeout=30) as client:
                poll = client.get(
                    f"{host}/v1/query/video_generation",
                    params={"task_id": task_id},
                    headers=headers,
                )
                poll.raise_for_status()
                poll_data = poll.json()

            status = poll_data.get("status", "")
            if status == "Success":
                file_id = poll_data.get("file_id")
                break
            elif status == "Fail":
                return json.dumps({"error": "Video generation failed", "raw": poll_data})
            # else: Preparing/Queueing/Processing — keep polling

        if not file_id:
            return json.dumps({"error": "Video generation timed out after 5 minutes"})

        # Step 3: Download
        with httpx.Client(timeout=120) as client:
            dl = client.get(
                f"{host}/v1/files/retrieve",
                params={"file_id": file_id},
                headers=headers,
            )
            dl.raise_for_status()
            dl_data = dl.json()

        download_url = dl_data.get("file", {}).get("download_url", "")
        if not download_url:
            return json.dumps({"error": "No download URL", "raw": dl_data})

        with httpx.Client(timeout=120) as client:
            vid = client.get(download_url)
            vid.raise_for_status()

        ts = int(time.time())
        path = os.path.join(out_dir, f"video_{ts}.mp4")
        with open(path, "wb") as f:
            f.write(vid.content)

        return json.dumps({
            "success": True,
            "file_path": path,
            "media_tag": f"MEDIA:{path}",
        })
    except Exception as e:
        logger.error("MiniMax video generation failed: %s", e)
        return json.dumps({"error": str(e)})


# ─── Registry ────────────────────────────────────────────────────────────────
from tools.registry import registry

IMAGE_UNDERSTAND_SCHEMA = {
    "name": "minimax_image_understand",
    "description": "PRIMARY image analysis tool — use this INSTEAD of vision_analyze. Analyze any image using MiniMax VLM (free, native). Accepts local file paths, URLs, or base64. Returns detailed description or answers questions about the image. ALWAYS use this for image analysis.",
    "parameters": {
        "type": "object",
        "properties": {
            "image_source": {
                "type": "string",
                "description": "Path to local image file, HTTP URL, or base64 data URL"
            },
            "prompt": {
                "type": "string",
                "description": "What to analyze or ask about the image",
                "default": "Describe this image in detail."
            }
        },
        "required": ["image_source"]
    }
}

IMAGE_GENERATE_SCHEMA = {
    "name": "minimax_image_generate",
    "description": "PRIMARY image generation tool — use this INSTEAD of image_generate. MiniMax image-01 (free, native). Returns image file paths, auto-sent via Telegram. ALWAYS use this for image generation.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text description of the image to generate (max 1500 chars)"
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16"],
                "description": "Aspect ratio of the generated image",
                "default": "1:1"
            },
            "n": {
                "type": "integer",
                "description": "Number of images to generate (1-4)",
                "default": 1
            }
        },
        "required": ["prompt"]
    }
}

SPEECH_SCHEMA = {
    "name": "minimax_speech",
    "description": "PRIMARY text-to-speech tool — use this INSTEAD of text_to_speech. MiniMax speech-2.8-hd with Aussie accent (English_aussie_buddy_vv2). 35+ languages, emotion control. Returns audio file auto-sent as voice message on Telegram. ALWAYS use this for voice/TTS.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to convert to speech (max 10000 chars)"
            },
            "voice_id": {
                "type": "string",
                "description": "Voice ID. Male: English_aussie_buddy_vv2 (energetic), English_Jovialman (upbeat), English_Strong-WilledBoy (young), English_Aussie_Bloke (casual), English_ManWithDeepVoice (deep), Casual_Guy, Young_Knight. Female: English_PlayfulGirl, English_CalmWoman, English_radiant_girl. Default is English_aussie_buddy_vv2.",
                "default": "English_aussie_buddy_vv2"
            },
            "emotion": {
                "type": "string",
                "enum": ["happy", "sad", "angry", "fearful", "disgusted", "surprised", "calm", "fluent", "whisper"],
                "description": "Emotional tone of the speech",
                "default": "calm"
            },
            "speed": {
                "type": "number",
                "description": "Speech speed (0.5-2.0)",
                "default": 1.0
            }
        },
        "required": ["text"]
    }
}

MUSIC_SCHEMA = {
    "name": "minimax_music",
    "description": "Generate music from a style/mood description and lyrics using MiniMax. NOTE: Requires music-2.5+ which may not be available on all plans. Provide lyrics for best results.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Style/mood description (e.g. 'upbeat pop song with electric guitar')"
            },
            "lyrics": {
                "type": "string",
                "description": "Song lyrics with structure tags like [Verse], [Chorus], [Bridge]. Use \\n for line breaks. Leave empty for instrumental.",
                "default": ""
            },
            "instrumental": {
                "type": "boolean",
                "description": "Generate instrumental music without vocals",
                "default": False
            }
        },
        "required": ["prompt"]
    }
}

VIDEO_SCHEMA = {
    "name": "minimax_video",
    "description": "Generate a short video from a text prompt (and optional first-frame image) using MiniMax Hailuo-2.3. Supports camera movement commands like [push in], [pan left]. Video generation takes 1-5 minutes. Returns a video file.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text description of the video to generate. Supports camera commands: [push in], [pull out], [pan left], [pan right], [tilt up], [tilt down], [zoom in], [zoom out]"
            },
            "image_path": {
                "type": "string",
                "description": "Optional path to a local image file to use as the first frame (image-to-video)",
                "default": ""
            },
            "duration": {
                "type": "integer",
                "enum": [6, 10],
                "description": "Video duration in seconds",
                "default": 6
            }
        },
        "required": ["prompt"]
    }
}

registry.register(
    name="minimax_image_understand",
    toolset="minimax_media",
    schema=IMAGE_UNDERSTAND_SCHEMA,
    handler=lambda args, **kw: minimax_image_understand(
        args.get("image_source", ""),
        args.get("prompt", "Describe this image in detail."),
    ),
    check_fn=_check_minimax_key,
    requires_env=["MINIMAX_API_KEY"],
    emoji="👁️",
)

registry.register(
    name="minimax_image_generate",
    toolset="minimax_media",
    schema=IMAGE_GENERATE_SCHEMA,
    handler=lambda args, **kw: minimax_image_generate(
        args.get("prompt", ""),
        args.get("aspect_ratio", "1:1"),
        args.get("n", 1),
    ),
    check_fn=_check_minimax_key,
    requires_env=["MINIMAX_API_KEY"],
    emoji="🎨",
)

registry.register(
    name="minimax_speech",
    toolset="minimax_media",
    schema=SPEECH_SCHEMA,
    handler=lambda args, **kw: minimax_speech(
        args.get("text", ""),
        args.get("voice_id", "English_aussie_buddy_vv2"),
        args.get("emotion", "happy"),
        args.get("speed", 1.0),
    ),
    check_fn=_check_minimax_key,
    requires_env=["MINIMAX_API_KEY"],
    emoji="🔊",
)

registry.register(
    name="minimax_music",
    toolset="minimax_media",
    schema=MUSIC_SCHEMA,
    handler=lambda args, **kw: minimax_music(
        args.get("prompt", ""),
        args.get("lyrics", ""),
        args.get("instrumental", False),
    ),
    check_fn=_check_minimax_key,
    requires_env=["MINIMAX_API_KEY"],
    emoji="🎵",
)

registry.register(
    name="minimax_video",
    toolset="minimax_media",
    schema=VIDEO_SCHEMA,
    handler=lambda args, **kw: minimax_video(
        args.get("prompt", ""),
        args.get("image_path", ""),
        args.get("duration", 6),
    ),
    check_fn=_check_minimax_key,
    requires_env=["MINIMAX_API_KEY"],
    emoji="🎬",
)
