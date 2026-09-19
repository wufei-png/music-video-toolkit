"""Add a checked Astrofox spectrum to a completed full-song MVT render."""

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
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def checked(path: Path, expected: str) -> Path:
    path = path.resolve()
    if not path.is_file() or sha(path) != expected:
        raise ValueError(f"missing or changed input: {path}")
    return path


def bounded(value: object, label: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return result


def probe(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=codec_name,pix_fmt,width,height,r_frame_rate,nb_read_frames",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    streams = json.loads(result.stdout)["streams"]
    if len(streams) != 1:
        raise ValueError(f"expected one video stream: {path}")
    return streams[0]


def make_full(config_path: Path, output: Path) -> Path:
    config_path = config_path.resolve()
    output = output.resolve()
    config = read(config_path)
    if config.get("schema_version") != "0.1" or output.exists():
        raise ValueError("expected config schema 0.1 and a new output directory")
    root = config_path.parent
    base_path = (root / config["base_render_manifest"]).resolve()
    provider_path = (root / config["provider_manifest"]).resolve()
    source_path = (root / config["source_record"]).resolve()
    base, provider, source = read(base_path), read(provider_path), read(source_path)
    if base["status"] != "completed" or provider["status"] != "completed":
        raise ValueError("base render and Astrofox provider must be completed")
    if len(base["ranges"]) != 1 or len(base["outputs"]) != 1:
        raise ValueError("expected one full-song base output")
    profile = config["profile"]
    if (profile["width"], profile["height"], profile["fps_num"], profile["fps_den"]) not in (
        (1920, 1080, 30, 1),
        (1080, 1920, 30, 1),
    ):
        raise ValueError("unsupported output profile")
    frame_samples = 48000 * profile["fps_den"]
    duration = source["canonical"]["duration_samples"]
    if (
        base["ranges"][0] != {"start_sample": 0, "end_sample": duration}
        or base["inputs"]["source_record"] != sha(source_path)
        or base["source_sha256"] != source["original"]["sha256"]
        or provider["backend"]["name"] != "astrofox"
        or provider["source_sha256"] != source["canonical"]["sha256"]
        or provider["profile"] != profile
        or provider["range"]["start_sample"] != 0
    ):
        raise ValueError("source, range, backend or profile identity differs")
    canonical_path = (source_path.parent / source["canonical"]["path"]).resolve()
    checked(canonical_path, source["canonical"]["sha256"])
    provider_end = (
        duration * profile["fps_num"] // frame_samples * frame_samples // profile["fps_num"]
    )
    if provider["range"]["end_sample"] != provider_end:
        raise ValueError("provider must end at the last complete frame")
    base_frames = math.ceil(duration * profile["fps_num"] / frame_samples)
    provider_frames = provider_end * profile["fps_num"] // frame_samples
    tail_frames = base_frames - provider_frames
    if tail_frames not in (0, 1) or provider["probe"]["frame_count"] != provider_frames:
        raise ValueError("expected zero or one final held frame")
    base_video = checked(
        base_path.parent / base["outputs"][0]["path"], base["outputs"][0]["sha256"]
    )
    provider_video = checked(
        provider_path.parent / provider["video"]["path"], provider["video"]["sha256"]
    )
    base_probe, provider_probe = probe(base_video), probe(provider_video)
    for media_probe, count in ((base_probe, base_frames), (provider_probe, provider_frames)):
        if (
            media_probe["codec_name"] != "h264"
            or media_probe["pix_fmt"] != "yuv420p"
            or media_probe["width"] != profile["width"]
            or media_probe["height"] != profile["height"]
            or media_probe["r_frame_rate"] != "30/1"
            or int(media_probe["nb_read_frames"]) != count
        ):
            raise ValueError("video probe differs from profile or expected frame count")
    up_px = int(bounded(config["up_px"], "up_px", 0, profile["height"]))
    if up_px != config["up_px"]:
        raise ValueError("up_px must be an integer")
    mix = bounded(config["mix"], "mix", 0, 1)
    rgb = config["background_subtract_rgb"]
    if (
        not isinstance(rgb, list)
        or len(rgb) != 3
        or any(int(bounded(value, "background channel", 0, 255)) != value for value in rgb)
    ):
        raise ValueError("background_subtract_rgb must have three integer channels")
    width, height = profile["width"], profile["height"]
    hold = f"tpad=stop_mode=clone:stop={tail_frames}," if tail_frames else ""
    filter_graph = (
        "[1:v]format=rgb24,"
        f"lutrgb=r='max(0,val-{rgb[0]})':g='max(0,val-{rgb[1]})':b='max(0,val-{rgb[2]})',"
        f"{hold}pad={width}:{height + up_px}:0:0:black,crop={width}:{height}:0:{up_px},"
        "format=gbrp[fx];[0:v]format=gbrp[base];"
        f"[base][fx]blend=all_expr='min(255,A+{mix:g}*B)',format=yuv420p[v]"
    )
    name = config["output_name"]
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".mp4"):
        raise ValueError("output_name must be one MP4 basename")
    output.mkdir(parents=True)
    video = output / name
    command = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(base_video),
        "-i",
        str(provider_video),
        "-filter_complex",
        filter_graph,
        "-map",
        "[v]",
        "-map",
        "0:a:0",
        "-frames:v",
        str(base_frames),
        "-t",
        f"{base_frames / 30:.9f}",
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
        str(video),
    ]
    subprocess.run(command, check=True)
    actual = probe(video)
    if int(actual["nb_read_frames"]) != base_frames:
        raise ValueError("composite output frame count differs from base")
    inputs = {
        "render_request": sha(config_path),
        "render_adapter": sha(Path(__file__)),
        "source_record": sha(source_path),
        "base_render": sha(base_path),
        "base_clip": sha(base_video),
        "provider_manifest": sha(provider_path),
        "provider_clip": sha(provider_video),
    }
    output_ref = {"path": name, "sha256": sha(video)}
    identity = json.dumps(
        {"inputs": inputs, "output": output_ref}, sort_keys=True, separators=(",", ":")
    )
    ffmpeg = subprocess.run(
        ["ffmpeg", "-version"], check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]
    manifest = {
        "schema_version": "0.1",
        "cache_key": hashlib.sha256(identity.encode()).hexdigest(),
        "status": "completed",
        "source_sha256": base["source_sha256"],
        "canonical_audio_sha256": provider["source_sha256"],
        "profile": profile,
        "inputs": inputs,
        "seed": base["seed"],
        "environment": {"ffmpeg": ffmpeg, "adapter": "full-base-plus-silent-Astrofox"},
        "ranges": base["ranges"],
        "outputs": [output_ref],
    }
    manifest_path = output / f"{name}.render.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(make_full(args.config, args.output))
    except (
        KeyError,
        IndexError,
        OSError,
        TypeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        parser.exit(2, f"Astrofox full overlay: {exc}\n")


if __name__ == "__main__":
    main()
