import json
import subprocess
import sys
from pathlib import Path

import pytest

from music_video_toolkit.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_capabilities_are_honest(capsys):
    assert main(["capabilities"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["stage"] == "s11"
    assert report["production_stage"] == "s11"
    assert report["can_render"] is True
    assert "render" in report["available"]
    assert "render" not in report["planned"]
    assert "imported lyrics" in report["render_scope"]
    assert "decode" in report["available"]
    assert "decode" not in report["planned"]
    assert "lyrics import" in report["available"]
    assert "lyrics align" in report["available"]
    assert "lyrics apply-edits" in report["available"]
    assert "preview" in report["available"]
    assert "preview" not in report["planned"]
    assert "compare" in report["available"]
    assert "same-audio previews" in report["comparison_scope"]


def test_doctor_reports_missing_tools(monkeypatch, capsys):
    monkeypatch.setattr("music_video_toolkit.cli.shutil.which", lambda name: None)
    assert main(["doctor"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["pipeline_ready"] is False
    assert report["tools"]["ffmpeg"] is None


@pytest.mark.parametrize(
    "contents",
    [
        '{"schema_version":"0.1","schema_version":"0.2"}',
        '{"value":NaN}',
        '{"value":1e999}',
        "[]",
        "{broken",
        '{"nested":{"value":Infinity}}',
    ],
)
def test_bad_json_returns_structured_failure(contents, tmp_path, capsys):
    path = tmp_path / "输入 with spaces.json"
    path.write_text(contents)
    assert main(["validate", "--kind", "timeline", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["code"] == "invalid_artifact"


def test_missing_file_and_schema_error(capsys, tmp_path):
    assert main(["validate", "--kind", "timeline", str(tmp_path / "missing")]) == 2
    assert json.loads(capsys.readouterr().err)["ok"] is False
    path = tmp_path / "wrong.json"
    path.write_text('{"schema_version":"0.1"}')
    assert main(["validate", "--kind", "timeline", str(path)]) == 2
    assert isinstance(json.loads(capsys.readouterr().err)["details"], list)


def test_installed_cli_from_different_directory(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "music_video_toolkit.cli",
            "validate",
            "--kind",
            "timeline",
            str(ROOT / "examples/timeline.json"),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True


def test_render_requires_explicit_inputs(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "music_video_toolkit.cli", "render"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "required" in result.stderr
