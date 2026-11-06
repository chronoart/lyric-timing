"""音声認識モデル（faster-whisper large-v3, 約3GB）を models フォルダにダウンロードする"""
import os

from huggingface_hub import snapshot_download

name = os.environ.get("LYRIC_TIMING_MODEL", "Systran/faster-whisper-large-v3")
print(f"Downloading model: {name}  (about 3 GB, only the first time)")
path = snapshot_download(name)
print(f"OK: {path}")
