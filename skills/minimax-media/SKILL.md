# MiniMax Media Tools

All native, all free with plan. Call via terminal:

```python
import sys; sys.path.insert(0, '/opt/hermes')
from tools.minimax_media_tools import minimax_speech, minimax_image_generate, minimax_video, minimax_image_understand
import json
```

## Voice (TTS)
```python
result = minimax_speech("Your text here", voice_id="English_aussie_buddy_vv2", emotion="happy", speed=1.0)
data = json.loads(result)
# data['file_path'] = path to mp3, data['media_tag'] = for Telegram auto-send
print(data['media_tag'])  # Include in response to auto-send as voice
```
Voices: English_aussie_buddy_vv2 (default), English_Comedian, English_Jovialman, Casual_Guy, Young_Knight
Emotions: happy, calm, surprised, angry, whisper, sad, fearful

## Image Generation
```python
result = minimax_image_generate("cyberpunk city at sunset", aspect_ratio="16:9", n=1)
data = json.loads(result)
# data['images'] = local paths, data['urls'] = public URLs, data['media_tag'] = for Telegram
print(data['media_tag'])
```
Aspect ratios: 1:1, 16:9, 4:3, 3:2, 2:3, 3:4, 9:16

## Video Generation (takes 1-5 min)
```python
result = minimax_video("waves crashing on beach, cinematic, [pan left]", duration=6)
data = json.loads(result)
print(data['media_tag'])
```
Camera: [push in], [pull out], [pan left], [pan right], [tilt up], [zoom in]
Duration: 6 or 10 seconds

## Image Analysis (VLM)
```python
result = minimax_image_understand("/path/to/image.jpg", prompt="What's in this image?")
# Also works with URLs: minimax_image_understand("https://example.com/img.jpg")
data = json.loads(result)
print(data['analysis'])
```

## IMPORTANT
- Always include media_tag in your response for Telegram auto-send
- Use MEDIA:/path/to/file.ext format for manual file sending
- Voice messages: prefix with [[audio_as_voice]] for voice bubble display
