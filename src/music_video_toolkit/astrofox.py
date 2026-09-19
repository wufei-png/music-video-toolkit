"""External-process Astrofox provider adapter; no application internals are imported."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .project import sha256_file
from .provider import ProviderError, validate_provider_request, validate_provider_result

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / "integrations/astrofox/lock.json"
CHECK_SCRIPT = ROOT / "scripts/astrofox_env.py"


class AstrofoxError(Exception):
    def __init__(self, code: str, details: object, exit_code: int = 4):
        super().__init__(str(details))
        self.code = code
        self.details = details
        self.exit_code = exit_code


def configured_checkout(checkout: Path | None = None) -> Path | None:
    selected = checkout or os.environ.get("MVT_ASTROFOX_CHECKOUT")
    return Path(selected).expanduser().resolve() if selected else None


def _source_check(checkout: Path) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "check", "--checkout", str(checkout)],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0, result.stderr.strip()


def astrofox_doctor(checkout: Path | None = None) -> dict[str, object]:
    selected = configured_checkout(checkout)
    result: dict[str, object] = {
        "checkout": str(selected) if selected else None,
        "state": "not_installed",
        "ready": False,
        "proven": False,
    }
    if selected is None or not selected.is_dir():
        return result
    result["state"] = "installed"
    valid, reason = _source_check(selected)
    if not valid:
        result["reason"] = reason
        return result
    required = [
        selected / "out/index.html",
        selected / "node_modules/.bin/electron",
        selected / "scripts/astrofox-render.mjs",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    tools = {name: shutil.which(name) for name in ("node", "ffmpeg", "ffprobe")}
    if missing or not all(tools.values()):
        result["reason"] = {"missing_files": missing, "tools": tools}
        return result
    result.update(state="ready", ready=True)
    proof_path = selected / ".git/mvt-proven.json"
    if proof_path.is_file():
        try:
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            manifest_path = Path(proof["manifest"])
            request_path = Path(proof["request"])
            if (
                proof["manifest_sha256"] == sha256_file(manifest_path)
                and proof["patch_stack_sha256"]
                == json.loads(LOCK_PATH.read_text(encoding="utf-8"))["patch_stack_sha256"]
            ):
                validate_provider_result(request_path, manifest_path)
                result.update(state="proven", proven=True, proof=str(manifest_path))
        except (OSError, ValueError, KeyError, ProviderError):
            result["proof_stale"] = True
    return result


def render_astrofox(
    request_path: Path, output: Path, *, checkout: Path | None = None
) -> dict[str, object]:
    request_path = request_path.resolve()
    output = output.resolve()
    try:
        request = validate_provider_request(request_path)
    except ProviderError as exc:
        raise AstrofoxError(exc.code, exc.details) from exc
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    if (
        request.backend.name != "astrofox"
        or request.backend.commit != lock["commit"]
        or request.backend.integration_patch_sha256 != lock["patch_stack_sha256"]
    ):
        raise AstrofoxError("astrofox_lock_mismatch", "request backend differs from pinned lock")
    if output.exists() or not output.parent.is_dir():
        raise AstrofoxError("invalid_provider_output", str(output))
    selected = configured_checkout(checkout)
    state = astrofox_doctor(selected)
    if not state["ready"] or selected is None:
        raise AstrofoxError("astrofox_not_ready", state)
    command = [
        str(shutil.which("node")),
        str(selected / "scripts/astrofox-render.mjs"),
        "--request",
        str(request_path),
        "--output",
        str(output),
    ]
    try:
        process = subprocess.run(
            command, cwd=selected, text=True, stdout=subprocess.PIPE, stderr=None, check=False
        )
        lines = process.stdout.strip().splitlines()
        if len(lines) != 1:
            raise AstrofoxError("astrofox_invalid_result", {"stdout": process.stdout})
        report = json.loads(lines[0])
        if not isinstance(report, dict):
            raise AstrofoxError("astrofox_invalid_result", report, 5)
        if process.returncode != 0 or report.get("status") != "completed":
            raise AstrofoxError("astrofox_render_failed", report, 5)
        manifest_path = output / "provider-manifest.json"
        video_path = output / "video.mp4"
        if report.get("manifest") != str(manifest_path) or report.get("video") != str(video_path):
            raise AstrofoxError("astrofox_invalid_result", report, 5)
        manifest = validate_provider_result(request_path, manifest_path)
        if report.get("video_sha256") != manifest.video.sha256:
            raise AstrofoxError("astrofox_invalid_result", "reported video hash differs", 5)
    except (ValueError, OSError, ProviderError) as exc:
        if output.is_dir():
            shutil.rmtree(output)
        raise AstrofoxError("astrofox_invalid_result", str(exc), 5) from exc
    except AstrofoxError:
        if output.is_dir():
            shutil.rmtree(output)
        raise
    proof = {
        "request": str(request_path),
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "patch_stack_sha256": lock["patch_stack_sha256"],
    }
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=selected / ".git", prefix=".mvt-proof-", delete=False
    ) as stream:
        json.dump(proof, stream, sort_keys=True)
        proof_temporary = Path(stream.name)
    proof_temporary.replace(selected / ".git/mvt-proven.json")
    return {
        "ok": True,
        "provider": "astrofox",
        "request": str(request_path),
        "manifest": str(manifest_path),
        "video": str(video_path),
        "video_sha256": manifest.video.sha256,
    }
