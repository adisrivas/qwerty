"""Vercel entry point.

Vercel runs Python files under ``api/`` as serverless functions. This module makes the
``backend`` package importable and exposes the FastAPI application as ``app``. All
``/api/*`` requests are routed here by ``vercel.json``; the React build is served as
static files from the same deployment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("WINDFORECAST_ENVIRONMENT", "vercel")
os.environ.setdefault("WINDFORECAST_SNAPSHOT_DIR", str(ROOT / "backend" / "data" / "snapshots"))

from app.main import create_app  # noqa: E402

app = create_app()
