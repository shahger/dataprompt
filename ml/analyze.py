"""analyze(video_path) -> API result (CPU-only, offline).

Pipeline: sample 3 fps -> RT-DETRv2 detector (ONNX) -> ByteTrack for people, fixed ids for the static objects,
cash tracker in the timeline -> DINOv2-small crop embeddings -> heads (role, object states, actions) ->
scene timeline -> rules -> calibrated thresholds -> report (types, timecodes, descriptions, JPEG evidence,
citations from rules/rules_db.json).

    from ml.analyze import Analyzer
    result = Analyzer().analyze("video.mov")
"""
import base64
import json
import os
import time
from pathlib import Path

import cv2
import joblib
import numpy as np
from PIL import Image

from .calibrate import decide
from .encoder import CropEncoder, crop
from .features import ACTION_MAP, CONTEXT_PAD, action_features_v2, person_geom, relation_features
from .rules import RULES, run_rules
from .scene import Frame, Obj
from .timeline import build_timeline

ROOT = Path(__file__).resolve().parent.parent
FPS = 3
DET_SIZE = 640
# static objects are always in the scene: the detector ranks them well but scores them low, so take the best box
DET_THRESHOLD = {"person": 0.45, "safe": 0.05, "door": 0.05, "laptop": 0.05, "counting_machine": 0.05,
                 "cash": 0.35, "package": 0.4, "stamp": 0.4, "document_id": 0.4, "cup_food": 0.4,
                 "clothing_bag": 0.4, "uv_scanner": 0.1}
STATIC = ["safe", "door", "laptop", "counting_machine", "uv_scanner"]
STATIC_IDS = {lab: 100 + k for k, lab in enumerate(STATIC)}
STATE_EVERY = 3   # object-state crops every 3rd frame (1 fps), held in between
CTX_EVERY = 2     # person context crops (actions) every 2nd frame
# classifier class -> timeline action names it stands for, by role
ACTION_TO_TIMELINE = {"id": {"cashier": "checking_id", "client": "showing_id"}}


def _sample_frames(path, fps=FPS):
    cap = cv2.VideoCapture(str(path))   # rotation metadata applied by OpenCV
    src = cap.get(cv2.CAP_PROP_FPS) or 30.0
    i, nxt, out = 0, 0.0, []
    while cap.grab():
        t = i / src
        if t + 0.5 / src >= nxt:
            ok, img = cap.retrieve()
            if ok:
                out.append((t, img))
            nxt += 1 / fps
        i += 1
    cap.release()
    return out


class Analyzer:
    def __init__(self, models_dir=ROOT / "models", threads=None, det_stride=None):
        import onnxruntime as ort
        threads = threads or int(os.environ.get("FORTE_THREADS", "2"))
        so = ort.SessionOptions()
        so.intra_op_num_threads, so.inter_op_num_threads = threads, 1
        det_dir = Path(models_dir) / "detector"
        self.det = ort.InferenceSession(str(det_dir / "detector.onnx"), so, providers=["CPUExecutionProvider"])
        self.cats = json.loads((det_dir / "config.json").read_text())["id2label"]
        self.cats = [self.cats[str(i)] for i in range(len(self.cats))]
        self.heads = joblib.load(Path(models_dir) / "heads.joblib")
        self.enc = CropEncoder(self.heads.get("encoder", "dinov2-small"), device="cpu", threads=threads)
        self.params = json.loads((Path(models_dir) / "rule_params.json").read_text())
        db = json.loads((ROOT / "rules" / "rules_db.json").read_text())
        self.rules_db = db
        self.type_names = {**{k: v["name"] for k, v in db["violation_types"].items()},
                           **{k: r["name"] for k, r in RULES.items() if r["name"]}}
        self.det_stride = det_stride

    # ---------- perception ----------
    def _detect(self, img_bgr):
        h, w = img_bgr.shape[:2]
        # same as RTDetrImageProcessor (resize 640x640 bilinear, RGB, /255, no normalisation), without its overhead
        rgb = cv2.cvtColor(cv2.resize(img_bgr, (DET_SIZE, DET_SIZE), interpolation=cv2.INTER_LINEAR), cv2.COLOR_BGR2RGB)
        x = (rgb.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
        logits, boxes = self.det.run(None, {"pixel_values": x})
        probs = 1 / (1 + np.exp(-logits[0]))
        cls, score = probs.argmax(-1), probs.max(-1)
        out = []
        for c, s, (cx, cy, bw, bh) in zip(cls, score, boxes[0]):
            lab = self.cats[c]
            if s >= DET_THRESHOLD.get(lab, 0.5):
                out.append((lab, float(s), [(cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h]))
        return _nms(out)

    def perceive(self, frames_bgr):
        """-> list[Frame] with roles, object states and action probabilities as attributes."""
        frames = self.detect_track(frames_bgr)
        apply_heads(frames, self.features(frames, frames_bgr), self.heads)
        return frames

    def detect_track(self, frames_bgr):
        """Detector (strided) + ByteTrack for people + one main object per static class. No attributes yet."""
        import supervision as sv
        from trackers import ByteTrackTracker
        n = len(frames_bgr)
        # detector on every 2nd frame (every 3rd for long videos): people are tracked and static objects held in between
        stride = self.det_stride or (2 if n <= 150 else 3)
        tracker = ByteTrackTracker(frame_rate=FPS / stride, lost_track_buffer=3 * FPS, track_activation_threshold=0.4,
                                   high_conf_det_threshold=0.5)
        frames, ds, people_now = [], [], []
        for k, (t, img) in enumerate(frames_bgr):
            if k % stride == 0:
                ds = self._detect(img)
                people = [d for d in ds if d[0] == "person"]
                sd = sv.Detections(xyxy=np.array([d[2] for d in people]).reshape(-1, 4), confidence=np.array([d[1] for d in people]),
                                   class_id=np.zeros(len(people), int)) if people else sv.Detections.empty()
                tracked = tracker.update(sd)
                people_now = [(int(tid), xyxy.tolist()) for xyxy, tid in zip(tracked.xyxy, tracked.tracker_id) if tid >= 0]
            objs = [Obj("person", box, 1.0, tid, {}) for tid, box in people_now]
            for lab in STATIC:   # one main object per static class: the best box in this frame
                cand = [d for d in ds if d[0] == lab]
                if cand:
                    best = max(cand, key=lambda d: d[1])
                    objs.append(Obj(lab, best[2], best[1], STATIC_IDS[lab], {}))
            objs += [Obj(lab, box, sc, None, {}) for lab, sc, box in ds if lab not in STATIC and lab != "person"]
            frames.append(Frame(t, f"{k:05d}", objs))
        return frames

    def features(self, frames, frames_bgr):
        """Crop features exactly as the heads see them (shared by runtime and training)."""
        return extract_features(frames, frames_bgr, self.enc)

    # ---------- report ----------
    def _evidence(self, frames_bgr, ts, max_frames=3):
        out, seen = [], set()
        times = np.array([t for t, _ in frames_bgr])
        for t in ts:
            k = int(np.argmin(np.abs(times - t)))
            if k in seen:
                continue
            seen.add(k)
            ok, buf = cv2.imencode(".jpg", frames_bgr[k][1], [cv2.IMWRITE_JPEG_QUALITY, 85])
            out.append(dict(timestamp_sec=round(float(times[k]), 1), image_base64=base64.b64encode(buf).decode()))
            if len(out) == max_frames:
                break
        return out

    def _rule_refs(self, type_id):
        meta = self.rules_db["violation_types"].get(type_id)
        ids = meta["rules"] if meta else (RULES.get(type_id, {}).get("rule_ids") or [])
        refs = []
        for rid in ids:
            r = self.rules_db["rules"].get(rid)
            if not r:
                continue
            d = self.rules_db["docs"][r["doc"]]
            refs.append(dict(id=rid, document=d["act"], title=d["title"], punkt=r["punkt"], subpunkt=r.get("subpunkt"),
                             quote=r["quote"], url=d["url"], relation=r.get("relation", "direct")))
        return refs

    def analyze(self, video_path):
        t0 = time.perf_counter()
        frames_bgr = _sample_frames(video_path)
        if not frames_bgr:
            return {"verdict": "no_violation", "violations": [], "insufficient_data_reason": "video could not be decoded"}
        frames = self.perceive(frames_bgr)
        tl = build_timeline(frames)
        _, findings = decide(run_rules(tl), self.params)
        violations = []
        for f in findings:
            meta = self.rules_db["violation_types"].get(f.type_id, {})
            refs = self._rule_refs(f.type_id)
            cite = _short_citation(refs)
            violations.append(dict(
                type=self.type_names.get(f.type_id, f.type_id),
                timecode_sec=round(f.t, 1),
                description=f.description + (f" Норма: {cite}." if cite else ""),
                evidence_frames=self._evidence(frames_bgr, [f.t] + list(f.evidence_ts)),
                type_id=f.type_id, score=round(float(f.score), 2), severity=meta.get("severity", "normal"),
                rule_refs=refs))
        result = {"verdict": "violation" if violations else "no_violation", "violations": violations,
                  "processing_sec": round(time.perf_counter() - t0, 1)}
        # "insufficient data" never replaces the verdict; it is an extra, justified note for the reviewer
        seen_people = np.mean([bool(f.of("person")) for f in frames])
        if seen_people < 0.2:
            result["insufficient_data_reason"] = f"кассир виден только в {seen_people:.0%} кадров — анализ действий ограничен"
        elif not any(f.of(lab) for f in frames for lab in ("safe", "laptop", "counting_machine")):
            result["insufficient_data_reason"] = "рабочее место кассы (сейф, ноутбук, счётная машина) не найдено в кадре"
        return result


STATE_HEADS = {"safe": ("safe_state", "p_state"), "door": ("door_state", "p_state"), "laptop": ("laptop_screen", "p_screen")}


def extract_features(frames, frames_bgr, enc):
    """-> dict(objects=[(k, label, emb)] at 1 fps, persons=DataFrame(i, track, box), Xr (role, 1 fps rows), r_idx, Xa (actions))."""
    import pandas as pd
    H, W = frames_bgr[0][1].shape[:2]
    pil = {}

    def img(k):
        if k not in pil:
            pil.clear()
            pil[k] = Image.fromarray(np.ascontiguousarray(frames_bgr[k][1][:, :, ::-1]))
        return pil[k]

    obj_items = [(k, o.label, o.box) for k, f in enumerate(frames) if k % STATE_EVERY == 0 for o in f.objs if o.label in STATE_HEADS]
    obj_emb = enc([crop(img(k), b) for k, _, b in obj_items]) if obj_items else np.zeros((0, 1))
    rows, tight, ctx = [], [], []
    for k, f in enumerate(frames):
        objs = [(o.label, o.box) for o in f.objs]
        for o in f.of("person"):
            rows.append(dict(vid="v", i=k, track=o.track, box=list(o.box), rel=relation_features(o.box, objs, W, H)))
            ctx.append(crop(img(k), o.box, pad=CONTEXT_PAD))
            tight.append(crop(img(k), o.box) if k % STATE_EVERY == 0 else None)
    df = pd.DataFrame(rows, columns=["vid", "i", "track", "box", "rel"])
    out = dict(objects=[(k, lab, e) for (k, lab, _), e in zip(obj_items, obj_emb)], persons=df, W=W, H=H)
    if rows:
        # context crops on every CTX_EVERY-th frame; frames in between reuse the same track's last embedding
        todo = [i for i, r in enumerate(rows) if r["i"] % CTX_EVERY == 0]
        e_some = enc([ctx[i] for i in todo])
        e_ctx = np.zeros((len(rows), e_some.shape[1]), np.float32)
        last = {}
        enc_at = dict(zip(todo, e_some))
        for i, r in enumerate(rows):
            if i in enc_at:
                e_ctx[i] = last[r["track"]] = enc_at[i]
            elif r["track"] in last:
                e_ctx[i] = last[r["track"]]
            else:
                e_ctx[i] = last[r["track"]] = enc([ctx[i]])[0]
        r_idx = [i for i, c in enumerate(tight) if c is not None]
        e_tight = enc([tight[i] for i in r_idx]) if r_idx else np.zeros((0, e_ctx.shape[1]))
        out["r_idx"] = r_idx
        out["Xr"] = np.hstack([e_tight, np.stack([person_geom(rows[i]["box"], W, H) for i in r_idx])]) if r_idx else np.zeros((0, 1))
        out["Xa"] = action_features_v2(df, e_ctx, np.stack(df.rel), W, H)
    return out


def apply_heads(frames, feats, heads):
    """Set role / state probabilities / action probabilities on the perceived objects."""
    held = {}
    by_k = {}
    for k, lab, e in feats["objects"]:
        head, _ = STATE_HEADS[lab]
        by_k[(k, lab)] = float(heads[head].predict_proba(e[None])[0, 1])
    for k, f in enumerate(frames):
        for o in f.objs:
            if o.label in STATE_HEADS:
                if (k, o.label) in by_k:
                    held[o.label] = by_k[(k, o.label)]
                if o.label in held:
                    o.attrs[STATE_HEADS[o.label][1]] = held[o.label]
    df = feats["persons"]
    if not len(df):
        return
    role_head = heads["role"]
    classes = [str(c) for c in role_head.classes_]
    role_p = {}
    for i, p in zip(feats["r_idx"], role_head.predict_proba(feats["Xr"]) if len(feats["r_idx"]) else []):
        role_p.setdefault(df.track.iloc[i], []).append(p)
    roles = {tr: classes[int(np.mean(ps, 0).argmax())] for tr, ps in role_p.items()}
    # one cashier at a time: tracks are cashier fragments (ID switches) only if they never co-occur
    if "cashier" in classes and role_p:
        ci = classes.index("cashier")
        span = {tr: set(df.i[df.track == tr]) for tr in role_p}
        ranked = sorted(role_p, key=lambda tr: -np.mean([p[ci] for p in role_p[tr]]) * min(1.0, len(role_p[tr]) / 3))
        cashier_frames = set()
        for n, tr in enumerate(ranked):
            pc = np.mean([p[ci] for p in role_p[tr]])
            if (n == 0 or pc >= 0.4) and len(span[tr] & cashier_frames) <= 3:
                roles[tr] = "cashier"
                cashier_frames |= span[tr]
            elif roles[tr] == "cashier":
                roles[tr] = "client"
    act_head = heads["action"]
    P = act_head.predict_proba(feats["Xa"])
    persons = {}
    for k, f in enumerate(frames):
        for o in f.of("person"):
            persons[(k, o.track)] = o
    for (k, tr), p in zip(zip(df.i, df.track), P):
        o = persons[(k, tr)]
        role = roles.get(tr, "client")
        o.attrs["role"] = role
        for cls, pv in zip(act_head.classes_, p):
            if cls == "none":
                continue
            name = ACTION_TO_TIMELINE.get(cls, {}).get(role, cls)
            o.attrs[f"p_{name}"] = max(o.attrs.get(f"p_{name}", 0.0), float(pv))


def _short_citation(refs):
    """'Постановление НБРК № 231: п.20, п.22; НБРК № 14: п.16 пп.1' (full act titles stay in rule_refs)."""
    import re
    by_doc = {}
    for r in refs:
        m = re.search(r"№\s*(\d+)", r["document"])
        doc = f"Постановление НБРК № {m.group(1)}" if m else r["document"]
        item = f"п.{r['punkt']}" + (f" пп.{r['subpunkt']}" if r.get("subpunkt") else "") + (" (косвенно)" if r.get("relation") == "indirect" else "")
        by_doc.setdefault(doc, []).append(item)
    return "; ".join(f"{d}: {', '.join(items)}" for d, items in by_doc.items())


def _nms(dets, iou_thr=0.6):
    out = []
    for lab in {d[0] for d in dets}:
        ds = sorted([d for d in dets if d[0] == lab], key=lambda d: -d[1])
        keep = []
        for d in ds:
            if all(_iou(d[2], k[2]) < iou_thr for k in keep):
                keep.append(d)
        out += keep
    return out


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0
