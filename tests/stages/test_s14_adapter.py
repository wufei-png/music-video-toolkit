"""The MVT process boundary revalidates projectM results before accepting them."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from test_s13_protocol import fake_provider as protocol_fixture

from music_video_toolkit import projectm
from music_video_toolkit.project import sha256_file
from music_video_toolkit.projectm_provider import LOCK, integration_identity


@pytest.fixture
def provider_fixture(tmp_path):
    return protocol_fixture.__wrapped__(tmp_path)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_adapter_accepts_checked_result_and_rejects_tampering(
    tmp_path, provider_fixture, monkeypatch
):
    request_path, _, video, request, manifest = provider_fixture
    request["backend"] = {
        "name": "projectm",
        "version": LOCK["version"],
        "commit": LOCK["commit"],
        "integration_patch_sha256": integration_identity(),
    }
    write_json(request_path, request)
    checkout = tmp_path / "checkout"
    build = tmp_path / "build"
    checkout.mkdir()
    build.mkdir()
    monkeypatch.setattr(projectm, "projectm_doctor", lambda *_: {"ready": True})
    real_run = subprocess.run

    def fake_run(command, **kwargs):
        if not command[1].endswith("scripts/projectm_render.py"):
            return real_run(command, **kwargs)
        output = Path(command[command.index("--output") + 1])
        output.mkdir()
        shutil.copy2(video, output / "video.mp4")
        produced = manifest.copy()
        produced.update(
            backend=request["backend"],
            request={
                "path": str(request_path.relative_to(output, walk_up=True)),
                "sha256": sha256_file(request_path),
            },
            video={"path": "video.mp4", "sha256": sha256_file(output / "video.mp4")},
        )
        write_json(output / "provider-manifest.json", produced)
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "status": "completed",
                    "manifest": str(output / "provider-manifest.json"),
                    "video": str(output / "video.mp4"),
                    "video_sha256": produced["video"]["sha256"],
                }
            ),
            "",
        )

    monkeypatch.setattr(projectm.subprocess, "run", fake_run)
    output = tmp_path / "accepted"
    result = projectm.run_projectm(request_path, output, checkout=checkout, build=build)
    assert result["video_sha256"] == sha256_file(output / "video.mp4")

    def tampered_run(command, **kwargs):
        reply = fake_run(command, **kwargs)
        output = Path(command[command.index("--output") + 1])
        (output / "video.mp4").write_bytes(b"tampered")
        return reply

    monkeypatch.setattr(projectm.subprocess, "run", tampered_run)
    rejected = tmp_path / "rejected"
    with pytest.raises(projectm.ProjectMAdapterError) as error:
        projectm.run_projectm(request_path, rejected, checkout=checkout, build=build)
    assert error.value.code == "projectm_invalid_result"
    assert not rejected.exists()

    def peer_run(command, **_kwargs):
        output = Path(command[command.index("--output") + 1])
        output.mkdir()
        (output / "peer-result").write_text("peer", encoding="utf-8")
        return subprocess.CompletedProcess(command, 5, '{"status":"failed"}', "")

    monkeypatch.setattr(projectm.subprocess, "run", peer_run)
    competing = tmp_path / "competing"
    with pytest.raises(projectm.ProjectMAdapterError) as error:
        projectm.run_projectm(request_path, competing, checkout=checkout, build=build)
    assert error.value.code == "projectm_render_failed"
    assert (competing / "peer-result").read_text(encoding="utf-8") == "peer"


def test_adapter_rejects_backend_before_launch(tmp_path, provider_fixture):
    request_path, _, _, _, _ = provider_fixture
    with pytest.raises(projectm.ProjectMAdapterError) as error:
        projectm.run_projectm(request_path, tmp_path / "result")
    assert error.value.code == "projectm_lock_mismatch"
