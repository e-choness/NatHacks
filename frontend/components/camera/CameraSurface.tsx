"use client";

import * as React from "react";
import { useAppStore } from "@/lib/state/store";
import {
  OverlayCanvas,
  type OverlayCanvasHandle,
  type OverlayDetections,
  drawOverlayFromMessage
} from "@/components/overlays/OverlayCanvas";
import { createRafLoop, type RafLoopHandle } from "@/lib/utils/rafLoop";
import type { MediapipeFrameResult, CVWorkerResponse } from "@/lib/cv/messages";

const FRAME_INTERVAL = 1000 / 24;

export function CameraSurface() {
  const videoRef = React.useRef<HTMLVideoElement | null>(null);
  const overlayRef = React.useRef<OverlayCanvasHandle | null>(null);
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const processLoopRef = React.useRef<RafLoopHandle | null>(null);
  const opencvWorkerRef = React.useRef<Worker | null>(null);
  const mediapipeWorkerRef = React.useRef<Worker | null>(null);
  const detectionsRef = React.useRef<OverlayDetections>({});
  const framePendingRef = React.useRef(false);
  const lastFrameTimeRef = React.useRef<number>(performance.now());
  const [status, setStatus] = React.useState<"idle" | "starting" | "ready" | "error">("idle");
  const [error, setError] = React.useState<string | null>(null);
  const [dimensions, setDimensions] = React.useState({ width: 1280, height: 720 });

  const overlayMessage = useAppStore((state) => state.overlays);
  const setOverlays = useAppStore((state) => state.actions.setOverlays);
  const overlayMessageRef = React.useRef(overlayMessage);
  const overlaySourceRef = React.useRef<"local" | "remote" | null>(null);
  const dimensionsRef = React.useRef(dimensions);
  const setOverlaysRef = React.useRef(setOverlays);

  React.useEffect(() => {
    overlayMessageRef.current = overlayMessage;
    overlaySourceRef.current = overlayMessage?.source ?? null;
  }, [overlayMessage]);

  React.useEffect(() => {
    dimensionsRef.current = dimensions;
  }, [dimensions]);

  React.useEffect(() => {
    setOverlaysRef.current = setOverlays;
  }, [setOverlays]);

  const updateDimensions = React.useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    const { videoWidth, videoHeight } = video;
    if (!videoWidth || !videoHeight) return;
    setDimensions((prev) => {
      if (prev.width === videoWidth && prev.height === videoHeight) return prev;
      return { width: videoWidth, height: videoHeight };
    });
  }, []);

  const sendFrame = React.useCallback(
    (video: HTMLVideoElement) => {
      if (framePendingRef.current) return;
      if (typeof createImageBitmap !== "function") return;
      framePendingRef.current = true;
      const width = video.videoWidth || dimensions.width;
      const height = video.videoHeight || dimensions.height;
      Promise.all([createImageBitmap(video), createImageBitmap(video)])
        .then(([cvFrame, mpFrame]) => {
          opencvWorkerRef.current?.postMessage(
            {
              type: "processFrame",
              payload: { frame: cvFrame, width, height }
            },
            [cvFrame]
          );
          mediapipeWorkerRef.current?.postMessage(
            {
              type: "processFrame",
              payload: { frame: mpFrame, width, height }
            },
            [mpFrame]
          );
        })
        .catch((err) => {
          console.warn("frame transfer failed", err);
        })
        .finally(() => {
          framePendingRef.current = false;
        });
    },
    [dimensions.height, dimensions.width]
  );

  React.useEffect(() => {
    let mounted = true;
    async function bootstrapCamera() {
      try {
        setStatus("starting");
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: "user",
            width: { ideal: 1280 },
            height: { ideal: 720 }
          },
          audio: false
        });
        if (!mounted) return;
        const video = videoRef.current;
        if (video) {
          video.srcObject = stream;
          await video.play();
          updateDimensions();
          setStatus("ready");
        }
      } catch (err) {
        console.error("Camera error", err);
        setStatus("error");
        setError((err as Error)?.message ?? "Unable to access camera");
      }
    }
    bootstrapCamera();
    const videoEl = videoRef.current;
    return () => {
      mounted = false;
      const stream = videoEl?.srcObject as MediaStream | null;
      stream?.getTracks().forEach((track) => track.stop());
      processLoopRef.current?.stop();
      opencvWorkerRef.current?.terminate();
      mediapipeWorkerRef.current?.terminate();
    };
  }, [updateDimensions]);

  React.useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.addEventListener("loadedmetadata", updateDimensions);
    return () => {
      video.removeEventListener("loadedmetadata", updateDimensions);
    };
  }, [updateDimensions]);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const opencvWorker = new Worker(new URL("../../lib/cv/opencv.worker.ts", import.meta.url), {
      type: "module"
    });
    const mediapipeWorker = new Worker(new URL("../../lib/cv/mediapipe.worker.ts", import.meta.url), {
      type: "module"
    });

    opencvWorkerRef.current = opencvWorker;
    mediapipeWorkerRef.current = mediapipeWorker;

    opencvWorker.postMessage({ type: "init" });

    opencvWorker.onmessage = (event) => {
      const message = event.data as CVWorkerResponse;
      if (!message) return;
      if (message.type === "overlay.set") {
        const source = message.source ?? "local";
        if (source === "local" && overlaySourceRef.current === "remote") {
          drawOverlayFromMessage(
            overlayRef.current,
            overlayMessageRef.current,
            dimensionsRef.current,
            detectionsRef.current
          );
          return;
        }
        overlaySourceRef.current = source;
        if (source === "local") {
          setOverlaysRef.current(message);
          overlayMessageRef.current = message;
        } else {
          const remoteMessage = { ...message, source: "remote" as const };
          setOverlaysRef.current(remoteMessage);
          overlayMessageRef.current = remoteMessage;
        }
        drawOverlayFromMessage(
          overlayRef.current,
          overlayMessageRef.current,
          dimensionsRef.current,
          detectionsRef.current
        );
      }
      if (message.type === "calibration.result") {
        // Calibration persistence handled elsewhere; we surface HUD update later in flow.
      }
    };

    mediapipeWorker.onmessage = (event) => {
      const message = event.data as MediapipeFrameResult;
      if (!message) return;
      if (message.type === "landmarks") {
        const hands = message.payload.hands ?? [];
        detectionsRef.current = {
          face: message.payload.face?.landmarks ?? undefined,
          hands: hands.length
            ? hands.map((hand: any) => ({
                handedness: hand.handedness,
                landmarks: hand.landmarks
              }))
            : undefined,
          aruco: detectionsRef.current.aruco
        };
        drawOverlayFromMessage(
          overlayRef.current,
          overlayMessageRef.current,
          dimensionsRef.current,
          detectionsRef.current
        );
      }
    };

    return () => {
      opencvWorker.terminate();
      mediapipeWorker.terminate();
    };
  }, []);

  React.useEffect(() => {
    if (status !== "ready") return;
    const loop = createRafLoop(() => {
      const now = performance.now();
      if (now - lastFrameTimeRef.current < FRAME_INTERVAL) {
        return;
      }
      const video = videoRef.current;
      if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;
      lastFrameTimeRef.current = now;
      sendFrame(video);
    });
    loop.start();
    processLoopRef.current = loop;
    return () => {
      loop.stop();
    };
  }, [status, sendFrame]);

  React.useEffect(() => {
    if (!overlayRef.current) return;
    drawOverlayFromMessage(overlayRef.current, overlayMessage, dimensions, detectionsRef.current);
  }, [overlayMessage, dimensions]);

  return (
    <div className="flex w-full flex-col gap-4">
      <div
        ref={containerRef}
        className="relative aspect-video w-full overflow-hidden rounded-3xl border border-border bg-black shadow-glass"
      >
        <video
          ref={videoRef}
          className="h-full w-full bg-black object-cover"
          playsInline
          muted
          autoPlay
        />
        <OverlayCanvas ref={overlayRef} className="absolute inset-0" />
        {status !== "ready" && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80">
            <div className="rounded-xl border border-border bg-card/90 px-6 py-4 text-lg font-medium">
              {status === "starting" && "Connecting to camera..."}
              {status === "error" && (error ?? "Camera unavailable")}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
