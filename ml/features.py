"""Feature builders shared by training (tools/train_heads.py) and runtime (ml/analyze.py)."""
import numpy as np
import pandas as pd

STATE_TASKS = {   # head name -> (label, attribute, positive value)
    "safe_state": ("safe", "state", "open"),
    "door_state": ("door", "state", "open"),
    "laptop_screen": ("laptop", "screen", "on"),
}
# fine-grained annotation actions -> classes the classifier learns (rare/ambiguous ones folded)
ACTION_MAP = {
    "handover_give": "handover_give", "handover_take": "handover_take",
    "showing_id": "id", "checking_id": "id",
    "counting_by_hand": "counting_by_hand", "counting_by_machine": "counting_by_machine",
    "using_scanner": "using_scanner",
    "putting_into_safe": "safe_op", "taking_from_safe": "safe_op",
    "opening_package": "opening_package",
    "putting_personal_items": "putting_personal_items",
}
WIN = 6   # frames on each side (+-2 s at 3 fps)
CONTEXT_PAD = 0.45   # wider person crop for actions: hands + objects held


def person_geom(box, W, H):
    x0, y0, x1, y1 = box
    return np.array([(x0 + x1) / 2 / W, (y0 + y1) / 2 / H, (x1 - x0) / W, (y1 - y0) / H, y1 / H], np.float32)


def action_features(df, emb, W, H):
    """df: rows (vid, i, track, box) aligned with emb [N, D]. Window = same track, frames i-WIN..i+WIN."""
    geom = np.stack([person_geom(b, W, H) for b in df.box])
    out = np.zeros((len(df), emb.shape[1] * 2 + geom.shape[1] * 2), np.float32)
    for (_, _), g in df.groupby(["vid", "track"], sort=False):
        order = g.sort_values("i")
        rows = order.index.to_numpy()
        frames = order.i.to_numpy()
        for k, r in enumerate(rows):
            sel = rows[np.abs(frames - frames[k]) <= WIN]
            e = emb[sel]
            first, last = rows[max(0, k - WIN)], rows[min(len(rows) - 1, k + WIN)]
            out[r] = np.concatenate([e.mean(0), emb[last] - emb[first], geom[r], geom[last] - geom[first]])
    return out


REL_OBJECTS = ["safe", "counting_machine", "laptop", "door", "uv_scanner"]


def relation_features(person_box, frame_objs, W, H):
    """Where the person is relative to the objects that define the actions (safe, machine, scanner, other people).
    frame_objs: list of (label, box) in the same frame (persons included)."""
    px, py = (person_box[0] + person_box[2]) / 2, (person_box[1] + person_box[3]) / 2
    diag = (W ** 2 + H ** 2) ** 0.5
    feats = []
    for lab in REL_OBJECTS + ["person"]:
        cand = [b for l, b in frame_objs if l == lab and b is not person_box and list(b) != list(person_box)]
        if not cand:
            feats += [1.0, 0.0]
            continue
        d = min((((b[0] + b[2]) / 2 - px) ** 2 + ((b[1] + b[3]) / 2 - py) ** 2) ** 0.5 for b in cand) / diag
        ov = max(_overlap(person_box, b) for b in cand)
        feats += [d, ov]
    return np.array(feats, np.float32)


def _overlap(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    area = max(1e-6, (a[2] - a[0]) * (a[3] - a[1]))
    return ix * iy / area


def action_features_v2(df, emb, rel, W, H):
    """Window (+-WIN) of context-crop embeddings + relation features: mean, motion (last - first)."""
    geom = np.stack([person_geom(b, W, H) for b in df.box])
    base = np.hstack([geom, rel])
    out = np.zeros((len(df), emb.shape[1] * 2 + base.shape[1] * 3), np.float32)
    for _, g in df.groupby(["vid", "track"], sort=False):
        order = g.sort_values("i")
        rows = order.index.to_numpy()
        frames = order.i.to_numpy()
        for k, r in enumerate(rows):
            sel = rows[np.abs(frames - frames[k]) <= WIN]
            first, last = rows[max(0, k - WIN)], rows[min(len(rows) - 1, k + WIN)]
            out[r] = np.concatenate([emb[sel].mean(0), emb[last] - emb[first], base[r], base[sel].min(0), base[last] - base[first]])
    return out


POSE_TARGETS = ["safe", "counting_machine", "laptop", "uv_scanner"]
POSE_DIM = 2 * 3 + 2 * len(POSE_TARGETS) + 2


def pose_features(kp, sc, frame_objs, other_wrists, W, H):
    """Wrist evidence for actions: wrist positions + confidence, wrist distance to the safe / machine / laptop /
    scanner, and to the closest wrist of another person (handover). kp [17, 2], sc [17]."""
    diag = (W ** 2 + H ** 2) ** 0.5
    feats = []
    wrists = [(kp[i], sc[i]) for i in (9, 10)]
    for (x, y), c in wrists:
        feats += [x / W, y / H, float(c)]
    for lab in POSE_TARGETS:
        boxes = [b for l, b in frame_objs if l == lab]
        for (x, y), c in wrists:
            if not boxes or c < 0.2:
                feats.append(1.0)
                continue
            feats.append(min(_point_box_dist(x, y, b) for b in boxes) / diag)
    for (x, y), c in wrists:
        if not other_wrists or c < 0.2:
            feats.append(1.0)
            continue
        feats.append(min(((x - ox) ** 2 + (y - oy) ** 2) ** 0.5 for ox, oy in other_wrists) / diag)
    return np.array(feats, np.float32)


def _point_box_dist(x, y, b):
    dx = max(b[0] - x, 0.0, x - b[2])
    dy = max(b[1] - y, 0.0, y - b[3])
    return (dx * dx + dy * dy) ** 0.5


def action_features_v3(df, emb, rel, pose, W, H):
    """v2 + pose: window (+-WIN) mean / min / change of the wrist features."""
    base = action_features_v2(df, emb, rel, W, H)
    extra = np.zeros((len(df), pose.shape[1] * 3), np.float32)
    for _, g in df.groupby(["vid", "track"], sort=False):
        order = g.sort_values("i")
        rows = order.index.to_numpy()
        frames = order.i.to_numpy()
        for k, r in enumerate(rows):
            sel = rows[np.abs(frames - frames[k]) <= WIN]
            first, last = rows[max(0, k - WIN)], rows[min(len(rows) - 1, k + WIN)]
            extra[r] = np.concatenate([pose[sel].mean(0), pose[sel].min(0), pose[last] - pose[first]])
    return np.hstack([base, extra])
