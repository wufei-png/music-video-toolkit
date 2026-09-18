"""Strict v0.1 artifact envelopes. Cross-file/media preflight arrives in S01/S05."""

from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

MAX_INT = 2**53 - 1  # Exact in JSON consumers using JavaScript numbers.
NonNegative = Annotated[int, Field(ge=0, le=MAX_INT)]
Positive = Annotated[int, Field(gt=0, le=MAX_INT)]
SafeInteger = Annotated[int, Field(ge=-MAX_INT, le=MAX_INT)]
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


class FileRef(Contract):
    path: Text
    sha256: Sha256


class CanonicalAudio(FileRef):
    sample_rate: Literal[48000]
    channels: Literal[2]
    sample_format: Literal["s24le"]
    codec: Literal["pcm_s24le"]
    duration_samples: Positive


class SourceRecord(Artifact):
    original: FileRef
    canonical: CanonicalAudio
    decoder: Provenance


class StemAlignment(Contract):
    input_sample_rate: Positive
    input_duration_samples: Positive
    natural_output_samples: Positive
    target_duration_samples: Positive
    adjustment: Literal["none", "pad", "trim"]
    adjustment_samples: SafeInteger

    @model_validator(mode="after")
    def coherent_adjustment(self) -> Self:
        delta = self.target_duration_samples - self.natural_output_samples
        expected = "none" if delta == 0 else "pad" if delta > 0 else "trim"
        if self.adjustment != expected or self.adjustment_samples != delta:
            raise ValueError("stem alignment adjustment does not match sample counts")
        return self


class StemAudio(CanonicalAudio):
    alignment: StemAlignment


class SeparationModel(Contract):
    name: Text
    config_sha256: Sha256
    weights_sha256: Sha256
    source: Text
    license_status: Literal["unconfirmed", "confirmed"]
    redistributable: bool

    @model_validator(mode="after")
    def redistribution_evidence(self) -> Self:
        if self.license_status == "unconfirmed" and self.redistributable:
            raise ValueError("a model with unconfirmed license cannot be marked redistributable")
        return self


class StemManifest(Artifact):
    source: Source
    cache_key: Sha256
    separator: Provenance
    model: SeparationModel
    stems: dict[Literal["vocals", "drums", "bass", "other"], StemAudio]

    @model_validator(mode="after")
    def exactly_four_stems(self) -> Self:
        required = {"vocals", "drums", "bass", "other"}
        if set(self.stems) != required:
            raise ValueError("four-stem manifest requires vocals, drums, bass and other")
        duration = self.source.duration_samples
        if any(stem.duration_samples != duration for stem in self.stems.values()):
            raise ValueError("stems must match canonical duration exactly")
        return self


class AnalysisRun(Artifact):
    source_sha256: Sha256
    mode: Literal["four", "none"]
    cache_key: Sha256
    environment: Annotated[dict[Name, Text], Field(min_length=1)]
    timings_seconds: dict[Name, Annotated[float, Field(ge=0)]]
    outputs: Annotated[dict[Name, FileRef], Field(min_length=1)]

    @model_validator(mode="after")
    def mode_outputs(self) -> Self:
        expected = {"timeline", "stems"} if self.mode == "four" else {"timeline"}
        if set(self.outputs) != expected:
            raise ValueError(f"{self.mode} analysis outputs must be {sorted(expected)}")
        required_timings = {"separation", "features", "total"}
        if set(self.timings_seconds) != required_timings:
            raise ValueError("analysis timings require separation, features and total")
        return self


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
    font_asset_id: Name | None = None

    @model_validator(mode="after")
    def stored_cues(self) -> Self:
        disabled = self.mode == "off"
        if disabled != (self.path is None) or disabled != (self.font_asset_id is None):
            raise ValueError(
                "off has no lyric fields; enabled lyrics require saved cues and a font asset"
            )
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


class ResolvedSpan(SampleRange):
    section_id: Name | None = None
    section_label: Text | None = None
    section_origin: Literal["automatic", "manual"] | None = None
    transition_samples: NonNegative = 0
    layers: Annotated[list[Layer], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_layers(self) -> Self:
        unique([layer.id for layer in self.layers], "resolved layer id")
        if (self.section_id is None) != (self.section_origin is None):
            raise ValueError("resolved section id and origin must appear together")
        if self.transition_samples > self.end_sample - self.start_sample:
            raise ValueError("transition cannot exceed its resolved span")
        return self


class ResolvedPlan(Artifact):
    source_plan: FileRef
    timeline_path: Text
    timeline_sha256: Sha256
    assets_path: Text
    assets_sha256: Sha256
    checked_assets_path: Text
    checked_assets_sha256: Sha256
    mode: Literal["abstract", "mood", "hybrid"]
    seed: NonNegative
    output: OutputProfile = Field(default_factory=OutputProfile)
    duration_samples: Positive
    routes: list[Route] = Field(default_factory=list)
    spans: Annotated[list[ResolvedSpan], Field(min_length=1)]
    lyrics: LyricsChoice = Field(default_factory=LyricsChoice)
    lyrics_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def complete_timeline(self) -> Self:
        if (self.lyrics.mode == "off") != (self.lyrics_sha256 is None):
            raise ValueError("enabled resolved lyrics require a lyrics artifact hash")
        ranges = [
            SampleRange(start_sample=span.start_sample, end_sample=span.end_sample)
            for span in self.spans
        ]
        ordered_ranges(ranges)
        if self.spans[0].start_sample != 0 or self.spans[-1].end_sample != self.duration_samples:
            raise ValueError("resolved spans must cover the complete timeline")
        if any(a.end_sample != b.start_sample for a, b in pairwise(self.spans)):
            raise ValueError("resolved spans must be contiguous")
        layer_ids = {layer.id for layer in self.spans[0].layers}
        if any({layer.id for layer in span.layers} != layer_ids for span in self.spans):
            raise ValueError("resolved spans must retain the same layer identities")
        if any(route.target_layer not in layer_ids for route in self.routes):
            raise ValueError("resolved route targets unknown layer")
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


class AssetProbe(FileRef):
    id: Name
    type: Literal["image", "video", "font"]
    width: Positive | None = None
    height: Positive | None = None
    frame_count: Positive | None = None
    fps_num: Positive | None = None
    fps_den: Positive | None = None
    duration_seconds: Annotated[float, Field(gt=0)] | None = None
    has_audio: bool | None = None
    font_families: list[Text] | None = None

    @model_validator(mode="after")
    def type_metadata(self) -> Self:
        media_clock = (
            self.frame_count,
            self.fps_num,
            self.fps_den,
            self.duration_seconds,
            self.has_audio,
        )
        image_fields = (
            self.width is not None
            and self.height is not None
            and all(value is None for value in media_clock)
        )
        video_fields = all(
            value is not None
            for value in (
                self.width,
                self.height,
                self.frame_count,
                self.fps_num,
                self.fps_den,
                self.duration_seconds,
                self.has_audio,
            )
        )
        font_fields = bool(self.font_families)
        valid = {
            "image": image_fields and self.font_families is None,
            "video": video_fields and self.font_families is None,
            "font": font_fields
            and self.width is None
            and self.height is None
            and all(value is None for value in media_clock),
        }[self.type]
        if not valid:
            raise ValueError(f"incomplete or mixed {self.type} probe metadata")
        return self


class CheckedAssetManifest(Artifact):
    source_manifest: FileRef
    cache_key: Sha256
    assets: list[AssetProbe]

    @model_validator(mode="after")
    def unique_assets(self) -> Self:
        unique([asset.id for asset in self.assets], "checked asset id")
        return self


class Cue(SampleRange):
    text: Annotated[str, Field(min_length=1, max_length=240)]


class Lyrics(Artifact):
    language: Text
    text_source: Text
    text_source_sha256: Sha256
    audio_sha256: Sha256
    origin: Literal["imported", "aligned", "edited"]
    provenance: Provenance
    cues: Annotated[list[Cue], Field(min_length=1)]

    @model_validator(mode="after")
    def cue_order(self) -> Self:
        ordered_ranges(self.cues)
        return self


class AlignmentLine(Contract):
    source_line: Positive
    text: Annotated[str, Field(min_length=1, max_length=240)]
    normalized_characters: Positive
    status: Literal["matched", "unmatched"]
    coverage: Unit
    start_sample: NonNegative | None = None
    end_sample: Positive | None = None
    reason: Text | None = None

    @model_validator(mode="after")
    def coherent_status(self) -> Self:
        timed = self.start_sample is not None and self.end_sample is not None
        if self.status == "matched":
            if not timed or self.reason is not None or self.end_sample <= self.start_sample:
                raise ValueError("matched alignment lines require an ordered range and no reason")
        elif timed or self.reason is None:
            raise ValueError("unmatched alignment lines require a reason and no range")
        return self


class AlignmentEvaluation(Contract):
    reference_points: Annotated[int, Field(ge=12, le=MAX_INT)]
    matched_reference_points: Positive
    unmatched_reference_points: NonNegative
    median_absolute_error_samples: NonNegative
    p90_absolute_error_samples: NonNegative
    median_limit_samples: Literal[12000] = 12000
    p90_limit_samples: Literal[24000] = 24000
    passed: bool

    @model_validator(mode="after")
    def threshold_result(self) -> Self:
        if self.matched_reference_points + self.unmatched_reference_points != self.reference_points:
            raise ValueError("alignment reference counts do not sum to reference_points")
        expected = (
            self.unmatched_reference_points == 0
            and self.matched_reference_points == self.reference_points
            and self.median_absolute_error_samples <= self.median_limit_samples
            and self.p90_absolute_error_samples <= self.p90_limit_samples
        )
        if self.passed != expected:
            raise ValueError("alignment evaluation result does not match the fixed thresholds")
        return self


class AlignmentReport(Artifact):
    cache_key: Sha256
    language: Literal["en", "zh"]
    text_source: FileRef
    audio: FileRef
    audio_kind: Literal["canonical", "vocals"]
    audio_offset_samples: Literal[0] = 0
    runtime: Provenance
    elapsed_seconds: Annotated[float, Field(ge=0)]
    output: FileRef
    lines: Annotated[list[AlignmentLine], Field(min_length=1)]
    evaluation: AlignmentEvaluation | None = None

    @model_validator(mode="after")
    def line_order(self) -> Self:
        source_lines = [line.source_line for line in self.lines]
        if source_lines != sorted(source_lines) or len(source_lines) != len(set(source_lines)):
            raise ValueError("alignment source lines must be unique and ordered")
        matched = [
            SampleRange(start_sample=line.start_sample, end_sample=line.end_sample)
            for line in self.lines
            if line.status == "matched"
        ]
        ordered_ranges(matched)
        return self


class PreviewRange(SampleRange):
    id: Name
    role: Literal["sparse", "climax", "transition", "other"] = "other"
    label: Text | None = None


class PreviewRequest(Artifact):
    ranges: Annotated[list[PreviewRange], Field(min_length=1)]

    @model_validator(mode="after")
    def ordered_unique_ranges(self) -> Self:
        ordered_ranges(self.ranges)
        unique([item.id for item in self.ranges], "preview range id")
        return self


class RenderManifest(Artifact):
    cache_key: Sha256
    status: Literal["completed", "failed"]
    source_sha256: Sha256
    canonical_audio_sha256: Sha256 | None = None
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


class ComparisonVariantRequest(Contract):
    id: Name
    label: Text
    preview_manifest_path: Text


class ComparisonRequest(Artifact):
    variants: Annotated[list[ComparisonVariantRequest], Field(min_length=2)]

    @model_validator(mode="after")
    def unique_variants(self) -> Self:
        unique([variant.id for variant in self.variants], "comparison variant id")
        unique(
            [variant.preview_manifest_path for variant in self.variants],
            "comparison preview manifest path",
        )
        return self


class ComparisonMediaProbe(Contract):
    width: Positive
    height: Positive
    fps_num: Positive
    fps_den: Positive
    frame_count: Positive
    has_audio: bool
    audio_sha256: Sha256 | None = None
    audio_sample_rate: Positive | None = None
    audio_channels: Positive | None = None

    @model_validator(mode="after")
    def coherent_audio(self) -> Self:
        audio_metadata = (
            self.audio_sha256 is not None
            and self.audio_sample_rate is not None
            and self.audio_channels is not None
        )
        if self.has_audio != audio_metadata:
            raise ValueError("audio metadata must be present exactly when has_audio is true")
        return self


class ComparisonClip(Contract):
    range_index: Positive
    range: SampleRange
    file: FileRef
    probe: ComparisonMediaProbe


class ComparisonVariant(Contract):
    id: Name
    label: Text
    preview_manifest: FileRef
    preview_cache_key: Sha256
    inputs: Annotated[dict[Name, Sha256], Field(min_length=1)]
    environment: Annotated[dict[Name, Text], Field(min_length=1)]
    seed: NonNegative
    clips: Annotated[list[ComparisonClip], Field(min_length=1)]


class ComparisonProfile(Contract):
    width: Positive
    height: Positive
    fps_num: Positive
    fps_den: Positive
    has_audio: bool
    range_count: Positive


class ComparisonArtifacts(Contract):
    review_reel: FileRef
    contact_sheet: FileRef


class ComparisonManifest(Artifact):
    cache_key: Sha256
    request: FileRef
    source_sha256: Sha256
    ranges: Annotated[list[SampleRange], Field(min_length=1)]
    profile: ComparisonProfile
    variants: Annotated[list[ComparisonVariant], Field(min_length=2)]
    tools: Annotated[dict[Name, Text], Field(min_length=1)]
    artifacts: ComparisonArtifacts

    @model_validator(mode="after")
    def coherent_comparison(self) -> Self:
        ordered_ranges(self.ranges)
        if self.profile.range_count != len(self.ranges):
            raise ValueError("comparison profile range_count must match ranges")
        unique([variant.id for variant in self.variants], "comparison variant id")
        expected_indexes = list(range(1, len(self.ranges) + 1))
        reference_clips = self.variants[0].clips
        for variant in self.variants:
            if [clip.range_index for clip in variant.clips] != expected_indexes:
                raise ValueError("comparison clips must cover each range once in order")
            if [clip.range for clip in variant.clips] != self.ranges:
                raise ValueError("comparison clip ranges must match the shared ranges")
            for clip in variant.clips:
                probe = clip.probe
                actual_profile = (
                    probe.width,
                    probe.height,
                    probe.fps_num,
                    probe.fps_den,
                    probe.has_audio,
                )
                expected_profile = (
                    self.profile.width,
                    self.profile.height,
                    self.profile.fps_num,
                    self.profile.fps_den,
                    self.profile.has_audio,
                )
                if actual_profile != expected_profile:
                    raise ValueError("comparison clip probe does not match the shared profile")
            for reference, clip in zip(reference_clips, variant.clips, strict=True):
                if clip.probe.frame_count != reference.probe.frame_count:
                    raise ValueError("comparison variants must have matching frame counts")
                if clip.probe.audio_sha256 != reference.probe.audio_sha256:
                    raise ValueError("comparison variants must have matching decoded audio")
        return self


CONTRACTS: dict[str, type[Artifact]] = {
    "source": SourceRecord,
    "stems": StemManifest,
    "analysis": AnalysisRun,
    "timeline": Timeline,
    "plan": VisualPlan,
    "resolved-plan": ResolvedPlan,
    "assets": AssetManifest,
    "checked-assets": CheckedAssetManifest,
    "lyrics": Lyrics,
    "alignment": AlignmentReport,
    "preview": PreviewRequest,
    "render": RenderManifest,
    "comparison-request": ComparisonRequest,
    "comparison": ComparisonManifest,
}
