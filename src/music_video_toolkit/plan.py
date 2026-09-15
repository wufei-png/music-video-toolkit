"""Resolve editable plans into bounded, complete per-section render plans."""

from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from .contracts import (
    FileRef,
    Layer,
    LayerOverride,
    ResolvedPlan,
    ResolvedSpan,
    Route,
    Section,
    Timeline,
    Transform,
    VisualPlan,
)
from .documents import read_document
from .project import ProjectPreflightError, preflight_source, resolve_record_path, sha256_file

DEFAULT_OUTPUT = Path("resolved-plan.json")
LAYER_SPECS: dict[str, dict[str, tuple[object, float | None, float | None]]] = {
    "orb": {
        "radius": (0.34, 0.05, 1.5),
        "x": (-0.48, -1.0, 1.0),
        "y": (0.0, -1.0, 1.0),
        "color": ("#55d6ff", None, None),
    },
    "ribbon": {
        "width": (0.12, 0.01, 0.5),
        "amplitude": (0.18, 0.0, 1.0),
        "y": (0.0, -1.0, 1.0),
        "color": ("#ff4fa3", None, None),
    },
    "particles": {
        "count": (320, 16, 2000),
        "size": (0.025, 0.001, 0.2),
        "spread": (1.4, 0.1, 2.0),
        "color": ("#ffe178", None, None),
    },
}
ROUTE_TARGETS = {
    "orb": {"radius", "x", "y"},
    "ribbon": {"width", "amplitude", "y"},
    "particles": {"size", "spread"},
}


class PlanError(Exception):
    """A stable plan-resolution failure for the CLI."""

    def __init__(self, code: str, details: object, exit_code: int = 2):
        super().__init__(str(details))
        self.code = code
        self.details = details
        self.exit_code = exit_code


def _load(model, path: Path, label: str):
    try:
        return model.model_validate(read_document(path))
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        details = (
            exc.errors(include_url=False, include_context=False, include_input=False)
            if isinstance(exc, ValidationError)
            else str(exc)
        )
        raise PlanError("invalid_plan_input", {"artifact": label, "details": details}) from exc


def _number(value: object, label: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PlanError("invalid_layer_parameter", {"parameter": label, "value": value})
    number = float(value)
    if not minimum <= number <= maximum:
        raise PlanError(
            "invalid_layer_parameter",
            {"parameter": label, "minimum": minimum, "maximum": maximum, "value": value},
        )
    return number


def _color(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        raise PlanError("invalid_layer_parameter", {"parameter": label, "value": value})
    try:
        int(value[1:], 16)
    except ValueError as exc:
        raise PlanError("invalid_layer_parameter", {"parameter": label, "value": value}) from exc
    return value.lower()


def _resolve_layer(layer: Layer) -> Layer:
    if layer.category != "abstract" or layer.kind not in LAYER_SPECS:
        raise PlanError(
            "unsupported_layer",
            {"layer": layer.id, "kind": layer.kind, "supported": sorted(LAYER_SPECS)},
        )
    spec = LAYER_SPECS[layer.kind]
    unknown = sorted(set(layer.parameters) - set(spec))
    if unknown:
        raise PlanError("unknown_layer_parameter", {"layer": layer.id, "parameters": unknown})
    parameters: dict[str, object] = {}
    for name, (default, minimum, maximum) in spec.items():
        value = layer.parameters.get(name, default)
        if minimum is None or maximum is None:
            parameters[name] = _color(value, f"{layer.id}.{name}")
        elif name == "count":
            parsed = _number(value, f"{layer.id}.{name}", minimum, maximum)
            if not parsed.is_integer():
                raise PlanError(
                    "invalid_layer_parameter", {"parameter": f"{layer.id}.{name}", "value": value}
                )
            parameters[name] = int(parsed)
        else:
            parameters[name] = _number(value, f"{layer.id}.{name}", minimum, maximum)
    return layer.model_copy(update={"parameters": parameters})


def _target_bounds(layer: Layer, target: str) -> tuple[float, float]:
    if target not in ROUTE_TARGETS[layer.kind]:
        raise PlanError(
            "unsupported_route_target",
            {"layer": layer.id, "kind": layer.kind, "parameter": target},
        )
    _, minimum, maximum = LAYER_SPECS[layer.kind][target]
    assert minimum is not None and maximum is not None
    return minimum, maximum


def _resolve_transform(
    transform: Transform, bounds: tuple[float, float], route: Route
) -> Transform:
    minimum, maximum = bounds
    params = transform.parameters
    required = {
        "linear": {"min", "max"},
        "threshold": {"threshold", "low", "high"},
        "smooth": {"min", "max", "attack_seconds", "release_seconds"},
    }[transform.kind]
    if set(params) != required:
        raise PlanError(
            "invalid_transform_parameters",
            {"source": route.source, "kind": transform.kind, "required": sorted(required)},
        )
    parsed: dict[str, float] = {}
    if transform.kind == "threshold":
        parsed["threshold"] = _number(params["threshold"], "threshold", 0.0, 1.0)
        parsed["low"] = _number(params["low"], "low", minimum, maximum)
        parsed["high"] = _number(params["high"], "high", minimum, maximum)
    else:
        parsed["min"] = _number(params["min"], "min", minimum, maximum)
        parsed["max"] = _number(params["max"], "max", minimum, maximum)
        if transform.kind == "smooth":
            parsed["attack_seconds"] = _number(
                params["attack_seconds"], "attack_seconds", 0.0, 10.0
            )
            parsed["release_seconds"] = _number(
                params["release_seconds"], "release_seconds", 0.0, 10.0
            )
    return transform.model_copy(update={"parameters": parsed})


def _apply_override(layer: Layer, override: LayerOverride) -> Layer:
    data = layer.model_dump()
    if override.enabled is not None:
        data["enabled"] = override.enabled
    if override.opacity is not None:
        data["opacity"] = override.opacity
    if override.asset_id is not None:
        data["asset_id"] = override.asset_id
    data["parameters"].update(override.parameters)
    return Layer.model_validate(data)


def _automatic_sections(timeline: Timeline) -> list[Section]:
    duration = timeline.source.duration_samples
    signal = timeline.signals.get("mix.rms")
    if signal is None or len(signal.values) < 3:
        return [
            Section(
                id="auto-001",
                start_sample=0,
                end_sample=duration,
                origin="automatic",
            )
        ]
    novelty = [
        abs(right - left) for left, right in zip(signal.values, signal.values[1:], strict=False)
    ]
    if max(novelty, default=0.0) <= 1e-12:
        return [
            Section(
                id="auto-001",
                start_sample=0,
                end_sample=duration,
                origin="automatic",
            )
        ]
    mean = sum(novelty) / len(novelty)
    variance = sum((value - mean) ** 2 for value in novelty) / len(novelty)
    threshold = mean + math.sqrt(variance)
    minimum_gap = 4 * timeline.source.sample_rate
    candidates = sorted(
        (
            (value, signal.start_sample + (index + 1) * signal.hop_samples)
            for index, value in enumerate(novelty)
            if value >= threshold
        ),
        reverse=True,
    )
    boundaries = [0, duration]
    for _, sample in candidates:
        if sample <= 0 or sample >= duration:
            continue
        if all(abs(sample - existing) >= minimum_gap for existing in boundaries):
            boundaries.append(sample)
        if len(boundaries) >= 8:
            break
    boundaries.sort()
    return [
        Section(
            id=f"auto-{index + 1:03d}",
            start_sample=start,
            end_sample=end,
            origin="automatic",
        )
        for index, (start, end) in enumerate(zip(boundaries, boundaries[1:], strict=False))
    ]


def _span_layers(base: list[Layer], overrides: dict[str, LayerOverride]) -> list[Layer]:
    return [
        _resolve_layer(
            _apply_override(layer, overrides[layer.id]) if layer.id in overrides else layer
        )
        for layer in base
    ]


def _check_mode(mode: str, layers: list[Layer], section_id: str | None) -> None:
    enabled_categories = {layer.category for layer in layers if layer.enabled}
    required = {"abstract": {"abstract"}, "mood": {"media"}, "hybrid": {"abstract", "media"}}[mode]
    if not required <= enabled_categories:
        raise PlanError(
            "required_layer_disabled",
            {"mode": mode, "section_id": section_id, "required": sorted(required)},
        )


def _make_spans(plan: VisualPlan, timeline: Timeline) -> list[ResolvedSpan]:
    sections = timeline.sections or _automatic_sections(timeline)
    overrides = {item.section_id: item for item in plan.sections}
    known = {section.id for section in sections}
    unknown = sorted(set(overrides) - known)
    if unknown:
        raise PlanError("unknown_section", {"section_ids": unknown})
    spans: list[ResolvedSpan] = []
    cursor = 0
    for section in sections:
        if cursor < section.start_sample:
            layers = _span_layers(plan.layers, {})
            _check_mode(plan.mode, layers, None)
            spans.append(
                ResolvedSpan(start_sample=cursor, end_sample=section.start_sample, layers=layers)
            )
        section_override = overrides.get(section.id)
        layer_overrides = (
            {item.layer_id: item for item in section_override.layers} if section_override else {}
        )
        layers = _span_layers(plan.layers, layer_overrides)
        _check_mode(plan.mode, layers, section.id)
        spans.append(
            ResolvedSpan(
                start_sample=section.start_sample,
                end_sample=section.end_sample,
                section_id=section.id,
                section_label=section.label,
                section_origin=section.origin,
                transition_samples=(section_override.transition_samples if section_override else 0),
                layers=layers,
            )
        )
        cursor = section.end_sample
    if cursor < timeline.source.duration_samples:
        layers = _span_layers(plan.layers, {})
        _check_mode(plan.mode, layers, None)
        spans.append(
            ResolvedSpan(
                start_sample=cursor,
                end_sample=timeline.source.duration_samples,
                layers=layers,
            )
        )
    return spans


def _resolve_routes(plan: VisualPlan, timeline: Timeline, layers: list[Layer]) -> list[Route]:
    by_id = {layer.id: layer for layer in layers}
    routes = []
    for route in plan.routes:
        if route.source not in timeline.signals:
            raise PlanError("missing_route_signal", {"source": route.source})
        layer = by_id[route.target_layer]
        bounds = _target_bounds(layer, route.target_parameter)
        routes.append(
            route.model_copy(
                update={"transform": _resolve_transform(route.transform, bounds, route)}
            )
        )
    return routes


def validate_resolved_plan(plan: ResolvedPlan, timeline: Timeline) -> None:
    for span in plan.spans:
        layers = [_resolve_layer(layer) for layer in span.layers]
        changed = any(
            resolved != original for resolved, original in zip(layers, span.layers, strict=True)
        )
        if changed:
            raise PlanError("unresolved_layer_parameters", {"section_id": span.section_id})
        _check_mode(plan.mode, layers, span.section_id)
    by_id = {layer.id: layer for layer in plan.spans[0].layers}
    for route in plan.routes:
        if route.source not in timeline.signals:
            raise PlanError("missing_route_signal", {"source": route.source})
        layer = by_id[route.target_layer]
        expected = _resolve_transform(
            route.transform, _target_bounds(layer, route.target_parameter), route
        )
        if expected != route.transform:
            raise PlanError("unresolved_transform_parameters", {"source": route.source})


def _write(path: Path, plan: ResolvedPlan) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(plan.model_dump_json(indent=2))
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def resolve_plan(
    project: Path, plan_path: Path, output_path: Path | None = None
) -> tuple[ResolvedPlan, Path]:
    try:
        source = preflight_source(project)
    except ProjectPreflightError as exc:
        raise PlanError(exc.code, exc.details, 4) from exc
    plan_path = plan_path.resolve()
    plan = _load(VisualPlan, plan_path, "plan")
    if plan.mode != "abstract":
        raise PlanError("unsupported_plan_mode", {"mode": plan.mode, "supported": ["abstract"]})
    timeline_path = resolve_record_path(plan_path, plan.timeline_path)
    assets_path = resolve_record_path(plan_path, plan.assets_path)
    timeline = _load(Timeline, timeline_path, "timeline")
    if (
        timeline.source.sha256 != source.record.canonical.sha256
        or resolve_record_path(timeline_path, timeline.source.path) != source.canonical_path
    ):
        raise PlanError("timeline_source_mismatch", {"timeline": timeline.source.sha256})
    output_path = (output_path or source.project / DEFAULT_OUTPUT).resolve()
    spans = _make_spans(plan, timeline)
    routes = _resolve_routes(plan, timeline, spans[0].layers)
    resolved = ResolvedPlan(
        schema_version="0.1",
        source_plan=FileRef(
            path=os.path.relpath(plan_path, output_path.parent), sha256=sha256_file(plan_path)
        ),
        timeline_path=os.path.relpath(timeline_path, output_path.parent),
        timeline_sha256=sha256_file(timeline_path),
        assets_path=os.path.relpath(assets_path, output_path.parent),
        mode=plan.mode,
        seed=plan.seed,
        output=plan.output,
        duration_samples=timeline.source.duration_samples,
        routes=routes,
        spans=spans,
        lyrics=plan.lyrics,
    )
    _write(output_path, resolved)
    return resolved, output_path
