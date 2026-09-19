"""Exercise the pinned Astrofox CLI with public synthetic media."""

import argparse
import json
import runpy
import subprocess
import tempfile
from pathlib import Path

from music_video_toolkit.provider import validate_provider_result

ROOT = Path(__file__).resolve().parents[1]


def invoke(checkout: Path, request: Path, output: Path) -> tuple[subprocess.CompletedProcess, dict]:
    result = subprocess.run(
        [
            "node",
            str(checkout / "scripts/astrofox-render.mjs"),
            "--request",
            str(request),
            "--output",
            str(output),
        ],
        cwd=checkout,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    lines = result.stdout.strip().splitlines()
    if len(lines) != 1:
        raise AssertionError(f"expected one JSON result: {result.stdout!r} {result.stderr!r}")
    return result, json.loads(lines[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    write_fixture = runpy.run_path(str(ROOT / "tests/fixtures/s13/create_fixture.py"))[
        "write_fixture"
    ]
    with tempfile.TemporaryDirectory(prefix="mvt-astrofox-render-") as temporary:
        directory = Path(temporary)
        request = write_fixture(directory / "fixture", with_plugin=True, with_asset=True)
        hashes = []
        for index in range(2):
            output = directory / f"result-{index}"
            result, report = invoke(checkout, request, output)
            if result.returncode != 0 or report.get("status") != "completed":
                raise AssertionError(f"render failed: {report} {result.stderr}")
            manifest = validate_provider_result(request, output / "provider-manifest.json")
            hashes.append(manifest.video.sha256)
        if hashes[0] != hashes[1]:
            raise AssertionError(f"video bytes differ across two identical renders: {hashes}")

        bad_output = directory / "failed"
        bad_request = json.loads(request.read_text(encoding="utf-8"))
        bad_request["backend"]["integration_patch_sha256"] = "0" * 64
        bad_path = request.parent / "bad-request.json"
        bad_path.write_text(json.dumps(bad_request), encoding="utf-8")
        result, report = invoke(checkout, bad_path, bad_output)
        if result.returncode == 0 or report.get("status") != "failed" or bad_output.exists():
            raise AssertionError(f"bad lock accepted: {report}")

        cancelled_output = directory / "cancelled"
        long_request = json.loads(request.read_text(encoding="utf-8"))
        long_request["source"]["duration_samples"] = 480000
        long_request["range"]["end_sample"] = 480000
        long_path = request.parent / "long-request.json"
        long_path.write_text(json.dumps(long_request), encoding="utf-8")
        # The long range is intentionally invalid against the one-second audio. The
        # controller must reject it without installing any output.
        result, report = invoke(checkout, long_path, cancelled_output)
        if result.returncode == 0 or report.get("status") != "failed" or cancelled_output.exists():
            raise AssertionError(f"invalid range accepted: {report}")
        if list(directory.glob(".*.tmp-*")):
            raise AssertionError("temporary provider output was retained")
    print(f"Astrofox render: silent CFR, plugin/asset, stable bytes {hashes[0]}, failure cleanup")


if __name__ == "__main__":
    main()
