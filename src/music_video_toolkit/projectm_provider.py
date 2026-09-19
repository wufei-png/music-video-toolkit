"""Offline, approved-preset projectM provider behind the S13 process contract."""

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .contracts import ProviderManifest
from .project import resolve_record_path, sha256_file
from .provider import (
    ProviderError,
    probe_silent_video,
    validate_provider_request,
    validate_provider_result,
)

ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = ROOT / "integrations/projectm"
LOCK = json.loads((INTEGRATION / "lock.json").read_text(encoding="utf-8"))


class ProjectMError(Exception):
    def __init__(self, code: str, details: object):
        super().__init__(str(details))
        self.code = code
        self.details = details


def integration_identity() -> str:
    digest = hashlib.sha256()
    digest.update(bytes.fromhex(LOCK["patch_stack_sha256"]))
    digest.update((INTEGRATION / "provider.cpp").read_bytes())
    return digest.hexdigest()


def _checked_runtime(checkout: Path, build: Path) -> dict[str, str]:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/projectm_env.py"),
            "check",
            "--checkout",
            str(checkout),
            "--build",
            str(build),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ProjectMError("projectm_not_ready", result.stderr.strip())
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise ProjectMError("projectm_invalid_runtime", result.stdout) from exc


def _approved_preset(request_path: Path, request) -> Path:
    if request.plugins or len(request.assets) != 1:
        raise ProjectMError("projectm_unsupported_inputs", "one approved preset asset; no plugins")
    if request.parameters != {"preset_id": "mvt-wave", "policy": "locked-single"}:
        raise ProjectMError("projectm_unsupported_parameters", request.parameters)
    project_path = resolve_record_path(request_path, request.project.path)
    try:
        document = json.loads(project_path.read_text(encoding="utf-8"))
        if set(document) != {"preset"} or set(document["preset"]) != {"path", "sha256"}:
            raise ValueError("expected only preset path and sha256")
        item = document["preset"]
        preset = resolve_record_path(project_path, item["path"])
        asset = resolve_record_path(request_path, request.assets[0].path)
        if preset != asset or item["sha256"] != request.assets[0].sha256:
            raise ValueError("project preset differs from checked asset")
        if sha256_file(preset) != LOCK["preset_sha256"]:
            raise ValueError("preset is not on the approved list")
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        raise ProjectMError("projectm_invalid_project", str(exc)) from exc
    return preset


def _stop(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.kill()
    for process in processes:
        process.wait()


def _encode_frames(
    *, binary: Path, pcm: Path, preset: Path, request, output: Path, log_dir: Path
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise ProjectMError("missing_dependency", "ffmpeg")
    width, height = request.profile.width, request.profile.height
    start = request.range.start_sample // 1600
    end = request.range.end_sample // 1600
    expected_bytes = (end - start) * width * height * 4
    producer_command = [
        str(binary),
        str(pcm),
        str(preset),
        str(preset.parent),
        str(width),
        str(height),
        str(start),
        str(end),
    ]
    encoder_command = [
        ffmpeg,
        "-nostdin",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgba",
        "-video_size",
        f"{width}x{height}",
        "-framerate",
        "30",
        "-i",
        "pipe:0",
        "-vf",
        "vflip",
        "-frames:v",
        str(end - start),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-an",
        "-movflags",
        "+faststart",
        str(output),
    ]
    count = 0
    with (
        (log_dir / "projectm.stderr").open("wb") as producer_log,
        (log_dir / "ffmpeg.stderr").open("wb") as encoder_log,
    ):
        producer = subprocess.Popen(producer_command, stdout=subprocess.PIPE, stderr=producer_log)
        encoder = subprocess.Popen(encoder_command, stdin=subprocess.PIPE, stderr=encoder_log)
        try:
            assert producer.stdout is not None and encoder.stdin is not None
            while block := producer.stdout.read(1024 * 1024):
                count += len(block)
                encoder.stdin.write(block)
            encoder.stdin.close()
            producer_code = producer.wait()
            encoder_code = encoder.wait()
        except BaseException:
            _stop([producer, encoder])
            raise
    if producer_code or encoder_code or count != expected_bytes:
        raise ProjectMError(
            "projectm_export_failed",
            {
                "provider_exit": producer_code,
                "encoder_exit": encoder_code,
                "bytes": count,
                "expected_bytes": expected_bytes,
                "provider_stderr": (log_dir / "projectm.stderr").read_text(errors="replace")[
                    -2000:
                ],
                "ffmpeg_stderr": (log_dir / "ffmpeg.stderr").read_text(errors="replace")[-2000:],
            },
        )


def render_projectm(
    request_path: Path, output: Path, checkout: Path, build: Path
) -> dict[str, object]:
    request_path = request_path.resolve()
    output = output.resolve()
    checkout = checkout.resolve()
    build = build.resolve()
    try:
        request = validate_provider_request(request_path)
    except ProviderError as exc:
        raise ProjectMError(exc.code, exc.details) from exc
    if (
        request.backend.name != "projectm"
        or request.backend.version != LOCK["version"]
        or request.backend.commit != LOCK["commit"]
        or request.backend.integration_patch_sha256 != integration_identity()
    ):
        raise ProjectMError("projectm_lock_mismatch", request.backend.model_dump())
    preset = _approved_preset(request_path, request)
    runtime = _checked_runtime(checkout, build)
    if output.exists() or not output.parent.is_dir():
        raise ProjectMError("invalid_provider_output", str(output))
    lock_dir = output.parent / f".{output.name}.mvt-lock"
    try:
        lock_dir.mkdir()
    except FileExistsError as exc:
        raise ProjectMError("provider_output_locked", str(output)) from exc
    temp: Path | None = None
    try:
        temp = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
        canonical = resolve_record_path(request_path, request.canonical_audio.path)
        pcm = temp / "canonical.f32le"
        decode = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-i",
                str(canonical),
                "-map",
                "0:a:0",
                "-f",
                "f32le",
                "-ac",
                "2",
                "-ar",
                "48000",
                str(pcm),
            ],
            capture_output=True,
            check=False,
        )
        if decode.returncode:
            raise ProjectMError(
                "projectm_pcm_failed", decode.stderr.decode(errors="replace")[-2000:]
            )
        video = temp / "video.mp4"
        _encode_frames(
            binary=build / "mvt-projectm-render",
            pcm=pcm,
            preset=preset,
            request=request,
            output=video,
            log_dir=temp,
        )
        probe = probe_silent_video(video)
        manifest = ProviderManifest(
            schema_version="0.1",
            status="completed",
            request={
                "path": os.path.relpath(request_path, temp),
                "sha256": sha256_file(request_path),
            },
            source_sha256=request.source.sha256,
            profile=request.profile,
            range=request.range,
            backend=request.backend,
            project_sha256=request.project.sha256,
            plugin_sha256=[],
            asset_sha256=[ref.sha256 for ref in request.assets],
            parameters_sha256=request.parameters_sha256,
            environment={
                "platform": platform.platform(),
                "provider_binary_sha256": sha256_file(build / "mvt-projectm-render"),
                "mvt_adapter_sha256": sha256_file(Path(__file__)),
                "core_library_sha256": runtime["library_sha256"],
                "ffmpeg": subprocess.run(
                    ["ffmpeg", "-version"], capture_output=True, text=True, check=True
                ).stdout.splitlines()[0],
                "global_time_policy": "preroll-from-zero",
            },
            video={"path": "video.mp4", "sha256": sha256_file(video)},
            probe=probe,
        )
        manifest_path = temp / "provider-manifest.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
        validate_provider_result(request_path, manifest_path)
        for name in ("canonical.f32le", "projectm.stderr", "ffmpeg.stderr"):
            (temp / name).unlink()
        os.replace(temp, output)
        return {
            "status": "completed",
            "provider": "projectm",
            "request": str(request_path),
            "manifest": str(output / "provider-manifest.json"),
            "video": str(output / "video.mp4"),
            "video_sha256": manifest.video.sha256,
        }
    except (OSError, ValueError, ProviderError) as exc:
        raise ProjectMError("projectm_invalid_result", str(exc)) from exc
    finally:
        if temp is not None:
            shutil.rmtree(temp, ignore_errors=True)
        lock_dir.rmdir()
