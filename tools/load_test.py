"""Simulates the jury submitting N videos at once. Every one must finish in < 300 s.
Usage: python load_test.py BASE_URL API_KEY video1.mov video2.mov ...
Requires: pip install requests"""
import sys, time
from concurrent.futures import ThreadPoolExecutor
import requests

base, key, paths = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3:]
H = {"X-API-Key": key}


def one(path):
    t0 = time.time()
    with open(path, "rb") as f:
        job = requests.post(f"{base}/api/v1/analyze", headers=H, files={"file": f}).json()["job_id"]
    while True:
        j = requests.get(f"{base}/api/v1/jobs/{job}", headers=H).json()
        if j["status"] != "processing":
            return path, j["status"], j.get("verdict"), round(time.time() - t0, 1)
        time.sleep(2)


with ThreadPoolExecutor(max_workers=len(paths)) as ex:
    results = list(ex.map(one, paths))
for r in results:
    print(r)
worst = max(r[3] for r in results)
print("WORST:", worst, "s ->", "OK (< 300 s)" if worst < 300 else "TOO SLOW")
