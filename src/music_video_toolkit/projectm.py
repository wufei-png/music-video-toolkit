"""MVT subprocess adapter for the bounded projectM provider job."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .provider import ProviderError, validate_provider_request, validate_provider_result

ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = ROOT / "scripts/projectm_env.py"
RENDER_SCRIPT = ROOT / "scripts/projectm_render.py"


class ProjectMAdapterError(Exception):
    def __init__(self, code: str, details: object, exit_code: int = 4):
        super().__init__(str(details))
        self.code = code
        self.details = details
        self.exit_code = exit_code


def configured_runtime(
    checkout: Path | None = None, build: Path | None = None
) -> tuple[Path | None, Path | None]:
    selected_checkout = checkout or os.environ.get("MVT_PROJECTM_CHECKOUT")
    selected_build = build or os.environ.get("MVT_PROJECTM_BUILD")
    return (
        Path(selected_checkout).expanduser().resolve() if selected_checkout else None,
        Path(selected_build).expanduser().resolve() if selected_build else None,
    )


def projectm_doctor(checkout: Path | None = None, build: Path | None = None) -> dict[str, object]:
    selected_checkout, selected_build = configured_runtime(checkout, build)
    result: dict[str, object] = {
        "checkout": str(selected_checkout) if selected_checkout else None,
        "build": str(selected_build) if selected_build else None,
        "state": "not_installed",
        "ready": False,
    }
    if selected_checkout is None or not selected_checkout.is_dir():
        return result
    result["state"] = "installed"
    if selected_build is None or not selected_build.is_dir() or not CHECK_SCRIPT.is_file():
        return result
    tools = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe")}
    if not all(tools.values()):
        result["reason"] = {"missing_tools": tools}
        return result
    checked = subprocess.run(
        [
            sys.executable,
            str(CHECK_SCRIPT),
            "check",
            "--checkout",
            str(selected_checkout),
            "--build",
            str(selected_build),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if checked.returncode:
        result["reason"] = checked.stderr.strip()
        return result
    result.update(state="ready", ready=True)
    return result


def run_projectm(
    request_path: Path,
    output: Path,
    *,
    checkout: Path | None = None,
    build: Path | None = None,
) -> dict[str, object]:
    request_path = request_path.resolve()
    output = output.resolve()
    try:
        request = validate_provider_request(request_path)
    except ProviderError as exc:
        raise ProjectMAdapterError(exc.code, exc.details) from exc
    try:
        from .projectm_provider import LOCK, integration_identity

        matches = (
            request.backend.name == "projectm"
            and request.backend.version == LOCK["version"]
            and request.backend.commit == LOCK["commit"]
            and request.backend.integration_patch_sha256 == integration_identity()
        )
    except OSError as exc:
        raise ProjectMAdapterError("projectm_not_installed", str(exc)) from exc
    if not matches:
        raise ProjectMAdapterError("projectm_lock_mismatch", "request backend differs from pin")
    if output.exists() or not output.parent.is_dir():
        raise ProjectMAdapterError("invalid_provider_output", str(output))
    selected_checkout, selected_build = configured_runtime(checkout, build)
    state = projectm_doctor(selected_checkout, selected_build)
    if not state["ready"] or selected_checkout is None or selected_build is None:
        raise ProjectMAdapterError("projectm_not_ready", state)
    child = subprocess.run(
        [
            sys.executable,
            str(RENDER_SCRIPT),
            "--request",
            str(request_path),
            "--output",
            str(output),
            "--checkout",
            str(selected_checkout),
            "--build",
            str(selected_build),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        lines = child.stdout.strip().splitlines()
        if len(lines) != 1:
            raise ValueError("expected one JSON result")
        report = json.loads(lines[0])
        if not isinstance(report, dict):
            raise ValueError("result is not an object")
    except ValueError as exc:
        raise ProjectMAdapterError(
            "projectm_invalid_result", {"stdout": child.stdout, "stderr": child.stderr}
        ) from exc
    if child.returncode or report.get("status") != "completed":
        raise ProjectMAdapterError("projectm_render_failed", report, 5)
    manifest_path = output / "provider-manifest.json"
    video_path = output / "video.mp4"
    if report.get("manifest") != str(manifest_path) or report.get("video") != str(video_path):
        raise ProjectMAdapterError("projectm_invalid_result", report, 5)
    try:
        manifest = validate_provider_result(request_path, manifest_path)
        if report.get("video_sha256") != manifest.video.sha256:
            raise ValueError("reported video hash differs")
    except (OSError, ValueError, ProviderError) as exc:
        if output.is_dir():
            shutil.rmtree(output)
        raise ProjectMAdapterError("projectm_invalid_result", str(exc), 5) from exc
    return {"ok": True, **report}
