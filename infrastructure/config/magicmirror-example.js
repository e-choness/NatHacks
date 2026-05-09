// MagicMirror² Configuration Example for AssistiveCoach
// Add this module configuration to your ~/MagicMirror/config/config.js

{
  module: "MMM-AssistiveCoach",
  position: "bottom_left", // Module position (doesn't affect overlay/HUD rendering)
  config: {
    // WebSocket connection to FastAPI backend
    wsUrl: "ws://127.0.0.1:8000/ws",
    
    // REST API base URL for health polling and settings
    // IMPORTANT: This fixes the 5055 port error
    apiBase: "http://127.0.0.1:8000",
    
    // Visual theme (high-contrast for better visibility)
    theme: "high-contrast",
    
    // Font size multiplier (1.0 = default, 1.2 = 20% larger)
    fontScale: 1.0,
    
    // Respect system reduce motion preference
    // Set to true to disable all animations
    reduceMotion: false,
    
    // Show yellow hint text in HUD
    showHints: true,
    
    // Show control chips (Camera/Lighting/Mic) in top-right
    showControls: true,
  }
}

/* 
 * Full example config.js structure:
 * 
 * let config = {
 *   address: "localhost",
 *   port: 8080,
 *   ipWhitelist: ["127.0.0.1", "::ffff:127.0.0.1", "::1"],
 *   language: "en",
 *   timeFormat: 24,
 *   units: "metric",
 *   
 *   modules: [
 *     {
 *       module: "alert",
 *     },
 *     {
 *       module: "clock",
 *       position: "top_left"
 *     },
 *     {
 *       module: "MMM-AssistiveCoach",
 *       position: "bottom_left",
 *       config: {
 *         wsUrl: "ws://127.0.0.1:8000/ws",
 *         apiBase: "http://127.0.0.1:8000",
 *         showHints: true,
 *         showControls: true
 *       }
 *     }
 *   ]
 * };
 * 
 * if (typeof module !== "undefined") { module.exports = config; }
 */
