/* Minimal MagicMirror config focusing only on AssistiveCoach module */
let config = {
	address: "0.0.0.0",
	port: 8080,
	electronOptions: {
		fullscreen: true,
		backgroundColor: "#000000",
	},
	language: "en",
	locale: "en-US",
	logLevel: ["INFO", "WARN", "ERROR"],
	modules: [
		{
			module: "MMM-AssistiveCoach",
			position: "fullscreen_above",
			config: {
				wsUrl: "ws://127.0.0.1:8000/ws", // backend WS endpoint
				apiBase: "http://127.0.0.1:8000",
				fontScale: 1.0,
				theme: "high-contrast",
				reduceMotion: false,
			},
		},
	],
};
/*************** DO NOT EDIT BELOW THIS LINE ***************/
if (typeof module !== "undefined") {
	module.exports = config;
}
