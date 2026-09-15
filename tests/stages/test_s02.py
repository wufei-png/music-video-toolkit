import hashlib
import json
import shutil
import struct
import subprocess
import wave
import zlib
from pathlib import Path

import pytest

from music_video_toolkit.audio import decode_audio
from music_video_toolkit.cli import main
from music_video_toolkit.contracts import RenderManifest
from music_video_toolkit.render import RenderError, render_minimal, renderer_doctor


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
    sample_rate = 48000
    samples = [0] * (5 * sample_rate)
    for second in (1, 2, 3):
        start = second * sample_rate
        for offset in range(480):
            samples[start + offset] = 28000 if offset % 2 == 0 else -28000
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for sample in samples:
            frames.extend(struct.pack("<hh", sample, sample))
        wav.writeframes(frames)


def write_render_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "S02 项目"
    project.mkdir()
    original = tmp_path / "synthetic clicks.wav"
    write_click_wav(original)
    source = decode_audio(original, project)
    image = project / "fixture image.png"
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
            {"name": "click", "source": "synthetic", "sample": second * 48000, "confidence": 1.0}
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
        "seed": 7,
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
                "parameters": {"text": "固定帧 · 音画同步"},
            },
        ],
    }
    (project / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
    (project / "assets.json").write_text(json.dumps(assets), encoding="utf-8")
    plan_path = project / "minimal plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return project, plan_path


def decode_video_luma(path: Path) -> bytes:
    result = subprocess.run(
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            "scale=1:1,format=gray",
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


def decode_audio_mono(path: Path) -> tuple[int, ...]:
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


@pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe", "node", "pnpm")),
    reason="S02 external tools required",
)
def test_fixed_frame_browser_render_audio_sync_and_repeatability(tmp_path, capsys):
    doctor = renderer_doctor()
    if not doctor["ready"]:
        pytest.skip("pinned Playwright Chromium is not installed")
    project, plan = write_render_project(tmp_path)
    first = tmp_path / "first output.mp4"

    assert (
        main(["render", "--project", str(project), "--plan", str(plan), "--output", str(first)])
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["frame_count"] == 150
    assert report["pulse_frames"] == [30, 60, 90]
    assert report["readiness"]["imageReady"] is True
    assert report["readiness"]["glyphInkPixels"] > 100
    assert report["acceleration"] in {"software", "hardware_or_system"}

    luma = decode_video_luma(first)
    assert len(luma) == 150
    for frame in (30, 60, 90):
        assert luma[frame] > luma[frame - 1] + 100
        assert luma[frame] > luma[frame + 1] + 100
    audio = decode_audio_mono(first)
    for frame in (30, 60, 90):
        expected_sample = frame * 1600
        window = range(expected_sample - 2400, expected_sample + 2400)
        peak_sample = max(window, key=lambda index: abs(audio[index]))
        assert abs((peak_sample * 30 // 48000) - frame) <= 1

    manifest = RenderManifest.model_validate(
        json.loads(first.with_suffix(".mp4.render.json").read_text())
    )
    assert manifest.status == "completed"
    assert manifest.outputs[0].sha256 == sha256(first)

    second = tmp_path / "second output.mp4"
    second_report = render_minimal(project, plan, second)
    assert second_report["frame_count"] == 150
    second_luma = decode_video_luma(second)
    assert len(second_luma) == 150
    assert max(abs(a - b) for a, b in zip(luma, second_luma, strict=True)) <= 2


def test_render_rejects_unknown_layer_before_creating_output(tmp_path):
    project, plan_path = write_render_project(tmp_path)
    plan = json.loads(plan_path.read_text())
    plan["layers"][0]["kind"] = "unimplemented"
    plan_path.write_text(json.dumps(plan))
    output = tmp_path / "should-not-exist.mp4"

    with pytest.raises(RenderError) as caught:
        render_minimal(project, plan_path, output)

    assert caught.value.code == "unsupported_render_plan"
    assert not output.exists()
