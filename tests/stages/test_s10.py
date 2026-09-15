import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from music_video_toolkit.analysis import analyze_project
from music_video_toolkit.assets import check_assets
from music_video_toolkit.audio import decode_audio
from music_video_toolkit.contracts import RenderManifest, SampleRange
from music_video_toolkit.plan import resolve_plan
from music_video_toolkit.preview import render_preview
from music_video_toolkit.project import sha256_file
from music_video_toolkit.render import render_minimal, renderer_doctor

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "examples/production-demo/create_fixture.py"


def decode_luma(path: Path) -> bytes:
    result = subprocess.run(
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            "scale=16:9,format=gray",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "pipe:1",
        ],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    return result.stdout


def frame_difference(left: bytes, right: bytes) -> tuple[float, int]:
    differences = [abs(a - b) for a, b in zip(left, right, strict=True)]
    return sum(differences) / len(differences), max(differences)


@pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe", "node", "pnpm", "uv")),
    reason="S10 production render tools required",
)
def test_preview_prerolls_smoothing_and_same_timeline_supports_a_b_modes(tmp_path):
    if not renderer_doctor()["ready"]:
        pytest.skip("pinned Playwright Chromium is not installed")

    demo = tmp_path / "demo"
    generated = subprocess.run(
        [sys.executable, str(FIXTURE), str(demo), "--review-mode", "sample-approval"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stderr
    project = demo / "project"
    decode_audio(demo / "synthetic-song.wav", project)
    analyze_project(project, "none")
    check_assets(project, project / "assets.json")
    resolved, resolved_path = resolve_plan(project, project / "visual-plan.json")
    timeline_hash = sha256_file(project / "timeline.json")

    full = demo / "full-c.mp4"
    render_minimal(project, resolved_path, full)
    ranges = project / "s10-ranges.json"
    ranges.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "ranges": [
                    {
                        "id": "late-smooth-route",
                        "role": "climax",
                        "start_sample": 96_000,
                        "end_sample": 120_000,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    preview = demo / "preview-c"
    result = render_preview(project, resolved_path, ranges, preview)
    assert len(result.manifest.outputs) == 1

    frame_size = 16 * 9
    full_frames = decode_luma(full)
    clip_frames = decode_luma(preview / "01-late-smooth-route.mp4")
    expected = full_frames[60 * frame_size : 75 * frame_size]
    mean_error, max_error = frame_difference(clip_frames, expected)
    assert mean_error <= 2.0
    assert max_error <= 16

    visual_plan = json.loads((project / "visual-plan.json").read_text())
    output_hashes = set()
    for mode, category in (("abstract", "abstract"), ("mood", "media")):
        variant = dict(visual_plan)
        variant["mode"] = mode
        variant["layers"] = [
            layer for layer in visual_plan["layers"] if layer["category"] == category
        ]
        target_ids = {layer["id"] for layer in variant["layers"]}
        variant["routes"] = [
            route for route in visual_plan["routes"] if route["target_layer"] in target_ids
        ]
        plan_path = project / f"visual-plan-{mode}.json"
        plan_path.write_text(json.dumps(variant), encoding="utf-8")
        _, variant_path = resolve_plan(project, plan_path, project / f"resolved-plan-{mode}.json")
        output = demo / f"sample-{mode}.mp4"
        render_minimal(
            project,
            variant_path,
            output,
            SampleRange(start_sample=0, end_sample=24_000),
        )
        manifest = RenderManifest.model_validate_json(
            output.with_suffix(".mp4.render.json").read_text()
        )
        assert manifest.status == "completed"
        pixels = decode_luma(output)
        assert pixels and sum(pixels) / len(pixels) > 1
        assert max(pixels) > 10
        output_hashes.add(sha256_file(output))

    assert len(output_hashes) == 2
    assert resolved.mode == "hybrid"
    assert sha256_file(project / "timeline.json") == timeline_hash
