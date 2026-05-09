"use client";

import { useEffect, useRef, useState } from "react";
import { useSettings } from "@/lib/state/useSettings";
import type { VisionFrame } from "@/lib/overlay/schema";

interface CameraFeedProps {
	onFrame?: (frame: VisionFrame) => void;
	onStreamReady?: (stream: MediaStream) => void;
	className?: string;
}

export function CameraFeed({
	onFrame,
	onStreamReady,
	className,
}: CameraFeedProps) {
	const videoRef = useRef<HTMLVideoElement>(null);
	const canvasRef = useRef<HTMLCanvasElement>(null);
	const workerRef = useRef<Worker | null>(null);
	const [permissionState, setPermissionState] = useState<
		"pending" | "granted" | "denied"
	>("pending");
	const [stream, setStream] = useState<MediaStream | null>(null);

	const settings = useSettings();

	useEffect(() => {
		let animationFrame: number;
		let isProcessing = false;

		async function startCamera() {
			try {
				const mediaStream = await navigator.mediaDevices.getUserMedia({
					video: {
						width: { ideal: 1280 },
						height: { ideal: 720 },
						facingMode: "user",
					},
				});

				if (videoRef.current) {
					videoRef.current.srcObject = mediaStream;
					// Use promise-based play() with error handling
					const playPromise = videoRef.current.play();
					if (playPromise !== undefined) {
						playPromise.catch((error) => {
							// Ignore AbortError which happens when play() is interrupted
							if (error.name !== "AbortError") {
								console.error("[CameraFeed] Play error:", error);
							}
						});
					}
				}

				setStream(mediaStream);
				setPermissionState("granted");
				onStreamReady?.(mediaStream);

				// Initialize Web Worker
				workerRef.current = new Worker(
					new URL("@/lib/vision/worker.ts", import.meta.url),
					{ type: "module" }
				);

				workerRef.current.onmessage = (e) => {
					const { type, frame, error } = e.data;

					if (type === "ready") {
						console.log("[CameraFeed] Worker ready");
						startProcessing();
					} else if (type === "frame") {
						onFrame?.(frame);
						isProcessing = false;
					} else if (type === "error") {
						console.error("[CameraFeed] Worker error:", error);
					}
				};

				// Send config to worker
				workerRef.current.postMessage({
					type: "config",
					data: {
						detect_scale: settings.detect_scale,
						aruco_stride: settings.aruco_stride,
						enableArUco: settings.enableArUco,
						enableHands: settings.enableHands,
						enableFace: settings.enableFace,
						calibration: settings.calibration,
					},
				});

				// Initialize worker
				workerRef.current.postMessage({ type: "init" });
			} catch (error) {
				console.error("[CameraFeed] Camera access error:", error);
				setPermissionState("denied");
			}
		}

		function startProcessing() {
			const processNextFrame = () => {
				if (!videoRef.current || !canvasRef.current || !workerRef.current) {
					return;
				}

				if (
					!isProcessing &&
					videoRef.current.readyState === videoRef.current.HAVE_ENOUGH_DATA
				) {
					const video = videoRef.current;
					const canvas = canvasRef.current;

					canvas.width = video.videoWidth;
					canvas.height = video.videoHeight;

					const ctx = canvas.getContext("2d");
					if (ctx) {
						ctx.drawImage(video, 0, 0);
						const imageData = ctx.getImageData(
							0,
							0,
							canvas.width,
							canvas.height
						);

						isProcessing = true;
						workerRef.current.postMessage(
							{
								type: "frame",
								data: {
									imageData,
									width: canvas.width,
									height: canvas.height,
								},
							},
							[imageData.data.buffer] // Transfer ownership for performance
						);
					}
				}

				animationFrame = requestAnimationFrame(processNextFrame);
			};

			processNextFrame();
		}

		startCamera();

		return () => {
			if (animationFrame) {
				cancelAnimationFrame(animationFrame);
			}
			if (workerRef.current) {
				workerRef.current.postMessage({ type: "destroy" });
				workerRef.current.terminate();
			}
			if (stream) {
				stream.getTracks().forEach((track) => track.stop());
			}
		};
	}, [onFrame, onStreamReady, settings]);

	if (permissionState === "denied") {
		return (
			<div className="flex items-center justify-center h-full bg-healthcare-primary text-healthcare-textLight p-8 rounded-xl">
				<div className="text-center">
					<p className="text-large-ui mb-4">📷 Camera Access Required</p>
					<p className="text-body">
						Please allow camera access in your browser settings to use this
						feature.
					</p>
				</div>
			</div>
		);
	}

	return (
		<div className={className}>
			<video
				ref={videoRef}
				className="w-full h-full object-cover rounded-xl"
				autoPlay
				playsInline
				muted
			/>
			<canvas ref={canvasRef} className="hidden" />
			{permissionState === "pending" && (
				<div className="absolute inset-0 flex items-center justify-center bg-healthcare-primary/80 rounded-xl">
					<p className="text-healthcare-textLight text-large-ui">
						Initializing camera...
					</p>
				</div>
			)}
		</div>
	);
}
