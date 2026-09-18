export interface LyricCue {
  readonly start_sample: number;
  readonly end_sample: number;
  readonly text: string;
}

export interface LyricMotion {
  readonly progress: number;
  readonly bulgeCenterX: number;
  readonly bulgeStrength: number;
  readonly trail: number;
  readonly lift: number;
  readonly scale: number;
}

export function activeCueAtSample(cues: readonly LyricCue[], sample: number): number {
  if (!Number.isSafeInteger(sample) || sample < 0) throw new RangeError("invalid sample");
  return cues.findIndex((cue) => sample >= cue.start_sample && sample < cue.end_sample);
}

export function lyricOpacity(cue: LyricCue, sample: number, fadeSamples: number): number {
  if (sample < cue.start_sample || sample >= cue.end_sample) return 0;
  if (!Number.isSafeInteger(fadeSamples) || fadeSamples < 0) {
    throw new RangeError("invalid lyric fade");
  }
  const fade = Math.min(fadeSamples, Math.floor((cue.end_sample - cue.start_sample) / 2));
  if (fade === 0) return 1;
  const into = sample - cue.start_sample;
  const remaining = cue.end_sample - sample;
  const ramp = Math.min(1, into / fade, remaining / fade);
  return 0.15 + 0.85 * ramp;
}

function smoothstep(edge0: number, edge1: number, value: number): number {
  const ratio = Math.max(0, Math.min(1, (value - edge0) / (edge1 - edge0)));
  return ratio * ratio * (3 - 2 * ratio);
}

export function lyricMotionAtSample(cue: LyricCue, sample: number): LyricMotion {
  if (sample < cue.start_sample || sample >= cue.end_sample) {
    return {
      progress: 0,
      bulgeCenterX: 0.24,
      bulgeStrength: 0,
      trail: 0,
      lift: 0,
      scale: 1,
    };
  }
  const duration = cue.end_sample - cue.start_sample;
  const progress = Math.max(0, Math.min(1, (sample - cue.start_sample) / duration));
  const travel = smoothstep(0, 1, progress);
  const entrance = 1 - smoothstep(0, 0.16, progress);
  const exit = smoothstep(0.84, 1, progress);
  return {
    progress,
    bulgeCenterX: 0.24 + 0.52 * travel,
    bulgeStrength: 0.15 + 0.075 * Math.sin(Math.PI * progress),
    trail: Math.max(entrance, exit),
    lift: -0.035 * entrance + 0.022 * exit,
    scale: 0.965 + 0.035 * smoothstep(0, 0.18, progress) - 0.012 * exit,
  };
}
