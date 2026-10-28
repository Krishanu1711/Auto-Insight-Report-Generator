import sys, time
print("Python:", sys.executable)
t0 = time.time()
print("Starting import sqlalchemy...", flush=True)
import sqlalchemy
print(f"SQLAlchemy imported in {time.time()-t0:.2f}s, version: {sqlalchemy.__version__}", flush=True)
