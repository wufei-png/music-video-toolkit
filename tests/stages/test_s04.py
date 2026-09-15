import hashlib
import json
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from music_video_toolkit.audio import decode_audio
from music_video_toolkit.cli import main
from music_video_toolkit.contracts import ResolvedPlan
from music_video_toolkit.plan import PlanError, resolve_plan


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_audio(path: Path, seconds: int = 3) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(48_000)
        frames = bytearray()
        for sample in range(seconds * 48_000):
            value = round(2000 * math.sin(2 * math.pi * 220 * sample / 48_000))
            frames.extend(struct.pack("<hh", value, value))
        wav.writeframes(frames)


def write_project(tmp_path: Path, *, sections=True) -> tuple[Path, Path]:
    original = tmp_path / "synthetic.wav"
    write_audio(original)
    project = tmp_path / "project"
    source = decode_audio(original, project)
    timeline = {
        "schema_version": "0.1",
        "source": {
            "path": "source/canonical.wav",
            "sha256": source.record.canonical.sha256,
            "sample_rate": 48_000,
            "duration_samples": 144_000,
        },
        "analysis": [],
        "signals": {
            "bass.rms": {
                "start_sample": 0,
                "hop_samples": 48_000,
                "values": [1.0, 0.0, 0.0],
                "unit": "normalized",
            },
            "drums.rms": {
                "start_sample": 0,
                "hop_samples": 48_000,
                "values": [0.0, 0.0, 0.0],
                "unit": "normalized",
            },
            "vocals.rms": {
                "start_sample": 0,
                "hop_samples": 48_000,
                "values": [0.0, 0.0, 0.0],
                "unit": "normalized",
            },
            "mix.rms": {
                "start_sample": 0,
                "hop_samples": 48_000,
                "values": [0.1, 0.9, 0.2],
                "unit": "normalized",
            },
        },
        "events": [],
        "sections": (
            [
                {
                    "id": "intro",
                    "label": "Intro",
                    "origin": "manual",
                    "start_sample": 0,
                    "end_sample": 48_000,
                },
                {
                    "id": "climax",
                    "label": "Climax",
                    "origin": "manual",
                    "start_sample": 96_000,
                    "end_sample": 120_000,
                },
            ]
            if sections
            else []
        ),
    }
    (project / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
    (project / "assets.json").write_text('{"schema_version":"0.1","assets":[]}', encoding="utf-8")
    plan = {
        "schema_version": "0.1",
        "timeline_path": "timeline.json",
        "assets_path": "assets.json",
        "mode": "abstract",
        "seed": 404,
        "layers": [
            {
                "id": "bass-orb",
                "kind": "orb",
                "category": "abstract",
                "parameters": {"x": -0.5, "color": "#55d6ff"},
            },
            {
                "id": "drum-ribbon",
                "kind": "ribbon",
                "category": "abstract",
                "parameters": {"y": 0.0, "color": "#ff4fa3"},
            },
            {
                "id": "vocal-particles",
                "kind": "particles",
                "category": "abstract",
                "parameters": {"count": 120, "color": "#ffe178"},
            },
        ],
        "routes": [
            {
                "source": "bass.rms",
                "target_layer": "bass-orb",
                "target_parameter": "radius",
                "transform": {"kind": "linear", "parameters": {"min": 0.1, "max": 0.6}},
            },
            {
                "source": "drums.rms",
                "target_layer": "drum-ribbon",
                "target_parameter": "amplitude",
                "transform": {"kind": "linear", "parameters": {"min": 0.0, "max": 0.5}},
            },
            {
                "source": "vocals.rms",
                "target_layer": "vocal-particles",
                "target_parameter": "size",
                "transform": {
                    "kind": "smooth",
                    "parameters": {
                        "min": 0.001,
                        "max": 0.08,
                        "attack_seconds": 0.08,
                        "release_seconds": 0.25,
                    },
                },
            },
        ],
        "sections": (
            [
                {
                    "section_id": "climax",
                    "transition_samples": 12_000,
                    "layers": [
                        {
                            "layer_id": "bass-orb",
                            "opacity": 0.7,
                            "parameters": {"x": 0.45},
                        }
                    ],
                }
            ]
            if sections
            else []
        ),
    }
    plan_path = project / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    return project, plan_path


def test_resolver_applies_section_override_and_gap_defaults(tmp_path):
    project, plan_path = write_project(tmp_path)
    resolved, output = resolve_plan(project, plan_path)

    assert output == (project / "resolved-plan.json").resolve()
    assert [(span.start_sample, span.end_sample, span.section_id) for span in resolved.spans] == [
        (0, 48_000, "intro"),
        (48_000, 96_000, None),
        (96_000, 120_000, "climax"),
        (120_000, 144_000, None),
    ]
    assert resolved.spans[0].section_label == "Intro"
    assert resolved.spans[0].section_origin == "manual"
    default_orb = next(layer for layer in resolved.spans[1].layers if layer.id == "bass-orb")
    climax_orb = next(layer for layer in resolved.spans[2].layers if layer.id == "bass-orb")
    assert default_orb.parameters["x"] == -0.5
    assert climax_orb.parameters["x"] == 0.45
    assert resolved.spans[2].transition_samples == 12_000
    assert ResolvedPlan.model_validate_json(output.read_text()) == resolved


def test_automatic_novelty_has_candidate_identity_without_semantic_label(tmp_path):
    project, plan_path = write_project(tmp_path, sections=False)
    resolved, _ = resolve_plan(project, plan_path)

    assert all(span.section_origin == "automatic" for span in resolved.spans)
    assert all(span.section_label is None for span in resolved.spans)
    assert resolved.spans[0].start_sample == 0
    assert resolved.spans[-1].end_sample == 144_000


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda plan: plan["layers"][0]["parameters"].update(unknown=1), "unknown_layer_parameter"),
        (lambda plan: plan["routes"][0].update(source="missing.rms"), "missing_route_signal"),
        (
            lambda plan: plan["routes"][0].update(target_parameter="color"),
            "unsupported_route_target",
        ),
        (lambda plan: plan["sections"][0].update(section_id="absent"), "unknown_section"),
        (
            lambda plan: plan["sections"][0]["layers"].append(
                {"layer_id": "bass-orb", "enabled": False}
            ),
            "invalid_plan_input",
        ),
    ],
)
def test_resolver_hard_fails_invalid_bounded_inputs(tmp_path, mutation, code):
    project, plan_path = write_project(tmp_path)
    plan = json.loads(plan_path.read_text())
    mutation(plan)
    plan_path.write_text(json.dumps(plan))

    with pytest.raises(PlanError) as caught:
        resolve_plan(project, plan_path)

    assert caught.value.code == code


def test_disabling_required_abstract_layers_fails_per_section(tmp_path):
    project, plan_path = write_project(tmp_path)
    plan = json.loads(plan_path.read_text())
    plan["sections"][0]["layers"] = [
        {"layer_id": layer["id"], "enabled": False} for layer in plan["layers"]
    ]
    plan_path.write_text(json.dumps(plan))

    with pytest.raises(PlanError) as caught:
        resolve_plan(project, plan_path)

    assert caught.value.code == "required_layer_disabled"


@pytest.mark.skipif(
    not all(shutil.which(name) for name in ("ffmpeg", "ffprobe", "node", "pnpm")),
    reason="browser render dependencies required",
)
def test_stem_isolation_plan_renders_real_abstract_clip(tmp_path, capsys):
    project, plan_path = write_project(tmp_path)
    assert main(["plan", "resolve", "--project", str(project), "--plan", str(plan_path)]) == 0
    resolution = json.loads(capsys.readouterr().out)
    output = project / "abstract.mp4"

    assert (
        main(
            [
                "render",
                "--project",
                str(project),
                "--plan",
                resolution["output"],
                "--output",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["frame_count"] == 90
    assert report["readiness"]["abstractReady"] is True
    probe = subprocess.run(
        [
            shutil.which("ffprobe") or "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,nb_frames",
            "-of",
            "json",
            str(output),
        ],
        text=True,
        capture_output=True,
    )
    assert probe.returncode == 0
    assert any(stream.get("nb_frames") == "90" for stream in json.loads(probe.stdout)["streams"])
