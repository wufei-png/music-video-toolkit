import {spawn} from "node:child_process";
import {once} from "node:events";
import {readFile} from "node:fs/promises";
import {dirname, join} from "node:path";
import {fileURLToPath} from "node:url";
import {chromium} from "playwright";
import {videoFrameAtSample} from "./media.js";

interface MediaAssetConfig {
  readonly type: "image" | "video";
  readonly width: number;
  readonly height: number;
  readonly dataUrl?: string;
  readonly framesDir?: string;
  readonly frameCount?: number;
  readonly fpsNum?: number;
  readonly fpsDen?: number;
}

interface RenderLayerConfig {
  readonly id: string;
  readonly category: string;
  readonly asset_id?: string;
  readonly opacity: number;
  readonly parameters: Record<string, any>;
}

interface RenderSpanConfig {
  readonly start_sample: number;
  readonly end_sample: number;
  readonly transition_samples: number;
  readonly layers: readonly RenderLayerConfig[];
}

interface LyricsConfig {
  readonly cues: readonly {start_sample: number; end_sample: number; text: string}[];
  readonly fontDataUrl: string;
  readonly fontFamily: string;
  readonly fadeSamples: number;
}

interface RenderConfig {
  readonly sceneMode: "fixture" | "abstract";
  readonly width: number;
  readonly height: number;
  readonly fpsNum: number;
  readonly fpsDen: number;
  readonly frameCount: number;
  readonly frameStart?: number;
  readonly pulseFrames?: readonly number[];
  readonly imageDataUrl?: string;
  readonly title?: string;
  readonly sampleRate?: number;
  readonly seed?: number;
  readonly signals?: Readonly<Record<string, unknown>>;
  readonly spans?: readonly RenderSpanConfig[];
  readonly routes?: readonly unknown[];
  readonly mediaAssets?: Readonly<Record<string, MediaAssetConfig>>;
  readonly lyrics?: LyricsConfig;
  readonly audioPath: string;
  readonly audioStartSeconds?: number;
  readonly outputPath: string;
  readonly ffmpegPath: string;
}

interface MediaFrame {
  readonly dataUrl: string;
  readonly width: number;
  readonly height: number;
}

interface MediaFramePair {
  readonly current: MediaFrame;
  readonly previous?: MediaFrame;
  readonly progress: number;
}

function positiveInteger(value: number, label: string): void {
  if (!Number.isSafeInteger(value) || value <= 0) throw new Error(`${label} must be positive`);
}

function nonNegativeInteger(value: number, label: string): void {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new Error(`${label} must be a non-negative integer`);
  }
}

function nonNegativeFinite(value: number, label: string): void {
  if (!Number.isFinite(value) || value < 0) {
    throw new Error(`${label} must be a non-negative finite number`);
  }
}

async function mediaFrame(
  asset: MediaAssetConfig,
  layer: RenderLayerConfig,
  sample: number,
  sampleRate: number,
): Promise<MediaFrame> {
  if (asset.type === "image") {
    if (asset.dataUrl === undefined) throw new Error("image data is missing");
    return {dataUrl: asset.dataUrl, width: asset.width, height: asset.height};
  }
  if (
    asset.framesDir === undefined ||
    asset.frameCount === undefined ||
    asset.fpsNum === undefined ||
    asset.fpsDen === undefined
  ) {
    throw new Error("decoded video metadata is missing");
  }
  const sourceFrame = videoFrameAtSample(
    sample,
    sampleRate,
    {fpsNum: asset.fpsNum, fpsDen: asset.fpsDen, frameCount: asset.frameCount},
    layer.parameters as any,
  );
  const path = join(asset.framesDir, `${String(sourceFrame).padStart(9, "0")}.png`);
  const bytes = await readFile(path);
  return {
    dataUrl: `data:image/png;base64,${bytes.toString("base64")}`,
    width: asset.width,
    height: asset.height,
  };
}

async function mediaFrames(
  config: RenderConfig,
  frame: number,
): Promise<Record<string, MediaFramePair>> {
  if (config.sceneMode !== "abstract" || config.spans === undefined) return {};
  const sampleRate = config.sampleRate ?? 48000;
  const sample = Math.floor((frame * sampleRate * config.fpsDen) / config.fpsNum);
  const found = config.spans.findIndex(
    (span) => sample >= span.start_sample && sample < span.end_sample,
  );
  const spanIndex = found < 0 ? config.spans.length - 1 : found;
  const span = config.spans[spanIndex];
  if (span === undefined) throw new Error("no resolved span for media frame");
  const progress =
    span.transition_samples > 0
      ? Math.min(1, (sample - span.start_sample) / span.transition_samples)
      : 1;
  const previousSpan = spanIndex > 0 ? config.spans[spanIndex - 1] : undefined;
  const payload: Record<string, MediaFramePair> = {};
  for (const layer of span.layers.filter((item) => item.category === "media")) {
    const asset = layer.asset_id === undefined ? undefined : config.mediaAssets?.[layer.asset_id];
    if (asset === undefined) throw new Error(`missing media asset ${layer.asset_id}`);
    const current = await mediaFrame(asset, layer, sample, sampleRate);
    const previousLayer = previousSpan?.layers.find((item) => item.id === layer.id);
    const previousAsset =
      previousLayer?.asset_id === undefined
        ? undefined
        : config.mediaAssets?.[previousLayer.asset_id];
    const previous =
      progress < 1 && previousLayer !== undefined && previousAsset !== undefined
        ? await mediaFrame(previousAsset, previousLayer, sample, sampleRate)
        : undefined;
    payload[layer.id] =
      previous === undefined ? {current, progress} : {current, previous, progress};
  }
  return payload;
}

async function main(): Promise<void> {
  const configPath = process.argv[2];
  if (configPath === undefined) throw new Error("usage: render CONFIG.json");
  const config = JSON.parse(await readFile(configPath, "utf8")) as RenderConfig;
  positiveInteger(config.width, "width");
  positiveInteger(config.height, "height");
  positiveInteger(config.fpsNum, "fpsNum");
  positiveInteger(config.fpsDen, "fpsDen");
  positiveInteger(config.frameCount, "frameCount");
  nonNegativeInteger(config.frameStart ?? 0, "frameStart");
  nonNegativeFinite(config.audioStartSeconds ?? 0, "audioStartSeconds");

  const browser = await chromium.launch({headless: true});
  let encoder: ReturnType<typeof spawn> | undefined;
  const stderr: Buffer[] = [];
  try {
    const page = await browser.newPage({
      viewport: {width: config.width, height: config.height},
      deviceScaleFactor: 1,
    });
    await page.setContent(
      '<!doctype html><html><body style="margin:0;overflow:hidden;background:#000">' +
        `<canvas id="mvt-canvas" width="${config.width}" height="${config.height}"></canvas>` +
        "</body></html>",
    );
    const bundle = join(dirname(fileURLToPath(import.meta.url)), "browser-scene.js");
    await page.addScriptTag({path: bundle});
    await page.evaluate(
      async (sceneConfig) => {
        await (globalThis as any).MvtScene.initialize(sceneConfig);
      },
      config,
    );
    await page.evaluate((frameStart) => {
      (globalThis as any).MvtScene.seekFrame(frameStart);
    }, config.frameStart ?? 0);
    const readiness = await page.evaluate(() => (globalThis as any).MvtScene.readiness());
    const ready =
      config.sceneMode === "fixture"
        ? readiness.imageReady && readiness.glyphInkPixels > 0
        : readiness.abstractReady && readiness.lyricsReady;
    if (!ready) {
      throw new Error(`scene readiness failed: ${JSON.stringify(readiness)}`);
    }
    const webgl = await page.evaluate(() => (globalThis as any).MvtScene.webglInfo());
    const duration = (config.frameCount * config.fpsDen) / config.fpsNum;
    encoder = spawn(
      config.ffmpegPath,
      [
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-f",
        "image2pipe",
        "-framerate",
        `${config.fpsNum}/${config.fpsDen}`,
        "-vcodec",
        "png",
        "-i",
        "pipe:0",
        "-ss",
        (config.audioStartSeconds ?? 0).toFixed(9),
        "-i",
        config.audioPath,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-frames:v",
        String(config.frameCount),
        "-t",
        duration.toFixed(9),
        "-fps_mode",
        "cfr",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        config.outputPath,
      ],
      {stdio: ["pipe", "ignore", "pipe"]},
    );
    const encoderInput = encoder.stdin;
    if (encoderInput === null) throw new Error("ffmpeg stdin is unavailable");
    encoder.stderr?.on("data", (chunk: Buffer) => stderr.push(chunk));
    const frameStart = config.frameStart ?? 0;
    for (let frame = 0; frame < config.frameCount; frame += 1) {
      const globalFrame = frameStart + frame;
      const media = await mediaFrames(config, globalFrame);
      await page.evaluate(async ({currentFrame, mediaFrames}) => {
        await (globalThis as any).MvtScene.renderFrame(currentFrame, mediaFrames);
      }, {currentFrame: globalFrame, mediaFrames: media});
      const png = await page.locator("#mvt-canvas").screenshot({type: "png"});
      if (!encoderInput.write(png)) await once(encoderInput, "drain");
    }
    encoderInput.end();
    const [exitCode] = (await once(encoder, "close")) as [number | null];
    if (exitCode !== 0) {
      throw new Error(`ffmpeg exited ${exitCode}: ${Buffer.concat(stderr).toString("utf8")}`);
    }
    process.stdout.write(
      `${JSON.stringify({ok: true, readiness, webgl, chromium: browser.version()})}\n`,
    );
  } catch (error) {
    encoder?.stdin?.destroy();
    encoder?.kill("SIGTERM");
    throw error;
  } finally {
    await browser.close();
  }
}

main().catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
  process.exitCode = 1;
});
