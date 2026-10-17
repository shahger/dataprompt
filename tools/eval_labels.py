"""Runs every labelled video through the API and compares with open_labels.xlsx.
Usage: python eval_labels.py BASE_URL API_KEY path/to/open  [tolerance_sec]
(path/to/open contains videos/ and open_labels.xlsx). Requires: pip install requests openpyxl"""
import sys, re, glob, os, time


def parse_ts(s):
    """'22 секунда' -> 22.0 ; '1минута 8 секунда' -> 68.0 ; empty -> None"""
    if not s:
        return None
    m = re.search(r"(\d+)\s*минут", s)
    sec = re.search(r"(\d+)\s*секунд", s)
    return (int(m.group(1)) * 60 if m else 0) + (int(sec.group(1)) if sec else 0)


def load_labels(xlsx):
    from openpyxl import load_workbook
    ws = load_workbook(xlsx, read_only=True).active
    out = {}
    for row in list(ws.iter_rows(values_only=True))[1:]:
        name, ts, verdict = row[0], row[1], row[2]
        if not name:
            continue
        num = int(re.search(r"(\d+)", str(name)).group(1))     # robust to Latin X / Cyrillic Х
        out[num] = ("violation" if str(verdict).strip() == "нарушение" else "no_violation", parse_ts(ts))
    return out


def main():
    import requests
    base, key, root = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
    tol = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
    H = {"X-API-Key": key}
    labels = load_labels(os.path.join(root, "open_labels.xlsx"))
    files = {int(re.search(r"(\d+)", os.path.basename(p)).group(1)): p
             for p in glob.glob(os.path.join(root, "videos", "*.mov"))}
    ok = 0; tl = 0; tl_total = 0; slowest = 0
    for num, (true_verdict, true_ts) in sorted(labels.items()):
        if num not in files:
            continue
        t0 = time.time()
        with open(files[num], "rb") as f:
            job = requests.post(f"{base}/api/v1/analyze", headers=H, files={"file": f}).json()["job_id"]
        while True:
            j = requests.get(f"{base}/api/v1/jobs/{job}", headers=H).json()
            if j["status"] != "processing":
                break
            time.sleep(2)
        dt = time.time() - t0; slowest = max(slowest, dt)
        pred = j.get("verdict")
        ok += pred == true_verdict
        near = None
        if true_verdict == "violation" and pred == "violation":
            near = min(abs(v["timecode_sec"] - true_ts) for v in j["violations"]) <= tol
            tl_total += 1; tl += bool(near)
        print(f"video {num}: true={true_verdict} pred={pred} time_ok={near} {dt:.0f}s")
    print(f"verdict accuracy: {ok}/{len(labels)}; timecode within {tol}s: {tl}/{tl_total}; slowest: {slowest:.0f}s")


if __name__ == "__main__":
    main()
