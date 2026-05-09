"use client";

import * as React from "react";
import type {
  Anchor,
  OverlayMessage,
  OverlayShape,
  OverlayHUD,
  Landmark
} from "@/lib/cv/messages";
import { cn } from "@/lib/utils/cn";

export type HandDetection = {
  handedness: "Left" | "Right";
  landmarks: Landmark[];
};

export type ArucoDetection = {
  id: number;
  center: { x: number; y: number };
  corners: {
    tl: { x: number; y: number };
    tr: { x: number; y: number };
    bl: { x: number; y: number };
    br: { x: number; y: number };
  };
};

export type OverlayDetections = {
  face?: Landmark[];
  hands?: HandDetection[];
  aruco?: Record<number, ArucoDetection>;
};

export type OverlayDrawOptions = {
  width: number;
  height: number;
  shapes: OverlayShape[];
  hud?: OverlayHUD;
  detections?: OverlayDetections;
};

export interface OverlayCanvasHandle {
  draw: (options: OverlayDrawOptions) => void;
  clear: () => void;
}

export type OverlayCanvasProps = React.CanvasHTMLAttributes<HTMLCanvasElement> & {
  className?: string;
};

export const OverlayCanvas = React.forwardRef<OverlayCanvasHandle, OverlayCanvasProps>(
  ({ className, ...props }, ref) => {
    const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
    const contextRef = React.useRef<CanvasRenderingContext2D | null>(null);

    React.useImperativeHandle(ref, () => ({
      draw: (options) => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const dpr = window.devicePixelRatio || 1;
        const displayWidth = options.width;
        const displayHeight = options.height;
        const neededWidth = Math.floor(displayWidth * dpr);
        const neededHeight = Math.floor(displayHeight * dpr);

        if (canvas.width !== neededWidth || canvas.height !== neededHeight) {
          canvas.width = neededWidth;
          canvas.height = neededHeight;
          canvas.style.width = `${displayWidth}px`;
          canvas.style.height = `${displayHeight}px`;
        }

        const ctx = contextRef.current ?? canvas.getContext("2d");
        if (!ctx) return;
        contextRef.current = ctx;
        ctx.save();
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, displayWidth, displayHeight);
        drawShapes(ctx, options.shapes, options, options.detections);
        ctx.restore();
      },
      clear: () => {
        const canvas = canvasRef.current;
        const ctx = contextRef.current;
        if (!canvas || !ctx) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    }));

    return <canvas ref={canvasRef} className={cn("pointer-events-none", className)} {...props} />;
  }
);
OverlayCanvas.displayName = "OverlayCanvas";

export function drawOverlayFromMessage(
  handle: OverlayCanvasHandle | null,
  message: OverlayMessage | null,
  dimensions: { width: number; height: number },
  detections?: OverlayDetections
) {
  if (!handle || !message) {
    handle?.clear();
    return;
  }
  handle.draw({
    width: dimensions.width,
    height: dimensions.height,
    shapes: message.shapes,
    hud: message.hud,
    detections
  });
}

function drawShapes(
  ctx: CanvasRenderingContext2D,
  shapes: OverlayShape[],
  options: OverlayDrawOptions,
  detections?: OverlayDetections
) {
  if (!shapes?.length) return;
  const hud = options.hud;
  for (const shape of shapes) {
    switch (shape.kind) {
      case "ring":
        drawRing(ctx, shape, detections);
        break;
      case "arrow":
        drawArrow(ctx, shape, detections);
        break;
      case "text":
        drawText(ctx, shape, detections);
        break;
      case "progress":
        drawProgress(ctx, shape, detections);
        break;
      default:
        break;
    }
  }
  if (hud) {
    drawHud(ctx, hud, options.width);
  }
}

type ResolvedPoint = { x: number; y: number } | null;

type AnchorResolutionContext = OverlayDetections | undefined;

function resolveAnchor(anchor: Anchor, context: AnchorResolutionContext): ResolvedPoint {
  if ("pixel" in anchor) {
    return anchor.pixel;
  }
  if ("face" in anchor) {
    const face = context?.face;
    if (!face) return null;
    return face[anchor.face.idx] ?? null;
  }
  if ("hand" in anchor) {
    const hands = context?.hands;
    if (!hands?.length) return null;
    const hand = hands[0];
    return hand.landmarks[anchor.hand.idx] ?? null;
  }
  if ("aruco" in anchor) {
    const aruco = context?.aruco?.[anchor.aruco.id];
    if (!aruco) return null;
    const part = anchor.aruco.part ?? "center";
    if (part === "center") return aruco.center;
    return aruco.corners[part as keyof typeof aruco.corners] ?? null;
  }
  return null;
}

function drawRing(
  ctx: CanvasRenderingContext2D,
  shape: Extract<OverlayShape, { kind: "ring" }>,
  detections?: OverlayDetections
) {
  const center = resolveAnchor(shape.anchor, detections);
  if (!center) return;
  const color = shape.color ?? "rgba(14, 165, 164, 0.9)";
  const thickness = shape.thickness_px ?? 8;
  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = thickness;
  ctx.shadowBlur = 12;
  ctx.shadowColor = "rgba(14, 165, 164, 0.35)";
  ctx.arc(center.x, center.y, shape.radius_px, 0, Math.PI * 2);
  ctx.stroke();
  ctx.shadowBlur = 0;
}

function drawArrow(
  ctx: CanvasRenderingContext2D,
  shape: Extract<OverlayShape, { kind: "arrow" }>,
  detections?: OverlayDetections
) {
  const start = resolveAnchor(shape.anchor, detections);
  const end = resolveAnchor(shape.to, detections);
  if (!start || !end) return;
  const color = shape.color ?? "rgba(245, 158, 11, 0.95)";
  const width = shape.width_px ?? 12;

  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = "round";
  ctx.shadowBlur = 20;
  ctx.shadowColor = "rgba(245, 158, 11, 0.4)";
  ctx.beginPath();
  ctx.moveTo(start.x, start.y);
  ctx.lineTo(end.x, end.y);
  ctx.stroke();

  const angle = Math.atan2(end.y - start.y, end.x - start.x);
  const headLength = Math.max(24, width * 2.5);
  ctx.beginPath();
  ctx.moveTo(end.x, end.y);
  ctx.lineTo(
    end.x - headLength * Math.cos(angle - Math.PI / 6),
    end.y - headLength * Math.sin(angle - Math.PI / 6)
  );
  ctx.lineTo(
    end.x - headLength * Math.cos(angle + Math.PI / 6),
    end.y - headLength * Math.sin(angle + Math.PI / 6)
  );
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
  ctx.shadowBlur = 0;
}

function drawText(
  ctx: CanvasRenderingContext2D,
  shape: Extract<OverlayShape, { kind: "text" }>,
  detections?: OverlayDetections
) {
  const anchor = resolveAnchor(shape.anchor, detections);
  if (!anchor) return;
  const color = shape.color ?? "#fff";
  const paddingX = 16;
  const paddingY = 10;
  const background = shape.background ?? "rgba(15, 23, 42, 0.75)";
  ctx.font = "600 20px var(--font-display, 'Manrope')";
  const metrics = ctx.measureText(shape.text);
  const width = metrics.width + paddingX * 2;
  const height = 32 + paddingY;
  const x = anchor.x - width / 2;
  const y = anchor.y - height - 20;
  ctx.fillStyle = background;
  roundRect(ctx, x, y, width, height, 14);
  ctx.fill();
  ctx.fillStyle = color;
  ctx.fillText(shape.text, x + paddingX, y + height - paddingY);
}

function drawProgress(
  ctx: CanvasRenderingContext2D,
  shape: Extract<OverlayShape, { kind: "progress" }>,
  detections?: OverlayDetections
) {
  const center = resolveAnchor(shape.anchor, detections);
  if (!center) return;
  const radius = 64;
  const baseColor = "rgba(255, 255, 255, 0.25)";
  const accent = shape.color ?? "rgba(14, 165, 164, 0.9)";
  const progress = Math.min(Math.max(shape.value, 0), 1);

  ctx.beginPath();
  ctx.strokeStyle = baseColor;
  ctx.lineWidth = 10;
  ctx.arc(center.x, center.y, radius, 0, Math.PI * 2);
  ctx.stroke();

  ctx.strokeStyle = accent;
  ctx.beginPath();
  ctx.arc(center.x, center.y, radius, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * progress);
  ctx.stroke();
}

function drawHud(ctx: CanvasRenderingContext2D, hud: OverlayHUD, width: number) {
  const panelWidth = Math.min(480, width - 40);
  const x = (width - panelWidth) / 2;
  const y = 24;
  ctx.fillStyle = "rgba(15, 23, 42, 0.82)";
  roundRect(ctx, x, y, panelWidth, 120, 20);
  ctx.fill();
  ctx.fillStyle = "#0EA5A4";
  ctx.font = "600 22px var(--font-display, 'Manrope')";
  if (hud.title) {
    ctx.fillText(hud.title, x + 28, y + 40);
  }
  ctx.fillStyle = "rgba(255,255,255,0.82)";
  ctx.font = "500 18px var(--font-sans, 'Inter')";
  if (hud.subtitle) {
    ctx.fillText(hud.subtitle, x + 28, y + 70);
  }
  if (hud.hint) {
    ctx.fillStyle = "rgba(255,255,255,0.7)";
    ctx.font = "400 16px var(--font-sans, 'Inter')";
    ctx.fillText(hud.hint, x + 28, y + 96);
  }
  if (hud.time_left_s && hud.max_time_s) {
    const progress = Math.max(0, Math.min(1, hud.time_left_s / hud.max_time_s));
    const barWidth = panelWidth - 56;
    const barX = x + 28;
    const barY = y + 108;
    ctx.fillStyle = "rgba(255,255,255,0.12)";
    roundRect(ctx, barX, barY, barWidth, 8, 4);
    ctx.fill();
    ctx.fillStyle = "rgba(14, 165, 164, 0.9)";
    roundRect(ctx, barX, barY, barWidth * progress, 8, 4);
    ctx.fill();
  }
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number
) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r);
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}
