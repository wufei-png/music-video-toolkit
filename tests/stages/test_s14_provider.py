"""Only checked, self-authored projectM presets enter the production path."""

import hashlib
import json
import runpy
from pathlib import Path

import pytest

from music_video_toolkit.project import sha256_file
from music_video_toolkit.projectm_provider import (
    LOCK,
    ProjectMError,
    _approved_preset,
    approved_preset_ids,
    integration_identity,
)
from music_video_toolkit.provider import validate_provider_request

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("preset_id", approved_preset_ids())
def test_catalog_preset_is_hash_bound(tmp_path, preset_id):
    write_fixture = runpy.run_path(str(ROOT / "tests/fixtures/s14/create_fixture.py"))[
        "write_fixture"
    ]
    request_path = write_fixture(tmp_path / "input", preset_id=preset_id)
    request = validate_provider_request(request_path)
    assert _approved_preset(request_path, request).name == f"{preset_id}.milk"
    assert (
        sha256_file(_approved_preset(request_path, request)) == LOCK["approved_presets"][preset_id]
    )


@pytest.mark.parametrize("preset_id", ["unknown", "study-soft-flow"])
def test_unknown_or_mismatched_preset_id_is_rejected(tmp_path, preset_id):
    write_fixture = runpy.run_path(str(ROOT / "tests/fixtures/s14/create_fixture.py"))[
        "write_fixture"
    ]
    request_path = write_fixture(tmp_path / "input")
    request_data = json.loads(request_path.read_text(encoding="utf-8"))
    parameters = {"preset_id": preset_id, "policy": "locked-single"}
    request_data["parameters"] = parameters
    request_data["parameters_sha256"] = hashlib.sha256(
        json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    request_path.write_text(json.dumps(request_data), encoding="utf-8")
    request = validate_provider_request(request_path)
    with pytest.raises(ProjectMError) as error:
        _approved_preset(request_path, request)
    assert error.value.code == (
        "projectm_unsupported_parameters" if preset_id == "unknown" else "projectm_invalid_project"
    )


def test_catalog_changes_integration_identity(monkeypatch):
    original = integration_identity()
    monkeypatch.setitem(LOCK["approved_presets"], "study-soft-flow", "0" * 64)
    assert integration_identity() != original


@pytest.mark.parametrize("change", ["unapproved", "extra_field"])
def test_approved_preset_is_hash_bound_and_project_is_closed(tmp_path, change):
    write_fixture = runpy.run_path(str(ROOT / "tests/fixtures/s14/create_fixture.py"))[
        "write_fixture"
    ]
    request_path = write_fixture(tmp_path / "input")
    request = validate_provider_request(request_path)
    assert _approved_preset(request_path, request).is_file()

    project_path = request_path.parent / "project.json"
    project = json.loads(project_path.read_text(encoding="utf-8"))
    request_data = json.loads(request_path.read_text(encoding="utf-8"))
    if change == "unapproved":
        preset = request_path.parent / "mvt-wave.milk"
        preset.write_text("[preset00]\nwave_r=1\n", encoding="utf-8")
        digest = sha256_file(preset)
        project["preset"]["sha256"] = digest
        request_data["assets"][0]["sha256"] = digest
    else:
        project["unreviewed"] = True
    project_path.write_text(json.dumps(project), encoding="utf-8")
    request_data["project"]["sha256"] = sha256_file(project_path)
    request_path.write_text(json.dumps(request_data), encoding="utf-8")
    request = validate_provider_request(request_path)
    with pytest.raises(ProjectMError) as error:
        _approved_preset(request_path, request)
    assert error.value.code == "projectm_invalid_project"
