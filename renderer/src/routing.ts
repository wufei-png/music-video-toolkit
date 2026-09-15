export interface SignalSeries {
  readonly start_sample: number;
  readonly hop_samples: number;
  readonly values: readonly number[];
}

export interface ResolvedTransform {
  readonly kind: "linear" | "threshold" | "smooth";
  readonly parameters: Readonly<Record<string, number>>;
}

export function sampleSignal(signal: SignalSeries, sample: number): number {
  if (!Number.isSafeInteger(sample) || sample < 0) throw new RangeError("sample must be non-negative");
  if (signal.values.length === 0 || signal.hop_samples <= 0) throw new RangeError("invalid signal");
  const position = (sample - signal.start_sample) / signal.hop_samples;
  if (position <= 0) return signal.values[0] ?? 0;
  const left = Math.floor(position);
  if (left >= signal.values.length - 1) return signal.values.at(-1) ?? 0;
  const fraction = position - left;
  const first = signal.values[left] ?? 0;
  const second = signal.values[left + 1] ?? first;
  return first + (second - first) * fraction;
}

export function targetValue(value: number, transform: ResolvedTransform): number {
  const p = transform.parameters;
  if (transform.kind === "threshold") {
    return value >= (p.threshold ?? 0) ? (p.high ?? 0) : (p.low ?? 0);
  }
  return (p.min ?? 0) + value * ((p.max ?? 0) - (p.min ?? 0));
}

export function smoothValue(
  previous: number,
  target: number,
  deltaSeconds: number,
  transform: ResolvedTransform,
): number {
  if (transform.kind !== "smooth") return target;
  const rising = target > previous;
  const seconds = rising
    ? (transform.parameters.attack_seconds ?? 0)
    : (transform.parameters.release_seconds ?? 0);
  if (seconds <= 0) return target;
  const alpha = 1 - Math.exp(-deltaSeconds / seconds);
  return previous + (target - previous) * alpha;
}
