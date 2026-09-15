import type { Object3D } from "three";
import type { FrameContext } from "./frame.js";

/** Python validates artifacts; S04 resolves them into this per-frame input. */
export interface RoutedFrame extends FrameContext {
  readonly signals: Readonly<Record<string, number>>;
  readonly events: readonly { readonly name: string; readonly source: string }[];
}

/** A and B share this lifecycle; hybrid composes existing layer instances. */
export interface VisualLayer {
  readonly id: string;
  readonly category: "abstract" | "media" | "text";
  readonly object: Object3D;
  update(frame: RoutedFrame): void | Promise<void>;
  dispose(): void;
}

/** Interface only. S02 supplies the actual host/capture/export adapter. */
export interface FrameRenderer {
  render(frame: RoutedFrame): Promise<Uint8Array>;
  dispose(): Promise<void>;
}
