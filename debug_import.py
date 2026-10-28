import time, sys

def log(msg):
    print(msg, flush=True)

t0 = time.time()
log("1. Importing pandas...")
import pandas
log(f"   pandas done ({time.time()-t0:.2f}s)")

t = time.time()
log("2. Importing sqlalchemy...")
import sqlalchemy
log(f"   sqlalchemy done ({time.time()-t:.2f}s)")

t = time.time()
log("3. Importing src.exceptions...")
import src.exceptions
log(f"   exceptions done ({time.time()-t:.2f}s)")

t = time.time()
log("4. Importing src.models...")
import src.models
log(f"   models done ({time.time()-t:.2f}s)")

t = time.time()
log("5. Importing src.utils...")
import src.utils
log(f"   utils done ({time.time()-t:.2f}s)")

t = time.time()
log("6. Importing src.database...")
import src.database
log(f"   database done ({time.time()-t:.2f}s)")

log(f"ALL DONE IN {time.time()-t0:.2f}s")
