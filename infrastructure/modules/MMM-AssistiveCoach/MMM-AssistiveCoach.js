/**
 * MagicMirror² Module: MMM-AssistiveCoach
 * LABISTS Smart Mirror - Iframe Wrapper for React SPA
 *
 * This module loads the React frontend in an iframe and injects configuration.
 * The React app handles all UI, camera, WebSocket, and overlay rendering.
 */

Module.register("MMM-AssistiveCoach", {
	defaults: {
		wsUrl: "ws://127.0.0.1:8000/ws",
		apiBase: "http://127.0.0.1:8000",
		reduceMotion: false,
		showHints: true,
		fullscreen: true,
		theme: "high-contrast",
		fontScale: 1.0,
	},

	start() {
		this.loaded = false;
		this.iframeReady = false;
		Log.info(`Starting ${this.name} module`);
	},

	getDom() {
		const wrapper = document.createElement("div");
		wrapper.className = "assistivecoach-wrapper";
		wrapper.style.width = "100%";
		wrapper.style.height = "100vh";
		wrapper.style.position = "relative";
		wrapper.style.overflow = "hidden";
		wrapper.style.backgroundColor = "#0F172A";

		// Create iframe to load React SPA
		const iframe = document.createElement("iframe");
		iframe.id = "assistivecoach-iframe";
		iframe.src = "modules/MMM-AssistiveCoach/public/index.html";
		iframe.style.width = "100%";
		iframe.style.height = "100%";
		iframe.style.border = "none";
		iframe.style.position = "absolute";
		iframe.style.top = "0";
		iframe.style.left = "0";

		// Allow camera and microphone access in iframe
		iframe.setAttribute("allow", "camera; microphone; fullscreen; geolocation");
		iframe.setAttribute(
			"sandbox",
			"allow-same-origin allow-scripts allow-forms allow-popups allow-presentation"
		);

		// Inject config into iframe when loaded
		iframe.onload = () => {
			try {
				// Inject configuration into React app via window globals
				iframe.contentWindow.__ASSISTIVE_WS__ = this.config.wsUrl;
				iframe.contentWindow.__ASSISTIVE_API__ = this.config.apiBase;
				iframe.contentWindow.__ASSISTIVE_CONFIG__ = {
					wsUrl: this.config.wsUrl,
					apiBase: this.config.apiBase,
					reduceMotion: this.config.reduceMotion,
					showHints: this.config.showHints,
					fullscreen: this.config.fullscreen,
					theme: this.config.theme,
					fontScale: this.config.fontScale,
				};

				this.loaded = true;
				this.iframeReady = true;
				Log.info(`${this.name}: React SPA loaded and configured`);

				// Notify React app that config is ready
				iframe.contentWindow.postMessage(
					{
						type: "MM_CONFIG_READY",
						config: iframe.contentWindow.__ASSISTIVE_CONFIG__,
					},
					"*"
				);
			} catch (err) {
				Log.error(`${this.name}: Failed to inject config:`, err);
			}
		};

		iframe.onerror = (err) => {
			Log.error(`${this.name}: Iframe load error:`, err);
			wrapper.innerHTML = `
        <div style="color: #FF6B6B; padding: 40px; text-align: center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
          <h2 style="font-size: 28px; margin-bottom: 16px;">⚠️ Failed to Load AssistiveCoach</h2>
          <p style="font-size: 16px; margin-bottom: 8px;">Could not load React frontend from:</p>
          <p style="font-size: 14px; color: #FFB3B3; font-family: monospace; margin-bottom: 24px;">modules/MMM-AssistiveCoach/public/</p>
          <p style="font-size: 14px; margin-bottom: 8px;">Error: ${
						err.message || "Unknown error"
					}</p>
          <p style="margin-top: 24px; font-size: 13px; opacity: 0.8;">
            Try rebuilding the frontend:<br>
            <code style="background: rgba(255, 107, 107, 0.1); padding: 8px 12px; border-radius: 4px; display: inline-block; margin-top: 8px;">
              cd frontend && npm run build:mm
            </code>
          </p>
        </div>
      `;
		};

		wrapper.appendChild(iframe);

		// Add loading indicator
		const loader = document.createElement("div");
		loader.className = "assistivecoach-loader";
		loader.innerHTML = `
      <div style="
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        text-align: center;
        color: #0EA5A4;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      ">
        <div style="font-size: 64px; margin-bottom: 20px; animation: pulse 2s ease-in-out infinite;">🏥</div>
        <div style="font-size: 26px; font-weight: 600; margin-bottom: 12px;">Initializing AssistiveCoach</div>
        <div style="font-size: 14px; opacity: 0.7; margin-bottom: 20px;">Setting up camera and sensors...</div>
        <div style="width: 200px; height: 4px; background: rgba(14, 165, 164, 0.2); border-radius: 2px; margin: 0 auto; overflow: hidden;">
          <div style="width: 100%; height: 100%; background: linear-gradient(90deg, transparent, #0EA5A4, transparent); animation: slideRight 2s infinite;"></div>
        </div>
      </div>
      <style>
        @keyframes pulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.05); }
        }
        @keyframes slideRight {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      </style>
    `;

		// Remove loader when iframe loads
		iframe.addEventListener("load", () => {
			setTimeout(() => {
				if (loader.parentNode) {
					loader.parentNode.removeChild(loader);
				}
			}, 800);
		});

		wrapper.appendChild(loader);

		return wrapper;
	},

	getStyles() {
		return ["MMM-AssistiveCoach.css"];
	},

	// Handle notifications from other MM modules
	notificationReceived(notification, payload, sender) {
		if (notification === "DOM_OBJECTS_CREATED") {
			// All modules loaded
			Log.info(`${this.name}: MagicMirror DOM ready`);
		}

		// Forward important notifications to React app if needed
		if (this.iframeReady) {
			const iframe = document.getElementById("assistivecoach-iframe");
			if (iframe && iframe.contentWindow) {
				try {
					iframe.contentWindow.postMessage(
						{
							type: "MM_NOTIFICATION",
							notification: notification,
							payload: payload,
							sender: sender ? sender.name : null,
						},
						"*"
					);
				} catch (err) {
					Log.debug(`${this.name}: Could not forward notification:`, err);
				}
			}
		}
	},

	// Handle socket notifications from node_helper
	socketNotificationReceived(notification, payload) {
		Log.debug(`${this.name}: Socket notification:`, notification);

		// Forward to React app
		if (this.iframeReady) {
			const iframe = document.getElementById("assistivecoach-iframe");
			if (iframe && iframe.contentWindow) {
				try {
					iframe.contentWindow.postMessage(
						{
							type: "MM_SOCKET_NOTIFICATION",
							notification: notification,
							payload: payload,
						},
						"*"
					);
				} catch (err) {
					Log.debug(
						`${this.name}: Could not forward socket notification:`,
						err
					);
				}
			}
		}
	},

	suspend() {
		Log.info(`${this.name}: Suspended`);
		// Notify React app to pause/cleanup if needed
		if (this.iframeReady) {
			const iframe = document.getElementById("assistivecoach-iframe");
			if (iframe && iframe.contentWindow) {
				iframe.contentWindow.postMessage({ type: "MM_SUSPEND" }, "*");
			}
		}
	},

	resume() {
		Log.info(`${this.name}: Resumed`);
		// Notify React app to resume
		if (this.iframeReady) {
			const iframe = document.getElementById("assistivecoach-iframe");
			if (iframe && iframe.contentWindow) {
				iframe.contentWindow.postMessage({ type: "MM_RESUME" }, "*");
			}
		}
	},
});
