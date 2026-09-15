import * as THREE from "three";

export interface SceneConfig {
  readonly width: number;
  readonly height: number;
  readonly imageDataUrl: string;
  readonly title: string;
}

let renderer: THREE.WebGLRenderer;
let scene: THREE.Scene;
let background: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshBasicMaterial>;
let imageReady = false;
let glyphInkPixels = 0;

function textTexture(text: string): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 1400;
  canvas.height = 180;
  const context = canvas.getContext("2d", {willReadFrequently: true});
  if (context === null) {
    throw new Error("2D canvas is unavailable");
  }
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

export async function initialize(config: SceneConfig): Promise<void> {
  const canvas = document.querySelector<HTMLCanvasElement>("#mvt-canvas");
  if (canvas === null) throw new Error("render canvas is missing");
  renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: false,
    antialias: false,
    preserveDrawingBuffer: true,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(1);
  renderer.setSize(config.width, config.height, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 10);
  camera.position.z = 2;

  background = new THREE.Mesh(
    new THREE.PlaneGeometry(2, 2),
    new THREE.MeshBasicMaterial({color: 0x10182c}),
  );
  background.position.z = -0.5;
  scene.add(background);

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

  (globalThis as unknown as {mvtCamera: THREE.Camera}).mvtCamera = camera;
  renderer.render(scene, camera);
}

export function renderFrame(frame: number, pulseFrames: readonly number[]): void {
  const pulse = pulseFrames.includes(frame);
  background.material.color.setHex(pulse ? 0xf4f7ff : 0x10182c);
  renderer.render(scene, (globalThis as unknown as {mvtCamera: THREE.Camera}).mvtCamera);
}

export function readiness(): {imageReady: boolean; glyphInkPixels: number} {
  return {imageReady, glyphInkPixels};
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
