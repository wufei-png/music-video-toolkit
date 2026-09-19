"""Auditable comparison of already-completed preview manifests and media."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import struct
import subprocess
import tempfile
import zlib
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from pydantic import ValidationError

from . import __version__
from .contracts import (
    ComparisonArtifacts,
    ComparisonClip,
    ComparisonManifest,
    ComparisonMediaProbe,
    ComparisonProfile,
    ComparisonRequest,
    ComparisonVariant,
    FileRef,
    RenderManifest,
    SampleRange,
)
from .documents import read_document
from .project import resolve_record_path, sha256_file

SAMPLE_RATE = 48000
CONTACT_MAX_DIMENSION = 480
CONTACT_LABEL_HEIGHT = 30
PREVIEW_INPUT_KEYS = {"preview_request", "preview_adapter"}


class ComparisonError(Exception):
    """A stable comparison failure suitable for machine-readable CLI output."""

    def __init__(self, code: str, details: object, exit_code: int = 2):
        super().__init__(str(details))
        self.code = code
        self.details = details
        self.exit_code = exit_code


@dataclass(frozen=True)
class PreparedVariant:
    record: ComparisonVariant
    clip_paths: tuple[Path, ...]


@dataclass(frozen=True)
class PreparedComparison:
    request: ComparisonRequest
    request_ref: FileRef
    source_sha256: str
    original_source_sha256: str
    ranges: tuple[SampleRange, ...]
    profile: ComparisonProfile
    variants: tuple[PreparedVariant, ...]


@dataclass(frozen=True)
class ComparisonResult:
    manifest: ComparisonManifest
    manifest_path: Path
    cached: bool

    def summary(self) -> dict[str, object]:
        return {
            "ok": True,
            "cached": self.cached,
            "manifest": str(self.manifest_path),
            "variants": len(self.manifest.variants),
            "ranges": len(self.manifest.ranges),
            "review_reel": str(
                resolve_record_path(self.manifest_path, self.manifest.artifacts.review_reel.path)
            ),
            "contact_sheet": str(
                resolve_record_path(self.manifest_path, self.manifest.artifacts.contact_sheet.path)
            ),
            "cache_key": self.manifest.cache_key,
        }


def _error_details(exc: Exception) -> object:
    if isinstance(exc, ValidationError):
        return exc.errors(include_url=False, include_context=False, include_input=False)
    return str(exc)


def _load_request(path: Path) -> ComparisonRequest:
    try:
        return ComparisonRequest.model_validate(read_document(path))
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        raise ComparisonError("invalid_comparison_request", _error_details(exc), 4) from exc


def _load_preview(path: Path) -> RenderManifest:
    try:
        return RenderManifest.model_validate(read_document(path))
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        raise ComparisonError(
            "invalid_preview_manifest", {"path": str(path), "details": _error_details(exc)}, 4
        ) from exc


def _dependency(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise ComparisonError(
            "missing_dependency",
            {"tool": name, "message": f"Install {name} and ensure it is on PATH"},
            3,
        )
    return path


def _run(
    command: list[str], *, cwd: Path | None = None, code: str
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise ComparisonError(code, str(exc), 3) from exc
    if result.returncode != 0:
        raise ComparisonError(
            code,
            {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr},
            5,
        )
    return result


def _tool_version(path: str) -> str:
    return _run([path, "-version"], code="comparison_tool_unavailable").stdout.splitlines()[0]


def _decoded_audio_sha256(ffmpeg: str, path: Path) -> str:
    result = _run(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "2",
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "pcm_s24le",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        code="comparison_audio_probe_failed",
    )
    prefix = "SHA256="
    value = result.stdout.strip()
    if not value.startswith(prefix) or len(value.removeprefix(prefix)) != 64:
        raise ComparisonError("comparison_audio_probe_failed", {"path": str(path)}, 5)
    return value.removeprefix(prefix).lower()


def _stream_compatibility_sha256(video: dict[str, object], audio: dict[str, object] | None) -> str:
    ignored = {"index", "codec_type", "nb_read_frames"}
    value = {
        "video": {key: value for key, value in video.items() if key not in ignored},
        "audio": (
            {key: value for key, value in audio.items() if key not in ignored}
            if audio is not None
            else None
        ),
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _probe_clip(ffprobe: str, ffmpeg: str, path: Path) -> ComparisonMediaProbe:
    result = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-show_data_hash",
            "sha256",
            "-show_entries",
            (
                "stream=index,codec_type,codec_name,profile,codec_tag_string,width,height,"
                "coded_width,coded_height,pix_fmt,level,color_range,color_space,color_transfer,"
                "color_primaries,chroma_location,field_order,refs,is_avc,nal_length_size,"
                "r_frame_rate,avg_frame_rate,time_base,nb_read_frames,sample_fmt,sample_rate,"
                "channels,channel_layout,initial_padding,extradata_hash"
            ),
            "-of",
            "json",
            str(path),
        ],
        code="comparison_media_probe_failed",
    )
    try:
        streams = json.loads(result.stdout)["streams"]
        videos = [stream for stream in streams if stream["codec_type"] == "video"]
        audios = [stream for stream in streams if stream["codec_type"] == "audio"]
        if len(videos) != 1 or len(audios) > 1:
            raise ValueError("expected exactly one video stream and at most one audio stream")
        video = videos[0]
        fps = Fraction(video["r_frame_rate"])
        average_fps = Fraction(video["avg_frame_rate"])
        audio = audios[0] if audios else None
        return ComparisonMediaProbe(
            video_codec=video["codec_name"],
            video_pixel_format=video["pix_fmt"],
            width=int(video["width"]),
            height=int(video["height"]),
            fps_num=fps.numerator,
            fps_den=fps.denominator,
            avg_fps_num=average_fps.numerator,
            avg_fps_den=average_fps.denominator,
            frame_count=int(video["nb_read_frames"]),
            stream_compatibility_sha256=_stream_compatibility_sha256(video, audio),
            has_audio=audio is not None,
            audio_codec=audio["codec_name"] if audio is not None else None,
            audio_sha256=_decoded_audio_sha256(ffmpeg, path) if audio is not None else None,
            audio_sample_rate=int(audio["sample_rate"]) if audio is not None else None,
            audio_channels=int(audio["channels"]) if audio is not None else None,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        raise ComparisonError(
            "comparison_media_probe_failed", {"path": str(path), "details": str(exc)}, 5
        ) from exc


def _relative(path: Path, anchor: Path) -> str:
    return os.path.relpath(path, anchor.parent)


def _require_file_hash(path: Path, expected: str, *, field: str) -> None:
    if not path.is_file():
        raise ComparisonError("comparison_input_missing", {"field": field, "path": str(path)}, 4)
    try:
        actual = sha256_file(path)
    except OSError as exc:
        raise ComparisonError(
            "comparison_input_unreadable",
            {"field": field, "path": str(path), "message": str(exc)},
            4,
        ) from exc
    if actual != expected:
        raise ComparisonError(
            "comparison_input_hash_mismatch",
            {"field": field, "path": str(path), "expected": expected, "actual": actual},
            4,
        )


def _prepare_comparison(
    request_path: Path, manifest_path: Path, ffprobe: str, ffmpeg: str
) -> PreparedComparison:
    request = _load_request(request_path)
    request_hash = sha256_file(request_path)
    request_ref = FileRef(path=_relative(request_path, manifest_path), sha256=request_hash)
    prepared: list[PreparedVariant] = []
    resolved_preview_paths: set[Path] = set()
    reference_manifest: RenderManifest | None = None
    reference_profile: tuple[str, str, int, int, int, int, str, bool] | None = None
    reference_frame_counts: list[int] | None = None
    reference_audio_hashes: list[str | None] | None = None

    for variant in request.variants:
        preview_path = resolve_record_path(request_path, variant.preview_manifest_path)
        if preview_path in resolved_preview_paths:
            raise ComparisonError(
                "comparison_preview_duplicate",
                {"variant": variant.id, "path": str(preview_path)},
                4,
            )
        resolved_preview_paths.add(preview_path)
        preview = _load_preview(preview_path)
        if preview.status != "completed":
            raise ComparisonError(
                "comparison_preview_incomplete",
                {"variant": variant.id, "path": str(preview_path)},
                4,
            )
        if preview.canonical_audio_sha256 is None:
            raise ComparisonError(
                "comparison_canonical_source_missing",
                {"variant": variant.id, "path": str(preview_path)},
                4,
            )
        if not PREVIEW_INPUT_KEYS.issubset(preview.inputs):
            raise ComparisonError(
                "comparison_preview_manifest_required",
                {
                    "variant": variant.id,
                    "path": str(preview_path),
                    "missing_inputs": sorted(PREVIEW_INPUT_KEYS - preview.inputs.keys()),
                },
                4,
            )
        range_count = len(preview.ranges)
        if len(preview.outputs) not in {range_count, range_count + 1}:
            raise ComparisonError(
                "comparison_preview_outputs_invalid",
                {"variant": variant.id, "ranges": range_count, "outputs": len(preview.outputs)},
                4,
            )
        preview_root = preview_path.parent.resolve()
        if len(preview.outputs) == range_count + 1:
            extra = resolve_record_path(preview_path, preview.outputs[-1].path)
            if extra.name != "review-reel.mp4" or not extra.is_relative_to(preview_root):
                raise ComparisonError(
                    "comparison_preview_outputs_invalid",
                    {"variant": variant.id, "extra_output": preview.outputs[-1].path},
                    4,
                )
            _require_file_hash(extra, preview.outputs[-1].sha256, field=f"{variant.id}.review_reel")

        clips: list[ComparisonClip] = []
        clip_paths: list[Path] = []
        for index, (sample_range, output) in enumerate(
            zip(preview.ranges, preview.outputs[:range_count], strict=True), 1
        ):
            clip_path = resolve_record_path(preview_path, output.path)
            if not clip_path.is_relative_to(preview_root):
                raise ComparisonError(
                    "comparison_preview_reference_invalid",
                    {"variant": variant.id, "path": output.path},
                    4,
                )
            _require_file_hash(clip_path, output.sha256, field=f"{variant.id}.clip.{index}")
            probe = _probe_clip(ffprobe, ffmpeg, clip_path)
            frame_numerator = (sample_range.end_sample - sample_range.start_sample) * probe.fps_num
            frame_denominator = SAMPLE_RATE * probe.fps_den
            if frame_numerator % frame_denominator:
                raise ComparisonError(
                    "comparison_range_profile_mismatch",
                    {"variant": variant.id, "range_index": index},
                    4,
                )
            expected_frames = frame_numerator // frame_denominator
            if probe.frame_count != expected_frames:
                raise ComparisonError(
                    "comparison_frame_count_mismatch",
                    {
                        "variant": variant.id,
                        "range_index": index,
                        "expected": expected_frames,
                        "actual": probe.frame_count,
                    },
                    4,
                )
            clips.append(
                ComparisonClip(
                    range_index=index,
                    range=sample_range,
                    file=FileRef(path=_relative(clip_path, manifest_path), sha256=output.sha256),
                    probe=probe,
                )
            )
            clip_paths.append(clip_path)

        profile = (
            clips[0].probe.video_codec,
            clips[0].probe.video_pixel_format,
            clips[0].probe.width,
            clips[0].probe.height,
            clips[0].probe.fps_num,
            clips[0].probe.fps_den,
            clips[0].probe.stream_compatibility_sha256,
            clips[0].probe.has_audio,
        )
        if any(
            (
                clip.probe.video_codec,
                clip.probe.video_pixel_format,
                clip.probe.width,
                clip.probe.height,
                clip.probe.fps_num,
                clip.probe.fps_den,
                clip.probe.stream_compatibility_sha256,
                clip.probe.has_audio,
            )
            != profile
            for clip in clips
        ):
            raise ComparisonError(
                "comparison_profile_mismatch", {"variant": variant.id, "scope": "ranges"}, 4
            )
        if preview.profile is not None:
            declared_profile = (
                preview.profile.width,
                preview.profile.height,
                preview.profile.fps_num,
                preview.profile.fps_den,
            )
            if declared_profile != profile[2:6]:
                raise ComparisonError(
                    "comparison_profile_mismatch",
                    {"variant": variant.id, "scope": "manifest"},
                    4,
                )
        if reference_manifest is None:
            reference_manifest = preview
            reference_profile = profile
            reference_frame_counts = [clip.probe.frame_count for clip in clips]
            reference_audio_hashes = [clip.probe.audio_sha256 for clip in clips]
        else:
            if preview.canonical_audio_sha256 != reference_manifest.canonical_audio_sha256:
                raise ComparisonError("comparison_source_mismatch", {"variant": variant.id}, 4)
            if preview.source_sha256 != reference_manifest.source_sha256:
                raise ComparisonError(
                    "comparison_original_source_mismatch", {"variant": variant.id}, 4
                )
            if preview.ranges != reference_manifest.ranges:
                raise ComparisonError("comparison_range_mismatch", {"variant": variant.id}, 4)
            if profile != reference_profile:
                raise ComparisonError("comparison_profile_mismatch", {"variant": variant.id}, 4)
            if [clip.probe.frame_count for clip in clips] != reference_frame_counts:
                raise ComparisonError("comparison_frame_count_mismatch", {"variant": variant.id}, 4)
            if [clip.probe.audio_sha256 for clip in clips] != reference_audio_hashes:
                raise ComparisonError("comparison_audio_mismatch", {"variant": variant.id}, 4)

        prepared.append(
            PreparedVariant(
                record=ComparisonVariant(
                    id=variant.id,
                    label=variant.label,
                    preview_manifest=FileRef(
                        path=_relative(preview_path, manifest_path),
                        sha256=sha256_file(preview_path),
                    ),
                    preview_cache_key=preview.cache_key,
                    inputs=preview.inputs,
                    environment=preview.environment,
                    seed=preview.seed,
                    clips=clips,
                ),
                clip_paths=tuple(clip_paths),
            )
        )

    assert reference_manifest is not None and reference_profile is not None
    return PreparedComparison(
        request=request,
        request_ref=request_ref,
        source_sha256=reference_manifest.canonical_audio_sha256,
        original_source_sha256=reference_manifest.source_sha256,
        ranges=tuple(reference_manifest.ranges),
        profile=ComparisonProfile(
            video_codec=reference_profile[0],
            video_pixel_format=reference_profile[1],
            width=reference_profile[2],
            height=reference_profile[3],
            fps_num=reference_profile[4],
            fps_den=reference_profile[5],
            stream_compatibility_sha256=reference_profile[6],
            has_audio=reference_profile[7],
            range_count=len(reference_manifest.ranges),
        ),
        variants=tuple(prepared),
    )


def _cache_key(prepared: PreparedComparison, tools: dict[str, str]) -> str:
    variants = []
    for item in prepared.variants:
        variants.append(
            {
                "id": item.record.id,
                "label": item.record.label,
                "preview_manifest_sha256": item.record.preview_manifest.sha256,
                "preview_cache_key": item.record.preview_cache_key,
                "inputs": item.record.inputs,
                "environment": item.record.environment,
                "seed": item.record.seed,
                "clips": [
                    {
                        "range_index": clip.range_index,
                        "range": clip.range.model_dump(mode="json"),
                        "sha256": clip.file.sha256,
                        "probe": clip.probe.model_dump(mode="json"),
                    }
                    for clip in item.record.clips
                ],
            }
        )
    value = {
        "request_sha256": prepared.request_ref.sha256,
        "source_sha256": prepared.source_sha256,
        "original_source_sha256": prepared.original_source_sha256,
        "ranges": [item.model_dump(mode="json") for item in prepared.ranges],
        "profile": prepared.profile.model_dump(mode="json"),
        "variants": variants,
        "tools": tools,
        "comparison_adapter": sha256_file(Path(__file__)),
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _ordered_clip_paths(prepared: PreparedComparison) -> list[Path]:
    return [
        variant.clip_paths[range_index]
        for range_index in range(len(prepared.ranges))
        for variant in prepared.variants
    ]


def _build_review_reel(ffmpeg: str, job_dir: Path, prepared: PreparedComparison) -> Path:
    local_clips: list[Path] = []
    for index, source in enumerate(_ordered_clip_paths(prepared), 1):
        target = job_dir / f".reel-{index:04d}.mp4"
        try:
            os.link(source, target)
        except OSError:
            shutil.copyfile(source, target)
        local_clips.append(target)
    concat_path = job_dir / ".review-concat.txt"
    concat_path.write_text(
        "".join(f"file '{clip.name}'\n" for clip in local_clips), encoding="utf-8"
    )
    output = job_dir / "review-reel.mp4"
    try:
        _run(
            [
                ffmpeg,
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-c",
                "copy",
                str(output),
            ],
            cwd=job_dir,
            code="comparison_review_reel_failed",
        )
    finally:
        concat_path.unlink(missing_ok=True)
        for clip in local_clips:
            clip.unlink(missing_ok=True)
    return output


def _validate_review_reel(
    ffprobe: str, ffmpeg: str, path: Path, prepared: PreparedComparison
) -> None:
    probe = _probe_clip(ffprobe, ffmpeg, path)
    profile = prepared.profile
    actual_profile = (
        probe.video_codec,
        probe.video_pixel_format,
        probe.width,
        probe.height,
        probe.fps_num,
        probe.fps_den,
        probe.stream_compatibility_sha256,
        probe.has_audio,
    )
    expected_profile = (
        profile.video_codec,
        profile.video_pixel_format,
        profile.width,
        profile.height,
        profile.fps_num,
        profile.fps_den,
        profile.stream_compatibility_sha256,
        profile.has_audio,
    )
    expected_frames = sum(
        clip.probe.frame_count for variant in prepared.variants for clip in variant.record.clips
    )
    if actual_profile != expected_profile or probe.frame_count != expected_frames:
        raise ComparisonError(
            "comparison_review_reel_invalid",
            {
                "path": str(path),
                "expected_profile": expected_profile,
                "actual_profile": actual_profile,
                "expected_frames": expected_frames,
                "actual_frames": probe.frame_count,
            },
            5,
        )


FONT_5X7 = {
    " ": ("00000",) * 7,
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00001", "00001", "00001", "00001", "10001", "10001", "01110"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}


def _contact_frame_size(profile: ComparisonProfile) -> tuple[int, int]:
    if profile.width >= profile.height:
        return CONTACT_MAX_DIMENSION, max(
            1, round(CONTACT_MAX_DIMENSION * profile.height / profile.width)
        )
    return (
        max(1, round(CONTACT_MAX_DIMENSION * profile.width / profile.height)),
        CONTACT_MAX_DIMENSION,
    )


def _extract_contact_frame(
    ffmpeg: str, path: Path, frame_index: int, width: int, height: int
) -> bytes:
    command = [
        ffmpeg,
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(path),
        "-vf",
        (f"select=eq(n\\,{frame_index}),scale={width}:{height}:flags=lanczos,format=rgb24"),
        "-frames:v",
        "1",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    try:
        result = subprocess.run(command, capture_output=True, check=False)
    except OSError as exc:
        raise ComparisonError("comparison_contact_sheet_failed", str(exc), 3) from exc
    expected = width * height * 3
    if result.returncode != 0 or len(result.stdout) != expected:
        raise ComparisonError(
            "comparison_contact_sheet_failed",
            {
                "path": str(path),
                "frame_index": frame_index,
                "returncode": result.returncode,
                "stderr": result.stderr.decode(errors="replace"),
            },
            5,
        )
    return result.stdout


def _draw_label(image: bytearray, width: int, x: int, y: int, text: str) -> None:
    scale = 3
    cursor = x
    for character in text.upper():
        glyph = FONT_5X7.get(character, FONT_5X7[" "])
        for row, bits in enumerate(glyph):
            for column, enabled in enumerate(bits):
                if enabled == "0":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        pixel = ((y + row * scale + dy) * width + cursor + column * scale + dx) * 3
                        image[pixel : pixel + 3] = b"\xff\xff\xff"
        cursor += 6 * scale


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _write_rgb_png(path: Path, width: int, height: int, pixels: bytes) -> None:
    rows = b"".join(
        b"\x00" + pixels[row * width * 3 : (row + 1) * width * 3] for row in range(height)
    )
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(rows, level=9))
        + _png_chunk(b"IEND", b"")
    )


def _build_contact_sheet(ffmpeg: str, job_dir: Path, prepared: PreparedComparison) -> Path:
    columns = len(prepared.variants)
    rows = len(prepared.ranges)
    frame_width, frame_height = _contact_frame_size(prepared.profile)
    cell_height = CONTACT_LABEL_HEIGHT + frame_height
    width = columns * frame_width
    height = rows * cell_height
    if width > 16384 or height > 16384:
        raise ComparisonError(
            "comparison_contact_sheet_too_large", {"width": width, "height": height}, 4
        )
    pixels = bytearray(width * height * 3)
    for range_index in range(rows):
        for variant_index, variant in enumerate(prepared.variants):
            clip = variant.record.clips[range_index]
            frame = _extract_contact_frame(
                ffmpeg,
                variant.clip_paths[range_index],
                clip.probe.frame_count // 2,
                frame_width,
                frame_height,
            )
            cell_x = variant_index * frame_width
            cell_y = range_index * cell_height
            for frame_row in range(frame_height):
                source_start = frame_row * frame_width * 3
                target_start = ((cell_y + CONTACT_LABEL_HEIGHT + frame_row) * width + cell_x) * 3
                pixels[target_start : target_start + frame_width * 3] = frame[
                    source_start : source_start + frame_width * 3
                ]
            label = f"R{range_index + 1:02d} {variant.record.id}"[:25]
            _draw_label(pixels, width, cell_x + 9, cell_y + 5, label)
    output = job_dir / "contact-sheet.png"
    _write_rgb_png(output, width, height, pixels)
    return output


def _write_manifest(path: Path, manifest: ComparisonManifest) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=".comparison-manifest-", suffix=".json"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(manifest.model_dump_json(indent=2))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _validated_cache(
    output_dir: Path,
    prepared: PreparedComparison,
    cache_key: str,
    tools: dict[str, str],
) -> ComparisonManifest | None:
    manifest_path = output_dir / "comparison.json"
    try:
        manifest = ComparisonManifest.model_validate(read_document(manifest_path))
        if (
            manifest.cache_key != cache_key
            or manifest.request != prepared.request_ref
            or manifest.source_sha256 != prepared.source_sha256
            or manifest.ranges != list(prepared.ranges)
            or manifest.profile != prepared.profile
            or manifest.variants != [variant.record for variant in prepared.variants]
            or manifest.tools != tools
            or manifest.artifacts.review_reel.path != "review-reel.mp4"
            or manifest.artifacts.contact_sheet.path != "contact-sheet.png"
        ):
            return None
        for field, reference in (
            ("review_reel", manifest.artifacts.review_reel),
            ("contact_sheet", manifest.artifacts.contact_sheet),
        ):
            path = resolve_record_path(manifest_path, reference.path)
            if not path.is_relative_to(output_dir):
                return None
            _require_file_hash(path, reference.sha256, field=field)
        return manifest
    except (OSError, UnicodeError, ValueError, ValidationError, ComparisonError):
        return None


def compare_previews(request_path: Path, output_dir: Path) -> ComparisonResult:
    request_path = request_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    manifest_path = output_dir / "comparison.json"
    ffmpeg = _dependency("ffmpeg")
    ffprobe = _dependency("ffprobe")
    prepared = _prepare_comparison(request_path, manifest_path, ffprobe, ffmpeg)
    tools = {
        "mvt": __version__,
        "python": platform.python_version(),
        "ffmpeg": _tool_version(ffmpeg),
        "ffprobe": _tool_version(ffprobe),
    }
    cache_key = _cache_key(prepared, tools)
    if output_dir.exists():
        cached = _validated_cache(output_dir, prepared, cache_key, tools)
        if cached is not None:
            return ComparisonResult(cached, manifest_path, cached=True)
        raise ComparisonError(
            "comparison_output_conflict",
            {"path": str(output_dir), "message": "existing comparison is incomplete or stale"},
            4,
        )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    job_dir = Path(tempfile.mkdtemp(dir=output_dir.parent, prefix=f".{output_dir.name}-"))
    try:
        reel = _build_review_reel(ffmpeg, job_dir, prepared)
        _validate_review_reel(ffprobe, ffmpeg, reel, prepared)
        contact_sheet = _build_contact_sheet(ffmpeg, job_dir, prepared)
        job_manifest_path = job_dir / "comparison.json"
        manifest = ComparisonManifest(
            schema_version="0.1",
            cache_key=cache_key,
            request=prepared.request_ref,
            source_sha256=prepared.source_sha256,
            ranges=list(prepared.ranges),
            profile=prepared.profile,
            variants=[variant.record for variant in prepared.variants],
            tools=tools,
            artifacts=ComparisonArtifacts(
                review_reel=FileRef(path=reel.name, sha256=sha256_file(reel)),
                contact_sheet=FileRef(path=contact_sheet.name, sha256=sha256_file(contact_sheet)),
            ),
        )
        _write_manifest(job_manifest_path, manifest)
        os.replace(job_dir, output_dir)
        return ComparisonResult(manifest, manifest_path, cached=False)
    except ComparisonError:
        raise
    except (OSError, ValueError, ValidationError) as exc:
        raise ComparisonError("comparison_failed", _error_details(exc), 5) from exc
    finally:
        if job_dir.exists():
            shutil.rmtree(job_dir)
