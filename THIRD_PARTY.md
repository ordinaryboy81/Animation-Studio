# Third-party software and assets

Animation Studio's own code is released under the MIT License (see `LICENSE`).
It uses the following components, each under its own license.

## Included in this repository

| Component | Where | License |
| --- | --- | --- |
| IBM Plex Sans (interface font) | `fonts/ui/` | SIL Open Font License 1.1 |
| Nunito (font used inside videos and subtitles) | `engine/vector/fonts/` | SIL Open Font License 1.1 |
| DejaVu fonts | `fonts/` | Bitstream Vera / DejaVu license |
| Pixelify Sans (pixel-art titles) | `engine/pixel/fonts/` | SIL Open Font License 1.1 |
| Tiny5 (small pixel-art text) | `engine/pixel/fonts/` | SIL Open Font License 1.1 |
| Three.js r170 and its GLTFLoader, RoomEnvironment, BufferGeometryUtils | `engine/3d/` | MIT |
| World map outlines from Natural Earth | `data/world.json` | Public domain |
| Sound effects and background music | `engine/sounds/` | Generated for this project, MIT like the code |

## Downloaded on the user's computer when needed

These are not part of the repository. The studio downloads them on first use.

| Component | Used for | License |
| --- | --- | --- |
| Python packages: Pillow, NumPy, PyYAML, Playwright, ffmpeg-binaries, uv | running the studio | see each package |
| FFmpeg (through ffmpeg-binaries, or your own install) | encoding video and audio | LGPL/GPL, depending on the build |
| Chatterbox TTS by Resemble AI | voice-over | MIT |
| Whisper large-v3-turbo by OpenAI | checking voice-over, subtitle timing | MIT |
| Qwen3-4B-Instruct by Alibaba Cloud | translation | Apache 2.0 |
| PyTorch, Transformers and their dependencies | running the models above | see each package |

Chatterbox can clone a voice from a short sample. Only use your own voice or
voices you have permission to use.
