/**
 * MagicMirror² Module: MMM-AssistiveCoach
 * Renders assistive HUD overlays driven by backend WebSocket events.
 */

// Detect reduced motion preference
const reduceMotion = window.matchMedia(
	"(prefers-reduced-motion: reduce)"
).matches;
if (reduceMotion) {
	document.documentElement.classList.add("prefers-reduced-motion");
}

Module.register("MMM-AssistiveCoach", {
	defaults: {
		wsUrl: "ws://localhost:5055/ws/mirror",
		apiBase: "http://127.0.0.1:8000", // Default to FastAPI backend
		theme: "high-contrast",
		fontScale: 1.0,
		reduceMotion: reduceMotion,
	},

	start() {
		this.state = {
			hud: {},
			shapes: [],
			devices: {
				camera: "off",
				lighting: "unknown",
				mic: "off",
			},
			showTaskMenu: false,
			availableTasks: [],
			currentTask: null,
		};
		this.socketConnected = false;
		this.pendingOverlay = null;
		this.rafScheduled = false;
		this._setupDomReadyListener();
		this._setupKeyboardShortcuts();
		this._loadAvailableTasks(); // Load tasks from backend
		this.sendSocketNotification("MMM_ASSISTIVECOACH_INIT", {
			wsUrl: this.config.wsUrl,
			apiBase: this.config.apiBase, // Pass apiBase to node_helper
		});
	},

	notificationReceived(notification, payload) {
		if (notification === "ALL_MODULES_STARTED") {
			this._resizeOverlay();
		}
	},

	socketNotificationReceived(notification, payload) {
		if (notification === "MMM_ASSISTIVECOACH_EVENT") {
			this._handleMirrorEvent(payload);
		} else if (notification === "MMM_ASSISTIVECOACH_STATUS") {
			this.socketConnected = payload.connected;
			this.updateDom(0);
		}
	},

	getDom() {
		const container = document.createElement("div");
		container.id = "assistive-coach";
		container.className = `assistivecoach ${this.config.theme}`;

		const chips = document.createElement("div");
		chips.id = "chips";
		this._renderChips(chips);
		container.appendChild(chips);

		const hud = document.createElement("div");
		hud.id = "hud";
		hud.className = "hud";
		hud.style.setProperty("--font-scale", this.config.fontScale);
		this._renderHud(hud);
		container.appendChild(hud);

		// Render task menu if shown
		this._renderTaskMenu(container);

		// Camera preview panel (bottom-right corner)
		const preview = document.createElement("img");
		preview.id = "camera-preview";
		preview.style.cssText = `
			position: fixed;
			bottom: 20px;
			right: 20px;
			width: 320px;
			height: 240px;
			border: 3px solid #00bcd4;
			border-radius: 10px;
			box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
			z-index: 9999;
		`;
		const apiBase = this.config.apiBase || "http://127.0.0.1:8000";
		preview.src = `${apiBase}/preview.jpg?t=${Date.now()}`;
		// Refresh preview every 100ms (10 FPS)
		setInterval(() => {
			preview.src = `${apiBase}/preview.jpg?t=${Date.now()}`;
		}, 100);
		container.appendChild(preview);

		const overlay = document.createElementNS(
			"http://www.w3.org/2000/svg",
			"svg"
		);
		overlay.id = "overlay";
		overlay.setAttribute("preserveAspectRatio", "none");
		this.overlaySvg = overlay;
		container.appendChild(overlay);

		this._resizeOverlay();

		return container;
	},

	getStyles() {
		return ["modules/MMM-AssistiveCoach/styles.css"];
	},

	_setupDomReadyListener() {
		window.addEventListener("resize", () => this._resizeOverlay());
	},

	_setupKeyboardShortcuts() {
		document.addEventListener("keydown", (e) => {
			// Prevent default if we're handling the key
			const isOurKey =
				["t", "n", "1", "2", "3", "4"].includes(e.key.toLowerCase()) ||
				(e.key.toLowerCase() === "s" && e.shiftKey);

			// T = Toggle task menu
			if (e.key.toLowerCase() === "t") {
				e.preventDefault();
				this._toggleTaskMenu();
				console.log("Toggling task menu");
			}
			// N = Next step (in active task)
			else if (e.key.toLowerCase() === "n") {
				e.preventDefault();
				this._nextStep();
				console.log("Next step");
			}
			// S = Stop current task
			else if (e.key.toLowerCase() === "s" && e.shiftKey) {
				e.preventDefault();
				this._stopTask();
				console.log("Stopping task");
			}
			// Number keys 1-4 = Start specific task quickly
			else if (["1", "2", "3", "4"].includes(e.key)) {
				const taskIndex = Number(e.key) - 1;
				console.log(
					`Key ${e.key} pressed, task index: ${taskIndex}, available tasks:`,
					this.state.availableTasks
				);
				if (this.state.availableTasks && this.state.availableTasks[taskIndex]) {
					e.preventDefault();
					const taskId = this.state.availableTasks[taskIndex].task_id;
					console.log(`Starting task: ${taskId}`);
					this._startTask(taskId);
				} else {
					console.warn(
						`No task at index ${taskIndex}. Tasks loaded: ${
							this.state.availableTasks?.length || 0
						}`
					);
				}
			}
		});
	},

	_demoStep(n) {
		const size = 90 + n * 10;
		const overlay = {
			type: "overlay.set",
			shapes: [
				{
					kind: "ring",
					anchor: {
						pixel: { x: window.innerWidth / 2, y: window.innerHeight / 2 },
					},
					radius_px: size,
					accent: "info",
				},
			],
			hud: {
				title: `Demo Step ${n}`,
				step: `Step ${n} of 3`,
				subtitle: "Keyboard preview",
				time_left_s: 5,
				max_time_s: 5,
				hint: "Press 1/2/3 for demo steps",
			},
			_local: true,
		};
		this._onOverlayMessage(overlay);
	},

	_resizeOverlay() {
		if (!this.overlaySvg) {
			return;
		}
		const width = window.innerWidth;
		const height = window.innerHeight;
		this.overlaySvg.setAttribute("viewBox", `0 0 ${width} ${height}`);
		this.overlaySvg.setAttribute("width", `${width}`);
		this.overlaySvg.setAttribute("height", `${height}`);
		this._ensureDefs();
		this._renderShapes();
	},

	_ensureDefs() {
		if (!this.overlaySvg) {
			return;
		}
		let defs = this.overlaySvg.querySelector("defs");
		if (!defs) {
			defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
			this.overlaySvg.appendChild(defs);
		}
		if (!this.overlaySvg.querySelector("marker#assistivecoach-arrow")) {
			const marker = document.createElementNS(
				"http://www.w3.org/2000/svg",
				"marker"
			);
			marker.setAttribute("id", "assistivecoach-arrow");
			marker.setAttribute("viewBox", "0 0 10 10");
			marker.setAttribute("refX", "5");
			marker.setAttribute("refY", "5");
			marker.setAttribute("markerWidth", "6");
			marker.setAttribute("markerHeight", "6");
			marker.setAttribute("orient", "auto-start-reverse");
			const path = document.createElementNS(
				"http://www.w3.org/2000/svg",
				"path"
			);
			path.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
			path.setAttribute("fill", "#ffffff");
			marker.appendChild(path);
			defs.appendChild(marker);
		}
	},

	_clearOverlay() {
		if (!this.overlaySvg) {
			return;
		}
		const children = Array.from(this.overlaySvg.children);
		children
			.filter((node) => node.tagName !== "defs")
			.forEach((node) => this.overlaySvg.removeChild(node));
	},

	_handleMirrorEvent(message) {
		if (!message || !message.type) {
			return;
		}

		switch (message.type) {
			case "overlay.set":
				this._onOverlayMessage(message);
				break;
			case "status":
				this.state.devices = {
					camera: message.camera || "off",
					lighting: message.lighting || "unknown",
					mic: message.mic || this.state.devices.mic,
				};
				this._renderChips();
				break;
			case "tts":
				this._maybeSpeak(message.text);
				break;
			case "safety.alert":
				this._showSafetyAlert(message);
				break;
			default:
				console.debug("MMM-AssistiveCoach: Unknown message", message);
		}
	},

	_onOverlayMessage(msg) {
		this.pendingOverlay = msg;
		if (!this.rafScheduled) {
			this.rafScheduled = true;
			requestAnimationFrame(() => this._flushOverlay());
		}
	},

	_flushOverlay() {
		this.rafScheduled = false;
		const msg = this.pendingOverlay;
		this.pendingOverlay = null;
		if (!msg) return;

		// Update state
		this.state.hud = msg.hud || {};
		this.state.shapes = msg.shapes || [];

		// Clear overlay SVG
		const svg = document.getElementById("overlay");
		if (svg) {
			while (svg.firstChild) svg.removeChild(svg.firstChild);
			this._ensureDefs();
		}

		// Draw shapes
		(msg.shapes || []).forEach((s) => {
			if (s.kind === "ring") {
				const { pixel, landmark_coords } = s.anchor || {};
				const coords = pixel || landmark_coords;
				if (coords) {
					this._drawRing(svg, coords.x, coords.y, s.radius_px || 90, true);
				}
			} else if (s.kind === "arrow") {
				this.overlaySvg.appendChild(this._makeArrow(s));
			} else if (s.kind === "badge") {
				this.overlaySvg.appendChild(this._makeBadge(s));
			}
		});

		// Update HUD
		const hud = document.getElementById("hud");
		if (hud && msg.hud) {
			const titleEl = hud.querySelector(".hud-title");
			const stepEl = hud.querySelector(".hud-step");
			const subtitleEl = hud.querySelector(".hud-subtitle");
			const hintEl = hud.querySelector(".hud-hint");
			const coachEl = hud.querySelector("#coach-tip");
			const progressEl = hud.querySelector(".progress");

			if (titleEl) titleEl.textContent = msg.hud.title || "";
			if (stepEl) stepEl.textContent = msg.hud.step || "";
			if (subtitleEl) subtitleEl.textContent = msg.hud.subtitle || "";
			if (hintEl) hintEl.textContent = msg.hud.hint || "";
			if (coachEl)
				coachEl.textContent = msg.hud.coach_tip
					? `Coach: ${msg.hud.coach_tip}`
					: "";

			if (progressEl && typeof msg.hud.time_left_s === "number") {
				const timeLeft = Math.max(0, msg.hud.time_left_s);
				const maxTime = msg.hud.max_time_s || timeLeft || 1;
				const progress = Math.min(1, Math.max(0, 1 - timeLeft / maxTime));
				const from = parseFloat(progressEl.dataset.value || "0");
				this._animateProgressBar(progressEl, from, progress);
				progressEl.dataset.value = String(progress);
			}

			this._enterHud(hud);
		}
	},

	_drawRing(svg, cx, cy, r, pulse = true) {
		if (!svg) return null;
		const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
		c.setAttribute("cx", cx);
		c.setAttribute("cy", cy);
		c.setAttribute("r", r);
		c.setAttribute("fill", "none");
		c.setAttribute("stroke", "#00d1ff");
		c.setAttribute("stroke-width", "6");
		c.setAttribute(
			"class",
			pulse && !this.config.reduceMotion ? "ring ring--pulse" : "ring"
		);
		svg.appendChild(c);
		return c;
	},

	_animateProgressBar(el, from = 0, to = 1) {
		if (!el) return;
		if (this.config.reduceMotion) {
			el.style.transform = `scaleX(${to})`;
			return;
		}
		el.animate(
			[{ transform: `scaleX(${from})` }, { transform: `scaleX(${to})` }],
			{ duration: 450, easing: "cubic-bezier(.22,.61,.36,1)", fill: "forwards" }
		);
	},

	_enterHud(hudEl) {
		if (!hudEl) return;
		if (this.config.reduceMotion) {
			hudEl.classList.remove("hud");
			hudEl.style.opacity = 1;
			hudEl.style.transform = "none";
			return;
		}
		hudEl.classList.add("hud", "hud--in");
	},

	_renderHud(target) {
		const hud = target || document.getElementById("hud");
		if (!hud) {
			return;
		}
		hud.innerHTML = "";

		const card = document.createElement("div");
		card.className = "hud-card";

		const titleEl = document.createElement("div");
		titleEl.className = "hud-title";
		card.appendChild(titleEl);

		const stepEl = document.createElement("div");
		stepEl.className = "hud-step";
		card.appendChild(stepEl);

		const subtitleEl = document.createElement("div");
		subtitleEl.className = "hud-subtitle";
		card.appendChild(subtitleEl);

		const progressWrap = document.createElement("div");
		progressWrap.className = "progress-wrap";
		const progress = document.createElement("div");
		progress.className = "progress";
		progress.style.transform = "scaleX(0)";
		progress.dataset.value = "0";
		progressWrap.appendChild(progress);
		card.appendChild(progressWrap);

		const hintEl = document.createElement("div");
		hintEl.className = "hud-hint";
		card.appendChild(hintEl);

		// Coach tip element (optional, styled like hint but dimmer)
		const coachEl = document.createElement("div");
		coachEl.className = "hud-hint";
		coachEl.style.opacity = 0.85;
		coachEl.style.marginTop = "8px";
		coachEl.id = "coach-tip";
		card.appendChild(coachEl);

		hud.appendChild(card);
	},

	_renderChips(target) {
		const chips = target || document.getElementById("chips");
		if (!chips) {
			return;
		}
		chips.innerHTML = "";

		const makeChip = (label, status, clickHandler) => {
			const chip = document.createElement("div");
			chip.className = `chip chip--${status}`;
			chip.textContent = label;
			chip.style.cursor = clickHandler ? "pointer" : "default";
			if (clickHandler) {
				chip.addEventListener("click", clickHandler);
				chip.setAttribute("role", "button");
				chip.setAttribute("tabindex", "0");
			}
			return chip;
		};

		// Tasks menu button
		chips.appendChild(makeChip("Tasks", "ok", () => this._toggleTaskMenu()));

		// Camera chip - toggle camera on/off
		chips.appendChild(
			makeChip("Camera", this._statusTone(this.state.devices.camera), () =>
				this._toggleSetting("camera")
			)
		);

		// Lighting chip - cycle through lighting modes
		chips.appendChild(
			makeChip("Lighting", this._statusTone(this.state.devices.lighting), () =>
				this._toggleSetting("lighting")
			)
		);

		// Mic chip - toggle mic (currently not used by backend)
		chips.appendChild(
			makeChip("Mic", this._statusTone(this.state.devices.mic || "ok"), () =>
				this._toggleSetting("mic")
			)
		);

		// Controls (Next, Stop, Replay, Coach)
		chips.appendChild(makeChip("Next", "ok", () => this._nextStep()));
		chips.appendChild(makeChip("Stop", "warn", () => this._stopTask()));
		chips.appendChild(
			makeChip("Replay", "ok", () => {
				const apiBase = this.config.apiBase || "http://127.0.0.1:8000";
				fetch(`${apiBase}/tts/replay`, { method: "POST" }).catch(() => {});
			})
		);
		chips.appendChild(
			makeChip("Coach", "ok", () => {
				const apiBase = this.config.apiBase || "http://127.0.0.1:8000";
				fetch(`${apiBase}/genai/coach`, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({}),
				})
					.then((r) => r.json())
					.then((data) => {
						this.state.hud = this.state.hud || {};
						this.state.hud.coach_tip = data.coach_tip;
						this.updateDom(0);
					})
					.catch(() => {});
			})
		);

		if (!this.socketConnected) {
			const chip = document.createElement("div");
			chip.className = "chip chip--warn";
			chip.textContent = "Link";
			chips.appendChild(chip);
		}
	},

	_toggleSetting(settingName) {
		const apiBase = this.config.apiBase || "http://127.0.0.1:8000";
		const currentState = this.state.devices[settingName];

		let newSettings = {};

		if (settingName === "camera") {
			// Toggle camera on/off by toggling pose detection
			const isOn = currentState === "on";
			newSettings = {
				pose: !isOn,
				hands: !isOn,
				aruco: !isOn,
			};
		} else if (settingName === "lighting") {
			// Cycle lighting modes (this is UI only, backend doesn't control lighting)
			console.log("Lighting toggle requested (UI feedback only)");
			return;
		} else if (settingName === "mic") {
			// Mic toggle (backend doesn't use this yet)
			console.log("Mic toggle requested (not implemented in backend)");
			return;
		}

		// Send settings to backend
		fetch(`${apiBase}/settings`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(newSettings),
		})
			.then((res) => res.json())
			.then((data) => {
				console.log("Settings updated:", data);
				// Update will come through health poll
			})
			.catch((err) => {
				console.error("Failed to update settings:", err);
			});
	},

	_statusTone(value) {
		if (!value) return "off";
		const normalized = String(value).toLowerCase();
		if (["on", "ok", "ready"].includes(normalized)) {
			return "ok";
		}
		if (["warn", "dim", "slow"].includes(normalized)) {
			return "warn";
		}
		return "off";
	},

	_renderShapes() {
		if (!this.overlaySvg) {
			return;
		}
		this._clearOverlay();

		this.state.shapes.forEach((shape) => {
			if (!shape || !shape.anchor) return;
			switch (shape.kind) {
				case "ring":
					this.overlaySvg.appendChild(this._makeRing(shape));
					break;
				case "arrow":
					this.overlaySvg.appendChild(this._makeArrow(shape));
					break;
				case "badge":
					this.overlaySvg.appendChild(this._makeBadge(shape));
					break;
				default:
					break;
			}
		});
	},

	_makeRing(shape) {
		const { anchor, radius_px = 50, accent = "info", offset_px } = shape;
		const ring = document.createElementNS(
			"http://www.w3.org/2000/svg",
			"circle"
		);
		const { x, y } = this._resolveAnchor(anchor, offset_px);
		ring.setAttribute("cx", x);
		ring.setAttribute("cy", y);
		ring.setAttribute("r", radius_px);
		ring.setAttribute("class", `shape-ring ${accent}`);
		if (this.config.reduceMotion) {
			ring.classList.add("no-motion");
		}
		return ring;
	},

	_makeArrow(shape) {
		const arrow = document.createElementNS(
			"http://www.w3.org/2000/svg",
			"line"
		);
		const from = this._resolveAnchor(shape.anchor, shape.offset_px);
		const toOffset = shape.to_offset_px || shape.offset_to_px;
		const to = this._resolveAnchor(shape.to, toOffset);
		arrow.setAttribute("x1", from.x);
		arrow.setAttribute("y1", from.y);
		arrow.setAttribute("x2", to.x);
		arrow.setAttribute("y2", to.y);
		arrow.setAttribute("class", "shape-arrow");
		arrow.setAttribute("marker-end", "url(#assistivecoach-arrow)");
		return arrow;
	},

	_makeBadge(shape) {
		const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
		const { x, y } = this._resolveAnchor(shape.anchor, shape.offset_px);
		const width = 180;
		const height = 60;
		const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
		rect.setAttribute("x", x - width / 2);
		rect.setAttribute("y", y - height / 2);
		rect.setAttribute("width", width);
		rect.setAttribute("height", height);
		rect.setAttribute("rx", 16);
		rect.setAttribute("ry", 16);
		rect.setAttribute("class", "shape-badge");
		const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
		text.setAttribute("x", x);
		text.setAttribute("y", y + 8);
		text.setAttribute("class", "shape-badge-text");
		text.textContent = shape.text || "";
		group.appendChild(rect);
		group.appendChild(text);
		return group;
	},

	_resolveAnchor(anchor, offset) {
		if (!anchor) {
			return { x: 0, y: 0 };
		}
		if (anchor.pixel) {
			return this._withOffset(anchor.pixel, offset);
		}
		if (anchor.landmark && anchor.landmark_coords) {
			return this._withOffset(anchor.landmark_coords, offset);
		}
		if (anchor.landmark) {
			console.warn("MMM-AssistiveCoach: Missing landmark coordinates", anchor);
		}
		return { x: 0, y: 0 };
	},

	_withOffset(point, offset) {
		const base = {
			x: Number(point.x ?? point.X ?? 0),
			y: Number(point.y ?? point.Y ?? 0),
		};
		if (
			offset &&
			typeof offset.x === "number" &&
			typeof offset.y === "number"
		) {
			base.x += offset.x;
			base.y += offset.y;
		}
		return base;
	},

	_maybeSpeak(text) {
		if (!window.speechSynthesis || !text) {
			return;
		}
		const utterance = new SpeechSynthesisUtterance(text);
		utterance.rate = 0.9;
		window.speechSynthesis.cancel();
		window.speechSynthesis.speak(utterance);
	},

	_showSafetyAlert(message) {
		const hud = document.getElementById("hud");
		if (!hud) {
			return;
		}
		const alert = document.createElement("div");
		alert.className = "hud-alert";
		alert.textContent = message.reason || "Check safety";
		hud.appendChild(alert);
		setTimeout(() => {
			alert.remove();
		}, 4000);
	},

	// ========================================================================
	// TASK SYSTEM METHODS
	// ========================================================================

	_loadAvailableTasks() {
		const apiBase = this.config.apiBase || "http://127.0.0.1:8000";
		fetch(`${apiBase}/tasks`)
			.then((res) => res.json())
			.then((data) => {
				this.state.availableTasks = data.tasks || [];
				console.log(`Loaded ${this.state.availableTasks.length} tasks`);
			})
			.catch((err) => {
				console.error("Failed to load tasks:", err);
			});
	},

	_toggleTaskMenu() {
		this.state.showTaskMenu = !this.state.showTaskMenu;
		this.updateDom(300);
	},

	_startTask(taskId) {
		const apiBase = this.config.apiBase || "http://127.0.0.1:8000";
		fetch(`${apiBase}/tasks/${taskId}/start`, { method: "POST" })
			.then((res) => res.json())
			.then((data) => {
				console.log("Task started:", data);
				this.state.showTaskMenu = false;
				this.state.currentTask = data;
				this.updateDom(0);
			})
			.catch((err) => {
				console.error("Failed to start task:", err);
			});
	},

	_nextStep() {
		const apiBase = this.config.apiBase || "http://127.0.0.1:8000";
		fetch(`${apiBase}/tasks/next_step`, { method: "POST" })
			.then((res) => res.json())
			.then((data) => {
				console.log("Next step:", data);
				if (data.task_complete) {
					this.state.currentTask = null;
				}
			})
			.catch((err) => {
				console.error("Failed to advance step:", err);
			});
	},

	_stopTask() {
		const apiBase = this.config.apiBase || "http://127.0.0.1:8000";
		fetch(`${apiBase}/tasks/stop`, { method: "POST" })
			.then((res) => res.json())
			.then((data) => {
				console.log("Task stopped:", data);
				this.state.currentTask = null;
				this.updateDom(0);
			})
			.catch((err) => {
				console.error("Failed to stop task:", err);
			});
	},

	_renderTaskMenu(container) {
		if (!this.state.showTaskMenu || this.state.availableTasks.length === 0) {
			return;
		}

		const menu = document.createElement("div");
		menu.className = "task-menu";

		const title = document.createElement("h2");
		title.textContent = "Select a Task";
		title.className = "task-menu-title";
		menu.appendChild(title);

		const hint = document.createElement("div");
		hint.className = "task-menu-hint";
		hint.textContent = "Press 1-4 to start, T to close, N for next step";
		menu.appendChild(hint);

		const taskList = document.createElement("div");
		taskList.className = "task-list";

		this.state.availableTasks.forEach((task, index) => {
			const taskCard = document.createElement("div");
			taskCard.className = "task-card";
			taskCard.addEventListener("click", () => this._startTask(task.task_id));

			const number = document.createElement("div");
			number.className = "task-number";
			number.textContent = index + 1;
			taskCard.appendChild(number);

			const icon = document.createElement("div");
			icon.className = "task-icon";
			icon.textContent = task.icon;
			taskCard.appendChild(icon);

			const info = document.createElement("div");
			info.className = "task-info";

			const name = document.createElement("div");
			name.className = "task-name";
			name.textContent = task.name;
			info.appendChild(name);

			const meta = document.createElement("div");
			meta.className = "task-meta";
			meta.textContent = `${task.num_steps} steps · ${Math.ceil(
				task.duration_s / 60
			)} min`;
			info.appendChild(meta);

			taskCard.appendChild(info);
			taskList.appendChild(taskCard);
		});

		menu.appendChild(taskList);
		container.appendChild(menu);
	},
});
