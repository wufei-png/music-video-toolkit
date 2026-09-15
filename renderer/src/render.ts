import {spawn} from "node:child_process";
import {once} from "node:events";
import {readFile} from "node:fs/promises";
import {dirname, join} from "node:path";
import {fileURLToPath} from "node:url";
import {chromium} from "playwright";

interface RenderConfig {
  readonly sceneMode: "fixture" | "abstract";
  readonly width: number;
  readonly height: number;
  readonly fpsNum: number;
  readonly fpsDen: number;
  readonly frameCount: number;
  readonly pulseFrames?: readonly number[];
  readonly imageDataUrl?: string;
  readonly title?: string;
  readonly sampleRate?: number;
  readonly seed?: number;
  readonly signals?: Readonly<Record<string, unknown>>;
  readonly spans?: readonly unknown[];
  readonly routes?: readonly unknown[];
  readonly audioPath: string;
  readonly outputPath: string;
  readonly ffmpegPath: string;
}

function positiveInteger(value: number, label: string): void {
  if (!Number.isSafeInteger(value) || value <= 0) throw new Error(`${label} must be positive`);
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
    const readiness = await page.evaluate(() => (globalThis as any).MvtScene.readiness());
    const ready =
      config.sceneMode === "fixture"
        ? readiness.imageReady && readiness.glyphInkPixels > 0
        : readiness.abstractReady;
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
    for (let frame = 0; frame < config.frameCount; frame += 1) {
      await page.evaluate((currentFrame) => {
        (globalThis as any).MvtScene.renderFrame(currentFrame);
      }, frame);
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
