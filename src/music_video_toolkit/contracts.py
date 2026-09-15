"""Strict v0.1 artifact envelopes. Cross-file/media preflight arrives in S01/S05."""

from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

MAX_INT = 2**53 - 1  # Exact in JSON consumers using JavaScript numbers.
NonNegative = Annotated[int, Field(ge=0, le=MAX_INT)]
Positive = Annotated[int, Field(gt=0, le=MAX_INT)]
Unit = Annotated[float, Field(ge=0, le=1)]
Name = Annotated[str, Field(min_length=1, pattern=r"^[a-zA-Z0-9_.-]+$")]
Text = Annotated[str, Field(min_length=1)]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Artifact(Contract):
    schema_version: Literal["0.1"]


class SampleRange(Contract):
    start_sample: NonNegative
    end_sample: Positive

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end_sample <= self.start_sample:
            raise ValueError("end_sample must be greater than start_sample")
        return self


def unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label}")


def ordered_ranges(ranges: list[SampleRange]) -> None:
    if any(a.end_sample > b.start_sample for a, b in pairwise(ranges)):
        raise ValueError("ranges must be ordered and non-overlapping")


class Source(Contract):
    path: Text
    sha256: Sha256
    sample_rate: Annotated[int, Field(ge=48000, le=48000)]
    duration_samples: Positive


class Provenance(Contract):
    tool: Text
    version: Text
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class Signal(Contract):
    start_sample: NonNegative = 0
    hop_samples: Positive
    values: Annotated[list[float], Field(min_length=1)]
    unit: Text


class Event(Contract):
    name: Name
    source: Name
    sample: NonNegative
    confidence: Unit | None = None


class Section(SampleRange):
    id: Name
    label: Text | None = None
    origin: Literal["automatic", "manual"]
    confidence: Unit | None = None


class Timeline(Artifact):
    source: Source
    analysis: list[Provenance]
    signals: dict[Name, Signal] = Field(default_factory=dict)
    events: list[Event] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)

    @model_validator(mode="after")
    def time_bounds(self) -> Self:
        duration = self.source.duration_samples
        for signal in self.signals.values():
            last = signal.start_sample + (len(signal.values) - 1) * signal.hop_samples
            if last >= duration:
                raise ValueError("signal sample lies outside canonical duration")
        if any(event.sample >= duration for event in self.events):
            raise ValueError("event lies outside canonical duration")
        if any(a.sample > b.sample for a, b in pairwise(self.events)):
            raise ValueError("events must be ordered by sample")
        unique([s.id for s in self.sections], "section id")
        ordered_ranges(self.sections)
        if any(s.end_sample > duration for s in self.sections):
            raise ValueError("section lies outside canonical duration")
        return self


class OutputProfile(Contract):
    width: Annotated[int, Field(ge=1920, le=1920)] = 1920
    height: Annotated[int, Field(ge=1080, le=1080)] = 1080
    fps_num: Annotated[int, Field(ge=30, le=30)] = 30
    fps_den: Annotated[int, Field(ge=1, le=1)] = 1


class Layer(Contract):
    id: Name
    kind: Name
    category: Literal["abstract", "media", "text"]
    enabled: bool = True
    opacity: Unit = 1.0
    asset_id: Name | None = None
    parameters: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def media_reference(self) -> Self:
        if self.category == "media" and self.asset_id is None:
            raise ValueError("media layers require asset_id")
        return self


class Transform(Contract):
    kind: Literal["linear", "threshold", "smooth"]
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class Route(Contract):
    source: Name
    target_layer: Name
    target_parameter: Name
    transform: Transform


class LayerOverride(Contract):
    layer_id: Name
    enabled: bool | None = None
    opacity: Unit | None = None
    asset_id: Name | None = None
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class SectionOverride(Contract):
    section_id: Name
    layers: list[LayerOverride]
    transition_samples: NonNegative = 0


class LyricsChoice(Contract):
    mode: Literal["off", "imported", "auto"] = "off"
    path: Text | None = None

    @model_validator(mode="after")
    def stored_cues(self) -> Self:
        if (self.mode == "off") != (self.path is None):
            raise ValueError("off has no path; enabled lyrics require a saved cue path")
        return self


class VisualPlan(Artifact):
    timeline_path: Text
    assets_path: Text
    mode: Literal["abstract", "mood", "hybrid"]
    seed: NonNegative
    output: OutputProfile = Field(default_factory=OutputProfile)
    layers: Annotated[list[Layer], Field(min_length=1)]
    routes: list[Route] = Field(default_factory=list)
    sections: list[SectionOverride] = Field(default_factory=list)
    lyrics: LyricsChoice = Field(default_factory=LyricsChoice)

    @model_validator(mode="after")
    def coherent_layers(self) -> Self:
        ids = [layer.id for layer in self.layers]
        unique(ids, "layer id")
        categories = {layer.category for layer in self.layers if layer.enabled}
        required = {"abstract": {"abstract"}, "mood": {"media"}, "hybrid": {"abstract", "media"}}[
            self.mode
        ]
        if not required <= categories:
            raise ValueError(f"{self.mode} requires enabled layer categories {sorted(required)}")
        if self.mode == "abstract" and "media" in categories:
            raise ValueError("use hybrid mode to combine abstract and media layers")
        if self.mode == "mood" and "abstract" in categories:
            raise ValueError("use hybrid mode to combine abstract and media layers")
        if any(route.target_layer not in ids for route in self.routes):
            raise ValueError("route targets unknown layer")
        unique([s.section_id for s in self.sections], "section override")
        for section in self.sections:
            unique([layer.layer_id for layer in section.layers], "layer override")
            if any(layer.layer_id not in ids for layer in section.layers):
                raise ValueError("override targets unknown layer")
        return self


class Asset(Contract):
    id: Name
    path: Text
    type: Literal["image", "video", "font"]
    sha256: Sha256
    origin: Literal["user", "harness", "synthetic"]
    license: Text | None = None
    source_note: Text | None = None


class AssetManifest(Artifact):
    assets: list[Asset]

    @model_validator(mode="after")
    def unique_assets(self) -> Self:
        unique([asset.id for asset in self.assets], "asset id")
        return self


class Cue(SampleRange):
    text: Text


class Lyrics(Artifact):
    language: Text
    text_source: Text
    audio_sha256: Sha256
    origin: Literal["imported", "aligned", "edited"]
    cues: Annotated[list[Cue], Field(min_length=1)]

    @model_validator(mode="after")
    def cue_order(self) -> Self:
        ordered_ranges(self.cues)
        return self


class FileRef(Contract):
    path: Text
    sha256: Sha256


class RenderManifest(Artifact):
    status: Literal["completed", "failed"]
    source_sha256: Sha256
    inputs: Annotated[dict[Name, Sha256], Field(min_length=1)]
    seed: NonNegative
    environment: Annotated[dict[Name, Text], Field(min_length=1)]
    ranges: Annotated[list[SampleRange], Field(min_length=1)]
    outputs: list[FileRef] = Field(default_factory=list)
    error: Text | None = None

    @model_validator(mode="after")
    def outcome(self) -> Self:
        ordered_ranges(self.ranges)
        if self.status == "completed" and (not self.outputs or self.error is not None):
            raise ValueError("completed render requires outputs and no error")
        if self.status == "failed" and self.error is None:
            raise ValueError("failed render requires an error")
        return self


CONTRACTS: dict[str, type[Artifact]] = {
    "timeline": Timeline,
    "plan": VisualPlan,
    "assets": AssetManifest,
    "lyrics": Lyrics,
    "render": RenderManifest,
}
