export interface LyricCue {
  readonly start_sample: number;
  readonly end_sample: number;
  readonly text: string;
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
