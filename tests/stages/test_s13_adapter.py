"""The Python adapter treats Astrofox as an untrusted external process."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from test_s13_protocol import fake_provider as protocol_fixture

from music_video_toolkit import astrofox
from music_video_toolkit.project import sha256_file


@pytest.fixture
def provider_fixture(tmp_path):
    return protocol_fixture.__wrapped__(tmp_path)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_adapter_accepts_checked_external_result(tmp_path, provider_fixture, monkeypatch):
    request_path, manifest_path, video, request, manifest = provider_fixture
    lock = json.loads(astrofox.LOCK_PATH.read_text(encoding="utf-8"))
    request["backend"] = {
        "name": "astrofox",
        "version": "2.0.0",
        "commit": lock["commit"],
        "integration_patch_sha256": lock["patch_stack_sha256"],
    }
    write_json(request_path, request)
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    monkeypatch.setattr(astrofox, "astrofox_doctor", lambda _: {"state": "ready", "ready": True})
    real_run = subprocess.run

    def fake_run(command, **_kwargs):
        if not command[1].endswith("scripts/astrofox-render.mjs"):
            return real_run(command, **_kwargs)
        assert command[1].endswith("scripts/astrofox-render.mjs")
        output = Path(command[-1])
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
        )

    monkeypatch.setattr(astrofox.subprocess, "run", fake_run)
    output = tmp_path / "accepted"
    result = astrofox.render_astrofox(request_path, output, checkout=checkout)
    assert result["video_sha256"] == sha256_file(output / "video.mp4")
    assert (checkout / ".git/mvt-proven.json").is_file()

    def tampered_run(command, **kwargs):
        reply = fake_run(command, **kwargs)
        output = Path(command[-1])
        (output / "video.mp4").write_bytes(b"tampered")
        return reply

    monkeypatch.setattr(astrofox.subprocess, "run", tampered_run)
    rejected = tmp_path / "rejected"
    with pytest.raises(astrofox.AstrofoxError) as error:
        astrofox.render_astrofox(request_path, rejected, checkout=checkout)
    assert error.value.code == "astrofox_invalid_result"
    assert not rejected.exists()

    def losing_run(command, **_kwargs):
        peer_output = Path(command[-1])
        peer_output.mkdir()
        (peer_output / "peer-result").write_text("completed by another job", encoding="utf-8")
        return subprocess.CompletedProcess(command, 5, '{"status":"failed","code":"output_busy"}')

    monkeypatch.setattr(astrofox.subprocess, "run", losing_run)
    competing = tmp_path / "competing"
    with pytest.raises(astrofox.AstrofoxError) as error:
        astrofox.render_astrofox(request_path, competing, checkout=checkout)
    assert error.value.code == "astrofox_render_failed"
    assert (competing / "peer-result").read_text(encoding="utf-8") == "completed by another job"


def test_adapter_rejects_backend_before_launch(tmp_path, provider_fixture):
    request_path, _, _, _, _ = provider_fixture
    with pytest.raises(astrofox.AstrofoxError) as error:
        astrofox.render_astrofox(request_path, tmp_path / "result")
    assert error.value.code == "astrofox_lock_mismatch"
