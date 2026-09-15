import hashlib
import json
import shutil
import struct
import subprocess
import wave
import zlib
from pathlib import Path

import pytest

from music_video_toolkit.assets import AssetError, check_assets
from music_video_toolkit.audio import decode_audio
from music_video_toolkit.plan import PlanError, resolve_plan
from music_video_toolkit.render import render_minimal


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png(path: Path, width: int, height: int, color: tuple[int, int, int]) -> None:
    def chunk(name: bytes, data: bytes) -> bytes:
        checksum = struct.pack(">I", zlib.crc32(name + data))
        return struct.pack(">I", len(data)) + name + data + checksum

    rows = b"".join(b"\0" + bytes(color) * width for _ in range(height))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def make_video(directory: Path) -> Path:
    frames = directory / "numbered"
    frames.mkdir()
    colors = [
        (220, 30, 30),
        (30, 200, 40),
        (30, 60, 220),
        (230, 210, 30),
        (180, 40, 200),
        (20, 210, 210),
    ]
    for index, color in enumerate(colors):
        png(frames / f"frame-{index}.png", 160, 90, color)
    output = directory / "numbered-with-audio.mp4"
    result = subprocess.run(
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-framerate",
            "2",
            "-i",
            str(frames / "frame-%d.png"),
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:sample_rate=48000:duration=3",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(output),
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    return output


def fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, Path]]:
    original = tmp_path / "silent.wav"
    with wave.open(str(original), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(48_000)
        wav.writeframes(b"\0" * 48_000 * 4)
    project = tmp_path / "project"
    source = decode_audio(original, project)
    timeline = {
        "schema_version": "0.1",
        "source": {
            "path": "source/canonical.wav",
            "sha256": source.record.canonical.sha256,
            "sample_rate": 48_000,
            "duration_samples": 48_000,
        },
        "analysis": [],
        "signals": {
            "mix.rms": {
                "start_sample": 0,
                "hop_samples": 24_000,
                "values": [0.2, 0.8],
                "unit": "normalized",
            }
        },
        "events": [],
        "sections": [
            {
                "id": "first",
                "origin": "manual",
                "start_sample": 0,
                "end_sample": 24_000,
            },
            {
                "id": "second",
                "origin": "manual",
                "start_sample": 24_000,
                "end_sample": 48_000,
            },
        ],
    }
    (project / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
    assets_dir = project / "media"
    assets_dir.mkdir()
    first = assets_dir / "red.png"
    second = assets_dir / "blue.png"
    png(first, 160, 90, (210, 35, 35))
    png(second, 160, 90, (35, 55, 220))
    video = make_video(assets_dir)
    font = Path("/System/Library/Fonts/SFNSMono.ttf")
    files = {"red": first, "blue": second, "numbered": video, "font": font}
    manifest = {
        "schema_version": "0.1",
        "assets": [
            {
                "id": name,
                "path": (
                    str(path.relative_to(project)) if path.is_relative_to(project) else str(path)
                ),
                "type": "font" if name == "font" else "video" if name == "numbered" else "image",
                "sha256": sha256(path),
                "origin": "synthetic",
            }
            for name, path in files.items()
        ],
    }
    manifest_path = project / "assets.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return project, manifest_path, files


def plan_document(mode: str) -> dict:
    abstract = {
        "id": "orb",
        "kind": "orb",
        "category": "abstract",
        "parameters": {"x": -0.45, "color": "#66ddff"},
    }
    background = {
        "id": "background",
        "kind": "image",
        "category": "media",
        "asset_id": "red",
        "parameters": {"fit": "cover", "z": -8},
    }
    video = {
        "id": "numbered",
        "kind": "video",
        "category": "media",
        "asset_id": "numbered",
        "opacity": 0.65,
        "parameters": {
            "fit": "contain",
            "scale": 0.35,
            "x": 0.48,
            "z": -3,
            "mask": "circle",
            "in_frame": 1,
            "out_frame": 5,
            "end_behavior": "loop",
            "muted": True,
        },
    }
    layers = [abstract] if mode == "abstract" else [background, video]
    if mode == "hybrid":
        layers.append(abstract)
    return {
        "schema_version": "0.1",
        "timeline_path": "timeline.json",
        "assets_path": "assets.json",
        "mode": mode,
        "seed": 505,
        "layers": layers,
        "routes": (
            [
                {
                    "source": "mix.rms",
                    "target_layer": "orb",
                    "target_parameter": "radius",
                    "transform": {
                        "kind": "linear",
                        "parameters": {"min": 0.15, "max": 0.48},
                    },
                }
            ]
            if mode != "mood"
            else []
        ),
        "sections": (
            [
                {
                    "section_id": "second",
                    "transition_samples": 12_000,
                    "layers": [{"layer_id": "background", "asset_id": "blue"}],
                }
            ]
            if mode != "abstract"
            else []
        ),
    }


def frame_pixels(path: Path, frames: list[int], x: int, y: int) -> list[tuple[int, int, int]]:
    selected = "+".join(f"eq(n,{frame})" for frame in frames)
    result = subprocess.run(
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            f"select='{selected}',format=rgb24,crop=1:1:{x}:{y}",
            "-vsync",
            "0",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert len(result.stdout) == len(frames) * 3
    return [tuple(result.stdout[index : index + 3]) for index in range(0, len(result.stdout), 3)]


@pytest.mark.skipif(not shutil.which("ffprobe"), reason="FFprobe required")
def test_asset_preflight_checks_image_video_font_and_cache_identity(tmp_path):
    project, manifest_path, files = fixture(tmp_path)
    checked, output, cached = check_assets(project, manifest_path)
    by_id = {asset.id: asset for asset in checked.assets}

    assert cached is False
    assert (by_id["red"].width, by_id["red"].height) == (160, 90)
    assert (by_id["numbered"].frame_count, by_id["numbered"].fps_num) == (6, 2)
    assert by_id["numbered"].has_audio is True
    assert by_id["font"].font_families
    assert check_assets(project, manifest_path)[2] is True
    first_key = checked.cache_key

    png(files["red"], 160, 90, (20, 220, 80))
    manifest = json.loads(manifest_path.read_text())
    red = next(item for item in manifest["assets"] if item["id"] == "red")
    red["sha256"] = sha256(files["red"])
    manifest_path.write_text(json.dumps(manifest))
    changed, changed_output, changed_cached = check_assets(project, manifest_path)
    assert changed_output == output
    assert changed_cached is False
    assert changed.cache_key != first_key


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (lambda item: item.update(path="missing.png"), "missing_asset"),
        (lambda item: item.update(sha256="0" * 64), "asset_hash_mismatch"),
        (lambda item: item.update(path="https://example.com/a.png"), "remote_asset_forbidden"),
        (lambda item: item.update(type="font"), "font_probe_failed"),
    ],
)
def test_asset_preflight_reports_explicit_failures(tmp_path, change, code):
    project, manifest_path, _ = fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    change(manifest["assets"][0])
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssetError) as caught:
        check_assets(project, manifest_path)
    assert caught.value.code == code


def test_short_video_requires_explicit_loop_or_hold(tmp_path):
    project, _, _ = fixture(tmp_path)
    plan = plan_document("mood")
    video = next(layer for layer in plan["layers"] if layer["kind"] == "video")
    video["parameters"].update(in_frame=1, out_frame=2, end_behavior="error")
    path = project / "plan.json"
    path.write_text(json.dumps(plan))
    with pytest.raises(PlanError) as caught:
        resolve_plan(project, path)
    assert caught.value.code == "media_too_short"
    video["parameters"]["end_behavior"] = "hold"
    path.write_text(json.dumps(plan))
    assert resolve_plan(project, path)[0].mode == "mood"


def test_media_plan_rejects_unknown_asset_and_declared_type_mismatch(tmp_path):
    project, manifest_path, _ = fixture(tmp_path)
    plan = plan_document("mood")
    plan["layers"][0]["asset_id"] = "unknown"
    path = project / "plan.json"
    path.write_text(json.dumps(plan))
    with pytest.raises(PlanError) as caught:
        resolve_plan(project, path)
    assert caught.value.code == "unknown_asset"

    manifest = json.loads(manifest_path.read_text())
    numbered = next(item for item in manifest["assets"] if item["id"] == "numbered")
    numbered["type"] = "image"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssetError) as caught:
        check_assets(project, manifest_path)
    assert caught.value.code == "asset_type_mismatch"


@pytest.mark.skipif(
    not all(shutil.which(name) for name in ("ffmpeg", "ffprobe", "node", "pnpm")),
    reason="render dependencies required",
)
def test_same_timeline_renders_abstract_mood_and_hybrid_without_media_audio(tmp_path):
    project, _, _ = fixture(tmp_path)
    source_timeline_hash = sha256(project / "timeline.json")
    outputs = {}
    for mode in ("abstract", "mood", "hybrid"):
        plan_path = project / f"plan-{mode}.json"
        plan_path.write_text(json.dumps(plan_document(mode)))
        resolved_path = project / f"resolved-{mode}.json"
        resolve_plan(project, plan_path, resolved_path)
        output = project / f"{mode}.mp4"
        report = render_minimal(project, resolved_path, output)
        assert report["frame_count"] == 30
        outputs[mode] = output
    assert sha256(project / "timeline.json") == source_timeline_hash
    assert len({sha256(path) for path in outputs.values()}) == 3

    background = frame_pixels(outputs["mood"], [14, 18, 23], 40, 40)
    assert background[0][0] > background[0][2]
    assert background[2][2] > background[2][0]
    assert background[0] != background[1] != background[2]
    numbered = frame_pixels(outputs["mood"], [0, 15], 1420, 540)
    assert numbered[0][1] > numbered[0][0]
    assert numbered[1][2] > numbered[1][0]

    decoded = subprocess.run(
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-v",
            "error",
            "-i",
            str(outputs["mood"]),
            "-map",
            "0:a:0",
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "pipe:1",
        ],
        capture_output=True,
    )
    assert decoded.returncode == 0
    assert set(decoded.stdout) <= {0}
