export type MediaFit = "cover" | "contain";

export interface LyricLayout {
  readonly meshWidth: number;
  readonly meshHeight: number;
  readonly centerY: number;
  readonly textureWidth: number;
  readonly textureHeight: number;
  readonly maximumTextWidth: number;
  readonly maximumLines: number;
  readonly initialFontSize: number;
  readonly minimumFontSize: number;
  readonly fontStep: number;
  readonly safeLeft: number;
  readonly safeRight: number;
  readonly safeTop: number;
  readonly safeBottom: number;
}

export interface OutputLayout {
  readonly width: 1920 | 1080;
  readonly height: 1080 | 1920;
  readonly aspect: number;
  readonly portrait: boolean;
  readonly lyrics: LyricLayout;
}

export interface Scale2D {
  readonly x: number;
  readonly y: number;
}

export interface NormalizedBounds {
  readonly left: number;
  readonly right: number;
  readonly top: number;
  readonly bottom: number;
}

export interface CaptionFit {
  readonly fontSize: number;
  readonly lineCount: number;
}

export function layoutForOutput(width: number, height: number): OutputLayout {
  const landscape = width === 1920 && height === 1080;
  const portrait = width === 1080 && height === 1920;
  if (!landscape && !portrait) {
    throw new RangeError(`unsupported output dimensions ${width}x${height}`);
  }
  const aspect = width / height;
  return {
    width,
    height,
    aspect,
    portrait,
    lyrics: portrait
      ? {
          meshWidth: 2 * aspect * 0.82,
          meshHeight: 0.62,
          centerY: -0.42,
          textureWidth: 1536,
          textureHeight: 1040,
          maximumTextWidth: 1350,
          maximumLines: 5,
          initialFontSize: 144,
          minimumFontSize: 52,
          fontStep: 6,
          safeLeft: 0.07,
          safeRight: 0.93,
          safeTop: 0.52,
          safeBottom: 0.92,
        }
      : {
          meshWidth: 2 * aspect * 0.86,
          meshHeight: 0.58,
          centerY: -0.5,
          textureWidth: 2048,
          textureHeight: 400,
          maximumTextWidth: 1880,
          maximumLines: 3,
          initialFontSize: 104,
          minimumFontSize: 38,
          fontStep: 6,
          safeLeft: 0.05,
          safeRight: 0.95,
          safeTop: 0.56,
          safeBottom: 0.95,
        },
  } as OutputLayout;
}

export function fitCaptionLayout(
  layout: LyricLayout,
  lineCountAtFontSize: (fontSize: number) => number,
): CaptionFit {
  let fontSize = layout.initialFontSize;
  while (true) {
    const lineCount = lineCountAtFontSize(fontSize);
    if (!Number.isInteger(lineCount) || lineCount < 0) {
      throw new RangeError("caption line count must be a non-negative integer");
    }
    if (lineCount <= layout.maximumLines) return {fontSize, lineCount};
    if (fontSize === layout.minimumFontSize) {
      throw new RangeError(
        `caption exceeds ${layout.maximumLines} lines at minimum font size ${fontSize}`,
      );
    }
    fontSize = Math.max(layout.minimumFontSize, fontSize - layout.fontStep);
  }
}

export function normalizedX(layout: OutputLayout, value: number): number {
  return value * layout.aspect;
}

export function mediaScale(
  layout: OutputLayout,
  assetAspect: number,
  fit: MediaFit,
): Scale2D {
  if (!Number.isFinite(assetAspect) || assetAspect <= 0) {
    throw new RangeError("asset aspect must be positive");
  }
  const widerThanCanvas = assetAspect >= layout.aspect;
  if (fit === "cover") {
    return widerThanCanvas
      ? {x: assetAspect, y: 1}
      : {x: layout.aspect, y: layout.aspect / assetAspect};
  }
  return widerThanCanvas
    ? {x: layout.aspect, y: layout.aspect / assetAspect}
    : {x: assetAspect, y: 1};
}

export function lyricBounds(
  layout: OutputLayout,
  scale = 1,
  lift = 0,
): NormalizedBounds {
  const lyrics = layout.lyrics;
  const halfWidth = (lyrics.meshWidth * scale) / 2;
  const halfHeight = (lyrics.meshHeight * scale) / 2;
  const centerY = lyrics.centerY + lift;
  return {
    left: (layout.aspect - halfWidth) / (2 * layout.aspect),
    right: (layout.aspect + halfWidth) / (2 * layout.aspect),
    top: (1 - centerY - halfHeight) / 2,
    bottom: (1 - centerY + halfHeight) / 2,
  };
}
