"""Strict LRC/SRT import into canonical sample-clock lyric cues."""

from __future__ import annotations

import os
import re
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import ValidationError

from . import __version__
from .contracts import Cue, Lyrics, Provenance
from .documents import read_document
from .project import ProjectPreflightError, preflight_source, sha256_file

SAMPLE_RATE = 48_000
LRC_TIMESTAMP = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
LRC_METADATA = re.compile(r"^\s*\[[A-Za-z][A-Za-z0-9_-]*:.*\]\s*$")
LRC_OFFSET = re.compile(r"^\s*\[offset:([+-]?\d+)\]\s*$", re.IGNORECASE)
STAGE_HEADING = re.compile(r"^\s*\[[^\]\r\n]+\]\s*$")
SRT_TIMING = re.compile(
    r"^(\d{2,}):(\d{2}):(\d{2})[,.](\d{3})\s+-->\s+"
    r"(\d{2,}):(\d{2}):(\d{2})[,.](\d{3})$"
)


class LyricsError(Exception):
    """A stable lyric import failure for machine-readable CLI output."""

    def __init__(self, code: str, details: object, exit_code: int = 2):
        super().__init__(str(details))
        self.code = code
        self.details = details
        self.exit_code = exit_code


def _checked_text(value: str, location: dict[str, object]) -> str:
    if len(value) > 240:
        raise LyricsError(
            "lyric_text_too_long", {**location, "characters": len(value), "limit": 240}
        )
    return value


def _fraction_samples(digits: str | None) -> int:
    if digits is None:
        return 0
    try:
        fraction = Decimal(digits) / (Decimal(10) ** len(digits))
    except InvalidOperation as exc:
        raise LyricsError("invalid_lyric_timestamp", {"fraction": digits}) from exc
    return int(fraction * SAMPLE_RATE)


def _lrc_start(minutes: str, seconds: str, fraction: str | None) -> int:
    second = int(seconds)
    if second >= 60:
        raise LyricsError("invalid_lyric_timestamp", {"seconds": seconds})
    return (int(minutes) * 60 + second) * SAMPLE_RATE + _fraction_samples(fraction)


def _parse_lrc(text: str, duration_samples: int) -> tuple[list[Cue], dict[str, object]]:
    starts: list[tuple[int, str]] = []
    offset_samples = 0
    skipped_headings = 0
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip("\ufeff")
        offset = LRC_OFFSET.match(line)
        if offset:
            offset_samples = int(offset.group(1)) * 48
            continue
        matches = list(LRC_TIMESTAMP.finditer(line))
        if not matches:
            if line.strip() and not LRC_METADATA.match(line):
                raise LyricsError("unsupported_lyric_line", {"line": line_number, "text": line})
            continue
        lyric = LRC_TIMESTAMP.sub("", line).strip()
        if not lyric:
            continue
        if STAGE_HEADING.match(lyric):
            skipped_headings += 1
            continue
        lyric = _checked_text(lyric, {"line": line_number})
        for match in matches:
            starts.append((_lrc_start(*match.groups()) + offset_samples, lyric))
    if not starts:
        raise LyricsError("no_lyric_cues", {"format": "lrc"})
    if any(start < 0 or start >= duration_samples for start, _ in starts):
        raise LyricsError("lyrics_out_of_bounds", {"duration_samples": duration_samples})
    if any(first[0] >= second[0] for first, second in zip(starts, starts[1:], strict=False)):
        raise LyricsError("non_monotonic_lyrics", "LRC timestamps must increase in source order")
    cues = [
        Cue(
            start_sample=start,
            end_sample=starts[index + 1][0] if index + 1 < len(starts) else duration_samples,
            text=lyric,
        )
        for index, (start, lyric) in enumerate(starts)
    ]
    return cues, {
        "format": "lrc",
        "end_time_policy": "next_start_or_song_end",
        "offset_samples": offset_samples,
        "skipped_stage_headings": skipped_headings,
    }


def _srt_sample(groups: tuple[str, str, str, str]) -> int:
    hours, minutes, seconds, milliseconds = map(int, groups)
    if minutes >= 60 or seconds >= 60:
        raise LyricsError("invalid_lyric_timestamp", {"timestamp": ":".join(groups)})
    return ((hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds) * 48


def _parse_srt(text: str, duration_samples: int) -> tuple[list[Cue], dict[str, object]]:
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip("\ufeff\n "))
    cues: list[Cue] = []
    skipped_headings = 0
    previous_end: int | None = None
    for block_number, block in enumerate(blocks, 1):
        lines = block.splitlines()
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        if len(lines) < 2:
            raise LyricsError("invalid_srt_block", {"block": block_number})
        timing = SRT_TIMING.fullmatch(lines[0].strip())
        if timing is None:
            raise LyricsError("invalid_lyric_timestamp", {"block": block_number, "value": lines[0]})
        lyric = "\n".join(line.strip() for line in lines[1:]).strip()
        if not lyric:
            raise LyricsError("empty_lyric_cue", {"block": block_number})
        start = _srt_sample(timing.groups()[:4])
        end = _srt_sample(timing.groups()[4:])
        if end <= start:
            raise LyricsError("invalid_lyric_range", {"block": block_number})
        if end > duration_samples:
            raise LyricsError("lyrics_out_of_bounds", {"block": block_number})
        if previous_end is not None and previous_end > start:
            raise LyricsError(
                "overlapping_lyrics", {"block": block_number, "previous_end_sample": previous_end}
            )
        previous_end = end
        if STAGE_HEADING.match(lyric):
            skipped_headings += 1
            continue
        lyric = _checked_text(lyric, {"block": block_number})
        cues.append(Cue(start_sample=start, end_sample=end, text=lyric))
    if not cues:
        raise LyricsError("no_lyric_cues", {"format": "srt"})
    return cues, {
        "format": "srt",
        "end_time_policy": "explicit",
        "skipped_stage_headings": skipped_headings,
    }


def _write(path: Path, lyrics: Lyrics) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(lyrics.model_dump_json(indent=2))
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def import_lyrics(
    source_path: Path,
    project: Path,
    language: str,
    output_path: Path | None = None,
) -> tuple[Lyrics, Path, bool]:
    try:
        source = preflight_source(project)
    except ProjectPreflightError as exc:
        raise LyricsError(exc.code, exc.details, 4) from exc
    if "://" in str(source_path):
        raise LyricsError("remote_lyric_source_forbidden", {"path": str(source_path)})
    source_path = source_path.expanduser().resolve()
    if not source_path.is_file():
        raise LyricsError("missing_lyric_source", {"path": str(source_path)}, 4)
    if not language.strip():
        raise LyricsError("invalid_lyric_language", {"language": language})
    try:
        text = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise LyricsError("invalid_lyric_source", str(exc), 4) from exc
    format_name = source_path.suffix.lower().lstrip(".")
    parser = {"lrc": _parse_lrc, "srt": _parse_srt}.get(format_name)
    if parser is None:
        raise LyricsError("unsupported_lyric_format", {"format": format_name})
    cues, parameters = parser(text, source.record.canonical.duration_samples)
    output_path = (output_path or source.project / "lyrics.json").resolve()
    lyrics = Lyrics(
        schema_version="0.1",
        language=language.strip(),
        text_source=os.path.relpath(source_path, output_path.parent),
        text_source_sha256=sha256_file(source_path),
        audio_sha256=source.record.canonical.sha256,
        origin="imported",
        provenance=Provenance(
            tool="mvt lyrics import",
            version=__version__,
            parameters={**parameters, "sample_rate": SAMPLE_RATE},
        ),
        cues=cues,
    )
    if output_path.exists():
        try:
            existing = Lyrics.model_validate(read_document(output_path))
        except (OSError, UnicodeError, ValueError, ValidationError) as exc:
            raise LyricsError(
                "lyrics_output_conflict",
                {"path": str(output_path), "message": "existing lyrics are not safely replaceable"},
                4,
            ) from exc
        if existing == lyrics:
            return existing, output_path, True
        raise LyricsError(
            "lyrics_output_conflict",
            {"path": str(output_path), "message": "preserve edited cues or choose another output"},
            4,
        )
    _write(output_path, lyrics)
    return lyrics, output_path, False
