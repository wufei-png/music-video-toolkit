"""Known-text lyric alignment using isolated WhisperX timing evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from . import __version__
from .contracts import (
    AlignmentEvaluation,
    AlignmentLine,
    AlignmentReport,
    Cue,
    FileRef,
    Lyrics,
    Provenance,
    StemManifest,
)
from .documents import read_document
from .project import ProjectPreflightError, preflight_source, resolve_record_path, sha256_file

SAMPLE_RATE = 48_000
MIN_COVERAGE = 0.45
MIN_MATCHED_CHARACTERS = 2
MIN_CUE_SAMPLES = 14_400
MAX_TEXT_CHARACTERS = 20_000
MAX_EVIDENCE_CHARACTERS = 50_000
STAGE_HEADING = re.compile(r"^\s*(?:#{1,6}\s+.+|\[[^\]\r\n]+\])\s*$")


class AlignmentError(Exception):
    """A stable automatic-alignment failure for machine-readable CLI output."""

    def __init__(self, code: str, details: object, exit_code: int = 2):
        super().__init__(str(details))
        self.code = code
        self.details = details
        self.exit_code = exit_code


@dataclass(frozen=True)
class KnownLine:
    source_line: int
    text: str
    normalized: str


@dataclass(frozen=True)
class TimedCharacter:
    value: str
    start_sample: int
    end_sample: int


@dataclass(frozen=True)
class AlignmentResult:
    lyrics: Lyrics
    lyrics_path: Path
    report: AlignmentReport
    report_path: Path
    cached: bool

    def summary(self) -> dict[str, object]:
        return {
            "ok": True,
            "cached": self.cached,
            "output": str(self.lyrics_path),
            "report": str(self.report_path),
            "language": self.lyrics.language,
            "cues": len(self.lyrics.cues),
            "unmatched": sum(line.status == "unmatched" for line in self.report.lines),
            "evaluation": (
                self.report.evaluation.model_dump(mode="json") if self.report.evaluation else None
            ),
        }


@dataclass(frozen=True)
class EditedLyricsResult:
    lyrics: Lyrics
    path: Path
    cached: bool

    def summary(self) -> dict[str, object]:
        return {
            "ok": True,
            "cached": self.cached,
            "output": str(self.path),
            "language": self.lyrics.language,
            "cues": len(self.lyrics.cues),
            "origin": self.lyrics.origin,
        }


def _normalize(text: str) -> str:
    return "".join(
        character.casefold()
        for character in unicodedata.normalize("NFKC", text)
        if character.isalnum()
    )


def _read_known_lines(path: Path) -> list[KnownLine]:
    if path.suffix.lower() not in {".md", ".txt"}:
        raise AlignmentError("unsupported_alignment_text_format", {"format": path.suffix.lower()})
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AlignmentError("invalid_lyric_source", str(exc), 4) from exc
    lines: list[KnownLine] = []
    for number, raw in enumerate(text.splitlines(), 1):
        value = raw.strip().strip("\ufeff")
        if not value or STAGE_HEADING.match(value):
            continue
        if len(value) > 240:
            raise AlignmentError(
                "lyric_text_too_long", {"line": number, "characters": len(value), "limit": 240}
            )
        normalized = _normalize(value)
        if normalized:
            lines.append(KnownLine(number, value, normalized))
    if not lines:
        raise AlignmentError("no_lyric_lines", {"path": str(path)})
    character_count = sum(len(line.normalized) for line in lines)
    if character_count > MAX_TEXT_CHARACTERS:
        raise AlignmentError(
            "alignment_text_too_large",
            {"normalized_characters": character_count, "limit": MAX_TEXT_CHARACTERS},
        )
    return lines


def _json_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _atomic_write(path: Path, model: Lyrics | AlignmentReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(model.model_dump_json(indent=2))
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _select_audio(project: Path, canonical_path: Path, source_hash: str) -> tuple[Path, str, str]:
    manifest_path = project / "stems/stems.json"
    if not manifest_path.exists():
        return canonical_path, source_hash, "canonical"
    try:
        manifest = StemManifest.model_validate(read_document(manifest_path))
        if manifest.source.sha256 != source_hash:
            raise ValueError("stem source hash differs from canonical audio")
        vocals = manifest.stems["vocals"]
        vocals_path = resolve_record_path(manifest_path, vocals.path)
        if vocals_path != (project / "stems/vocals.wav").resolve():
            raise ValueError("vocals stem path is outside the fixed project location")
        if not vocals_path.is_file() or sha256_file(vocals_path) != vocals.sha256:
            raise ValueError("vocals stem is missing or has a different hash")
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        raise AlignmentError("invalid_vocals_stem", str(exc), 4) from exc
    return vocals_path, vocals.sha256, "vocals"


def _runtime() -> tuple[list[str], Path, str]:
    runner = os.environ.get("MVT_ALIGNMENT_RUNNER")
    if runner:
        path = Path(runner).expanduser().resolve()
        if not path.is_file():
            raise AlignmentError("missing_alignment_runtime", {"path": str(path)}, 3)
        return [sys.executable, str(path)], path, sha256_file(path)
    configured = os.environ.get("MVT_ALIGNMENT_PROJECT")
    project = (
        Path(configured).expanduser()
        if configured
        else Path(__file__).resolve().parents[2] / "environments/alignment"
    ).resolve()
    runner_path = project / "align_audio.py"
    lock_path = project / "uv.lock"
    missing = [
        str(path)
        for path in (runner_path, project / "pyproject.toml", lock_path)
        if not path.is_file()
    ]
    if missing:
        raise AlignmentError(
            "missing_alignment_runtime",
            {"path": str(project), "missing": missing, "message": "install the locked S07 runtime"},
            3,
        )
    uv = shutil.which("uv")
    if uv is None:
        raise AlignmentError("missing_dependency", {"tool": "uv"}, 3)
    return (
        [uv, "run", "--project", str(project), "--locked", "python", str(runner_path)],
        runner_path,
        sha256_file(lock_path),
    )


def _run_runtime(
    command: list[str], audio: Path, output: Path, language: str, model: str, model_dir: Path
) -> dict[str, object]:
    full = [
        *command,
        "--audio",
        str(audio),
        "--output",
        str(output),
        "--language",
        language,
        "--model",
        model,
        "--model-dir",
        str(model_dir),
        "--threads",
        "4",
    ]
    try:
        result = subprocess.run(full, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise AlignmentError("alignment_runtime_failed", str(exc), 3) from exc
    if result.returncode != 0:
        raise AlignmentError(
            "alignment_runtime_failed",
            {
                "returncode": result.returncode,
                "stdout_tail": result.stdout[-4000:],
                "stderr_tail": result.stderr[-4000:],
            },
            5,
        )
    try:
        document = read_document(output)
    except (OSError, UnicodeError, ValueError) as exc:
        raise AlignmentError("invalid_alignment_runtime_output", str(exc), 5) from exc
    if not isinstance(document.get("segments"), list) or not isinstance(
        document.get("runtime"), dict
    ):
        raise AlignmentError("invalid_alignment_runtime_output", "missing segments or runtime", 5)
    return document


def _timed_characters(document: dict[str, object], duration: int) -> list[TimedCharacter]:
    characters: list[TimedCharacter] = []
    segments = document["segments"]
    assert isinstance(segments, list)
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        words = segment.get("words")
        units = words if isinstance(words, list) and words else [segment]
        for unit in units:
            if not isinstance(unit, dict):
                continue
            text = unit.get("word", unit.get("text"))
            start = unit.get("start")
            end = unit.get("end")
            if (
                not isinstance(text, str)
                or not isinstance(start, (int, float))
                or not isinstance(end, (int, float))
                or isinstance(start, bool)
                or isinstance(end, bool)
            ):
                continue
            normalized = _normalize(text)
            if not normalized or end <= start or end <= 0 or start * SAMPLE_RATE >= duration:
                continue
            start_sample = max(0, min(duration - 1, round(float(start) * SAMPLE_RATE)))
            end_sample = max(start_sample + 1, min(duration, round(float(end) * SAMPLE_RATE)))
            span = end_sample - start_sample
            for index, value in enumerate(normalized):
                char_start = start_sample + span * index // len(normalized)
                char_end = start_sample + span * (index + 1) // len(normalized)
                characters.append(TimedCharacter(value, char_start, max(char_start + 1, char_end)))
                if len(characters) > MAX_EVIDENCE_CHARACTERS:
                    raise AlignmentError(
                        "alignment_evidence_too_large",
                        {"characters": len(characters), "limit": MAX_EVIDENCE_CHARACTERS},
                        5,
                    )
    characters.sort(key=lambda character: (character.start_sample, character.end_sample))
    return characters


def _matching_pairs(known: str, observed: str) -> list[tuple[int, int]]:
    rows, columns = len(known) + 1, len(observed) + 1
    directions = bytearray(rows * columns)
    previous = list(range(columns))
    for column in range(1, columns):
        directions[column] = 2
    for row in range(1, rows):
        current = [row] + [0] * (columns - 1)
        directions[row * columns] = 1
        for column in range(1, columns):
            diagonal = previous[column - 1] + (known[row - 1] != observed[column - 1])
            delete = previous[column] + 1
            insert = current[column - 1] + 1
            best = min(diagonal, delete, insert)
            current[column] = best
            directions[row * columns + column] = (
                0 if diagonal == best else 1 if delete == best else 2
            )
        previous = current
    row, column = len(known), len(observed)
    pairs: list[tuple[int, int]] = []
    while row or column:
        direction = directions[row * columns + column]
        if row and column and direction == 0:
            if known[row - 1] == observed[column - 1]:
                pairs.append((row - 1, column - 1))
            row -= 1
            column -= 1
        elif row and (column == 0 or direction == 1):
            row -= 1
        else:
            column -= 1
    pairs.reverse()
    return pairs


def _map_lines(
    lines: list[KnownLine], observed: list[TimedCharacter], duration: int
) -> list[AlignmentLine]:
    known = "".join(line.normalized for line in lines)
    observed_text = "".join(character.value for character in observed)
    pairs = _matching_pairs(known, observed_text) if observed_text else []
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for line in lines:
        offsets.append((cursor, cursor + len(line.normalized)))
        cursor += len(line.normalized)
    mapped: list[AlignmentLine] = []
    pair_index = 0
    for line, (begin, end) in zip(lines, offsets, strict=True):
        while pair_index < len(pairs) and pairs[pair_index][0] < begin:
            pair_index += 1
        selected: list[int] = []
        scan = pair_index
        while scan < len(pairs) and pairs[scan][0] < end:
            selected.append(pairs[scan][1])
            scan += 1
        pair_index = scan
        coverage = len(selected) / len(line.normalized)
        if len(selected) < MIN_MATCHED_CHARACTERS or coverage < MIN_COVERAGE:
            mapped.append(
                AlignmentLine(
                    source_line=line.source_line,
                    text=line.text,
                    normalized_characters=len(line.normalized),
                    status="unmatched",
                    coverage=coverage,
                    reason="insufficient_exact_character_matches",
                )
            )
            continue
        start = observed[selected[0]].start_sample
        raw_end = observed[selected[-1]].end_sample
        mapped.append(
            AlignmentLine(
                source_line=line.source_line,
                text=line.text,
                normalized_characters=len(line.normalized),
                status="matched",
                coverage=coverage,
                start_sample=start,
                end_sample=min(duration, max(raw_end, start + MIN_CUE_SAMPLES)),
            )
        )
    for index, line in enumerate(mapped):
        if line.status != "matched":
            continue
        next_start = next(
            (
                candidate.start_sample
                for candidate in mapped[index + 1 :]
                if candidate.status == "matched"
            ),
            duration,
        )
        assert (
            line.start_sample is not None and line.end_sample is not None and next_start is not None
        )
        if next_start <= line.start_sample:
            mapped[index] = line.model_copy(
                update={
                    "status": "unmatched",
                    "start_sample": None,
                    "end_sample": None,
                    "reason": "non_increasing_mapped_time",
                }
            )
        elif line.end_sample > next_start:
            mapped[index] = line.model_copy(update={"end_sample": next_start})
    return mapped


def _evaluation(
    reference_path: Path | None, audio_hash: str, lines: list[AlignmentLine]
) -> AlignmentEvaluation | None:
    if reference_path is None:
        return None
    try:
        document = read_document(reference_path)
        if document.get("schema_version") != "0.1" or document.get("audio_sha256") != audio_hash:
            raise ValueError("reference schema or audio hash mismatch")
        points = document.get("points")
        if not isinstance(points, list) or len(points) < 12:
            raise ValueError("at least 12 reference points are required")
        predicted = {
            line.source_line: line.start_sample for line in lines if line.status == "matched"
        }
        errors = []
        unmatched_references = 0
        seen = set()
        for point in points:
            if not isinstance(point, dict):
                raise ValueError("reference point must be an object")
            source_line, start = point.get("source_line"), point.get("start_sample")
            if (
                not isinstance(source_line, int)
                or isinstance(source_line, bool)
                or source_line in seen
            ):
                raise ValueError("reference source lines must be unique integers")
            if not isinstance(start, int) or isinstance(start, bool) or start < 0:
                raise ValueError("reference starts must be non-negative integer samples")
            seen.add(source_line)
            if source_line not in predicted:
                unmatched_references += 1
                continue
            errors.append(abs(predicted[source_line] - start))
        if not errors:
            raise ValueError("at least one reference source line must have an automatic candidate")
    except (OSError, UnicodeError, ValueError) as exc:
        raise AlignmentError("invalid_alignment_references", str(exc), 4) from exc
    errors.sort()
    middle = len(errors) // 2
    median = errors[middle] if len(errors) % 2 else (errors[middle - 1] + errors[middle]) // 2
    p90 = errors[(9 * len(errors) + 9) // 10 - 1]
    return AlignmentEvaluation(
        reference_points=len(errors) + unmatched_references,
        matched_reference_points=len(errors),
        unmatched_reference_points=unmatched_references,
        median_absolute_error_samples=median,
        p90_absolute_error_samples=p90,
        passed=unmatched_references == 0 and median <= 12_000 and p90 <= 24_000,
    )


def align_lyrics(
    text_path: Path,
    project: Path,
    language: str,
    output_path: Path | None = None,
    report_path: Path | None = None,
    reference_path: Path | None = None,
) -> AlignmentResult:
    if language not in {"en", "zh"}:
        raise AlignmentError("unsupported_alignment_language", {"language": language})
    try:
        source = preflight_source(project)
    except ProjectPreflightError as exc:
        raise AlignmentError(exc.code, exc.details, 4) from exc
    if "://" in str(text_path):
        raise AlignmentError("remote_lyric_source_forbidden", {"path": str(text_path)})
    text_path = text_path.expanduser().resolve()
    if not text_path.is_file():
        raise AlignmentError("missing_lyric_source", {"path": str(text_path)}, 4)
    lines = _read_known_lines(text_path)
    audio_path, audio_hash, audio_kind = _select_audio(
        source.project, source.canonical_path, source.record.canonical.sha256
    )
    command, runner_path, lock_hash = _runtime()
    model = "small.en" if language == "en" else "small"
    config = {
        "adapter_version": 1,
        "runtime_lock_sha256": lock_hash,
        "runtime_runner_sha256": sha256_file(runner_path),
        "model": model,
        "device": "cpu",
        "compute_type": "int8",
        "vad_method": "pyannote",
        "mapping": "global_levenshtein_exact_characters",
        "minimum_coverage": MIN_COVERAGE,
        "minimum_matched_characters": MIN_MATCHED_CHARACTERS,
        "audio_offset_samples": 0,
    }
    cache_key = _json_hash(
        {
            "text_sha256": sha256_file(text_path),
            "audio_sha256": audio_hash,
            "language": language,
            "reference_sha256": sha256_file(reference_path.resolve()) if reference_path else None,
            "config": config,
        }
    )
    output_path = (output_path or source.project / "lyrics.aligned.json").resolve()
    report_path = (report_path or source.project / "alignment/report.json").resolve()
    if output_path.exists() or report_path.exists():
        try:
            lyrics = Lyrics.model_validate(read_document(output_path))
            report = AlignmentReport.model_validate(read_document(report_path))
            if (
                report.cache_key == cache_key
                and report.output.sha256 == sha256_file(output_path)
                and lyrics.origin == "aligned"
            ):
                return AlignmentResult(lyrics, output_path, report, report_path, True)
        except (OSError, UnicodeError, ValueError, ValidationError):
            pass
        raise AlignmentError(
            "alignment_output_conflict",
            {
                "output": str(output_path),
                "report": str(report_path),
                "message": "preserve edited cues or choose new output and report paths",
            },
            4,
        )
    model_dir = (
        Path(
            os.environ.get(
                "MVT_ALIGNMENT_MODEL_DIR",
                str(Path.home() / "Library/Caches/music-video-toolkit/whisperx"),
            )
        )
        .expanduser()
        .resolve()
    )
    try:
        model_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AlignmentError("alignment_model_directory_unavailable", str(exc), 3) from exc
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="mvt-alignment-") as temporary:
        runtime_output = Path(temporary) / "whisperx.json"
        evidence = _run_runtime(command, audio_path, runtime_output, language, model, model_dir)
    mapped = _map_lines(
        lines,
        _timed_characters(evidence, source.record.canonical.duration_samples),
        source.record.canonical.duration_samples,
    )
    cues = [
        Cue(start_sample=line.start_sample, end_sample=line.end_sample, text=line.text)
        for line in mapped
        if line.status == "matched"
    ]
    if not cues:
        raise AlignmentError("no_aligned_lyric_cues", {"lines": len(lines)}, 5)
    runtime_record = evidence["runtime"]
    assert isinstance(runtime_record, dict)
    parameters = {**config, **runtime_record}
    lyrics = Lyrics(
        schema_version="0.1",
        language=language,
        text_source=os.path.relpath(text_path, output_path.parent),
        text_source_sha256=sha256_file(text_path),
        audio_sha256=source.record.canonical.sha256,
        origin="aligned",
        provenance=Provenance(tool="mvt lyrics align", version=__version__, parameters=parameters),
        cues=cues,
    )
    evaluation = _evaluation(reference_path, source.record.canonical.sha256, mapped)
    _atomic_write(output_path, lyrics)
    report = AlignmentReport(
        schema_version="0.1",
        cache_key=cache_key,
        language=language,
        text_source=FileRef(
            path=os.path.relpath(text_path, report_path.parent), sha256=sha256_file(text_path)
        ),
        audio=FileRef(path=os.path.relpath(audio_path, report_path.parent), sha256=audio_hash),
        audio_kind=audio_kind,
        runtime=Provenance(
            tool=str(runner_path),
            version=str(runtime_record.get("version", "unknown")),
            parameters=parameters,
        ),
        elapsed_seconds=time.monotonic() - started,
        output=FileRef(
            path=os.path.relpath(output_path, report_path.parent), sha256=sha256_file(output_path)
        ),
        lines=mapped,
        evaluation=evaluation,
    )
    try:
        _atomic_write(report_path, report)
    except Exception:
        output_path.unlink(missing_ok=True)
        raise
    return AlignmentResult(lyrics, output_path, report, report_path, False)


def apply_alignment_edits(
    project: Path,
    edits_path: Path,
    aligned_path: Path | None = None,
    report_path: Path | None = None,
    output_path: Path | None = None,
) -> EditedLyricsResult:
    """Apply a complete set of reviewed line starts without running a model."""
    try:
        source = preflight_source(project)
    except ProjectPreflightError as exc:
        raise AlignmentError(exc.code, exc.details, 4) from exc
    aligned_path = (aligned_path or source.project / "lyrics.aligned.json").resolve()
    report_path = (report_path or source.project / "alignment/report.json").resolve()
    edits_path = edits_path.expanduser().resolve()
    output_path = (output_path or source.project / "lyrics.edited.json").resolve()
    try:
        aligned = Lyrics.model_validate(read_document(aligned_path))
        report = AlignmentReport.model_validate(read_document(report_path))
        edits = read_document(edits_path)
        if aligned.origin != "aligned":
            raise ValueError("base lyrics must have aligned origin")
        if aligned.audio_sha256 != source.record.canonical.sha256:
            raise ValueError("base lyrics audio hash differs from canonical audio")
        report_output = resolve_record_path(report_path, report.output.path)
        if report_output != aligned_path or report.output.sha256 != sha256_file(aligned_path):
            raise ValueError("alignment report does not identify the base lyrics artifact")
        if edits.get("schema_version") != "0.1":
            raise ValueError("unsupported edit schema version")
        if edits.get("audio_sha256") != source.record.canonical.sha256:
            raise ValueError("edit audio hash differs from canonical audio")
        points = edits.get("points")
        if not isinstance(points, list):
            raise ValueError("edit points must be an array")
        starts: dict[int, int] = {}
        for point in points:
            if not isinstance(point, dict):
                raise ValueError("edit point must be an object")
            line = point.get("source_line")
            start = point.get("start_sample")
            if (
                not isinstance(line, int)
                or isinstance(line, bool)
                or line in starts
                or not isinstance(start, int)
                or isinstance(start, bool)
                or start < 0
                or start >= source.record.canonical.duration_samples
            ):
                raise ValueError("edit points require unique source lines and in-range starts")
            starts[line] = start
        expected = [line.source_line for line in report.lines]
        if set(starts) != set(expected):
            raise ValueError(
                f"complete edits required; expected source lines {expected}, got {sorted(starts)}"
            )
        ordered_starts = [starts[line] for line in expected]
        if any(a >= b for a, b in zip(ordered_starts, ordered_starts[1:], strict=False)):
            raise ValueError("edited line starts must increase in source order")
        text_source = resolve_record_path(aligned_path, aligned.text_source)
        if sha256_file(text_source) != aligned.text_source_sha256:
            raise ValueError("base lyric text source has a different hash")
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        raise AlignmentError("invalid_alignment_edits", str(exc), 4) from exc

    cues = [
        Cue(
            start_sample=start,
            end_sample=(
                ordered_starts[index + 1]
                if index + 1 < len(ordered_starts)
                else source.record.canonical.duration_samples
            ),
            text=line.text,
        )
        for index, (line, start) in enumerate(zip(report.lines, ordered_starts, strict=True))
    ]
    edited = Lyrics(
        schema_version="0.1",
        language=aligned.language,
        text_source=os.path.relpath(text_source, output_path.parent),
        text_source_sha256=aligned.text_source_sha256,
        audio_sha256=aligned.audio_sha256,
        origin="edited",
        provenance=Provenance(
            tool="mvt lyrics apply-edits",
            version=__version__,
            parameters={
                "aligned_sha256": sha256_file(aligned_path),
                "alignment_report_sha256": sha256_file(report_path),
                "edits_sha256": sha256_file(edits_path),
                "end_time_policy": "next_edited_start_or_song_end",
                "sample_rate": SAMPLE_RATE,
            },
        ),
        cues=cues,
    )
    if output_path.exists():
        try:
            existing = Lyrics.model_validate(read_document(output_path))
        except (OSError, UnicodeError, ValueError, ValidationError) as exc:
            raise AlignmentError(
                "alignment_edit_output_conflict",
                {"path": str(output_path), "message": "existing output is not safely replaceable"},
                4,
            ) from exc
        if existing == edited:
            return EditedLyricsResult(existing, output_path, True)
        raise AlignmentError(
            "alignment_edit_output_conflict",
            {"path": str(output_path), "message": "preserve the existing edited lyrics"},
            4,
        )
    _atomic_write(output_path, edited)
    return EditedLyricsResult(edited, output_path, False)
