"use client";

import { useRef, useEffect, useState } from "react";
import {
	renderShapes,
	drawHUD,
	type RenderContext,
} from "@/lib/overlay/engine";
import type { Shape, HUD } from "@/lib/overlay/schema";

interface OverlayCanvasProps {
	width?: number;
	height?: number;
	shapes: Shape[];
	hud?: HUD;
	landmarkMap?: Map<string, { x: number; y: number }>;
	arucoCorners?: Map<number, Array<{ x: number; y: number }>>;
	className?: string;
}

export function OverlayCanvas({
	width: propWidth,
	height: propHeight,
	shapes,
	hud,
	landmarkMap,
	arucoCorners,
	className = "",
}: OverlayCanvasProps) {
	const canvasRef = useRef<HTMLCanvasElement>(null);
	const containerRef = useRef<HTMLDivElement>(null);
	const [dimensions, setDimensions] = useState({
		width: propWidth || 1280,
		height: propHeight || 720,
	});

	// Update dimensions when container size changes
	useEffect(() => {
		if (!propWidth || !propHeight) {
			const updateDimensions = () => {
				if (containerRef.current) {
					const rect = containerRef.current.getBoundingClientRect();
					setDimensions({ width: rect.width, height: rect.height });
				}
			};

			updateDimensions();
			window.addEventListener("resize", updateDimensions);
			return () => window.removeEventListener("resize", updateDimensions);
		} else {
			setDimensions({ width: propWidth, height: propHeight });
		}
	}, [propWidth, propHeight]);

	useEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas) return;

		const ctx = canvas.getContext("2d");
		if (!ctx) return;

		const { width, height } = dimensions;

		console.log("[OverlayCanvas] Rendering:", {
			dimensions,
			shapesCount: shapes.length,
			hasHUD: !!hud,
		});

		// Clear canvas
		ctx.clearRect(0, 0, width, height);

		const renderCtx: RenderContext = { ctx, width, height };

		// Draw all shapes
		renderShapes(renderCtx, shapes, landmarkMap, arucoCorners);

		// Draw HUD if present
		if (hud) {
			drawHUD(renderCtx, hud);
		}
	}, [shapes, hud, dimensions, landmarkMap, arucoCorners]);

	return (
		<div
			ref={containerRef}
			className={className}
			style={{
				position: "absolute",
				top: 0,
				left: 0,
				width: "100%",
				height: "100%",
				pointerEvents: "none",
			}}
		>
			<canvas
				ref={canvasRef}
				width={dimensions.width}
				height={dimensions.height}
				style={{
					width: "100%",
					height: "100%",
					pointerEvents: "none",
				}}
			/>
		</div>
	);
}
