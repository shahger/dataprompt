"""Model adapter: our cashier-discipline pipeline (ml/) behind the service contract.

analyze_video(path, deadline=None) -> [{"type", "timecode_sec", "description", "rule"}]; [] = no signs.
Pipeline (CPU, offline): 3 fps frames -> RT-DETRv2 detector (ONNX) -> ByteTrack -> DINOv2-small crop heads
-> scene timeline -> rules -> calibrated thresholds. Citations come only from rules/rules_db.json.
Weights are loaded ONCE at import from MODEL_DIR: detector/, encoder/dinov2-small/, heads.joblib, rule_params.json.
"""
import os
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from ml.analyze import Analyzer, _short_citation  # noqa: E402

MODEL_DIR = os.environ.get("MODEL_DIR", "models")
THREADS = int(os.environ.get("FORTE_THREADS", "4"))

ANALYZER = Analyzer(models_dir=MODEL_DIR, threads=THREADS)   # loaded once


def _rule_text(refs):
    """'<act>, п.20: «verbatim quote»; ...' from rules_db.json entries (never generated)."""
    parts = []
    for r in refs:
        item = f"п.{r['punkt']}" + (f" пп.{r['subpunkt']}" if r.get("subpunkt") else "")
        note = " (косвенная связь)" if r.get("relation") == "indirect" else ""
        parts.append(f"{r['document']}, {item}{note}: «{r['quote']}» ({r['url']})")
    return "; ".join(parts)


def analyze_video(path, deadline=None):
    # Typical run is 10-60 s on CPU; the service timeout covers the rest. The pipeline is not resumable,
    # so on a tight budget only the detector stride is raised (fewer detector calls, same output format).
    if deadline is not None and deadline - time.monotonic() < 120:
        ANALYZER.det_stride = 3
    else:
        ANALYZER.det_stride = None
    result = ANALYZER.analyze(str(path))
    note = result.get("insufficient_data_reason")
    out = []
    for v in result["violations"]:
        refs = v.get("rule_refs") or []
        cite = _short_citation(refs)
        desc = v["description"]
        if cite and desc.endswith(f" Норма: {cite}."):
            desc = desc[: -len(f" Норма: {cite}.")]
        desc += f" Оценка модели: {v['score']:.2f} из 1 — подсказка для проверки человеком."
        if note:
            desc += f" Недостаточно данных: {note}."
        out.append({"type": v["type"], "timecode_sec": float(v["timecode_sec"]),
                    "description": desc, "rule": _rule_text(refs) or "Норма не подтверждена — требуется проверка"})
    return out
