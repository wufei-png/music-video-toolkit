import * as THREE from "three";
import {
  sampleSignal,
  smoothValue,
  targetValue,
  type ResolvedTransform,
  type SignalSeries,
} from "./routing.js";

interface BaseConfig {
  readonly width: number;
  readonly height: number;
  readonly sceneMode: "fixture" | "abstract";
}

export interface FixtureSceneConfig extends BaseConfig {
  readonly sceneMode: "fixture";
  readonly imageDataUrl: string;
  readonly title: string;
  readonly pulseFrames: readonly number[];
}

interface LayerConfig {
  readonly id: string;
  readonly kind: "orb" | "ribbon" | "particles" | "image" | "video";
  readonly category: "abstract" | "media" | "text";
  readonly asset_id?: string;
  readonly enabled: boolean;
  readonly opacity: number;
  readonly parameters: Readonly<Record<string, number | string>>;
}

interface SpanConfig {
  readonly start_sample: number;
  readonly end_sample: number;
  readonly transition_samples: number;
  readonly layers: readonly LayerConfig[];
}

interface RouteConfig {
  readonly source: string;
  readonly target_layer: string;
  readonly target_parameter: string;
  readonly transform: ResolvedTransform;
}

export interface AbstractSceneConfig extends BaseConfig {
  readonly sceneMode: "abstract";
  readonly sampleRate: number;
  readonly fpsNum: number;
  readonly fpsDen: number;
  readonly seed: number;
  readonly signals: Readonly<Record<string, SignalSeries>>;
  readonly spans: readonly SpanConfig[];
  readonly routes: readonly RouteConfig[];
}

export type SceneConfig = FixtureSceneConfig | AbstractSceneConfig;

interface AbstractObject {
  readonly kind: "orb" | "ribbon" | "particles";
  readonly object: THREE.Object3D;
  readonly material: THREE.MeshBasicMaterial | THREE.PointsMaterial;
  readonly particleGeometry?: THREE.BufferGeometry;
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

interface MediaObject {
  readonly current: THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>;
  readonly previous: THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>;
  currentUrl?: string;
  previousUrl?: string;
}

let renderer: THREE.WebGLRenderer;
let scene: THREE.Scene;
let camera: THREE.Camera;
let background: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshBasicMaterial>;
let config: SceneConfig;
let imageReady = false;
let glyphInkPixels = 0;
let abstractReady = false;
const abstractObjects = new Map<string, AbstractObject>();
const mediaObjects = new Map<string, MediaObject>();
const smoothedRoutes = new Map<number, number>();

function textTexture(text: string): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 1400;
  canvas.height = 180;
  const context = canvas.getContext("2d", {willReadFrequently: true});
  if (context === null) throw new Error("2D canvas is unavailable");
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "white";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.font = '700 88px "PingFang SC", "Noto Sans CJK SC", sans-serif';
  context.fillText(text, canvas.width / 2, canvas.height / 2);
  const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
  glyphInkPixels = 0;
  for (let index = 3; index < pixels.length; index += 4) {
    if ((pixels[index] ?? 0) > 0) glyphInkPixels += 1;
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.needsUpdate = true;
  return texture;
}

function random(seed: number): () => number {
  let state = (seed >>> 0) || 1;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 0x100000000;
  };
}

function color(value: number | string | undefined): THREE.Color {
  return new THREE.Color(typeof value === "string" ? value : "#ffffff");
}

function createAbstractObject(layer: LayerConfig, seed: number, maximumCount: number): AbstractObject {
  if (layer.kind === "orb") {
    const material = new THREE.MeshBasicMaterial({
      color: color(layer.parameters.color),
      transparent: true,
      opacity: layer.opacity,
      blending: THREE.AdditiveBlending,
    });
    const object = new THREE.Mesh(new THREE.CircleGeometry(1, 96), material);
    object.position.z = 0.2;
    scene.add(object);
    return {kind: layer.kind, object, material};
  }
  if (layer.kind === "ribbon") {
    const material = new THREE.MeshBasicMaterial({
      color: color(layer.parameters.color),
      transparent: true,
      opacity: layer.opacity,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    });
    const object = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 1), material);
    object.position.z = 0.1;
    scene.add(object);
    return {kind: layer.kind, object, material};
  }
  if (layer.kind !== "particles") throw new Error(`unsupported abstract kind ${layer.kind}`);
  const makeRandom = random(seed);
  const positions = new Float32Array(maximumCount * 3);
  for (let index = 0; index < maximumCount; index += 1) {
    positions[index * 3] = makeRandom() * 2 - 1;
    positions[index * 3 + 1] = makeRandom() * 2 - 1;
    positions[index * 3 + 2] = makeRandom() * 0.2;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const material = new THREE.PointsMaterial({
    color: color(layer.parameters.color),
    transparent: true,
    opacity: layer.opacity,
    size: Number(layer.parameters.size),
    sizeAttenuation: false,
    blending: THREE.AdditiveBlending,
  });
  const object = new THREE.Points(geometry, material);
  object.position.z = 0.3;
  scene.add(object);
  return {kind: layer.kind, object, material, particleGeometry: geometry};
}

function createMediaObject(layer: LayerConfig): MediaObject {
  const makeGeometry = () =>
    layer.parameters.mask === "circle"
      ? new THREE.CircleGeometry(1, 96)
      : new THREE.PlaneGeometry(2, 2);
  const makeMaterial = () =>
    new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0,
      depthWrite: false,
      blending:
        layer.parameters.blend === "add" ? THREE.AdditiveBlending : THREE.NormalBlending,
    });
  const previous = new THREE.Mesh(makeGeometry(), makeMaterial());
  const current = new THREE.Mesh(makeGeometry(), makeMaterial());
  scene.add(previous);
  scene.add(current);
  return {current, previous};
}

async function setMediaTexture(
  object: MediaObject,
  slot: "current" | "previous",
  frame: MediaFrame | undefined,
): Promise<void> {
  const mesh = object[slot];
  if (frame === undefined) {
    mesh.visible = false;
    return;
  }
  mesh.visible = true;
  const key = slot === "current" ? "currentUrl" : "previousUrl";
  if (object[key] !== frame.dataUrl) {
    const old = mesh.material.map;
    const texture = await new THREE.TextureLoader().loadAsync(frame.dataUrl);
    texture.colorSpace = THREE.SRGBColorSpace;
    mesh.material.map = texture;
    mesh.material.needsUpdate = true;
    object[key] = frame.dataUrl;
    old?.dispose();
  }
  const canvasAspect = config.width / config.height;
  const assetAspect = frame.width / frame.height;
  mesh.userData.assetAspect = assetAspect;
  mesh.userData.canvasAspect = canvasAspect;
}

function placeMedia(
  mesh: THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>,
  layer: LayerConfig,
  frame: MediaFrame,
  opacity: number,
  seconds: number,
): void {
  const mask = String(layer.parameters.mask);
  if (mesh.userData.mask !== mask) {
    mesh.geometry.dispose();
    mesh.geometry =
      mask === "circle" ? new THREE.CircleGeometry(1, 96) : new THREE.PlaneGeometry(2, 2);
    mesh.userData.mask = mask;
  }
  mesh.material.blending =
    layer.parameters.blend === "add" ? THREE.AdditiveBlending : THREE.NormalBlending;
  mesh.material.needsUpdate = true;
  const canvasAspect = config.width / config.height;
  const assetAspect = frame.width / frame.height;
  const cover = layer.parameters.fit === "cover";
  const xScale = cover
    ? Math.max(1, assetAspect / canvasAspect)
    : Math.min(1, assetAspect / canvasAspect);
  const yScale = cover
    ? Math.max(1, canvasAspect / assetAspect)
    : Math.min(1, canvasAspect / assetAspect);
  const scale = Number(layer.parameters.scale);
  mesh.scale.set(xScale * scale, yScale * scale, 1);
  mesh.position.x = Number(layer.parameters.x) + Math.sin(seconds * 0.2) * Number(layer.parameters.motion);
  mesh.position.y = Number(layer.parameters.y) + Math.cos(seconds * 0.17) * Number(layer.parameters.motion);
  mesh.position.z = Number(layer.parameters.z) * 0.02 - 0.2;
  mesh.material.opacity = opacity;
}

async function configureMedia(
  layer: LayerConfig,
  previousLayer: LayerConfig | undefined,
  pair: MediaFramePair,
  seconds: number,
): Promise<void> {
  const object = mediaObjects.get(layer.id);
  if (object === undefined) throw new Error(`missing media object ${layer.id}`);
  await setMediaTexture(object, "current", pair.current);
  await setMediaTexture(object, "previous", pair.previous);
  const currentOpacity =
    (pair.previous === undefined ? layer.opacity : layer.opacity * pair.progress) *
    Number(layer.enabled);
  placeMedia(object.current, layer, pair.current, currentOpacity, seconds);
  if (pair.previous !== undefined && previousLayer !== undefined) {
    const previousOpacity =
      previousLayer.opacity * (1 - pair.progress) * Number(previousLayer.enabled);
    placeMedia(object.previous, previousLayer, pair.previous, previousOpacity, seconds);
  }
}

function numericParameter(
  current: LayerConfig,
  previous: LayerConfig | undefined,
  name: string,
  progress: number,
): number {
  const end = Number(current.parameters[name]);
  if (previous === undefined || progress >= 1) return end;
  const start = Number(previous.parameters[name]);
  return start + (end - start) * progress;
}

function configureObject(
  definition: LayerConfig,
  previous: LayerConfig | undefined,
  progress: number,
  values: Readonly<Record<string, number>>,
  seconds: number,
): void {
  const target = abstractObjects.get(definition.id);
  if (target === undefined) throw new Error(`missing abstract object ${definition.id}`);
  target.object.visible = definition.enabled;
  target.material.opacity =
    previous === undefined || progress >= 1
      ? definition.opacity
      : previous.opacity + (definition.opacity - previous.opacity) * progress;
  target.material.color.copy(color(definition.parameters.color));
  const parameter = (name: string) =>
    values[name] ?? numericParameter(definition, previous, name, progress);
  if (target.kind === "orb") {
    const radius = parameter("radius");
    target.object.scale.set(radius, radius, 1);
    target.object.position.x = parameter("x");
    target.object.position.y = parameter("y");
    target.object.rotation.z = seconds * 0.08;
  } else if (target.kind === "ribbon") {
    const width = parameter("width");
    const amplitude = parameter("amplitude");
    target.object.scale.set(1, width + amplitude, 1);
    target.object.position.y = parameter("y");
    target.object.rotation.z = Math.sin(seconds * 0.7) * amplitude * 0.25;
  } else {
    const points = target.object as THREE.Points;
    const size = parameter("size");
    const spread = parameter("spread");
    (target.material as THREE.PointsMaterial).size = size * config.height;
    points.scale.set(spread, spread, 1);
    points.rotation.z = seconds * 0.05;
    const count = Math.floor(Number(definition.parameters.count));
    target.particleGeometry?.setDrawRange(0, count);
  }
}

function initializeAbstract(abstractConfig: AbstractSceneConfig): void {
  const first = abstractConfig.spans[0];
  if (first === undefined) throw new Error("abstract plan has no spans");
  for (const layer of first.layers) {
    if (layer.category === "media") {
      mediaObjects.set(layer.id, createMediaObject(layer));
      continue;
    }
    const maximumCount = Math.max(
      ...abstractConfig.spans.map((span) => {
        const candidate = span.layers.find((item) => item.id === layer.id);
        return Number(candidate?.parameters.count ?? 16);
      }),
    );
    abstractObjects.set(layer.id, createAbstractObject(layer, abstractConfig.seed, maximumCount));
  }
  abstractReady = true;
}

async function renderAbstract(
  frame: number,
  abstractConfig: AbstractSceneConfig,
  mediaFrames: Readonly<Record<string, MediaFramePair>>,
): Promise<void> {
  const sample = Math.floor(
    (frame * abstractConfig.sampleRate * abstractConfig.fpsDen) / abstractConfig.fpsNum,
  );
  const spanIndex = abstractConfig.spans.findIndex(
    (span) => sample >= span.start_sample && sample < span.end_sample,
  );
  const index = spanIndex < 0 ? abstractConfig.spans.length - 1 : spanIndex;
  const span = abstractConfig.spans[index];
  if (span === undefined) throw new Error("sample is outside resolved spans");
  const previous = index > 0 ? abstractConfig.spans[index - 1] : undefined;
  const progress =
    span.transition_samples > 0
      ? Math.min(1, (sample - span.start_sample) / span.transition_samples)
      : 1;
  const routed = new Map<string, Record<string, number>>();
  abstractConfig.routes.forEach((route, routeIndex) => {
    const signal = abstractConfig.signals[route.source];
    if (signal === undefined) throw new Error(`missing route signal ${route.source}`);
    const rawTarget = targetValue(sampleSignal(signal, sample), route.transform);
    const old = smoothedRoutes.get(routeIndex) ?? rawTarget;
    const value = smoothValue(
      old,
      rawTarget,
      abstractConfig.fpsDen / abstractConfig.fpsNum,
      route.transform,
    );
    smoothedRoutes.set(routeIndex, value);
    const layerValues = routed.get(route.target_layer) ?? {};
    layerValues[route.target_parameter] = value;
    routed.set(route.target_layer, layerValues);
  });
  const seconds = sample / abstractConfig.sampleRate;
  for (const layer of span.layers) {
    if (layer.category === "media") {
      const pair = mediaFrames[layer.id];
      if (pair === undefined) throw new Error(`missing decoded frame for ${layer.id}`);
      const prior = previous?.layers.find((item) => item.id === layer.id);
      await configureMedia(layer, prior, pair, seconds);
      continue;
    }
    const prior = previous?.layers.find((item) => item.id === layer.id);
    configureObject(layer, prior, progress, routed.get(layer.id) ?? {}, seconds);
  }
  background.material.color.setHex(0x08101f + Math.min(index, 5) * 0x010204);
  renderer.render(scene, camera);
}

export async function initialize(sceneConfig: SceneConfig): Promise<void> {
  config = sceneConfig;
  const canvas = document.querySelector<HTMLCanvasElement>("#mvt-canvas");
  if (canvas === null) throw new Error("render canvas is missing");
  renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: false,
    antialias: true,
    preserveDrawingBuffer: true,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(1);
  renderer.setSize(config.width, config.height, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  scene = new THREE.Scene();
  camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 10);
  camera.position.z = 2;
  background = new THREE.Mesh(
    new THREE.PlaneGeometry(2, 2),
    new THREE.MeshBasicMaterial({color: 0x10182c}),
  );
  background.position.z = -0.5;
  scene.add(background);

  if (config.sceneMode === "fixture") {
    const imageTexture = await new THREE.TextureLoader().loadAsync(config.imageDataUrl);
    imageTexture.colorSpace = THREE.SRGBColorSpace;
    const image = new THREE.Mesh(
      new THREE.PlaneGeometry(0.72, 0.72),
      new THREE.MeshBasicMaterial({map: imageTexture}),
    );
    image.position.set(0.52, 0.18, 0);
    scene.add(image);
    imageReady = true;
    await document.fonts.ready;
    const title = new THREE.Mesh(
      new THREE.PlaneGeometry(1.5, 0.193),
      new THREE.MeshBasicMaterial({map: textTexture(config.title), transparent: true}),
    );
    title.position.set(-0.12, -0.67, 0.1);
    scene.add(title);
  } else {
    initializeAbstract(config);
  }
  renderer.render(scene, camera);
}

export async function renderFrame(
  frame: number,
  mediaFrames: Readonly<Record<string, MediaFramePair>> = {},
): Promise<void> {
  if (config.sceneMode === "fixture") {
    const pulse = config.pulseFrames.includes(frame);
    background.material.color.setHex(pulse ? 0xf4f7ff : 0x10182c);
    renderer.render(scene, camera);
  } else {
    await renderAbstract(frame, config, mediaFrames);
  }
}

export function readiness(): {
  imageReady: boolean;
  glyphInkPixels: number;
  abstractReady: boolean;
} {
  return {imageReady, glyphInkPixels, abstractReady};
}

export function webglInfo(): {vendor: string; renderer: string} {
  const context = renderer.getContext();
  const extension = context.getExtension("WEBGL_debug_renderer_info");
  if (extension === null) return {vendor: "unknown", renderer: "unknown"};
  return {
    vendor: String(context.getParameter(extension.UNMASKED_VENDOR_WEBGL)),
    renderer: String(context.getParameter(extension.UNMASKED_RENDERER_WEBGL)),
  };
}
