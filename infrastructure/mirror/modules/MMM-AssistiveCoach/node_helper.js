/* eslint-disable no-console */
const NodeHelper = require("node_helper");
const WebSocket = require("ws");
const http = require("http");

module.exports = NodeHelper.create({
	start() {
		this.wsUrl = null;
		this.apiBase = "http://127.0.0.1:8000"; // Default to FastAPI backend
		this.client = null;
		this.connected = false;
		this.messageCount = 0;
		this.healthTimer = null;
	},

	stop() {
		this._teardown();
	},

	socketNotificationReceived(notification, payload) {
		if (notification === "MMM_ASSISTIVECOACH_INIT") {
			this.wsUrl = payload.wsUrl;
			// Honor apiBase from config if provided
			if (payload.apiBase) {
				this.apiBase = payload.apiBase;
			}
			this._connect();
			this._scheduleHealthPoll();
		}
	},

	_connect() {
		if (!this.wsUrl) {
			console.warn("MMM-AssistiveCoach: WS URL missing");
			return;
		}

		if (this.client) {
			this.client.removeAllListeners();
			this.client.terminate();
			this.client = null;
		}

		const connectWithDelay = (delay) => {
			setTimeout(() => this._connect(), delay);
		};

		try {
			this.client = new WebSocket(this.wsUrl);
		} catch (error) {
			console.warn("MMM-AssistiveCoach: WS init failed", error);
			connectWithDelay(2000);
			return;
		}
		this.client.on("open", () => {
			this.connected = true;
			this._retryLevel = 0;
			this.messageCount = 0;
			this.sendSocketNotification("MMM_ASSISTIVECOACH_STATUS", {
				connected: true,
			});
			console.log("MMM-AssistiveCoach: Connected to backend");
		});

		this.client.on("close", () => {
			if (this.connected) {
				console.log("MMM-AssistiveCoach: Connection closed");
			}
			this.connected = false;
			this.sendSocketNotification("MMM_ASSISTIVECOACH_STATUS", {
				connected: false,
			});
			connectWithDelay(this._nextBackoff());
		});

		this.client.on("message", (data) => {
			this.messageCount += 1;
			let payload;
			try {
				payload = JSON.parse(data);
			} catch (error) {
				console.error("MMM-AssistiveCoach: Invalid JSON", error);
				return;
			}
			this.sendSocketNotification("MMM_ASSISTIVECOACH_EVENT", payload);
		});

		this.client.on("error", (error) => {
			console.warn("MMM-AssistiveCoach WS error", error.message || error);
		});
	},

	_nextBackoff() {
		if (!this._retryLevel) {
			this._retryLevel = 0;
		}
		const levels = [500, 2000, 5000];
		const delay = levels[Math.min(this._retryLevel, levels.length - 1)];
		this._retryLevel += 1;
		return delay;
	},

	_scheduleHealthPoll() {
		if (this.healthTimer) {
			clearInterval(this.healthTimer);
		}
		this.healthTimer = setInterval(() => this._pollHealth(), 2000);
	},

	_pollHealth() {
		// Use configurable apiBase instead of hardcoded 5055
		const healthUrl = `${this.apiBase}/health`;
		const url = new URL(healthUrl);
		const request = http.get(url, (response) => {
			let data = "";
			response.on("data", (chunk) => {
				data += chunk;
			});
			response.on("end", () => {
				try {
					const payload = JSON.parse(data);
					this.sendSocketNotification("MMM_ASSISTIVECOACH_EVENT", {
						type: "status",
						camera: payload.camera,
						lighting: payload.lighting,
						fps: payload.fps,
					});
				} catch (error) {
					console.warn(
						"MMM-AssistiveCoach health parse error",
						error.message || error
					);
				}
			});
		});

		request.on("error", (error) => {
			console.warn(
				"MMM-AssistiveCoach health poll failed",
				error.message || error
			);
		});
	},

	_teardown() {
		if (this.healthTimer) {
			clearInterval(this.healthTimer);
			this.healthTimer = null;
		}
		if (this.client) {
			this.client.removeAllListeners();
			this.client.terminate();
			this.client = null;
		}
	},
});
