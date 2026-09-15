import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from music_video_toolkit.contracts import RenderManifest
from music_video_toolkit.project import resolve_record_path, sha256_file
from music_video_toolkit.render import renderer_doctor

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "examples/production-demo/create_fixture.py"


def create_demo(tmp_path: Path, name: str, mode: str) -> Path:
    output = tmp_path / name
    result = subprocess.run(
        [sys.executable, str(FIXTURE), str(output), "--review-mode", mode],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return output


def command_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{environment['PATH']}"
    return environment


def run_script(path: Path, *arguments: Path, no_models: bool = False) -> None:
    environment = command_environment()
    if no_models:
        environment["MVT_ALIGNMENT_PROJECT"] = str(path.parent / "missing-alignment")
        environment["MVT_SEPARATION_PROJECT"] = str(path.parent / "missing-separation")
        environment["MVT_MODEL_DIR"] = str(path.parent / "missing-model-cache")
    result = subprocess.run(
        [str(path), *(str(argument) for argument in arguments)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def validate_render_manifest(path: Path) -> RenderManifest:
    manifest = RenderManifest.model_validate_json(path.read_text())
    assert manifest.status == "completed"
    for output in manifest.outputs:
        output_path = resolve_record_path(path, output.path)
        assert output_path.is_file()
        assert sha256_file(output_path) == output.sha256
    return manifest


def test_fixture_generator_preserves_review_mode_gate(tmp_path):
    sample = create_demo(tmp_path, "sample", "sample-approval")
    autonomous = create_demo(tmp_path, "autonomous", "autonomous")

    sample_workflow = (sample / "run-workflow.sh").read_text()
    assert "mvt capabilities" in sample_workflow
    assert "mvt doctor" in sample_workflow
    assert "mvt render" not in sample_workflow
    assert not (sample / "rerender-first-cut.sh").exists()
    assert "awaiting explicit sample feedback" in (sample / "feedback.md").read_text()
    assert "mvt render" in (autonomous / "run-workflow.sh").read_text()
    assert (autonomous / "rerender-first-cut.sh").is_file()
    assert "not user approval" in (autonomous / "feedback.md").read_text()
    assert json.loads((sample / "brief.json").read_text())["review_mode"] == "sample-approval"


@pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe", "node", "pnpm")),
    reason="S09 production demo tools required",
)
def test_sample_and_autonomous_workflows_create_reproducible_bundles(tmp_path):
    if not renderer_doctor()["ready"]:
        pytest.skip("pinned Playwright Chromium is not installed")

    sample = create_demo(tmp_path, "sample", "sample-approval")
    run_script(sample / "run-workflow.sh")
    sample_project = sample / "project"
    required = [
        sample / "brief.json",
        sample / "feedback.md",
        sample / "synthetic-song.wav",
        sample_project / "source/source.json",
        sample_project / "source/canonical.wav",
        sample_project / "analysis/run.json",
        sample_project / "timeline.json",
        sample_project / "assets.json",
        sample_project / "assets.checked.json",
        sample_project / "visual-plan.json",
        sample_project / "resolved-plan.json",
        sample_project / "preview.json",
        sample / "preview/preview.render.json",
        sample / "rerender-preview.sh",
    ]
    assert all(path.is_file() for path in required)
    assert not (sample / "first-cut.mp4").exists()
    sample_manifest = validate_render_manifest(sample / "preview/preview.render.json")
    assert len(sample_manifest.ranges) == 3

    feedback = sample / "feedback.md"
    feedback.write_text(
        feedback.read_text()
        + "\nSynthetic reviewer decision: approved for full-render rehearsal.\n"
    )
    approved = sample / "approved-first-cut.mp4"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "music_video_toolkit.cli",
            "render",
            "--project",
            str(sample_project),
            "--plan",
            str(sample_project / "resolved-plan.json"),
            "--output",
            str(approved),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    validate_render_manifest(approved.with_suffix(".mp4.render.json"))

    preview_copy = sample / "preview-copy"
    run_script(sample / "rerender-preview.sh", preview_copy, no_models=True)
    copied = validate_render_manifest(preview_copy / "preview.render.json")
    assert copied.cache_key == sample_manifest.cache_key

    autonomous = create_demo(tmp_path, "autonomous", "autonomous")
    run_script(autonomous / "run-workflow.sh")
    first_cut = autonomous / "first-cut.mp4"
    first_manifest = validate_render_manifest(first_cut.with_suffix(".mp4.render.json"))
    reproduced = autonomous / "first-cut-copy.mp4"
    run_script(autonomous / "rerender-first-cut.sh", reproduced, no_models=True)
    copy_manifest = validate_render_manifest(reproduced.with_suffix(".mp4.render.json"))
    assert copy_manifest.cache_key == first_manifest.cache_key
    assert sha256_file(reproduced) == sha256_file(first_cut)
