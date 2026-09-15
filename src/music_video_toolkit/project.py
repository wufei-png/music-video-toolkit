"""Project path resolution and source artifact preflight."""

import hashlib
import wave
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .contracts import SourceRecord
from .documents import read_document

SOURCE_RECORD_PATH = Path("source/source.json")
CANONICAL_AUDIO_PATH = Path("source/canonical.wav")


class ProjectPreflightError(Exception):
    """A stable project preflight failure for CLI adapters."""

    def __init__(self, code: str, details: object):
        super().__init__(str(details))
        self.code = code
        self.details = details


@dataclass(frozen=True)
class SourcePreflight:
    project: Path
    record_path: Path
    original_path: Path
    canonical_path: Path
    record: SourceRecord


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_record_path(record_path: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = record_path.parent / path
    return path.resolve()


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise ProjectPreflightError("missing_project_file", {"field": label, "path": str(path)})


def _require_hash(path: Path, expected: str, label: str) -> None:
    try:
        actual = sha256_file(path)
    except OSError as exc:
        raise ProjectPreflightError(
            "project_file_unreadable", {"field": label, "path": str(path), "message": str(exc)}
        ) from exc
    if actual != expected:
        raise ProjectPreflightError(
            "project_hash_mismatch",
            {"field": label, "path": str(path), "expected": expected, "actual": actual},
        )


def _require_canonical_audio(path: Path, record: SourceRecord) -> None:
    try:
        with wave.open(str(path), "rb") as wav:
            actual = {
                "sample_rate": wav.getframerate(),
                "channels": wav.getnchannels(),
                "sample_width": wav.getsampwidth(),
                "duration_samples": wav.getnframes(),
            }
    except (OSError, EOFError, wave.Error) as exc:
        raise ProjectPreflightError(
            "invalid_canonical_audio", {"path": str(path), "message": str(exc)}
        ) from exc
    expected = {
        "sample_rate": record.canonical.sample_rate,
        "channels": record.canonical.channels,
        "sample_width": 3,
        "duration_samples": record.canonical.duration_samples,
    }
    if actual != expected:
        raise ProjectPreflightError(
            "canonical_audio_mismatch",
            {"path": str(path), "expected": expected, "actual": actual},
        )


def preflight_source(project: Path, *, require_original: bool = False) -> SourcePreflight:
    project = project.resolve()
    record_path = project / SOURCE_RECORD_PATH
    _require_file(record_path, "source_record")
    try:
        record = SourceRecord.model_validate(read_document(record_path))
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        details = (
            exc.errors(include_url=False, include_context=False, include_input=False)
            if isinstance(exc, ValidationError)
            else str(exc)
        )
        raise ProjectPreflightError("invalid_source_record", details) from exc

    canonical_path = resolve_record_path(record_path, record.canonical.path)
    expected_canonical = (project / CANONICAL_AUDIO_PATH).resolve()
    if canonical_path != expected_canonical:
        raise ProjectPreflightError(
            "invalid_project_reference",
            {
                "field": "canonical.path",
                "expected": str(expected_canonical),
                "actual": str(canonical_path),
            },
        )
    _require_file(canonical_path, "canonical.path")
    _require_hash(canonical_path, record.canonical.sha256, "canonical.sha256")
    _require_canonical_audio(canonical_path, record)

    original_path = resolve_record_path(record_path, record.original.path)
    if require_original:
        _require_file(original_path, "original.path")
        _require_hash(original_path, record.original.sha256, "original.sha256")

    return SourcePreflight(
        project=project,
        record_path=record_path,
        original_path=original_path,
        canonical_path=canonical_path,
        record=record,
    )
