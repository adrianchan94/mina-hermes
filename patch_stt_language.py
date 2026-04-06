#!/usr/bin/env python3
"""Patch faster-whisper transcription to respect HERMES_LOCAL_STT_LANGUAGE env var.

The default _transcribe_local() doesn't pass language to whisper.transcribe(),
so it auto-detects — which fails on short voice clips. This patch makes it
read the env var and pass it through.
"""

BASE = "/opt/hermes"

def _read(path):
    with open(path) as f:
        return f.read()

def _write(path, content):
    with open(path, "w") as f:
        f.write(content)

tp = _read(f"{BASE}/tools/transcription_tools.py")

old = '        segments, info = _local_model.transcribe(file_path, beam_size=5)'
new = '''        # Pass explicit language if configured (prevents misdetection on short clips)
        _stt_lang = os.getenv("HERMES_LOCAL_STT_LANGUAGE", "").strip() or None
        segments, info = _local_model.transcribe(file_path, beam_size=5, language=_stt_lang)'''

if old in tp:
    tp = tp.replace(old, new)
    _write(f"{BASE}/tools/transcription_tools.py", tp)
    print("[patch] transcription_tools.py — added language passthrough for local whisper")
else:
    print("[patch] transcription_tools.py — transcribe pattern not found (may already be patched)")

print("\n[patch] STT language patch complete.")
