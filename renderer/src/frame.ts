/** Integer arithmetic owns time. Floating seconds are a drawing convenience only. */
export interface Clock {
  readonly sampleRate: number;
  readonly fpsNum: number;
  readonly fpsDen: number;
}

function integer(value: number, name: string, minimum = 0): bigint {
  if (!Number.isSafeInteger(value) || value < minimum) {
    throw new RangeError(`${name} must be a safe integer >= ${minimum}`);
  }
  return BigInt(value);
}

function clockParts(clock: Clock): readonly [bigint, bigint, bigint] {
  return [integer(clock.sampleRate, "sampleRate", 1),
          integer(clock.fpsNum, "fpsNum", 1), integer(clock.fpsDen, "fpsDen", 1)];
}

function safeResult(value: bigint): number {
  if (value > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new RangeError("time exceeds the JSON safe integer range");
  }
  return Number(value);
}

export function sampleAtFrame(globalFrame: number, clock: Clock): number {
  const frame = integer(globalFrame, "globalFrame");
  const [rate, num, den] = clockParts(clock);
  return safeResult(frame * rate * den / num);
}

/** First frame whose start is at or after the event; no early visual impulse. */
export function firstFrameAtSample(sample: number, clock: Clock): number {
  const position = integer(sample, "sample");
  const [rate, num, den] = clockParts(clock);
  const divisor = rate * den;
  return safeResult((position * num + divisor - 1n) / divisor);
}

export interface FrameContext {
  readonly globalFrame: number;
  readonly sample: number;
  readonly seconds: number;
  readonly deltaSeconds: number;
  readonly seed: number;
}

export function frameContext(globalFrame: number, clock: Clock, seed: number): FrameContext {
  integer(seed, "seed");
  const sample = sampleAtFrame(globalFrame, clock);
  return Object.freeze({globalFrame, sample,
    seconds: globalFrame * clock.fpsDen / clock.fpsNum,
    deltaSeconds: clock.fpsDen / clock.fpsNum, seed});
}
