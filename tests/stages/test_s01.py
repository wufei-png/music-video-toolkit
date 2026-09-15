import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from music_video_toolkit.contracts import SourceRecord
from music_video_toolkit.project import ProjectPreflightError, preflight_source


def digest(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def write_source_project(tmp_path: Path) -> tuple[Path, dict]:
    project = tmp_path / "项目 with spaces"
    source = project / "source"
    source.mkdir(parents=True)
    original = tmp_path / "输入 音频.mp3"
    original.write_bytes(b"synthetic original")
    canonical = source / "canonical.wav"
    canonical.write_bytes(b"synthetic canonical")
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
