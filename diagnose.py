"""
diagnose.py - Find exactly why server.py fails to start.
Run: python diagnose.py
"""
import sys
import traceback

if sys.platform == "win32":
    try:
        import platform
        platform._wmi = None
    except Exception:
        pass

print("=" * 60)
print("DIAGNOSTIC: Auto-Insight Server")
print("=" * 60)

# Step 1: Basic imports
print("\n[1] Testing standard library imports...")
try:
    import threading, uuid, math, json, os, io, socket, ipaddress, logging, time, urllib.parse, re
    print("    OK")
except Exception as e:
    print(f"    FAIL: {e}")
    sys.exit(1)

# Step 2: Third-party imports
print("\n[2] Testing third-party imports...")
deps = [
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("requests", "requests"),
    ("fastapi", "fastapi"),
    ("pydantic", "pydantic"),
    ("uvicorn", "uvicorn"),
    ("sqlalchemy", "sqlalchemy"),
    ("plotly", "plotly"),
    ("statsmodels", "statsmodels"),
    ("jinja2", "jinja2"),
]
for name, mod in deps:
    try:
        __import__(mod)
        print(f"    {name}: OK")
    except ImportError as e:
        print(f"    {name}: MISSING - {e}")

# Step 3: src modules
print("\n[3] Testing src module imports...")
for mod in ["src.config", "src.exceptions", "src.utils", "src.models", "src.database",
            "src.ingest", "src.clean", "src.profile", "src.analyze", "src.transform",
            "src.visualize", "src.forecast", "src.insights", "src.pipeline", "src.report"]:
    try:
        __import__(mod)
        print(f"    {mod}: OK")
    except Exception as e:
        print(f"    {mod}: FAIL")
        traceback.print_exc()
        print()

# Step 4: Check data directory and db
print("\n[4] Checking data directory and DB path...")
from pathlib import Path
data_dir = Path("data")
print(f"    data/ exists: {data_dir.exists()}")
db_path = data_dir / "insight.db"
print(f"    insight.db exists: {db_path.exists()}")
if db_path.exists():
    print(f"    insight.db size: {db_path.stat().st_size} bytes")

# Step 5: Check frontend dist
print("\n[5] Checking frontend/dist...")
dist = Path("frontend/dist")
print(f"    frontend/dist exists: {dist.exists()}")
if dist.exists():
    html = dist / "index.html"
    print(f"    index.html exists: {html.exists()}")
    assets = dist / "assets"
    print(f"    assets/ exists: {assets.exists()}")
    if assets.exists():
        files = list(assets.iterdir())
        print(f"    asset files: {[f.name for f in files]}")

# Step 6: Try to construct the FastAPI app manually
print("\n[6] Constructing FastAPI app...")
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    app = FastAPI(title="Test")
    print("    FastAPI app created: OK")
except Exception as e:
    print(f"    FAIL: {e}")
    traceback.print_exc()

# Step 7: Try init_db
print("\n[7] Testing database init...")
try:
    from src.database import get_engine, init_db
    from src.config import DB_PATH
    print(f"    DB_PATH = {DB_PATH}")
    engine = get_engine(DB_PATH)
    print(f"    Engine created: OK")
    init_db(engine)
    print(f"    init_db: OK")
except Exception as e:
    print(f"    FAIL: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
