"""
Thin compatibility entrypoint.
TruthLens AI 2.0 has migrated the canonical FastAPI application to backend.api
to support real pipeline execution and proper architectural boundaries.
This file exists solely to prevent startup/deployment flows from breaking if they point to backend.main:app.
"""
from backend.api import app
