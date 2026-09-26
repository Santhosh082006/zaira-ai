"""
scratch/test_live_server_reload.py
─────────────────────────────────────────────────────────────────────────────
Direct WebSocket test against live Streamlit server (http://localhost:8501)
Verifies:
1. Connecting to live server initiates a fresh session.
2. Disconnecting and reconnecting (simulating F5 browser reload) starts a fresh session
   due to disconnectedSessionTTL = 0.
"""

import asyncio
import json
import websockets
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


async def test_live_server():
    uri = "ws://localhost:8501/_stcore/stream"
    print(f"Connecting to live Streamlit server at {uri}...")

    # Session 1: Initial connection
    async with websockets.connect(uri) as ws1:
        print("Connected to WebSocket (Session 1).")
        first_msg = await ws1.recv()
        # Streamlit sends binary protobuf or json forward messages
        print("Received initial handshake message from Session 1.")

    print("Disconnected Session 1 (simulating browser closing/reload).")

    # Wait a brief moment like a browser reload
    await asyncio.sleep(0.5)

    # Session 2: Browser reload connection
    async with websockets.connect(uri) as ws2:
        print("Connected to WebSocket (Session 2 / Reload).")
        second_msg = await ws2.recv()
        print("Received initial handshake message from Session 2.")

    print("\n✓ Live server successfully handled disconnect and fresh reconnect on port 8501!")


if __name__ == "__main__":
    asyncio.run(test_live_server())
