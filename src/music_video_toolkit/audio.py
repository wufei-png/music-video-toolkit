"""Canonical audio decoding through explicit FFmpeg and ffprobe processes."""

import json
import os
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from .contracts import CanonicalAudio, FileRef, Provenance, SourceRecord
from .project import (
    CANONICAL_AUDIO_PATH,
    SOURCE_RECORD_PATH,
    ProjectPreflightError,
    preflight_source,
    sha256_file,
)

SAMPLE_RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 3
SAMPLE_FORMAT = "s24le"
CODEC = "pcm_s24le"
AUDIO_STREAM = "0:a:0"


class DecodeError(Exception):
    """A stable decode failure suitable for machine-readable CLI output."""

    def __init__(self, code: str, details: object, exit_code: int = 2):
        super().__init__(str(details))
        self.code = code
        self.details = details
        self.exit_code = exit_code


@dataclass(frozen=True)
class DecodeResult:
    project: Path
    record_path: Path
    canonical_path: Path
    record: SourceRecord
    cached: bool

    def report(self) -> dict[str, object]:
        canonical = self.record.canonical
        return {
            "ok": True,
            "cached": self.cached,
            "project": str(self.project),
            "source_record": str(self.record_path),
            "canonical": str(self.canonical_path),
            "source_sha256": self.record.original.sha256,
            "canonical_sha256": canonical.sha256,
            "sample_rate": canonical.sample_rate,
            "channels": canonical.channels,
            "sample_format": canonical.sample_format,
            "codec": canonical.codec,
            "duration_samples": canonical.duration_samples,
        }


def _dependency(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise DecodeError(
            "missing_dependency",
            {"tool": name, "message": f"Install {name} and ensure it is on PATH"},
            3,
        )
    return path


def _run(command: list[str], *, code: str) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise DecodeError(code, str(exc), 3) from exc
    if result.returncode != 0:
        raise DecodeError(
            code,
            {"returncode": result.returncode, "stderr": result.stderr.strip()},
            5,
        )
    return result


def _ffmpeg_version(ffmpeg: str) -> str:
    lines = _run([ffmpeg, "-version"], code="ffmpeg_unavailable").stdout.splitlines()
    if not lines:
        raise DecodeError("ffmpeg_unavailable", "ffmpeg returned no version information", 3)
    first_line = lines[0]
    parts = first_line.split()
    return parts[2] if len(parts) >= 3 and parts[:2] == ["ffmpeg", "version"] else first_line


def _probe_canonical(ffprobe: str, path: Path) -> int:
    result = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        code="probe_failed",
    )
    try:
        streams = json.loads(result.stdout)["streams"]
        stream = streams[0]
        observed = {
            "codec": stream["codec_name"],
            "sample_rate": int(stream["sample_rate"]),
            "channels": int(stream["channels"]),
        }
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DecodeError("probe_failed", "ffprobe returned incomplete audio metadata", 5) from exc
    expected = {"codec": CODEC, "sample_rate": SAMPLE_RATE, "channels": CHANNELS}
    if observed != expected:
        raise DecodeError(
            "unexpected_canonical_format", {"expected": expected, "actual": observed}, 5
        )

    try:
        with wave.open(str(path), "rb") as wav:
            wav_observed = {
                "sample_rate": wav.getframerate(),
                "channels": wav.getnchannels(),
                "sample_width": wav.getsampwidth(),
            }
            duration_samples = wav.getnframes()
    except (OSError, EOFError, wave.Error) as exc:
        raise DecodeError("probe_failed", f"invalid canonical WAV: {exc}", 5) from exc
    wav_expected = {
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "sample_width": SAMPLE_WIDTH,
    }
    if wav_observed != wav_expected or duration_samples <= 0:
        raise DecodeError(
            "unexpected_canonical_format",
            {
                "expected": wav_expected,
                "actual": wav_observed,
                "duration_samples": duration_samples,
            },
            5,
        )
    return duration_samples


def _existing_result(project: Path, input_hash: str) -> DecodeResult | None:
    record_path = project / SOURCE_RECORD_PATH
    canonical_path = project / CANONICAL_AUDIO_PATH
    if not record_path.exists() and not canonical_path.exists():
        return None
    if not record_path.is_file() or not canonical_path.is_file():
        raise DecodeError(
            "project_conflict",
            {
                "message": "Project has an incomplete canonical source; refusing to overwrite",
                "source_record": str(record_path),
                "canonical": str(canonical_path),
            },
            4,
        )
    try:
        existing = preflight_source(project)
    except ProjectPreflightError as exc:
        raise DecodeError(
            "project_conflict",
            {
                "message": "Existing canonical source failed preflight",
                "cause": exc.code,
                "details": exc.details,
            },
            4,
        ) from exc
    if existing.record.original.sha256 != input_hash:
        raise DecodeError(
            "project_conflict",
            {
                "message": "Project already contains a different source input",
                "existing_source_sha256": existing.record.original.sha256,
                "requested_source_sha256": input_hash,
            },
            4,
        )
    return DecodeResult(
        project=project,
        record_path=existing.record_path,
        canonical_path=existing.canonical_path,
        record=existing.record,
        cached=True,
    )


def decode_audio(input_path: Path, project: Path) -> DecodeResult:
    input_path = input_path.resolve()
    project = project.resolve()
    if not input_path.is_file():
        raise DecodeError("input_missing", {"path": str(input_path)}, 2)
    if project.exists() and not project.is_dir():
        raise DecodeError(
            "invalid_project", {"path": str(project), "message": "Not a directory"}, 2
        )

    try:
        input_hash = sha256_file(input_path)
    except OSError as exc:
        raise DecodeError(
            "input_unreadable", {"path": str(input_path), "message": str(exc)}, 2
        ) from exc
    existing = _existing_result(project, input_hash)
    if existing is not None:
        return existing

    ffmpeg = _dependency("ffmpeg")
    ffprobe = _dependency("ffprobe")
    ffmpeg_version = _ffmpeg_version(ffmpeg)
    source_dir = project / "source"
    try:
        source_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DecodeError(
            "project_write_failed", {"path": str(source_dir), "message": str(exc)}, 5
        ) from exc
    audio_temp: Path | None = None
    record_temp: Path | None = None
    canonical_path = project / CANONICAL_AUDIO_PATH
    record_path = project / SOURCE_RECORD_PATH
    canonical_installed = False
    record_installed = False
    completed = False
    try:
        descriptor, audio_temp_name = tempfile.mkstemp(
            dir=source_dir, prefix=".canonical-", suffix=".wav"
        )
        os.close(descriptor)
        audio_temp = Path(audio_temp_name)
        _run(
            [
                ffmpeg,
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-i",
                str(input_path),
                "-map",
                AUDIO_STREAM,
                "-map_metadata",
                "-1",
                "-vn",
                "-ac",
                str(CHANNELS),
                "-ar",
                str(SAMPLE_RATE),
                "-c:a",
                CODEC,
                "-f",
                "wav",
                str(audio_temp),
            ],
            code="decode_failed",
        )
        duration_samples = _probe_canonical(ffprobe, audio_temp)
        record = SourceRecord(
            schema_version="0.1",
            original=FileRef(path=str(input_path), sha256=input_hash),
            canonical=CanonicalAudio(
                path="canonical.wav",
                sha256=sha256_file(audio_temp),
                sample_rate=SAMPLE_RATE,
                channels=CHANNELS,
                sample_format=SAMPLE_FORMAT,
                codec=CODEC,
                duration_samples=duration_samples,
            ),
            decoder=Provenance(
                tool="ffmpeg",
                version=ffmpeg_version,
                parameters={
                    "audio_stream": AUDIO_STREAM,
                    "sample_rate": SAMPLE_RATE,
                    "channels": CHANNELS,
                    "sample_format": SAMPLE_FORMAT,
                    "codec": CODEC,
                },
            ),
        )
        descriptor, record_temp_name = tempfile.mkstemp(
            dir=source_dir, prefix=".source-", suffix=".json"
        )
        record_temp = Path(record_temp_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(record.model_dump_json(indent=2))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(audio_temp, canonical_path)
        audio_temp = None
        canonical_installed = True
        os.replace(record_temp, record_path)
        record_temp = None
        record_installed = True
        result = preflight_source(project, require_original=True)
        completed = True
    except DecodeError:
        raise
    except (OSError, ProjectPreflightError) as exc:
        details = (
            {"cause": exc.code, "details": exc.details}
            if isinstance(exc, ProjectPreflightError)
            else str(exc)
        )
        raise DecodeError("project_write_failed", details, 5) from exc
    finally:
        for temporary in (audio_temp, record_temp):
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        if not completed and record_installed:
            record_path.unlink(missing_ok=True)
        if not completed and canonical_installed:
            canonical_path.unlink(missing_ok=True)

    return DecodeResult(
        project=project,
        record_path=result.record_path,
        canonical_path=result.canonical_path,
        record=result.record,
        cached=False,
    )
