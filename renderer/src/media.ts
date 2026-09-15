export interface VideoClock {
  readonly fpsNum: number;
  readonly fpsDen: number;
  readonly frameCount: number;
}

export interface VideoPolicy {
  readonly offset_samples: number;
  readonly in_frame: number;
  readonly out_frame: number;
  readonly end_behavior: "error" | "loop" | "hold";
}

export function videoFrameAtSample(
  sample: number,
  sampleRate: number,
  clock: VideoClock,
  policy: VideoPolicy,
): number {
  if (!Number.isSafeInteger(sample) || sample < 0) throw new RangeError("invalid sample");
  const elapsed = Math.max(0, sample - policy.offset_samples);
  const advanced = Math.floor((elapsed * clock.fpsNum) / (sampleRate * clock.fpsDen));
  const frame = policy.in_frame + advanced;
  if (frame < policy.out_frame) return frame;
  const length = policy.out_frame - policy.in_frame;
  if (length <= 0) throw new RangeError("empty video trim range");
  if (policy.end_behavior === "loop") return policy.in_frame + ((frame - policy.in_frame) % length);
  if (policy.end_behavior === "hold") return policy.out_frame - 1;
  throw new RangeError("video is too short for error end_behavior");
}
