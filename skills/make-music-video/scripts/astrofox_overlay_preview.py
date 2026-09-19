"""Layer checked silent Astrofox clips over one completed built-in preview."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def checked(path: Path, expected: str) -> Path:
    if not path.is_file() or sha(path) != expected:
        raise ValueError(f"missing or changed input: {path}")
    return path


def bounded(value: object, label: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return number


def make_preview(config_path: Path, output: Path) -> Path:
    config = read(config_path)
    if config.get("schema_version") != "0.1":
        raise ValueError("expected overlay config schema 0.1")
    if output.exists():
        raise ValueError("output directory already exists")
    config_dir = config_path.resolve().parent
    base_path = (config_dir / config["base_preview_manifest"]).resolve()
    base = read(base_path)
    if base["status"] != "completed":
        raise ValueError("base preview is incomplete")
    profile = base.get("profile", config.get("profile"))
    if profile is None or (
        "profile" in base and "profile" in config and base["profile"] != config["profile"]
    ):
        raise ValueError("base/config profile is missing or different")
    if (profile["width"], profile["height"], profile["fps_num"], profile["fps_den"]) not in (
        (1920, 1080, 30, 1),
        (1080, 1920, 30, 1),
    ):
        raise ValueError("unsupported output profile")
    width, height = profile["width"], profile["height"]
    up_px = int(bounded(config["up_px"], "up_px", 0, height))
    if up_px != config["up_px"]:
        raise ValueError("up_px must be an integer")
    mix = bounded(config["mix"], "mix", 0, 1)
    subtract = config["background_subtract_rgb"]
    if not isinstance(subtract, list) or len(subtract) != 3:
        raise ValueError("background_subtract_rgb must contain three channels")
    rgb = [int(bounded(channel, "background channel", 0, 255)) for channel in subtract]
    if rgb != subtract:
        raise ValueError("background channels must be integers")
    provider_refs = config["provider_manifests"]
    ranges = base["ranges"]
    if not isinstance(provider_refs, list) or len(provider_refs) != len(ranges):
        raise ValueError("one provider manifest is required per base range")
    source_outputs = base["outputs"][: len(ranges)]
    if len(source_outputs) != len(ranges):
        raise ValueError("base preview has missing clips")
    filter_graph = (
        "[1:v]format=rgb24,"
        f"lutrgb=r='max(0,val-{rgb[0]})':g='max(0,val-{rgb[1]})':b='max(0,val-{rgb[2]})',"
        f"pad={width}:{height + up_px}:0:0:black,crop={width}:{height}:0:{up_px},"
        "format=gbrp[fx];[0:v]format=gbrp[base];"
        f"[base][fx]blend=all_expr='min(255,A+{mix:g}*B)',format=yuv420p[v]"
    )
    inputs = {
        "preview_request": sha(config_path),
        "preview_adapter": sha(Path(__file__)),
        "base_preview": sha(base_path),
    }
    jobs = []
    for index, reference in enumerate(provider_refs):
        source = source_outputs[index]
        base_clip = checked(base_path.parent / source["path"], source["sha256"])
        provider_path = (config_dir / reference).resolve()
        provider = read(provider_path)
        if (
            provider["status"] != "completed"
            or provider["backend"]["name"] != "astrofox"
            or provider["source_sha256"] != base["canonical_audio_sha256"]
            or provider["range"] != ranges[index]
            or provider["profile"] != profile
        ):
            raise ValueError(f"provider/base mismatch: {provider_path}")
        fx_clip = checked(
            provider_path.parent / provider["video"]["path"], provider["video"]["sha256"]
        )
        inputs[f"base_clip_{index + 1}"] = source["sha256"]
        inputs[f"provider_manifest_{index + 1}"] = sha(provider_path)
        inputs[f"provider_clip_{index + 1}"] = provider["video"]["sha256"]
        jobs.append((base_clip, fx_clip, ranges[index]))

    output.mkdir(parents=True)
    outputs = []
    for index, (base_clip, fx_clip, span) in enumerate(jobs, 1):
        frames = (
            (span["end_sample"] - span["start_sample"])
            * profile["fps_num"]
            // (48000 * profile["fps_den"])
        )
        if (
            frames <= 0
            or frames * 48000 * profile["fps_den"]
            != (span["end_sample"] - span["start_sample"]) * profile["fps_num"]
        ):
            raise ValueError("range is not on the frame grid")
        destination = output / f"{index:02d}-overlay.mp4"
        command = [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(base_clip),
            "-i",
            str(fx_clip),
            "-filter_complex",
            filter_graph,
            "-map",
            "[v]",
            "-map",
            "0:a:0",
            "-frames:v",
            str(frames),
            "-t",
            f"{frames * profile['fps_den'] / profile['fps_num']:.9f}",
            "-fps_mode",
            "cfr",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(destination),
        ]
        print(f"Rendering {destination.name}", flush=True)
        subprocess.run(command, check=True)
        outputs.append({"path": destination.name, "sha256": sha(destination)})
    version = subprocess.run(
        ["ffmpeg", "-version"], check=True, text=True, capture_output=True
    ).stdout.splitlines()[0]
    identity = json.dumps(
        {"inputs": inputs, "outputs": outputs}, sort_keys=True, separators=(",", ":")
    )
    manifest = {
        "schema_version": "0.1",
        "cache_key": hashlib.sha256(identity.encode()).hexdigest(),
        "status": "completed",
        "source_sha256": base["source_sha256"],
        "canonical_audio_sha256": base["canonical_audio_sha256"],
        "profile": profile,
        "inputs": inputs,
        "seed": base["seed"],
        "environment": {"ffmpeg": version, "adapter": "checked-base-preview-plus-silent-Astrofox"},
        "ranges": ranges,
        "outputs": outputs,
    }
    path = output / "preview.render.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(make_preview(args.config, args.output))
    except (
        KeyError,
        IndexError,
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        parser.exit(2, f"Astrofox overlay preview: {exc}\n")


if __name__ == "__main__":
    main()
