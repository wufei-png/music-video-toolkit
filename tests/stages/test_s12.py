import hashlib
import json
import shutil
import wave
from pathlib import Path

import pytest

from music_video_toolkit.cli import main
from music_video_toolkit.contracts import Structure
from music_video_toolkit.plan import resolve_plan
from music_video_toolkit.structure import StructureError, analyze_structure, apply_structure

PITCHES = ("c", "c_sharp", "d", "d_sharp", "e", "f", "f_sharp", "g", "g_sharp", "a", "a_sharp", "b")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_project(tmp_path: Path, cells: int = 16) -> Path:
    project = tmp_path / "structure project"
    source_dir = project / "source"
    source_dir.mkdir(parents=True)
    canonical = source_dir / "canonical.wav"
    with wave.open(str(canonical), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(3)
        wav.setframerate(48_000)
        wav.writeframes(b"\0" * cells * 48_000 * 6)
    original = tmp_path / "original.wav"
    original.write_bytes(b"synthetic structure source")
    (source_dir / "source.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "original": {"path": str(original), "sha256": sha256(original)},
                "canonical": {
                    "path": "canonical.wav",
                    "sha256": sha256(canonical),
                    "sample_rate": 48_000,
                    "channels": 2,
                    "sample_format": "s24le",
                    "codec": "pcm_s24le",
                    "duration_samples": cells * 48_000,
                },
                "decoder": {"tool": "synthetic", "version": "1", "parameters": {}},
            }
        ),
        encoding="utf-8",
    )
    return project


def write_timeline(
    project: Path,
    *,
    silence: bool = False,
    sparse_beats: bool = False,
    existing_sections: bool = False,
) -> Path:
    cells = 16
    repeated_pitches = [0, 2, 4, 5, 7, 9, 11, 7, 0, 2, 4, 5, 1, 3, 6, 10]
    energy = [0.4, 0.6, 0.5, 0.7, 0.3, 0.8, 0.2, 0.6] * 2
    if silence:
        energy = [0.0] * cells
    signals = {
        "mix.rms": {
            "start_sample": 0,
            "hop_samples": 48_000,
            "values": energy,
            "unit": "normalized_observed_max",
        }
    }
    for pitch_index, name in enumerate(PITCHES):
        signals[f"mix.chroma.{name}"] = {
            "start_sample": 0,
            "hop_samples": 48_000,
            "values": [
                0.0 if silence else float(cell_pitch == pitch_index)
                for cell_pitch in repeated_pitches
            ],
            "unit": "normalized_observed_max",
        }
    beat_indexes = [4] if sparse_beats else list(range(1, cells))
    timeline = {
        "schema_version": "0.1",
        "source": {
            "path": "source/canonical.wav",
            "sha256": sha256(project / "source/canonical.wav"),
            "sample_rate": 48_000,
            "duration_samples": cells * 48_000,
        },
        "analysis": [],
        "signals": signals,
        "events": [
            {"name": "beat", "source": "mix", "sample": index * 48_000, "confidence": 1.0}
            for index in beat_indexes
        ],
        "sections": (
            [
                {
                    "id": "reviewed-base",
                    "label": "Existing review",
                    "start_sample": 0,
                    "end_sample": cells * 48_000,
                    "origin": "manual",
                }
            ]
            if existing_sections
            else []
        ),
    }
    path = project / "timeline.json"
    path.write_text(json.dumps(timeline), encoding="utf-8")
    return path


def write_selection(
    project: Path,
    structure: Structure,
    *,
    policy: str = "require-empty",
    adjusted: bool = False,
) -> Path:
    candidate = structure.boundaries[0]
    sample = candidate.sample + (1600 if adjusted else 0)
    selection = {
        "schema_version": "0.1",
        "reviewed": True,
        "structure": {"path": "structure.json", "sha256": sha256(project / "structure.json")},
        "timeline": {"path": "timeline.json", "sha256": sha256(project / "timeline.json")},
        "existing_sections_policy": policy,
        "sections": [
            {
                "id": "selected-001",
                "start_sample": 0,
                "end_sample": sample,
                "end_boundary_id": candidate.id,
            },
            {
                "id": "selected-002",
                "label": "Reviewed label" if adjusted else None,
                "start_sample": sample,
                "end_sample": structure.source.duration_samples,
                "start_boundary_id": candidate.id,
            },
        ],
    }
    path = project / "structure-selection.json"
    path.write_text(json.dumps(selection), encoding="utf-8")
    return path


@pytest.mark.skipif(not shutil.which("uv"), reason="locked librosa runtime requires uv")
def test_structure_analyze_finds_repetition_without_mutating_timeline_and_reuses_cache(
    tmp_path, capsys
):
    project = source_project(tmp_path)
    timeline = write_timeline(project)
    before = timeline.read_bytes()

    assert main(["structure", "analyze", "--project", str(project)]) == 0
    report = json.loads(capsys.readouterr().out)
    structure = Structure.model_validate_json((project / "structure.json").read_text())
    assert report["cached"] is False
    assert timeline.read_bytes() == before
    assert structure.analyzer.tool == "librosa-structure"
    assert structure.analyzer.parameters["semantics"].startswith("unlabeled candidates")
    assert structure.repeated_groups
    repeated_ranges = {
        (span.start_sample, span.end_sample)
        for group in structure.repeated_groups
        for span in group.spans
    }
    assert {(0, 192_000), (384_000, 576_000)} <= repeated_ranges
    assert all(boundary.sample not in {0, 16 * 48_000} for boundary in structure.boundaries)
    assert analyze_structure(project).cached is True


@pytest.mark.skipif(not shutil.which("uv"), reason="locked librosa runtime requires uv")
@pytest.mark.parametrize(
    ("silence", "sparse_beats"),
    [(True, False), (False, True)],
)
def test_structure_analyze_handles_silence_and_sparse_beats(tmp_path, silence, sparse_beats):
    project = source_project(tmp_path)
    write_timeline(project, silence=silence, sparse_beats=sparse_beats)

    result = analyze_structure(project)

    assert result.structure.repeated_groups == []
    if silence:
        assert result.structure.boundaries == []
    else:
        assert result.structure.beat_samples == [192_000]


@pytest.mark.skipif(not shutil.which("uv"), reason="locked librosa runtime requires uv")
@pytest.mark.parametrize("tamper", ["artifact", "timeline"])
def test_structure_analyze_rejects_tampered_cache_inputs(tmp_path, tamper):
    project = source_project(tmp_path)
    timeline_path = write_timeline(project)
    result = analyze_structure(project)
    if tamper == "artifact":
        document = json.loads(result.output_path.read_text())
        document["cache_key"] = "f" * 64
        result.output_path.write_text(json.dumps(document), encoding="utf-8")
    else:
        timeline = json.loads(timeline_path.read_text())
        timeline["signals"]["mix.rms"]["values"][0] = 0.9
        timeline_path.write_text(json.dumps(timeline), encoding="utf-8")

    with pytest.raises(StructureError) as caught:
        analyze_structure(project)

    assert caught.value.code == "structure_output_conflict"


@pytest.mark.skipif(not shutil.which("uv"), reason="locked librosa runtime requires uv")
def test_structure_apply_writes_reusable_enriched_timeline_and_resolves_plan(tmp_path, capsys):
    project = source_project(tmp_path)
    base_timeline = write_timeline(project)
    structure = analyze_structure(project).structure
    selection = write_selection(project, structure)
    output = project / "timeline.enriched.json"
    before = base_timeline.read_bytes()

    assert (
        main(
            [
                "structure",
                "apply",
                "--project",
                str(project),
                "--selection",
                str(selection),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["cached"] is False
    assert base_timeline.read_bytes() == before
    result = apply_structure(project, selection, output)
    assert result.cached is True
    assert [section.origin for section in result.timeline.sections] == ["automatic", "automatic"]
    assert result.timeline.analysis[-1].tool == "music-video-toolkit.structure.apply"

    (project / "assets.json").write_text(
        json.dumps({"schema_version": "0.1", "assets": []}), encoding="utf-8"
    )
    plan = project / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "timeline_path": "timeline.enriched.json",
                "assets_path": "assets.json",
                "mode": "abstract",
                "seed": 12,
                "layers": [{"id": "orb", "kind": "orb", "category": "abstract"}],
            }
        ),
        encoding="utf-8",
    )
    resolved, _ = resolve_plan(project, plan, project / "plans/resolved.json")
    assert [span.section_id for span in resolved.spans] == ["selected-001", "selected-002"]

    changed = json.loads(output.read_text())
    changed["sections"][0]["id"] = "tampered"
    output.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(StructureError) as caught:
        apply_structure(project, selection, output)
    assert caught.value.code == "structure_output_conflict"


@pytest.mark.skipif(not shutil.which("uv"), reason="locked librosa runtime requires uv")
def test_structure_apply_marks_adjustments_manual_and_rejects_base_alias(tmp_path):
    project = source_project(tmp_path)
    timeline = write_timeline(project)
    structure = analyze_structure(project).structure
    selection = write_selection(project, structure, adjusted=True)

    result = apply_structure(project, selection, project / "timeline.adjusted.json")
    assert [section.origin for section in result.timeline.sections] == ["manual", "manual"]
    assert all(section.confidence is None for section in result.timeline.sections)

    with pytest.raises(StructureError) as caught:
        apply_structure(project, selection, timeline)
    assert caught.value.code == "structure_output_alias"


@pytest.mark.skipif(not shutil.which("uv"), reason="locked librosa runtime requires uv")
def test_structure_apply_requires_explicit_replacement_for_existing_sections(tmp_path):
    project = source_project(tmp_path)
    timeline = write_timeline(project, existing_sections=True)
    before = timeline.read_bytes()
    structure = analyze_structure(project).structure
    selection = write_selection(project, structure, policy="require-empty")

    with pytest.raises(StructureError) as caught:
        apply_structure(project, selection, project / "rejected.json")
    assert caught.value.code == "structure_existing_sections"

    document = json.loads(selection.read_text())
    document["existing_sections_policy"] = "replace"
    selection.write_text(json.dumps(document), encoding="utf-8")
    result = apply_structure(project, selection, project / "replaced.json")
    assert result.timeline.sections[0].id == "selected-001"
    assert timeline.read_bytes() == before
