import time, platform
platform._wmi = None

t0 = time.time()
print("Starting platform.uname() with _wmi=None...", flush=True)
u = platform.uname()
print(f"uname: {u} in {time.time()-t0:.2f}s", flush=True)

t1 = time.time()
print("Starting import sqlalchemy...", flush=True)
import sqlalchemy
print(f"SQLAlchemy imported in {time.time()-t1:.2f}s, version: {sqlalchemy.__version__}", flush=True)

t2 = time.time()
print("Starting import server...", flush=True)
import server
print(f"server imported in {time.time()-t2:.2f}s", flush=True)
