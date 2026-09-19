"""Renderer-neutral, read-only conformance checks for external visual results."""

import json
import re
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from pydantic import ValidationError

from .contracts import ProviderManifest, ProviderRequest, ProviderVideoProbe
from .documents import read_document
from .project import resolve_record_path, sha256_file


class ProviderError(Exception):
    def __init__(self, code: str, details: object):
        super().__init__(str(details))
        self.code = code
        self.details = details


def _load(model, path: Path):
    try:
        return model.model_validate(read_document(path))
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        raise ProviderError(
            "invalid_provider_document", {"path": str(path), "details": str(exc)}
        ) from exc


def _local_file(record: Path, value: str, digest: str, label: str) -> Path:
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value):
        raise ProviderError("remote_provider_input", {"field": label, "path": value})
    path = resolve_record_path(record, value)
    if not path.is_file():
        raise ProviderError("missing_provider_file", {"field": label, "path": str(path)})
    try:
        actual = sha256_file(path)
    except OSError as exc:
        raise ProviderError(
            "unreadable_provider_file", {"field": label, "path": str(path)}
        ) from exc
    if actual != digest:
        raise ProviderError(
            "provider_hash_mismatch",
            {"field": label, "path": str(path), "expected": digest, "actual": actual},
        )
    return path


def validate_provider_request(path: Path) -> ProviderRequest:
    request = _load(ProviderRequest, path)
    _local_file(
        path, request.canonical_audio.path, request.canonical_audio.sha256, "canonical_audio"
    )
    if resolve_record_path(path, request.source.path) != resolve_record_path(
        path, request.canonical_audio.path
    ):
        raise ProviderError("provider_source_mismatch", "source and canonical paths differ")
    _local_file(path, request.project.path, request.project.sha256, "project")
    resolved = {
        resolve_record_path(path, request.canonical_audio.path),
        resolve_record_path(path, request.project.path),
    }
    for kind, refs in (("plugin", request.plugins), ("asset", request.assets)):
        for index, ref in enumerate(refs):
            target = _local_file(path, ref.path, ref.sha256, f"{kind}[{index}]")
            if target in resolved:
                raise ProviderError("provider_path_alias", {"field": kind, "path": str(target)})
            resolved.add(target)
    return request


def probe_silent_video(path: Path) -> ProviderVideoProbe:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise ProviderError("missing_dependency", {"tool": "ffprobe"})
    command = [
        ffprobe,
        "-v",
        "error",
        "-count_frames",
        "-show_entries",
        "stream=codec_type,codec_name,pix_fmt,width,height,r_frame_rate,avg_frame_rate,"
        "nb_read_frames,time_base",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        raise ProviderError("provider_probe_failed", {"path": str(path), "stderr": result.stderr})
    try:
        streams = json.loads(result.stdout)["streams"]
        if len(streams) != 1 or streams[0]["codec_type"] != "video":
            raise ValueError("expected exactly one video stream and no audio or data streams")
        video = streams[0]
        rate = Fraction(video["r_frame_rate"])
        average = Fraction(video["avg_frame_rate"])
        probe = ProviderVideoProbe(
            video_codec=video["codec_name"],
            pixel_format=video["pix_fmt"],
            width=int(video["width"]),
            height=int(video["height"]),
            fps_num=rate.numerator,
            fps_den=rate.denominator,
            avg_fps_num=average.numerator,
            avg_fps_den=average.denominator,
            frame_count=int(video["nb_read_frames"]),
            has_audio=False,
        )
        time_base = Fraction(video["time_base"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError, ValidationError) as exc:
        raise ProviderError(
            "provider_probe_failed", {"path": str(path), "details": str(exc)}
        ) from exc
    frames = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_frames",
            "-show_entries",
            "frame=best_effort_timestamp",
            "-of",
            "json",
            str(path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if frames.returncode:
        raise ProviderError("provider_probe_failed", {"path": str(path), "stderr": frames.stderr})
    try:
        timestamps = [
            int(frame["best_effort_timestamp"]) for frame in json.loads(frames.stdout)["frames"]
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderError(
            "provider_probe_failed", {"path": str(path), "details": str(exc)}
        ) from exc
    if len(timestamps) != probe.frame_count or any(
        abs(Fraction(timestamp) * time_base - Fraction(index * probe.fps_den, probe.fps_num))
        > time_base
        for index, timestamp in enumerate(timestamps)
    ):
        raise ProviderError("provider_not_cfr", {"path": str(path), "frames": len(timestamps)})
    return probe


def validate_provider_result(request_path: Path, manifest_path: Path) -> ProviderManifest:
    request = validate_provider_request(request_path)
    manifest = _load(ProviderManifest, manifest_path)
    _local_file(manifest_path, manifest.request.path, manifest.request.sha256, "request")
    if resolve_record_path(manifest_path, manifest.request.path) != request_path.resolve():
        raise ProviderError("provider_request_mismatch", "manifest references a different request")
    expected = (
        request.source.sha256,
        request.profile,
        request.range,
        request.backend,
        request.project.sha256,
        [ref.sha256 for ref in request.plugins],
        [ref.sha256 for ref in request.assets],
        request.parameters_sha256,
    )
    actual = (
        manifest.source_sha256,
        manifest.profile,
        manifest.range,
        manifest.backend,
        manifest.project_sha256,
        manifest.plugin_sha256,
        manifest.asset_sha256,
        manifest.parameters_sha256,
    )
    if actual != expected:
        raise ProviderError("provider_identity_mismatch", "manifest identities differ from request")
    if manifest.status != "completed":
        raise ProviderError(
            "provider_failed", manifest.error.model_dump() if manifest.error else None
        )
    assert manifest.video is not None and manifest.probe is not None
    video = _local_file(manifest_path, manifest.video.path, manifest.video.sha256, "video")
    if video in {request_path.resolve(), manifest_path.resolve()}:
        raise ProviderError("provider_path_alias", {"field": "video", "path": str(video)})
    observed = probe_silent_video(video)
    if observed != manifest.probe:
        raise ProviderError(
            "provider_probe_mismatch",
            {"expected": manifest.probe.model_dump(), "actual": observed.model_dump()},
        )
    return manifest
