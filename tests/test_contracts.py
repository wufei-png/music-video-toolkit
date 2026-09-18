import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from music_video_toolkit.contracts import CONTRACTS

ROOT = Path(__file__).resolve().parents[1]


def document(name):
    return json.loads((ROOT / "examples" / name).read_text())


@pytest.mark.parametrize(
    "kind,name",
    [
        ("timeline", "timeline.json"),
        ("assets", "assets.json"),
        ("lyrics", "lyrics.json"),
        ("preview", "preview.json"),
        ("render", "render.json"),
        ("comparison-request", "comparison-request.json"),
        ("comparison", "comparison.json"),
        ("plan", "plan-abstract.json"),
        ("plan", "plan-mood.json"),
        ("plan", "plan-hybrid.json"),
    ],
)
def test_examples_and_generated_schemas(kind, name):
    model = CONTRACTS[kind]
    data = document(name)
    parsed = model.model_validate(data)
    assert parsed.schema_version == "0.1"
    schema = json.loads((ROOT / "schemas" / f"{kind}.schema.json").read_text())
    assert schema == model.model_json_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema_version="9.0"),
        lambda d: d.update(unknown_field=1),
        lambda d: d["source"].update(sample_rate=True),
        lambda d: d["source"].update(duration_samples=0),
        lambda d: d["source"].update(sha256="not-a-hash"),
        lambda d: d["events"][0].update(sample=480000),
        lambda d: d["events"][0].update(sample=1.5),
        lambda d: d["signals"]["bass.rms"].update(hop_samples=480000),
        lambda d: d["signals"]["bass.rms"].update(values=[float("nan")]),
        lambda d: d["sections"][1].update(start_sample=239999),
        lambda d: d["sections"][1].update(end_sample=480001),
        lambda d: d["sections"][1].update(id="intro"),
    ],
)
def test_timeline_rejects_invalid_clock_or_identity(mutate):
    data = document("timeline.json")
    mutate(data)
    with pytest.raises(ValidationError):
        CONTRACTS["timeline"].model_validate(data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(mode="mood"),
        lambda d: d["layers"].append(copy.deepcopy(d["layers"][0])),
        lambda d: d["layers"][0].update(opacity=1.1),
        lambda d: d["routes"][0].update(target_layer="absent"),
        lambda d: d.update(lyrics={"mode": "auto"}),
        lambda d: d.update(lyrics={"mode": "off", "path": "lyrics.json"}),
        lambda d: d.update(seed=2**53),
        lambda d: d.update(output={"width": 3840}),
    ],
)
def test_plan_rejects_unusable_local_structure(mutate):
    data = document("plan-abstract.json")
    mutate(data)
    with pytest.raises(ValidationError):
        CONTRACTS["plan"].model_validate(data)


@pytest.mark.parametrize(
    ("width", "height", "fps_num", "fps_den"),
    [
        (1920, 1080, 30, 1),
        (1080, 1920, 30, 1),
    ],
)
def test_plan_accepts_only_the_two_supported_output_profiles(width, height, fps_num, fps_den):
    data = document("plan-abstract.json")
    data["output"] = {
        "width": width,
        "height": height,
        "fps_num": fps_num,
        "fps_den": fps_den,
    }

    parsed = CONTRACTS["plan"].model_validate(data)
    assert (
        parsed.output.width,
        parsed.output.height,
        parsed.output.fps_num,
        parsed.output.fps_den,
    ) == (
        width,
        height,
        fps_num,
        fps_den,
    )


@pytest.mark.parametrize(
    ("width", "height", "fps_num", "fps_den"),
    [
        (1920, 1920, 30, 1),
        (1080, 1080, 30, 1),
        (1080, 1920, 60, 1),
        (3840, 2160, 30, 1),
        (720, 1280, 30, 1),
        (1920, 1080, 30000, 1001),
    ],
)
def test_plan_and_schema_reject_every_unsupported_output_tuple(width, height, fps_num, fps_den):
    data = document("plan-abstract.json")
    data["output"] = {
        "width": width,
        "height": height,
        "fps_num": fps_num,
        "fps_den": fps_den,
    }

    with pytest.raises(ValidationError):
        CONTRACTS["plan"].model_validate(data)
    schema = json.loads((ROOT / "schemas" / "plan.schema.json").read_text())
    errors = list(Draft202012Validator(schema).iter_errors(data))
    assert errors


def test_legacy_plan_without_output_defaults_to_landscape():
    data = document("plan-abstract.json")
    data.pop("output", None)

    parsed = CONTRACTS["plan"].model_validate(data)
    assert (
        parsed.output.width,
        parsed.output.height,
        parsed.output.fps_num,
        parsed.output.fps_den,
    ) == (
        1920,
        1080,
        30,
        1,
    )


def test_lyric_overlap_and_empty_cues_rejected():
    data = document("lyrics.json")
    data["cues"][1]["start_sample"] = 95000
    with pytest.raises(ValidationError):
        CONTRACTS["lyrics"].model_validate(data)
    data["cues"] = []
    with pytest.raises(ValidationError):
        CONTRACTS["lyrics"].model_validate(data)


def test_duplicate_assets_rejected():
    data = document("assets.json")
    data["assets"] *= 2
    with pytest.raises(ValidationError):
        CONTRACTS["assets"].model_validate(data)


def test_render_requires_evidence_or_error():
    data = document("render.json")
    data["outputs"] = []
    with pytest.raises(ValidationError):
        CONTRACTS["render"].model_validate(data)
    data["status"] = "failed"
    with pytest.raises(ValidationError):
        CONTRACTS["render"].model_validate(data)
    data["error"] = "encoder failed"
    assert CONTRACTS["render"].model_validate(data).status == "failed"


def test_comparison_request_requires_ordered_unique_variants():
    data = document("comparison-request.json")
    data["variants"][1]["id"] = data["variants"][0]["id"]
    with pytest.raises(ValidationError):
        CONTRACTS["comparison-request"].model_validate(data)

    data = document("comparison-request.json")
    data["variants"][1]["preview_manifest_path"] = data["variants"][0]["preview_manifest_path"]
    with pytest.raises(ValidationError):
        CONTRACTS["comparison-request"].model_validate(data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["profile"].update(range_count=3),
        lambda d: d["variants"][1].update(id="abstract-a"),
        lambda d: d["variants"][0]["clips"][0].update(range_index=2),
        lambda d: d["variants"][0]["clips"][0]["range"].update(end_sample=240000),
        lambda d: d["variants"][0]["clips"][0]["probe"].update(width=1080),
        lambda d: d["variants"][0]["clips"][0]["probe"].update(has_audio=False),
    ],
)
def test_comparison_rejects_incoherent_shared_evidence(mutate):
    data = document("comparison.json")
    mutate(data)
    with pytest.raises(ValidationError):
        CONTRACTS["comparison"].model_validate(data)


def test_comparison_rejects_shared_but_duration_incoherent_frame_counts():
    data = document("comparison.json")
    for variant in data["variants"]:
        for clip in variant["clips"]:
            clip["probe"]["frame_count"] = 1

    with pytest.raises(ValidationError, match="frame count must match"):
        CONTRACTS["comparison"].model_validate(data)
