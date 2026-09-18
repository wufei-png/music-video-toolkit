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
from .contracts import (
    FileRef,
    Provenance,
    Section,
    Source,
    Structure,
    StructureSelection,
    Timeline,
)
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


@dataclass(frozen=True)
class StructureApplyResult:
    timeline: Timeline
    output_path: Path
    cached: bool

    def summary(self) -> dict[str, object]:
        return {
            "ok": True,
            "cached": self.cached,
            "output": str(self.output_path),
            "sections": len(self.timeline.sections),
            "manual_sections": sum(
                section.origin == "manual" for section in self.timeline.sections
            ),
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


def _load(model, path: Path, label: str):
    try:
        return model.model_validate(read_document(path))
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        details = (
            exc.errors(include_url=False, include_context=False, include_input=False)
            if isinstance(exc, ValidationError)
            else str(exc)
        )
        raise StructureError(
            "invalid_structure_input", {"artifact": label, "details": details}, 4
        ) from exc


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


def _write(path: Path, structure: Structure | Timeline) -> None:
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


def _selected_sections(
    selection: StructureSelection,
    structure: Structure,
    duration_samples: int,
) -> list[Section]:
    if (
        selection.sections[0].start_sample != 0
        or selection.sections[-1].end_sample != duration_samples
    ):
        raise StructureError(
            "structure_selection_incomplete",
            {"duration_samples": duration_samples},
            4,
        )
    boundaries = {boundary.id: boundary for boundary in structure.boundaries}
    sections: list[Section] = []
    for selected in selection.sections:
        evidence = []
        manual = selected.label is not None
        references = (
            ("start", selected.start_sample, selected.start_boundary_id),
            ("end", selected.end_sample, selected.end_boundary_id),
        )
        for edge, sample, boundary_id in references:
            endpoint = sample == 0 if edge == "start" else sample == duration_samples
            if endpoint:
                if boundary_id is not None:
                    raise StructureError(
                        "structure_selection_boundary_mismatch",
                        {"section": selected.id, "edge": edge, "boundary_id": boundary_id},
                        4,
                    )
                continue
            if boundary_id is None:
                manual = True
                continue
            boundary = boundaries.get(boundary_id)
            if boundary is None:
                raise StructureError(
                    "structure_selection_unknown_boundary",
                    {"section": selected.id, "edge": edge, "boundary_id": boundary_id},
                    4,
                )
            if boundary.sample != sample:
                manual = True
            else:
                evidence.append(boundary.confidence)
        sections.append(
            Section(
                id=selected.id,
                label=selected.label,
                start_sample=selected.start_sample,
                end_sample=selected.end_sample,
                origin="manual" if manual else "automatic",
                confidence=None if manual or not evidence else min(evidence),
            )
        )
    return sections


def apply_structure(
    project: Path,
    selection_path: Path,
    output_path: Path,
) -> StructureApplyResult:
    try:
        source = preflight_source(project)
    except ProjectPreflightError as exc:
        raise StructureError(exc.code, exc.details, 4) from exc
    selection_path = selection_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    selection = _load(StructureSelection, selection_path, "structure-selection")
    structure_path = resolve_record_path(selection_path, selection.structure.path)
    timeline_path = resolve_record_path(selection_path, selection.timeline.path)
    if output_path in {selection_path, structure_path, timeline_path}:
        raise StructureError(
            "structure_output_alias",
            {"output": str(output_path), "message": "enriched timeline must be a separate file"},
            4,
        )
    structure = _load(Structure, structure_path, "structure")
    timeline = _load(Timeline, timeline_path, "timeline")
    actual_hashes = {
        "structure": sha256_file(structure_path) if structure_path.is_file() else None,
        "timeline": sha256_file(timeline_path) if timeline_path.is_file() else None,
    }
    expected_hashes = {
        "structure": selection.structure.sha256,
        "timeline": selection.timeline.sha256,
    }
    if actual_hashes != expected_hashes:
        raise StructureError(
            "structure_selection_hash_mismatch",
            {"expected": expected_hashes, "actual": actual_hashes},
            4,
        )
    if (
        resolve_record_path(structure_path, structure.timeline.path) != timeline_path
        or structure.timeline.sha256 != selection.timeline.sha256
    ):
        raise StructureError("structure_selection_timeline_mismatch", {}, 4)
    if (
        timeline.source.sha256 != source.record.canonical.sha256
        or structure.source.sha256 != source.record.canonical.sha256
        or resolve_record_path(timeline_path, timeline.source.path) != source.canonical_path
        or resolve_record_path(structure_path, structure.source.path) != source.canonical_path
    ):
        raise StructureError("structure_timeline_source_mismatch", {}, 4)
    if timeline.sections and selection.existing_sections_policy != "replace":
        raise StructureError(
            "structure_existing_sections",
            {
                "policy": selection.existing_sections_policy,
                "sections": [section.id for section in timeline.sections],
            },
            4,
        )
    sections = _selected_sections(selection, structure, timeline.source.duration_samples)
    selection_hash = sha256_file(selection_path)
    enriched = timeline.model_copy(
        update={
            "analysis": [
                *timeline.analysis,
                Provenance(
                    tool="music-video-toolkit.structure.apply",
                    version=__version__,
                    parameters={
                        "base_timeline_sha256": selection.timeline.sha256,
                        "structure_sha256": selection.structure.sha256,
                        "selection_sha256": selection_hash,
                        "existing_sections_policy": selection.existing_sections_policy,
                    },
                ),
            ],
            "sections": sections,
        }
    )
    enriched = Timeline.model_validate(enriched.model_dump(mode="json"))
    if output_path.exists():
        existing = _load(Timeline, output_path, "enriched-timeline")
        if existing == enriched:
            return StructureApplyResult(existing, output_path, True)
        raise StructureError(
            "structure_output_conflict",
            {"path": str(output_path), "message": "existing enriched timeline differs"},
            4,
        )
    _write(output_path, enriched)
    return StructureApplyResult(enriched, output_path, False)
