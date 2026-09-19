"""Exercise the real pinned projectM CLI with synthetic public inputs."""

import argparse
import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

from music_video_toolkit.provider import validate_provider_result

ROOT = Path(__file__).resolve().parents[1]


def run_job(checkout: Path, build: Path, request: Path, output: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/projectm_render.py"),
            "--request",
            str(request),
            "--output",
            str(output),
            "--checkout",
            str(checkout),
            "--build",
            str(build),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, json.loads(result.stdout.strip())


def invoke(checkout: Path, build: Path, request: Path, output: Path) -> dict:
    code, report = run_job(checkout, build, request, output)
    if code or report.get("status") != "completed":
        raise AssertionError(f"projectM render failed: {report}")
    return report


def invoke_mvt(checkout: Path, build: Path, request: Path, output: Path) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "music_video_toolkit.cli",
            "provider",
            "projectm",
            "--request",
            str(request),
            "--output",
            str(output),
            "--checkout",
            str(checkout),
            "--build",
            str(build),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(f"MVT adapter failed: {result.stderr}")
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    write_fixture = runpy.run_path(str(ROOT / "tests/fixtures/s14/create_fixture.py"))[
        "write_fixture"
    ]
    with tempfile.TemporaryDirectory(prefix="mvt-projectm-check-") as temporary:
        directory = Path(temporary)
        request = write_fixture(directory / "input")
        first = invoke(args.checkout, args.build, request, directory / "first")
        second = invoke(args.checkout, args.build, request, directory / "second")
        adapter = invoke_mvt(args.checkout, args.build, request, directory / "adapter")
        for name in ("first", "second", "adapter"):
            validate_provider_result(request, directory / name / "provider-manifest.json")
        if len({first["video_sha256"], second["video_sha256"], adapter["video_sha256"]}) != 1:
            raise AssertionError("same-environment projectM output differs")
        code, conflict = run_job(args.checkout, args.build, request, directory / "first")
        if code == 0 or conflict.get("code") != "invalid_provider_output":
            raise AssertionError(f"completed output was not protected: {conflict}")
        locked_output = directory / "locked"
        output_lock = directory / ".locked.mvt-lock"
        output_lock.mkdir()
        code, locked = run_job(args.checkout, args.build, request, locked_output)
        output_lock.rmdir()
        if code == 0 or locked.get("code") != "provider_output_locked" or locked_output.exists():
            raise AssertionError(f"contended output was not rejected: {locked}")
        (request.parent / "mvt-wave.milk").write_text("tampered\n", encoding="utf-8")
        rejected_output = directory / "tampered"
        code, rejected = run_job(args.checkout, args.build, request, rejected_output)
        if (
            code == 0
            or rejected.get("code") != "provider_hash_mismatch"
            or rejected_output.exists()
        ):
            raise AssertionError(f"tampered preset was not rejected: {rejected}")
        print(json.dumps({"ok": True, "video_sha256": first["video_sha256"]}))


if __name__ == "__main__":
    main()
