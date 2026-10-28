"""
run_server.py - Launch uvicorn without spawning duplicate backend processes.
Run: python run_server.py
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request

HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"
ROOT = os.path.dirname(__file__) or "."
LOG_PATH = os.path.join(ROOT, "run_server.log")


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def _is_auto_insight_backend_running() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/session", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status == 200 and isinstance(payload, dict) and "bundle" in payload
    except (OSError, ValueError, urllib.error.URLError):
        return False


def main() -> int:
    print("Starting Auto-Insight server...")
    print(f"Log: {LOG_PATH}")
    print(f"URL: {BASE_URL}")

    if _is_port_open(HOST, PORT):
        if _is_auto_insight_backend_running():
            print("\nAuto-Insight backend is already running on port 8000.")
            print(f"Reuse the existing instance at {BASE_URL}")
            return 0
        print("\nPort 8000 is already in use by another process.")
        print("Stop that process or free the port before starting Auto-Insight.")
        return 1

    print("Press Ctrl+C to stop.\n")
    with open(LOG_PATH, "w", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "server:app",
                "--host",
                HOST,
                "--port",
                str(PORT),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=ROOT,
        )
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                print(line, end="")
                logf.write(line)
                logf.flush()
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
