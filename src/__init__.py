# src/__init__.py
# Fix Windows Python 3.13 WMI hang on platform.uname() / platform.machine()
import sys
if sys.platform == "win32":
    try:
        import platform
        platform._wmi = None
    except Exception:
        pass
