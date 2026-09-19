"""Synthetic external-provider conformance without a real application backend."""

import hashlib
import json
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from music_video_toolkit.contracts import ProviderManifest, ProviderRequest
from music_video_toolkit.project import sha256_file
from music_video_toolkit.provider import (
    ProviderError,
    validate_provider_request,
    validate_provider_result,
)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def fake_provider(tmp_path: Path) -> tuple[Path, Path, Path, dict, dict]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg is needed for real media conformance")
    audio = tmp_path / "canonical.wav"
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(3)
        wav.setframerate(48000)
        wav.writeframes(b"\0" * 48000 * 2 * 3)
    project = tmp_path / "project.json"
    write_json(project, {"name": "public synthetic"})
    plugin = tmp_path / "plugin.js"
    plugin.write_text("export default () => 1;", encoding="utf-8")
    asset = tmp_path / "asset.txt"
    asset.write_text("public synthetic asset", encoding="utf-8")
    parameters = {"seed": 7, "gain": 0.5}
    parameters_sha = hashlib.sha256(
        json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    request = {
        "schema_version": "0.1",
        "source": {
            "path": audio.name,
            "sha256": sha256_file(audio),
            "sample_rate": 48000,
            "duration_samples": 48000,
        },
        "canonical_audio": {"path": audio.name, "sha256": sha256_file(audio)},
        "profile": {"width": 1920, "height": 1080, "fps_num": 30, "fps_den": 1},
        "range": {"start_sample": 0, "end_sample": 48000},
        "backend": {
            "name": "fake",
            "version": "1.0",
            "commit": "a" * 40,
            "integration_patch_sha256": "b" * 64,
        },
        "project": {"path": project.name, "sha256": sha256_file(project)},
        "plugins": [{"path": plugin.name, "sha256": sha256_file(plugin)}],
        "assets": [{"path": asset.name, "sha256": sha256_file(asset)}],
        "parameters": parameters,
        "parameters_sha256": parameters_sha,
    }
    request_path = tmp_path / "request.json"
    write_json(request_path, request)
    video = tmp_path / "video.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=navy:s=1920x1080:r=30:d=1",
            "-frames:v",
            "30",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(video),
        ],
        check=True,
    )
    manifest = {
        "schema_version": "0.1",
        "status": "completed",
        "request": {"path": request_path.name, "sha256": sha256_file(request_path)},
        "source_sha256": request["source"]["sha256"],
        "profile": request["profile"],
        "range": request["range"],
        "backend": request["backend"],
        "project_sha256": request["project"]["sha256"],
        "plugin_sha256": [request["plugins"][0]["sha256"]],
        "asset_sha256": [request["assets"][0]["sha256"]],
        "parameters_sha256": parameters_sha,
        "environment": {"host": "synthetic"},
        "video": {"path": video.name, "sha256": sha256_file(video)},
        "probe": {
            "video_codec": "h264",
            "pixel_format": "yuv420p",
            "width": 1920,
            "height": 1080,
            "fps_num": 30,
            "fps_den": 1,
            "avg_fps_num": 30,
            "avg_fps_den": 1,
            "frame_count": 30,
            "has_audio": False,
        },
    }
    manifest_path = tmp_path / "manifest.json"
    write_json(manifest_path, manifest)
    return request_path, manifest_path, video, request, manifest


def test_completed_fake_provider_conforms(fake_provider):
    request_path, manifest_path, _, _, _ = fake_provider
    assert validate_provider_request(request_path).backend.name == "fake"
    assert validate_provider_result(request_path, manifest_path).probe.frame_count == 30


@pytest.mark.parametrize("field", ["source", "profile", "range", "backend", "project_sha256"])
def test_manifest_identity_tampering_rejected(fake_provider, field):
    request_path, manifest_path, _, _, manifest = fake_provider
    manifest[field] = "0" * 64 if field == "project_sha256" else None
    write_json(manifest_path, manifest)
    with pytest.raises(ProviderError):
        validate_provider_result(request_path, manifest_path)


def test_stale_request_and_input_hashes_rejected(fake_provider):
    request_path, manifest_path, _, request, _ = fake_provider
    request["parameters"]["seed"] = 8
    write_json(request_path, request)
    with pytest.raises(ProviderError):
        validate_provider_result(request_path, manifest_path)


def test_partial_or_tampered_video_rejected(fake_provider):
    request_path, manifest_path, video, _, _ = fake_provider
    video.write_bytes(b"partial")
    with pytest.raises(ProviderError) as error:
        validate_provider_result(request_path, manifest_path)
    assert error.value.code == "provider_hash_mismatch"


def test_audio_bearing_result_rejected(fake_provider):
    request_path, manifest_path, video, _, manifest = fake_provider
    ffmpeg = shutil.which("ffmpeg")
    with_audio = video.with_name("with-audio.mp4")
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(with_audio),
        ],
        check=True,
    )
    manifest["video"] = {"path": with_audio.name, "sha256": sha256_file(with_audio)}
    write_json(manifest_path, manifest)
    with pytest.raises(ProviderError) as error:
        validate_provider_result(request_path, manifest_path)
    assert error.value.code == "provider_probe_failed"


def test_wrong_clock_result_rejected(fake_provider):
    request_path, manifest_path, _, _, manifest = fake_provider
    ffmpeg = shutil.which("ffmpeg")
    wrong = manifest_path.with_name("wrong.mp4")
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=navy:s=1920x1080:r=25:d=1",
            "-frames:v",
            "25",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(wrong),
        ],
        check=True,
    )
    manifest["video"] = {"path": wrong.name, "sha256": sha256_file(wrong)}
    write_json(manifest_path, manifest)
    with pytest.raises(ProviderError):
        validate_provider_result(request_path, manifest_path)


def test_schema_and_failure_semantics(fake_provider):
    request_path, _, _, request, manifest = fake_provider
    assert ProviderRequest.model_validate(request).schema_version == "0.1"
    manifest["status"] = "failed"
    manifest["video"] = None
    manifest["probe"] = None
    manifest["error"] = {"stage": "render", "code": "cancelled", "message": "cancelled"}
    assert ProviderManifest.model_validate(manifest).error.code == "cancelled"
    with pytest.raises(ProviderError):
        validate_provider_request(request_path.with_name("missing.json"))
