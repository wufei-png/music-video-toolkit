# Singing alignment runtime

This locked Python 3.12 environment isolates WhisperX, Faster Whisper, PyTorch and downloaded speech/alignment models from the lightweight `mvt` CLI.

```bash
uv sync --project environments/alignment --locked
uv run --project environments/alignment --locked whisperx --version
```

S07 pins WhisperX 3.8.6 and runs CPU int8 transcription with its packaged Pyannote VAD weights. Models and Hugging Face caches remain outside Git. The adapter treats ASR only as coarse evidence, maps it monotonically to supplied text, records unmatched lines, and never substitutes the recognized transcript for the user's lyrics.
