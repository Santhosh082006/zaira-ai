import sys
import os

# Ensure project root is in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import uvicorn

if __name__ == "__main__":
    print("Starting Zaira FastAPI backend on http://0.0.0.0:8000 ...", flush=True)
    try:
        from backend.api import app
        print("Backend app loaded successfully. Starting uvicorn...", flush=True)
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except Exception as e:
        print("Uvicorn startup error:", e, flush=True)
