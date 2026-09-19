"""Exercise the pinned Astrofox CLI with public synthetic media."""

import argparse
import json
import queue
import runpy
import signal
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

from music_video_toolkit.project import sha256_file
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
        export_module = json.dumps((checkout / "electron/mvt-export.mjs").as_uri())
        lock_test = f"""
import {{ prepareMvtOutput, discardMvtOutput }} from {export_module};
const output = {json.dumps(str(directory / "contended"))};
const first = prepareMvtOutput(output);
try {{
  try {{ prepareMvtOutput(output); throw new Error('second job acquired output lock'); }}
  catch (error) {{ if (error.code !== 'EEXIST') throw error; }}
}} finally {{ discardMvtOutput(first); }}
"""
        subprocess.run(
            ["node", "--input-type=module", "--eval", lock_test],
            cwd=checkout,
            capture_output=True,
            text=True,
            check=True,
        )
        if list(directory.glob(".*.mvt-lock")):
            raise AssertionError("provider output lock was retained")
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

        with wave.open(str(request.parent / "canonical.wav"), "rb") as source:
            frames = source.readframes(source.getnframes())
        extended_audio = request.parent / "extended.wav"
        with wave.open(str(extended_audio), "wb") as target:
            target.setnchannels(2)
            target.setsampwidth(3)
            target.setframerate(48000)
            target.writeframes(frames * 8)
        cancel_request = json.loads(request.read_text(encoding="utf-8"))
        cancel_request["source"].update(
            path=str(extended_audio), sha256=sha256_file(extended_audio), duration_samples=384000
        )
        cancel_request["canonical_audio"].update(
            path=str(extended_audio), sha256=sha256_file(extended_audio)
        )
        cancel_request["range"]["end_sample"] = 384000
        cancel_path = request.parent / "cancel-request.json"
        cancel_path.write_text(json.dumps(cancel_request), encoding="utf-8")
        active_output = directory / "active-cancel"
        process = subprocess.Popen(
            [
                "node",
                str(checkout / "scripts/astrofox-render.mjs"),
                "--request",
                str(cancel_path),
                "--output",
                str(active_output),
            ],
            cwd=checkout,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stderr is not None
        progress: queue.Queue[str] = queue.Queue()

        def read_progress() -> None:
            for line in process.stderr:
                if '"currentFrame":0' in line:
                    progress.put(line)

        reader = threading.Thread(target=read_progress, daemon=True)
        reader.start()
        try:
            progress.get(timeout=40)
            process.send_signal(signal.SIGINT)
            process.wait(timeout=40)
            assert process.stdout is not None
            stdout = process.stdout.read()
        except (queue.Empty, subprocess.TimeoutExpired):
            process.kill()
            process.wait()
            raise AssertionError("provider did not cancel after active video export") from None
        report = json.loads(stdout.strip())
        if (
            process.returncode == 0
            or report.get("code") != "cancelled"
            or active_output.exists()
            or (directory / ".active-cancel.mvt-lock").exists()
        ):
            raise AssertionError(f"active cancellation left output or lock: {report}")
        if list(directory.glob(".*.tmp-*")):
            raise AssertionError("temporary provider output was retained")
    print(
        f"Astrofox render: silent CFR, plugin/asset, stable bytes {hashes[0]}, "
        "failure cleanup, active cancellation and exclusive output lock"
    )


if __name__ == "__main__":
    main()
