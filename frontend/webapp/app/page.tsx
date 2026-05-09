"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { CameraFeed } from "@/components/camera/CameraFeed";
import { OverlayCanvas } from "@/components/overlay/OverlayCanvas";
import { useRoutine, DEFAULT_ROUTINES } from "@/lib/state/useRoutine";
import { useSettings } from "@/lib/state/useSettings";
import { MotionTracker } from "@/lib/tracking/motionTracker";
import type { VisionFrame } from "@/lib/overlay/schema";
import type { Shape, HUD } from "@/lib/overlay/schema";

export default function MirrorPage() {
	const [visionFrame, setVisionFrame] = useState<VisionFrame | null>(null);
	const [shapes, setShapes] = useState<Shape[]>([]);
	const [hud, setHUD] = useState<HUD | undefined>();
	const [landmarkMap, setLandmarkMap] = useState<
		Map<string, { x: number; y: number }>
	>(new Map());
	const [activityCompletion, setActivityCompletion] = useState(0);

	const motionTrackerRef = useRef(new MotionTracker());

	const {
		currentRoutine,
		currentStepIndex,
		isRunning,
		isPaused,
		timeRemaining,
		startRoutine,
		pauseRoutine,
		resumeRoutine,
		nextStep,
		completeStep,
		tick,
		totalXP,
		currentStreak,
	} = useRoutine();

	const settings = useSettings();

	// Build landmark map and track motion from vision frame
	useEffect(() => {
		const newMap = new Map<string, { x: number; y: number }>();
		const tracker = motionTrackerRef.current;

		if (visionFrame) {
			// Add hand landmarks and track motion
			if (visionFrame.hands.landmarks) {
				visionFrame.hands.landmarks.forEach((hand, handIdx) => {
					for (let i = 0; i < hand.length / 3; i++) {
						const x = hand[i * 3];
						const y = hand[i * 3 + 1];
						const z = hand[i * 3 + 2];
						newMap.set(`hand_${handIdx}_${i}`, { x, y });

						// Add named landmarks for common points
						if (i === 0) {
							newMap.set(`hand_${handIdx}_wrist`, { x, y });
							// Track wrist position for motion detection
							tracker.updateHand(handIdx, { x, y, z });
						}
						if (i === 8) newMap.set(`hand_${handIdx}_index_tip`, { x, y });
						if (i === 4) newMap.set(`hand_${handIdx}_thumb_tip`, { x, y });
					}
				});
			}

			// Add face landmarks and track motion
			if (visionFrame.face.landmarks) {
				const face = visionFrame.face.landmarks;
				for (let i = 0; i < face.length / 3; i++) {
					const x = face[i * 3];
					const y = face[i * 3 + 1];
					const z = face[i * 3 + 2];
					newMap.set(`face_${i}`, { x, y });

					// Track face center (nose tip is typically landmark 1)
					if (i === 1) {
						tracker.updateFace({ x, y, z });
					}
				}
			}

			// Calculate activity completion if routine is running
			if (isRunning && currentRoutine) {
				const currentStep = currentRoutine.steps[currentStepIndex];
				if (
					currentStep &&
					visionFrame.hands.present &&
					visionFrame.hands.landmarks
				) {
					let completion = 0;

					// Get hand position (index finger tip)
					const hand0 = visionFrame.hands.landmarks[0];
					if (hand0) {
						const indexTipX = hand0[8 * 3];
						const indexTipY = hand0[8 * 3 + 1];

						// Determine activity type based on step
						if (
							currentStep.id.includes("brush") ||
							currentStep.id.includes("floss")
						) {
							// For brushing, check if hand is near mouth/face
							let handNearMouth = false;
							if (visionFrame.face.present && visionFrame.face.roi) {
								const roi = visionFrame.face.roi;
								const mouthX = roi.x + roi.w / 2;
								const mouthY = roi.y + roi.h / 2 + 0.1;

								const dx = indexTipX - mouthX;
								const dy = indexTipY - mouthY;
								const distance = Math.sqrt(dx * dx + dy * dy);

								handNearMouth = distance < 0.15; // Within 15% of screen
							}

							// Only count circular motion when hand is near mouth
							if (handNearMouth) {
								completion = tracker.calculateActivityCompletion("circular", 0);
							} else {
								// Partial completion for reaching the mouth area
								completion = 0.1;
							}
						} else if (currentStep.id.includes("comb")) {
							completion = tracker.calculateActivityCompletion("vertical", 0);
						} else {
							completion = tracker.calculateActivityCompletion("static", 0);
						}
					}

					setActivityCompletion(completion);

					// Auto-complete step if activity is done
					if (completion >= 0.9 && timeRemaining === 0) {
						completeStep(1);
						tracker.reset();
					}
				}
			}
		}

		setLandmarkMap(newMap);
	}, [
		visionFrame,
		isRunning,
		currentRoutine,
		currentStepIndex,
		timeRemaining,
		completeStep,
	]);

	// Timer tick every second
	useEffect(() => {
		if (isRunning && !isPaused) {
			const interval = setInterval(() => {
				tick();
			}, 1000);
			return () => clearInterval(interval);
		}
	}, [isRunning, isPaused, tick]);

	// Generate overlays based on current routine step and vision data
	useEffect(() => {
		const newShapes: Shape[] = [];
		let newHUD: HUD | undefined;

		if (currentRoutine && isRunning) {
			const currentStep = currentRoutine.steps[currentStepIndex];

			if (currentStep) {
				// HUD display
				newHUD = {
					title: currentRoutine.title,
					step: `${currentStepIndex + 1}/${currentRoutine.steps.length}: ${currentStep.label}`,
					hint: currentStep.hint,
					time_left_s: timeRemaining,
					max_time_s: currentStep.duration_s,
				};

				// Hand target overlay for hand-based tasks
				if (currentStep.target?.type === "hand") {
					// Determine target position based on task type
					let targetX = 0.5;
					let targetY = 0.5;
					let targetLabel = "Move here";

					// For brushing/mouth-related tasks, target is the mouth
					if (
						currentStep.id.includes("brush") ||
						currentStep.id.includes("floss")
					) {
						if (visionFrame?.face.present && visionFrame.face.landmarks) {
							// Use mouth center (landmarks around index 13 are near mouth)
							// Mouth landmarks are typically 61, 291, 0, 17, etc.
							// We'll use face ROI center for simplicity
							const roi = visionFrame.face.roi;
							if (roi) {
								targetX = roi.x + roi.w / 2;
								targetY = roi.y + roi.h / 2 + 0.1; // Slightly below face center
								targetLabel = "Bring to mouth";
							}
						} else {
							// Show message to show face first
							newShapes.push({
								kind: "text",
								anchor: { norm: { x: 0.5, y: 0.3 } },
								text: "Show your face first",
								size: 28,
							});
						}
					}

					if (visionFrame?.hands.present && visionFrame.hands.count > 0) {
						// Show target zone at mouth/face position
						newShapes.push({
							kind: "ring",
							anchor: { norm: { x: targetX, y: targetY } },
							radius_px: 80,
							pulse: true,
						});

						// Track each hand
						for (let i = 0; i < visionFrame.hands.count; i++) {
							const handLandmarks = visionFrame.hands.landmarks?.[i];
							if (handLandmarks) {
								// Use index finger tip (landmark 8) for brushing
								const indexTipX = handLandmarks[8 * 3];
								const indexTipY = handLandmarks[8 * 3 + 1];

								// Calculate distance to target
								const dx = indexTipX - targetX;
								const dy = indexTipY - targetY;
								const distance = Math.sqrt(dx * dx + dy * dy);

								// Show hand indicator
								newShapes.push({
									kind: "handTarget",
									anchor: { norm: { x: indexTipX, y: indexTipY } },
									radius_px: 50,
								});

								// Draw arrow if hand is far from target
								if (distance > 0.15) {
									newShapes.push({
										kind: "arrow",
										from: { norm: { x: indexTipX, y: indexTipY } },
										to: { norm: { x: targetX, y: targetY } },
										label: targetLabel,
									});
								} else {
									// Hand is at target - show success feedback
									newShapes.push({
										kind: "text",
										anchor: { norm: { x: targetX, y: targetY - 0.15 } },
										text: "Perfect! Keep moving",
										size: 24,
									});

									// Highlight the target zone in green
									newShapes.push({
										kind: "badge",
										anchor: { norm: { x: targetX, y: targetY } },
										text: "✓",
										accent: "success",
									});
								}
							}
						}
					} else {
						// Show target zone and instruction when no hands detected
						newShapes.push({
							kind: "ring",
							anchor: { norm: { x: targetX, y: targetY } },
							radius_px: 80,
							pulse: true,
						});

						newShapes.push({
							kind: "text",
							anchor: { norm: { x: 0.5, y: 0.5 } },
							text: "Show your hands",
							size: 32,
						});
					}
				}

				// Face overlay for face-based tasks
				if (currentStep.target?.type === "face") {
					if (visionFrame?.face.present && visionFrame.face.roi) {
						const roi = visionFrame.face.roi;
						// Draw ring around detected face
						newShapes.push({
							kind: "ring",
							anchor: { norm: { x: roi.x + roi.w / 2, y: roi.y + roi.h / 2 } },
							radius_px: Math.max(roi.w, roi.h) * 300, // Scale to pixels
							pulse: true,
						});
					} else {
						// Show message when no face detected
						newShapes.push({
							kind: "text",
							anchor: { norm: { x: 0.5, y: 0.5 } },
							text: "Position your face in view",
							size: 32,
						});

						newShapes.push({
							kind: "ring",
							anchor: { norm: { x: 0.5, y: 0.3 } },
							radius_px: 150,
							pulse: true,
						});
					}
				}

				// Progress indicator (time-based)
				const timeProgress =
					currentStep.duration_s > 0
						? (currentStep.duration_s - timeRemaining) / currentStep.duration_s
						: 0;

				newShapes.push({
					kind: "progress",
					anchor: { pixel: { x: 100, y: 100 } },
					value: Math.round(timeProgress * 100),
					max: 100,
				});

				// Activity completion indicator (motion-based)
				if (currentStep.target?.type === "hand") {
					newShapes.push({
						kind: "text",
						anchor: { pixel: { x: 100, y: 200 } },
						text: `Activity: ${Math.round(activityCompletion * 100)}%`,
						size: 20,
					});

					// Show checkmark when activity is complete
					if (activityCompletion >= 0.9) {
						newShapes.push({
							kind: "badge",
							anchor: { norm: { x: 0.5, y: 0.5 } },
							text: "✓",
							accent: "success",
						});
					}
				}

				// Step counter badge
				newShapes.push({
					kind: "badge",
					anchor: { pixel: { x: 50, y: 50 } },
					text: `${currentStepIndex + 1}`,
					accent: "info",
				});
			}
		} else {
			// Idle HUD
			newHUD = {
				title: "Assistive Coach",
				subtitle: "Ready to start",
				hint: "Press Start to begin your routine",
			};
		}

		console.log("[MirrorPage] Generated shapes:", newShapes.length, newShapes);
		console.log("[MirrorPage] Vision:", {
			hands: visionFrame?.hands,
			face: visionFrame?.face,
		});
		setShapes(newShapes);
		setHUD(newHUD);
	}, [currentRoutine, currentStepIndex, isRunning, timeRemaining, visionFrame]);

	// Handle vision frame updates
	const handleFrame = useCallback((frame: VisionFrame) => {
		setVisionFrame(frame);
	}, []);

	// Start default routine
	const handleStart = () => {
		startRoutine(DEFAULT_ROUTINES[0]);
	};

	return (
		<main className="relative w-full h-screen bg-healthcare-background overflow-hidden">
			{/* Camera feed */}
			<div className="relative w-full h-full">
				<CameraFeed onFrame={handleFrame} className="object-cover" />

				{/* Overlay canvas */}
				<OverlayCanvas shapes={shapes} hud={hud} landmarkMap={landmarkMap} />
			</div>

			{/* Control panel (bottom) */}
			<div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-healthcare-background/90 to-transparent">
				<div className="flex items-center justify-center gap-4">
					{!isRunning && (
						<button
							onClick={handleStart}
							className="touch-target px-8 py-4 bg-healthcare-accent text-white rounded-lg font-semibold text-lg shadow-lg hover:bg-healthcare-accent/90 transition-colors"
						>
							Start Routine
						</button>
					)}

					{isRunning && (
						<>
							<button
								onClick={isPaused ? resumeRoutine : pauseRoutine}
								className="touch-target px-6 py-3 bg-healthcare-warmAccent text-white rounded-lg font-semibold shadow-lg hover:bg-healthcare-warmAccent/90 transition-colors"
							>
								{isPaused ? "Resume" : "Pause"}
							</button>

							<button
								onClick={nextStep}
								className="touch-target px-6 py-3 bg-healthcare-accent text-white rounded-lg font-semibold shadow-lg hover:bg-healthcare-accent/90 transition-colors"
							>
								Next Step
							</button>
						</>
					)}
				</div>

				{/* Stats bar */}
				<div className="mt-4 flex items-center justify-center gap-8 text-white text-body">
					<div className="flex items-center gap-2">
						<span>⭐</span>
						<span className="font-semibold">{totalXP} XP</span>
					</div>
					<div className="flex items-center gap-2">
						<span>🔥</span>
						<span className="font-semibold">{currentStreak} day streak</span>
					</div>
					<div className="flex items-center gap-2">
						<span>📹</span>
						<span className="font-semibold">
							{visionFrame?.fps.toFixed(1) || 0} FPS
						</span>
					</div>
				</div>
			</div>

			{/* Debug info (top-right corner) */}
			{process.env.NODE_ENV === "development" && (
				<div className="absolute top-4 right-4 bg-black/80 text-white text-xs p-3 rounded-lg font-mono space-y-1">
					<div>Face: {visionFrame?.face.present ? "✓" : "✗"}</div>
					<div>Hands: {visionFrame?.hands.count || 0}</div>
					<div>ArUco: {visionFrame?.aruco.count || 0}</div>
					<div>FPS: {visionFrame?.fps.toFixed(1) || 0}</div>
					<div>Scale: {settings.detect_scale}</div>
				</div>
			)}
		</main>
	);
}
