"""Run the pinned hidden-renderer and input-denial checks with public synthetic data."""

import argparse
import json
import runpy
import subprocess
import tempfile
from pathlib import Path

from music_video_toolkit.project import sha256_file

ROOT = Path(__file__).resolve().parents[1]


def invoke(checkout: Path, request: Path, *, expected: str) -> dict:
    result = subprocess.run(
        [
            str(checkout / "node_modules/.bin/electron"),
            str(checkout / "electron/main.mjs"),
            "--mvt-job",
            str(request),
            "--mvt-smoke",
        ],
        cwd=checkout,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    lines = result.stdout.strip().splitlines()
    if len(lines) != 1:
        raise AssertionError(f"expected one JSON result, got stdout={result.stdout!r}")
    report = json.loads(lines[0])
    if report["status"] != expected or (result.returncode == 0) != (expected == "ready"):
        raise AssertionError(
            f"unexpected result: exit={result.returncode} report={report} stderr={result.stderr}"
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    if not (checkout / "out/index.html").is_file():
        parser.error("build the pinned Astrofox renderer before running smoke checks")
    write_fixture = runpy.run_path(str(ROOT / "tests/fixtures/s13/create_fixture.py"))[
        "write_fixture"
    ]
    with tempfile.TemporaryDirectory(prefix="mvt-astrofox-s13-") as temporary:
        request_path = write_fixture(Path(temporary) / "synthetic")
        ready = invoke(checkout, request_path, expected="ready")
        if ready.get("blocked_network_requests", 0) < 1:
            raise AssertionError("the Electron job did not prove its network guard")

        audio = request_path.parent / "canonical.wav"
        original_audio = audio.read_bytes()
        audio.write_bytes(original_audio + b"tampered")
        assert invoke(checkout, request_path, expected="failed")["code"] == "startup_failed"
        audio.write_bytes(original_audio)

        project_path = request_path.parent / "project.json"
        original_project = project_path.read_text(encoding="utf-8")
        project = json.loads(original_project)
        project["snapshot"]["scenes"][0]["displays"][0]["properties"]["src"] = (
            "https://example.invalid/image.png"
        )
        project_path.write_text(json.dumps(project), encoding="utf-8")
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request["project"]["sha256"] = sha256_file(project_path)
        request_path.write_text(json.dumps(request), encoding="utf-8")
        assert invoke(checkout, request_path, expected="failed")["code"] == "startup_failed"

        project_path.write_text(original_project, encoding="utf-8")
        plugin_path = request_path.parent / "remote-plugin.json"
        plugin_path.write_text(
            json.dumps(
                {
                    "sourceUrl": "https://example.invalid/plugin.json",
                    "dev": False,
                    "manifest": {"name": "@synthetic/remote", "permissions": []},
                    "files": {"index.js": "export default 1"},
                    "integrity": {"index.js": "sha384-invalid"},
                }
            ),
            encoding="utf-8",
        )
        request["project"]["sha256"] = sha256_file(project_path)
        request["plugins"] = [{"path": plugin_path.name, "sha256": sha256_file(plugin_path)}]
        request_path.write_text(json.dumps(request), encoding="utf-8")
        assert invoke(checkout, request_path, expected="failed")["code"] == "startup_failed"
        plugin_path.write_text("tampered", encoding="utf-8")
        assert invoke(checkout, request_path, expected="failed")["code"] == "startup_failed"
    print("Astrofox headless smoke: ready, network blocked, invalid media/plugin/hash rejected")


if __name__ == "__main__":
    main()
