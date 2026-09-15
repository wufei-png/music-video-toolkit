import hashlib
import json
import shutil
import struct
import subprocess
import wave
import zlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from music_video_toolkit.audio import decode_audio as decode_source_audio
from music_video_toolkit.cli import main
from music_video_toolkit.contracts import PreviewRequest, RenderManifest
from music_video_toolkit.preview import PreviewError, _cache_key, render_preview
from music_video_toolkit.render import render_minimal, renderer_doctor


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def write_png(path: Path) -> None:
    width = height = 32
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.extend((240 if x < 16 else 40, 80 if y < 16 else 220, 120, 255))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(bytes(rows)))
        + png_chunk(b"IEND", b"")
    )


def write_click_wav(path: Path) -> None:
    samples = [0] * (5 * 48000)
    for second in (1, 2, 3):
        for offset in range(480):
            samples[second * 48000 + offset] = 28000 if offset % 2 == 0 else -28000
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        wav.writeframes(b"".join(struct.pack("<hh", sample, sample) for sample in samples))


def write_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "S08 project"
    project.mkdir()
    original = tmp_path / "clicks.wav"
    write_click_wav(original)
    source = decode_source_audio(original, project)
    image = project / "fixture.png"
    write_png(image)
    timeline = {
        "schema_version": "0.1",
        "source": {
            "path": "source/canonical.wav",
            "sha256": source.record.canonical.sha256,
            "sample_rate": 48000,
            "duration_samples": source.record.canonical.duration_samples,
        },
        "analysis": [],
        "events": [
            {"name": "click", "source": "synthetic", "sample": second * 48000}
            for second in (1, 2, 3)
        ],
    }
    assets = {
        "schema_version": "0.1",
        "assets": [
            {
                "id": "fixture",
                "path": image.name,
                "type": "image",
                "sha256": sha256(image),
                "origin": "synthetic",
            }
        ],
    }
    plan = {
        "schema_version": "0.1",
        "timeline_path": "timeline.json",
        "assets_path": "assets.json",
        "mode": "hybrid",
        "seed": 17,
        "layers": [
            {
                "id": "pulse",
                "kind": "s02.pulse",
                "category": "abstract",
                "parameters": {"event": "click"},
            },
            {
                "id": "image",
                "kind": "s02.image",
                "category": "media",
                "asset_id": "fixture",
            },
            {
                "id": "title",
                "kind": "s02.text",
                "category": "text",
                "parameters": {"text": "global time"},
            },
        ],
    }
    (project / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
    (project / "assets.json").write_text(json.dumps(assets), encoding="utf-8")
    plan_path = project / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    return project, plan_path


def write_ranges(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "ranges": [
                    {
                        "id": "first-click",
                        "role": "transition",
                        "start_sample": 48000,
                        "end_sample": 72000,
                    },
                    {
                        "id": "second-click",
                        "role": "climax",
                        "start_sample": 96000,
                        "end_sample": 120000,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


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
    )
    assert result.returncode == 0, result.stderr.decode()
    return result.stdout


def frame_difference(left: bytes, right: bytes) -> tuple[float, int]:
    differences = [abs(a - b) for a, b in zip(left, right, strict=True)]
    return sum(differences) / len(differences), max(differences)


def decode_video_audio(path: Path) -> tuple[int, ...]:
    result = subprocess.run(
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "48000",
            "-f",
            "s16le",
            "pipe:1",
        ],
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode()
    return struct.unpack(f"<{len(result.stdout) // 2}h", result.stdout)


def test_preview_contract_rejects_overlaps_and_duplicate_ids():
    base = {
        "schema_version": "0.1",
        "ranges": [
            {"id": "one", "start_sample": 0, "end_sample": 1600},
            {"id": "two", "start_sample": 800, "end_sample": 2400},
        ],
    }
    with pytest.raises(ValidationError):
        PreviewRequest.model_validate(base)
    base["ranges"][1] = {"id": "one", "start_sample": 1600, "end_sample": 2400}
    with pytest.raises(ValidationError):
        PreviewRequest.model_validate(base)


def test_preview_rejects_unaligned_range_without_output(tmp_path, capsys):
    project, plan = write_project(tmp_path)
    ranges = tmp_path / "ranges.json"
    ranges.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "ranges": [{"id": "bad", "start_sample": 1, "end_sample": 1600}],
            }
        )
    )
    output = tmp_path / "preview"

    assert (
        main(
            [
                "preview",
                "--project",
                str(project),
                "--plan",
                str(plan),
                "--ranges",
                str(ranges),
                "--output",
                str(output),
            ]
        )
        == 4
    )
    assert json.loads(capsys.readouterr().err)["code"] == "preview_range_not_frame_aligned"
    assert not output.exists()


def test_preview_cache_key_covers_material_inputs_seed_and_analysis():
    request = PreviewRequest.model_validate(
        {
            "schema_version": "0.1",
            "ranges": [{"id": "sample", "start_sample": 0, "end_sample": 1600}],
        }
    )
    inputs = {
        "plan": "1" * 64,
        "asset.image": "2" * 64,
        "asset.font": "3" * 64,
        "timeline": "4" * 64,
    }
    baseline = _cache_key("0" * 64, inputs, 7, request, False)
    for field in inputs:
        changed = dict(inputs)
        changed[field] = "f" * 64
        assert _cache_key("0" * 64, changed, 7, request, False) != baseline
    assert _cache_key("0" * 64, inputs, 8, request, False) != baseline


@pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe", "node", "pnpm")),
    reason="S08 external tools required",
)
def test_preview_matches_full_global_frames_reproduces_and_invalidates(tmp_path):
    if not renderer_doctor()["ready"]:
        pytest.skip("pinned Playwright Chromium is not installed")
    project, plan = write_project(tmp_path)
    ranges = tmp_path / "ranges.json"
    write_ranges(ranges)
    full = tmp_path / "full.mp4"
    render_minimal(project, plan, full)

    first_dir = tmp_path / "first-preview"
    first = render_preview(project, plan, ranges, first_dir, review_reel=True)
    assert first.cached is False
    assert [item.model_dump() for item in first.manifest.ranges] == [
        {"start_sample": 48000, "end_sample": 72000},
        {"start_sample": 96000, "end_sample": 120000},
    ]
    assert len(first.manifest.outputs) == 3
    assert (first_dir / "review-reel.mp4").is_file()
    assert render_preview(project, plan, ranges, first_dir, review_reel=True).cached is True

    second_dir = tmp_path / "second-preview"
    second = render_preview(project, plan, ranges, second_dir, review_reel=True)
    assert second.cached is False
    assert second.manifest.cache_key == first.manifest.cache_key

    full_frames = decode_luma(full)
    frame_size = 16 * 9
    for index, start_frame in enumerate((30, 60), 1):
        clip_name = f"0{index}-{'first' if index == 1 else 'second'}-click.mp4"
        first_clip = decode_luma(first_dir / clip_name)
        second_clip = decode_luma(second_dir / clip_name)
        assert len(first_clip) == len(second_clip) == 15 * frame_size
        expected = full_frames[start_frame * frame_size : (start_frame + 15) * frame_size]
        mean_error, max_error = frame_difference(first_clip, expected)
        assert mean_error <= 2.0
        assert max_error <= 16
        repeat_mean, repeat_max = frame_difference(first_clip, second_clip)
        assert repeat_mean <= 2.0
        assert repeat_max <= 16
        audio = decode_video_audio(first_dir / clip_name)
        peak = max(range(min(4800, len(audio))), key=lambda sample: abs(audio[sample]))
        assert peak < 2400
        assert abs(audio[peak]) > 1000

    aggregate = RenderManifest.model_validate(
        json.loads((first_dir / "preview.render.json").read_text())
    )
    assert all((first_dir / item.path).is_file() for item in aggregate.outputs)
    assert all(sha256(first_dir / item.path) == item.sha256 for item in aggregate.outputs)

    (first_dir / "02-second-click.mp4").unlink()
    with pytest.raises(PreviewError) as caught:
        render_preview(project, plan, ranges, first_dir, review_reel=True)
    assert caught.value.code == "preview_output_conflict"

    plan_data = json.loads(plan.read_text())
    plan_data["seed"] = 18
    plan.write_text(json.dumps(plan_data))
    with pytest.raises(PreviewError) as caught:
        render_preview(project, plan, ranges, second_dir, review_reel=True)
    assert caught.value.code == "preview_output_conflict"


def test_preview_rejects_missing_cached_output(tmp_path):
    project, plan = write_project(tmp_path)
    ranges = tmp_path / "ranges.json"
    write_ranges(ranges)
    output = tmp_path / "preview"
    output.mkdir()
    (output / "preview.render.json").write_text("{}")

    with pytest.raises(PreviewError) as caught:
        render_preview(project, plan, ranges, output)

    assert caught.value.code == "preview_output_conflict"
