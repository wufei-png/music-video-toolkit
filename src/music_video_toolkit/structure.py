"""Separate deterministic repeated-structure analysis and cache validation."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from . import __version__
from .analysis import AnalysisError, _dependency, _run, _runtime_project
from .contracts import FileRef, Provenance, Source, Structure, Timeline
from .documents import read_document
from .project import ProjectPreflightError, preflight_source, resolve_record_path, sha256_file

DEFAULT_OUTPUT = Path("structure.json")
DEFAULT_TIMELINE = Path("timeline.json")
STRUCTURE_PARAMETERS = {
    "anchor_policy": "canonical endpoints plus sorted unique interior mix beat estimates",
    "feature_policy": "mean beat-synchronized mix RMS plus L2-normalized 12-bin mix chroma",
    "similarity": "cosine self-similarity on beat-synchronized feature cells",
    "novelty_window_cells": 4,
    "novelty_threshold": 0.12,
    "novelty_energy_weight": 0.25,
    "repetition_similarity_threshold": 0.86,
    "minimum_repeated_cells": 3,
    "maximum_repeated_cells": 16,
    "maximum_repeated_groups": 8,
    "silence_epsilon": 1e-12,
    "semantics": "unlabeled candidates; no downbeat, bar, pitch, melody or section-name inference",
}


class StructureError(Exception):
    """A stable structure-analysis failure suitable for machine-readable CLI output."""

    def __init__(self, code: str, details: object, exit_code: int = 2):
        super().__init__(str(details))
        self.code = code
        self.details = details
        self.exit_code = exit_code


@dataclass(frozen=True)
class StructureResult:
    structure: Structure
    output_path: Path
    cached: bool

    def summary(self) -> dict[str, object]:
        return {
            "ok": True,
            "cached": self.cached,
            "output": str(self.output_path),
            "cache_key": self.structure.cache_key,
            "beats": len(self.structure.beat_samples),
            "boundaries": len(self.structure.boundaries),
            "repeated_groups": len(self.structure.repeated_groups),
        }


def _json_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_timeline(path: Path) -> Timeline:
    try:
        return Timeline.model_validate(read_document(path))
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        details = (
            exc.errors(include_url=False, include_context=False, include_input=False)
            if isinstance(exc, ValidationError)
            else str(exc)
        )
        raise StructureError("invalid_structure_input", details, 4) from exc


def _identity(runtime: Path, timeline_path: Path) -> tuple[str, dict[str, str]]:
    analyzer_script = runtime / "analyze_structure.py"
    if not analyzer_script.is_file():
        raise StructureError("missing_analysis_runtime", {"path": str(analyzer_script)}, 3)
    identities = {
        "timeline_sha256": sha256_file(timeline_path),
        "runtime_lock_sha256": sha256_file(runtime / "uv.lock"),
        "analyzer_script_sha256": sha256_file(analyzer_script),
        "adapter_sha256": sha256_file(Path(__file__)),
    }
    return _json_hash({"parameters": STRUCTURE_PARAMETERS, **identities}), identities


def _validated_cache(
    output: Path,
    cache_key: str,
    timeline_path: Path,
    source_hash: str,
    source_path: Path,
) -> Structure | None:
    try:
        structure = Structure.model_validate(read_document(output))
        if structure.cache_key != cache_key or structure.source.sha256 != source_hash:
            return None
        recorded_timeline = resolve_record_path(output, structure.timeline.path)
        if (
            recorded_timeline != timeline_path
            or not recorded_timeline.is_file()
            or sha256_file(recorded_timeline) != structure.timeline.sha256
        ):
            return None
        recorded_source = resolve_record_path(output, structure.source.path)
        if (
            recorded_source != source_path
            or not recorded_source.is_file()
            or sha256_file(recorded_source) != structure.source.sha256
        ):
            return None
        return structure
    except (OSError, UnicodeError, ValueError, ValidationError):
        return None


def _write(path: Path, structure: Structure) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(structure.model_dump_json(indent=2))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def analyze_structure(
    project: Path,
    timeline_path: Path | None = None,
    output_path: Path | None = None,
) -> StructureResult:
    try:
        source = preflight_source(project)
    except ProjectPreflightError as exc:
        raise StructureError(exc.code, exc.details, 4) from exc
    project = source.project
    timeline_path = (timeline_path or project / DEFAULT_TIMELINE).expanduser().resolve()
    output_path = (output_path or project / DEFAULT_OUTPUT).expanduser().resolve()
    timeline = _load_timeline(timeline_path)
    actual_source_path = resolve_record_path(timeline_path, timeline.source.path)
    if (
        timeline.source.sha256 != source.record.canonical.sha256
        or timeline.source.duration_samples != source.record.canonical.duration_samples
        or actual_source_path != source.canonical_path
    ):
        raise StructureError(
            "structure_timeline_source_mismatch", {"timeline": str(timeline_path)}, 4
        )
    try:
        runtime = _runtime_project()
    except AnalysisError as exc:
        raise StructureError(exc.code, exc.details, exc.exit_code) from exc
    cache_key, identities = _identity(runtime, timeline_path)
    if output_path.exists():
        cached = _validated_cache(
            output_path,
            cache_key,
            timeline_path,
            source.record.canonical.sha256,
            source.canonical_path,
        )
        if cached is not None:
            return StructureResult(cached, output_path, True)
        raise StructureError(
            "structure_output_conflict",
            {
                "path": str(output_path),
                "message": "existing structure artifact is stale or invalid",
            },
            4,
        )

    try:
        uv = _dependency("uv")
    except AnalysisError as exc:
        raise StructureError(exc.code, exc.details, exc.exit_code) from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_path.parent, prefix=".structure-") as name:
        raw_path = Path(name) / "analysis.json"
        try:
            _run(
                [
                    uv,
                    "run",
                    "--project",
                    str(runtime),
                    "--locked",
                    "python",
                    str(runtime / "analyze_structure.py"),
                    "--timeline",
                    str(timeline_path),
                    "--output",
                    str(raw_path),
                ],
                "structure_analysis_failed",
            )
        except AnalysisError as exc:
            raise StructureError(exc.code, exc.details, exc.exit_code) from exc
        try:
            raw = read_document(raw_path)
        except (OSError, UnicodeError, ValueError) as exc:
            raise StructureError("invalid_structure_output", str(exc), 5) from exc
    if raw.get("parameters") != STRUCTURE_PARAMETERS:
        raise StructureError(
            "structure_configuration_mismatch",
            {"expected": STRUCTURE_PARAMETERS, "actual": raw.get("parameters")},
            5,
        )
    parameters = {
        **STRUCTURE_PARAMETERS,
        **identities,
        "cache_key": cache_key,
        "mvt_version": __version__,
    }
    try:
        structure = Structure(
            schema_version="0.1",
            source=Source(
                path=os.path.relpath(source.canonical_path, output_path.parent),
                sha256=source.record.canonical.sha256,
                sample_rate=source.record.canonical.sample_rate,
                duration_samples=source.record.canonical.duration_samples,
            ),
            timeline=FileRef(
                path=os.path.relpath(timeline_path, output_path.parent),
                sha256=identities["timeline_sha256"],
            ),
            cache_key=cache_key,
            analyzer=Provenance(
                tool="librosa-structure",
                version=str(raw["librosa_version"]),
                parameters=parameters,
            ),
            beat_samples=raw["beat_samples"],
            boundaries=raw["boundaries"],
            repeated_groups=raw["repeated_groups"],
        )
    except (KeyError, TypeError, ValidationError) as exc:
        details = exc.errors(include_url=False) if isinstance(exc, ValidationError) else str(exc)
        raise StructureError("invalid_structure_output", details, 5) from exc
    _write(output_path, structure)
    return StructureResult(structure, output_path, False)
