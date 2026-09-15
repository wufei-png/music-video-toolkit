import hashlib
import json
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from music_video_toolkit.audio import DecodeError, decode_audio
from music_video_toolkit.cli import main
from music_video_toolkit.contracts import SourceRecord
from music_video_toolkit.project import ProjectPreflightError, preflight_source


def digest(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def write_mp3(tmp_path: Path, name: str, *, frequency: float = 440.0) -> Path:
    wav_path = tmp_path / f"{name}.wav"
    mp3_path = tmp_path / f"{name}.mp3"
    sample_rate = 44100
    frame_count = 11025
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for index in range(frame_count):
            value = round(12000 * math.sin(2 * math.pi * frequency * index / sample_rate))
            frames.extend(struct.pack("<h", value))
        wav.writeframes(frames)
    result = subprocess.run(
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(wav_path),
            "-c:a",
            "libmp3lame",
            str(mp3_path),
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    return mp3_path


def write_source_project(tmp_path: Path) -> tuple[Path, dict]:
    project = tmp_path / "项目 with spaces"
    source = project / "source"
    source.mkdir(parents=True)
    original = tmp_path / "输入 音频.mp3"
    original.write_bytes(b"synthetic original")
    canonical = source / "canonical.wav"
    with wave.open(str(canonical), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(3)
        wav.setframerate(48000)
        wav.writeframes(b"\0" * 48000 * 2 * 3)
    record = {
        "schema_version": "0.1",
        "original": {"path": str(original), "sha256": digest(original.read_bytes())},
        "canonical": {
            "path": "canonical.wav",
            "sha256": digest(canonical.read_bytes()),
            "sample_rate": 48000,
            "channels": 2,
            "sample_format": "s24le",
            "codec": "pcm_s24le",
            "duration_samples": 48000,
        },
        "decoder": {
            "tool": "ffmpeg",
            "version": "8.1",
            "parameters": {"audio_stream": "0:a:0"},
        },
    }
    (source / "source.json").write_text(json.dumps(record), encoding="utf-8")
    return project, record


def test_source_schema_matches_authoritative_model():
    root = Path(__file__).resolve().parents[2]
    schema = json.loads((root / "schemas/source.schema.json").read_text())
    assert schema == SourceRecord.model_json_schema()
    Draft202012Validator.check_schema(schema)


def test_project_preflight_resolves_manifest_paths_independent_of_cwd(tmp_path, monkeypatch):
    project, record = write_source_project(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    result = preflight_source(project, require_original=True)

    assert result.record == SourceRecord.model_validate(record)
    assert result.canonical_path == (project / "source/canonical.wav").resolve()
    assert result.original_path == (tmp_path / "输入 音频.mp3").resolve()


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda project, record: record["canonical"].update(path="../elsewhere.wav"),
            "invalid_project_reference",
        ),
        (
            lambda project, record: (project / "source/canonical.wav").write_bytes(b"changed"),
            "project_hash_mismatch",
        ),
        (
            lambda project, record: (project / "source/canonical.wav").unlink(),
            "missing_project_file",
        ),
    ],
)
def test_project_preflight_rejects_broken_canonical_reference(tmp_path, mutate, code):
    project, record = write_source_project(tmp_path)
    mutate(project, record)
    (project / "source/source.json").write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ProjectPreflightError, match=".+") as caught:
        preflight_source(project)

    assert caught.value.code == code


def test_project_preflight_checks_actual_pcm_frame_count(tmp_path):
    project, record = write_source_project(tmp_path)
    record["canonical"]["duration_samples"] = 47999
    (project / "source/source.json").write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ProjectPreflightError) as caught:
        preflight_source(project)

    assert caught.value.code == "canonical_audio_mismatch"


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
def test_decode_real_mp3_from_different_cwd_and_reuses_cache(tmp_path, monkeypatch, capsys):
    input_dir = tmp_path / "输入 files"
    input_dir.mkdir()
    write_mp3(input_dir, "合成 音频")
    working_dir = tmp_path / "other cwd"
    working_dir.mkdir()
    monkeypatch.chdir(working_dir)
    relative_input = Path("../输入 files/合成 音频.mp3")
    relative_project = Path("../输出 project")

    assert main(["decode", str(relative_input), "--project", str(relative_project)]) == 0
    report = json.loads(capsys.readouterr().out)
    canonical = tmp_path / "输出 project/source/canonical.wav"
    record_path = tmp_path / "输出 project/source/source.json"
    assert report["cached"] is False
    assert report["sample_rate"] == 48000
    assert report["channels"] == 2
    assert report["sample_format"] == "s24le"
    assert report["codec"] == "pcm_s24le"
    with wave.open(str(canonical), "rb") as decoded:
        assert decoded.getframerate() == 48000
        assert decoded.getnchannels() == 2
        assert decoded.getsampwidth() == 3
        assert report["duration_samples"] == decoded.getnframes()
    probe = subprocess.run(
        [
            shutil.which("ffprobe") or "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels",
            "-of",
            "json",
            str(canonical),
        ],
        text=True,
        capture_output=True,
    )
    assert probe.returncode == 0, probe.stderr
    assert json.loads(probe.stdout)["streams"] == [
        {"codec_name": "pcm_s24le", "sample_rate": "48000", "channels": 2}
    ]
    canonical_hash = digest(canonical.read_bytes())
    record_hash = digest(record_path.read_bytes())

    assert main(["decode", str(relative_input), "--project", str(relative_project)]) == 0
    cached = json.loads(capsys.readouterr().out)
    assert cached["cached"] is True
    assert digest(canonical.read_bytes()) == canonical_hash
    assert digest(record_path.read_bytes()) == record_hash
    assert (
        preflight_source(relative_project, require_original=True).record.canonical.duration_samples
        == report["duration_samples"]
    )


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
def test_decode_refuses_different_source_without_modifying_project(tmp_path):
    first = write_mp3(tmp_path, "first", frequency=330)
    second = write_mp3(tmp_path, "second", frequency=660)
    project = tmp_path / "project"
    initial = decode_audio(first, project)
    canonical_hash = digest(initial.canonical_path.read_bytes())
    record_hash = digest(initial.record_path.read_bytes())

    with pytest.raises(DecodeError) as caught:
        decode_audio(second, project)

    assert caught.value.code == "project_conflict"
    assert digest(initial.canonical_path.read_bytes()) == canonical_hash
    assert digest(initial.record_path.read_bytes()) == record_hash


@pytest.mark.parametrize("missing", ["ffmpeg", "ffprobe"])
def test_decode_reports_missing_dependency_without_partial_output(
    tmp_path, monkeypatch, capsys, missing
):
    input_path = tmp_path / "input.wav"
    input_path.write_bytes(b"input identity")
    actual_which = shutil.which
    monkeypatch.setattr(
        "music_video_toolkit.audio.shutil.which",
        lambda name: None if name == missing else actual_which(name),
    )
    project = tmp_path / "project"

    assert main(["decode", str(input_path), "--project", str(project)]) == 3
    error = json.loads(capsys.readouterr().err)
    assert error["code"] == "missing_dependency"
    assert error["details"]["tool"] == missing
    assert not project.exists()


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
def test_decode_failure_is_structured_and_cleans_temporary_files(tmp_path, capsys):
    corrupt = tmp_path / "损坏 input.mp3"
    corrupt.write_bytes(b"not an audio file")
    project = tmp_path / "project with spaces"

    assert main(["decode", str(corrupt), "--project", str(project)]) == 5
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["code"] == "decode_failed"
    assert not (project / "source/canonical.wav").exists()
    assert not (project / "source/source.json").exists()
    assert list((project / "source").glob(".*")) == []


def test_decode_missing_input_and_partial_project_conflict_are_structured(tmp_path, capsys):
    project = tmp_path / "project"
    assert main(["decode", str(tmp_path / "missing.mp3"), "--project", str(project)]) == 2
    assert json.loads(capsys.readouterr().err)["code"] == "input_missing"
    input_path = tmp_path / "input.wav"
    input_path.write_bytes(b"identity")
    (project / "source").mkdir(parents=True)
    (project / "source/canonical.wav").write_bytes(b"existing")

    assert main(["decode", str(input_path), "--project", str(project)]) == 4
    assert json.loads(capsys.readouterr().err)["code"] == "project_conflict"
