import hashlib
import json
import math
import shutil
import struct
import wave
from pathlib import Path

import pytest

from music_video_toolkit.analysis import (
    AnalysisError,
    _analyze_files,
    _normalize_stem,
    _runtime_project,
    analyze_project,
)
from music_video_toolkit.cli import main
from music_video_toolkit.contracts import AnalysisRun, StemManifest, Timeline


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_pcm24(path: Path, channels: list[list[float]], sample_rate: int = 48_000) -> None:
    frame_count = len(channels[0])
    assert all(len(channel) == frame_count for channel in channels)
    frames = bytearray()
    for index in range(frame_count):
        for channel in channels:
            value = max(-(2**23), min(2**23 - 1, round(channel[index] * (2**22))))
            frames.extend(struct.pack("<i", value)[:3])
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(len(channels))
        wav.setsampwidth(3)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)


def source_project(tmp_path: Path, samples: list[float]) -> Path:
    project = tmp_path / "project with spaces"
    source_dir = project / "source"
    source_dir.mkdir(parents=True)
    canonical = source_dir / "canonical.wav"
    write_pcm24(canonical, [samples, samples])
    original = tmp_path / "original.wav"
    original.write_bytes(b"source identity")
    record = {
        "schema_version": "0.1",
        "original": {"path": str(original), "sha256": digest(original)},
        "canonical": {
            "path": "canonical.wav",
            "sha256": digest(canonical),
            "sample_rate": 48_000,
            "channels": 2,
            "sample_format": "s24le",
            "codec": "pcm_s24le",
            "duration_samples": len(samples),
        },
        "decoder": {"tool": "synthetic-test", "version": "1", "parameters": {}},
    }
    (source_dir / "source.json").write_text(json.dumps(record), encoding="utf-8")
    return project


@pytest.mark.skipif(not shutil.which("uv"), reason="uv required")
def test_none_mode_silence_emits_mix_only_and_reuses_verified_cache(tmp_path, capsys):
    project = source_project(tmp_path, [0.0] * 48_000)

    assert main(["analyze", "--project", str(project), "--stems", "none"]) == 0
    report = json.loads(capsys.readouterr().out)
    timeline = Timeline.model_validate_json((project / "timeline.json").read_text())
    run = AnalysisRun.model_validate_json((project / "analysis/run.json").read_text())

    assert report["cached"] is False
    assert run.mode == "none"
    assert set(timeline.signals) == {"mix.rms"} | {
        f"mix.chroma.{name}"
        for name in (
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
    }
    assert all(value == 0.0 for signal in timeline.signals.values() for value in signal.values)
    assert timeline.events == []
    assert not (project / "stems/stems.json").exists()

    cached = analyze_project(project, "none")
    assert cached.cached is True
    assert cached.run.cache_key == report["cache_key"]


@pytest.mark.skipif(not shutil.which("uv"), reason="uv required")
def test_synthetic_four_tracks_have_canonical_clock_and_required_features(tmp_path):
    duration = 96_000
    drums = [0.0] * duration
    for center in (24_000, 72_000):
        for index in range(center, center + 240):
            drums[index] = 0.9 * math.exp(-(index - center) / 60)
    bass = [
        0.0 if index < duration // 2 else 0.5 * math.sin(2 * math.pi * 80 * index / 48_000)
        for index in range(duration)
    ]
    vocals = [0.0] * duration
    other = [0.1 * math.sin(2 * math.pi * 880 * index / 48_000) for index in range(duration)]
    mix = [min(0.95, drums[index] + bass[index] + other[index]) for index in range(duration)]
    paths = {}
    for name, samples in {
        "mix": mix,
        "drums": drums,
        "bass": bass,
        "vocals": vocals,
        "other": other,
    }.items():
        path = tmp_path / f"{name}.wav"
        write_pcm24(path, [samples, samples])
        paths[name] = path

    output = tmp_path / "timeline.json"
    timeline = _analyze_files(
        _runtime_project(),
        shutil.which("uv") or "uv",
        paths["mix"],
        {name: paths[name] for name in ("vocals", "drums", "bass", "other")},
        output,
        digest(paths["mix"]),
        duration,
    )

    required = {
        "mix.rms",
        "vocals.rms",
        "drums.rms",
        "bass.rms",
        "other.rms",
        "bass.low_energy",
    }
    assert required <= set(timeline.signals)
    assert all(
        len(signal.values) == math.ceil(duration / 1_024) for signal in timeline.signals.values()
    )
    assert all(value == 0.0 for value in timeline.signals["vocals.rms"].values)
    low_energy = timeline.signals["bass.low_energy"].values
    assert sum(low_energy[len(low_energy) // 2 :]) > sum(low_energy[: len(low_energy) // 2]) * 4
    drum_onsets = [event.sample for event in timeline.events if event.source == "drums"]
    assert drum_onsets
    assert any(abs(sample - 24_000) <= 2_048 for sample in drum_onsets)
    assert all(event.name != "downbeat" for event in timeline.events)
    assert all(event.sample < duration for event in timeline.events)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
@pytest.mark.parametrize(
    ("target", "adjustment", "delta"), [(48_001, "pad", 1), (47_999, "trim", -1)]
)
def test_stem_alignment_records_explicit_padding_and_trimming(tmp_path, target, adjustment, delta):
    source = tmp_path / "model-44k.wav"
    samples = [0.2 * math.sin(2 * math.pi * 220 * index / 44_100) for index in range(44_100)]
    write_pcm24(source, [samples, samples], sample_rate=44_100)
    output = tmp_path / f"normalized-{target}.wav"

    alignment = _normalize_stem(shutil.which("ffmpeg") or "ffmpeg", source, output, target)

    assert alignment.natural_output_samples == 48_000
    assert alignment.adjustment == adjustment
    assert alignment.adjustment_samples == delta
    with wave.open(str(output), "rb") as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()) == (
            48_000,
            2,
            3,
            target,
        )


def test_separator_success_without_four_files_is_a_failure(tmp_path, monkeypatch):
    project = source_project(tmp_path, [0.0] * 2_048)
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    (model_dir / "htdemucs.yaml").write_text("model")
    (model_dir / "955717e8-8726e21a.th").write_bytes(b"weights")
    monkeypatch.setenv("MVT_MODEL_DIR", str(model_dir))
    monkeypatch.setattr("music_video_toolkit.analysis._run", lambda command, code: None)

    with pytest.raises(AnalysisError) as caught:
        analyze_project(project, "four")

    assert caught.value.code == "separation_output_missing"


def test_s03_schemas_match_authoritative_models():
    root = Path(__file__).resolve().parents[2]
    for name, model in {"analysis": AnalysisRun, "stems": StemManifest}.items():
        schema = json.loads((root / f"schemas/{name}.schema.json").read_text())
        assert schema == model.model_json_schema()
