#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "======================================================="
echo "         Starting Zaira AI Local Server Suite          "
echo "======================================================="

# Check for Python venv
if [ ! -f "venv/bin/uvicorn" ]; then
    echo "[SETUP] Creating Python virtual environment in ./venv..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Check for frontend dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo "[SETUP] Installing frontend npm dependencies..."
    cd frontend && npm install && cd ..
fi

# Remove Next.js dev lock if stale
rm -f frontend/.next/dev/lock 2>/dev/null || true

echo "[1/2] Starting FastAPI backend on port 8000..."
uvicorn backend.api:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo "[2/2] Starting Next.js frontend on port 3000..."
cd frontend
npm run dev -- -H 127.0.0.1 -p 3000 &
FRONTEND_PID=$!
cd ..

cleanup() {
    echo "Shutting down Zaira servers..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "Servers running! Press Ctrl+C to stop."
wait
