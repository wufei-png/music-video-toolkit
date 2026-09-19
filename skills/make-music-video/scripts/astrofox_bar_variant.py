"""Create a hashable Astrofox bar-spectrum project variant without touching its source."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path

COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
BAR_DEFAULTS: dict[str, object] = {
    "color": ["#FFFFFF", "#FFFFFF"],
    "shadowColor": ["#333333", "#000000"],
    "shadowHeight": 100,
    "minFrequency": 0,
    "maxFrequency": 6000,
    "maxDecibels": -12,
    "smoothingTimeConstant": 0.5,
    "barWidth": -1,
    "barSpacing": -1,
    "barWidthAutoSize": 1,
    "barSpacingAutoSize": 1,
    "width": 770,
    "height": 240,
    "opacity": 1.0,
}


def positive(value: float, label: str, *, allow_zero: bool = False) -> float:
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{label} must be {'non-negative' if allow_zero else 'positive'}")
    return value


def bounded(value: float, label: str, low: float, high: float) -> float:
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_variant(args: argparse.Namespace) -> dict[str, object]:
    source = args.input.resolve()
    output = args.output.resolve()
    if source == output or output.exists():
        raise ValueError("output must be a new file separate from the source project")
    project = json.loads(source.read_text(encoding="utf-8"))
    if project.get("version") != "2.0.0" or project.get("snapshot", {}).get("version") != "2.0.0":
        raise ValueError("expected an Astrofox 2.0.0 project")
    displays = [
        display
        for scene in project["snapshot"]["scenes"]
        for display in scene.get("displays", [])
        if display.get("id") == args.display_id
    ]
    if len(displays) != 1 or displays[0].get("name") != "BarSpectrumDisplay":
        raise ValueError("display-id must select one BarSpectrumDisplay")
    properties = displays[0]["properties"]
    stage = project["snapshot"]["stage"]["properties"]
    stage_width = positive(float(stage["width"]), "stage width")
    stage_height = positive(float(stage["height"]), "stage height")
    changes: dict[str, object] = {}

    for key, top, bottom in (
        ("color", args.color_top, args.color_bottom),
        ("shadowColor", args.shadow_color_top, args.shadow_color_bottom),
    ):
        if top is not None or bottom is not None:
            current = properties.get(key, BAR_DEFAULTS[key])
            if not isinstance(current, list) or len(current) != 2:
                raise ValueError(f"{key} must be a two-color gradient")
            colors = [top or current[0], bottom or current[1]]
            if any(not isinstance(color, str) or not COLOR.fullmatch(color) for color in colors):
                raise ValueError(f"{key} colors must be six-digit hex values")
            changes[key] = colors
    if args.shadow_height is not None:
        changes["shadowHeight"] = bounded(args.shadow_height, "shadow-height", 0, stage_width)
    if args.min_frequency is not None:
        changes["minFrequency"] = bounded(args.min_frequency, "min-frequency", 0, 22000)
    if args.max_frequency is not None:
        changes["maxFrequency"] = bounded(args.max_frequency, "max-frequency", 0, 22000)
    minimum = float(
        changes.get("minFrequency", properties.get("minFrequency", BAR_DEFAULTS["minFrequency"]))
    )
    maximum = float(
        changes.get("maxFrequency", properties.get("maxFrequency", BAR_DEFAULTS["maxFrequency"]))
    )
    if minimum >= maximum:
        raise ValueError("min-frequency must be lower than max-frequency")
    if args.max_decibels is not None:
        changes["maxDecibels"] = bounded(args.max_decibels, "max-decibels", -40, 0)
    if args.smoothing is not None:
        changes["smoothingTimeConstant"] = bounded(args.smoothing, "smoothing", 0, 0.99)
    if args.bar_width is not None:
        changes.update(
            barWidth=bounded(args.bar_width, "bar-width", 1, stage_width), barWidthAutoSize=0
        )
    if args.bar_spacing is not None:
        changes.update(
            barSpacing=bounded(args.bar_spacing, "bar-spacing", 1, stage_width),
            barSpacingAutoSize=0,
        )
    if args.width is not None:
        changes["width"] = bounded(args.width, "width", 0, stage_width)
    if args.height is not None:
        changes["height"] = bounded(args.height, "height", 0, stage_height)
    if args.opacity is not None:
        changes["opacity"] = bounded(args.opacity, "opacity", 0, 1)
    if not changes:
        raise ValueError("specify at least one changed property")

    before = {key: properties.get(key, BAR_DEFAULTS.get(key)) for key in changes}
    properties.update(changes)
    if args.name is not None:
        project["name"] = args.name
    output.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(project, indent=2, ensure_ascii=False) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(dir=output.parent, prefix=f".{output.name}-")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "source": str(source),
        "source_sha256": digest(source),
        "output": str(output),
        "output_sha256": digest(output),
        "display_id": args.display_id,
        "before": before,
        "after": changes,
        "effective_frequency_range_hz": [minimum, maximum],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--display-id", required=True)
    parser.add_argument("--name")
    parser.add_argument("--color-top")
    parser.add_argument("--color-bottom")
    parser.add_argument("--shadow-color-top")
    parser.add_argument("--shadow-color-bottom")
    parser.add_argument("--shadow-height", type=float)
    parser.add_argument("--min-frequency", type=float)
    parser.add_argument("--max-frequency", type=float)
    parser.add_argument("--max-decibels", type=float)
    parser.add_argument("--smoothing", type=float)
    parser.add_argument("--bar-width", type=float)
    parser.add_argument("--bar-spacing", type=float)
    parser.add_argument("--width", type=float)
    parser.add_argument("--height", type=float)
    parser.add_argument("--opacity", type=float)
    args = parser.parse_args()
    try:
        print(json.dumps(make_variant(args), ensure_ascii=False, indent=2))
    except (KeyError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"astrofox project variant: {exc}\n")


if __name__ == "__main__":
    main()
