"""Deterministic librosa feature extraction used by the lightweight CLI adapter."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

SAMPLE_RATE = 48_000
HOP_SAMPLES = 1_024
RMS_FRAME_SAMPLES = 2_048
CHROMA_FFT_SAMPLES = 4_096
SILENCE_EPSILON = 1e-12
LOW_FREQUENCY_MAX_HZ = 200.0
CHROMA_NAMES = (
    "c",
    "c_sharp",
    "d",
    "d_sharp",
    "e",
    "f",
    "f_sharp",
    "g",
    "g_sharp",
    "a",
    "a_sharp",
    "b",
)


def _load(path: Path, expected_samples: int) -> np.ndarray:
    metadata = sf.info(path)
    if metadata.samplerate != SAMPLE_RATE or metadata.channels != 2:
        raise ValueError(f"{path} must be 48 kHz stereo")
    if metadata.frames != expected_samples:
        raise ValueError(
            f"{path} has {metadata.frames} samples; expected {expected_samples} canonical samples"
        )
    audio, sample_rate = librosa.load(path, sr=None, mono=True, dtype=np.float32)
    if sample_rate != SAMPLE_RATE or len(audio) != expected_samples:
        raise ValueError(f"{path} decoded with an unexpected sample clock")
    return audio


def _pad_for_frames(audio: np.ndarray, frame_length: int) -> np.ndarray:
    frame_count = math.ceil(len(audio) / HOP_SAMPLES)
    required = (frame_count - 1) * HOP_SAMPLES + frame_length
    return np.pad(audio, (0, max(0, required - len(audio))))


def _normalize(values: np.ndarray) -> list[float]:
    values = np.nan_to_num(np.asarray(values, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    maximum = float(np.max(np.abs(values))) if values.size else 0.0
    if maximum <= SILENCE_EPSILON:
        return [0.0] * int(values.size)
    return [float(value) for value in np.clip(values / maximum, 0.0, 1.0)]


def _signal(values: np.ndarray) -> dict[str, object]:
    return {
        "start_sample": 0,
        "hop_samples": HOP_SAMPLES,
        "values": _normalize(values),
        "unit": "normalized_observed_max",
    }


def _rms(audio: np.ndarray) -> np.ndarray:
    padded = _pad_for_frames(audio, RMS_FRAME_SAMPLES)
    return librosa.feature.rms(
        y=padded,
        frame_length=RMS_FRAME_SAMPLES,
        hop_length=HOP_SAMPLES,
        center=False,
    )[0]


def _onset_envelope(audio: np.ndarray) -> np.ndarray:
    padded = _pad_for_frames(audio, RMS_FRAME_SAMPLES)
    return librosa.onset.onset_strength(
        y=padded,
        sr=SAMPLE_RATE,
        hop_length=HOP_SAMPLES,
        center=False,
    )[: math.ceil(len(audio) / HOP_SAMPLES)]


def _events(name: str, source: str, envelope: np.ndarray, frames: np.ndarray, duration: int):
    normalized = _normalize(envelope)
    events = []
    for frame in np.asarray(frames, dtype=np.int64):
        sample = int(frame) * HOP_SAMPLES
        if sample >= duration:
            continue
        confidence = normalized[int(frame)] if int(frame) < len(normalized) else None
        event = {"name": name, "source": source, "sample": sample}
        if confidence is not None:
            event["confidence"] = confidence
        events.append(event)
    return events


def analyze(
    source: Path,
    stems: dict[str, Path],
    duration_samples: int,
    source_sha256: str,
    source_path: str,
):
    mix = _load(source, duration_samples)
    audio = {"mix": mix}
    audio.update({name: _load(path, duration_samples) for name, path in stems.items()})

    signals = {f"{name}.rms": _signal(_rms(track)) for name, track in audio.items()}
    events: list[dict[str, object]] = []

    mix_onset = _onset_envelope(mix)
    _, beat_frames = librosa.beat.beat_track(
        onset_envelope=mix_onset,
        sr=SAMPLE_RATE,
        hop_length=HOP_SAMPLES,
        sparse=True,
    )
    events.extend(_events("beat", "mix", mix_onset, beat_frames, duration_samples))

    chroma_audio = _pad_for_frames(mix, CHROMA_FFT_SAMPLES)
    chroma = librosa.feature.chroma_stft(
        y=chroma_audio,
        sr=SAMPLE_RATE,
        n_fft=CHROMA_FFT_SAMPLES,
        hop_length=HOP_SAMPLES,
        center=False,
    )[:, : math.ceil(duration_samples / HOP_SAMPLES)]
    for index, name in enumerate(CHROMA_NAMES):
        signals[f"mix.chroma.{name}"] = _signal(chroma[index])

    if "drums" in audio:
        drum_onset = _onset_envelope(audio["drums"])
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=drum_onset,
            sr=SAMPLE_RATE,
            hop_length=HOP_SAMPLES,
            backtrack=False,
            units="frames",
            sparse=True,
        )
        events.extend(_events("onset", "drums", drum_onset, onset_frames, duration_samples))

    if "bass" in audio:
        bass_audio = _pad_for_frames(audio["bass"], RMS_FRAME_SAMPLES)
        spectrum = np.abs(
            librosa.stft(
                bass_audio,
                n_fft=RMS_FRAME_SAMPLES,
                hop_length=HOP_SAMPLES,
                center=False,
            )
        )
        frequencies = librosa.fft_frequencies(sr=SAMPLE_RATE, n_fft=RMS_FRAME_SAMPLES)
        low_spectrum = spectrum[frequencies <= LOW_FREQUENCY_MAX_HZ]
        low_energy = np.sqrt(np.mean(np.square(low_spectrum), axis=0))
        signals["bass.low_energy"] = _signal(low_energy)

    events.sort(key=lambda event: (int(event["sample"]), str(event["name"]), str(event["source"])))
    parameters = {
        "hop_samples": HOP_SAMPLES,
        "rms_frame_samples": RMS_FRAME_SAMPLES,
        "chroma_fft_samples": CHROMA_FFT_SAMPLES,
        "center": False,
        "end_padding": (
            "zero_pad_each_analysis_window; emit ceil(duration_samples/hop_samples) values"
        ),
        "normalization": "each signal divided by its observed absolute maximum",
        "silence_policy": f"max <= {SILENCE_EPSILON} emits all zeros",
        "low_frequency_max_hz": LOW_FREQUENCY_MAX_HZ,
        "beat_semantics": "beat estimate; not downbeat or bar phase",
    }
    return {
        "schema_version": "0.1",
        "source": {
            "path": source_path,
            "sha256": source_sha256,
            "sample_rate": SAMPLE_RATE,
            "duration_samples": duration_samples,
        },
        "analysis": [{"tool": "librosa", "version": librosa.__version__, "parameters": parameters}],
        "signals": signals,
        "events": events,
        "sections": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-path", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--duration-samples", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stem", action="append", default=[])
    args = parser.parse_args()
    stems: dict[str, Path] = {}
    for value in args.stem:
        name, separator, path = value.partition("=")
        if separator != "=" or name in stems:
            raise ValueError(f"invalid or duplicate --stem value: {value}")
        stems[name] = Path(path)
    document = analyze(
        args.source,
        stems,
        args.duration_samples,
        args.source_sha256,
        args.source_path,
    )
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
