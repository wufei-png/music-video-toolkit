"""Run WhisperX in the isolated alignment environment and emit timing evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import whisperx

ALIGNMENT_MODELS = {
    "en": "WAV2VEC2_ASR_BASE_960H",
    "zh": "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn",
}
ASR_REPOSITORIES = {
    "small.en": "Systran/faster-whisper-small.en",
    "small": "Systran/faster-whisper-small",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repository_revision(model_dir: Path, repository: str) -> str | None:
    reference = model_dir / f"models--{repository.replace('/', '--')}" / "refs/main"
    return reference.read_text(encoding="utf-8").strip() if reference.is_file() else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--language", choices=("en", "zh"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()

    started = time.monotonic()
    audio = whisperx.load_audio(str(args.audio))
    model = whisperx.load_model(
        args.model,
        "cpu",
        compute_type="int8",
        language=args.language,
        vad_method="pyannote",
        download_root=str(args.model_dir),
        threads=args.threads,
    )
    transcription = model.transcribe(
        audio,
        batch_size=4,
        language=args.language,
        print_progress=False,
        verbose=False,
    )
    del model
    align_model, metadata = whisperx.load_align_model(
        language_code=args.language,
        device="cpu",
        model_name=ALIGNMENT_MODELS[args.language],
        model_dir=str(args.model_dir),
    )
    aligned = whisperx.align(
        transcription["segments"],
        align_model,
        metadata,
        audio,
        "cpu",
        return_char_alignments=False,
        print_progress=False,
    )
    alignment_weights = sorted(args.model_dir.glob("*.pth"))
    alignment_repository = (
        ALIGNMENT_MODELS[args.language] if "/" in ALIGNMENT_MODELS[args.language] else None
    )
    document = {
        "runtime": {
            "tool": "whisperx",
            "version": "3.8.6",
            "model": args.model,
            "model_revision": repository_revision(args.model_dir, ASR_REPOSITORIES[args.model]),
            "alignment_language": metadata["language"],
            "alignment_model": ALIGNMENT_MODELS[args.language],
            "alignment_revision": (
                repository_revision(args.model_dir, alignment_repository)
                if alignment_repository
                else None
            ),
            "alignment_weight_sha256": (
                sha256(alignment_weights[0])
                if args.language == "en" and len(alignment_weights) == 1
                else None
            ),
            "device": "cpu",
            "compute_type": "int8",
            "vad_method": "pyannote",
            "threads": args.threads,
        },
        "language": transcription["language"],
        "segments": aligned["segments"],
        "elapsed_seconds": time.monotonic() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    # Some upstream libraries leave non-daemon workers alive after successful
    # CPU inference. This process owns no state after the result file is closed,
    # so bypass interpreter thread shutdown.
    os._exit(main())
