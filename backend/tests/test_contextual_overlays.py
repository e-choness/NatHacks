#!/usr/bin/env python3
"""
Test script for contextual overlay generation.
Connects to WebSocket and monitors overlay messages for regional shapes.
"""
import asyncio
import websockets
import json
import sys

async def test_overlays():
    """Connect to backend WebSocket and monitor overlay messages."""
    uri = "ws://localhost:8000/ws"
    
    print("🔗 Connecting to", uri)
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected! Monitoring overlay messages...")
            print("=" * 60)
            
            message_count = 0
            while message_count < 20:  # Monitor 20 messages
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    
                    if data.get("type") == "overlay.set":
                        message_count += 1
                        shapes = data.get("shapes", [])
                        hud = data.get("hud", {})
                        
                        print(f"\n📊 Overlay #{message_count}")
                        print(f"   HUD Title: {hud.get('title', 'N/A')}")
                        print(f"   Shapes: {len(shapes)}")
                        
                        for i, shape in enumerate(shapes):
                            kind = shape.get("kind", "unknown")
                            anchor = shape.get("anchor", {}).get("pixel", {})
                            text = shape.get("text", "")
                            
                            print(f"     Shape {i+1}: {kind} at ({anchor.get('x', 0)}, {anchor.get('y', 0)})", end="")
                            if text:
                                print(f" - '{text}'", end="")
                            if kind == "ring":
                                print(f" (radius: {shape.get('radius_px', 0)}px)", end="")
                            print()
                            
                except asyncio.TimeoutError:
                    print("⏱️  No messages for 5s, still listening...")
                except json.JSONDecodeError:
                    print("⚠️  Invalid JSON received")
                    
    except ConnectionRefusedError:
        print("❌ Connection refused - is the backend running on port 8000?")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✓ Test complete!")

if __name__ == "__main__":
    print("Testing Contextual Overlay Generation")
    print("=" * 60)
    asyncio.run(test_overlays())
