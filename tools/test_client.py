"""Smoke test of the jury API. Usage: python test_client.py BASE_URL API_KEY path/to/video.mov
Requires: pip install requests"""
import sys, time, base64
import requests

base, key, path = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
H = {"X-API-Key": key}
t0 = time.time()
with open(path, "rb") as f:
    r = requests.post(f"{base}/api/v1/analyze", headers=H, files={"file": f})
r.raise_for_status()
job = r.json()["job_id"]
print("job_id:", job)
while True:
    j = requests.get(f"{base}/api/v1/jobs/{job}", headers=H).json()
    if j["status"] != "processing":
        break
    time.sleep(2)
print("status:", j["status"], "| elapsed:", round(time.time() - t0, 1), "s")
print("verdict:", j.get("verdict"), "| error:", j.get("error"))
for v in j.get("violations", []):
    print("-", v["type"], v["timecode_sec"], v["description"])
    for k, fr in enumerate(v["evidence_frames"]):
        with open(f"evidence_{job}_{k}.jpg", "wb") as out:
            out.write(base64.b64decode(fr["image_base64"]))
