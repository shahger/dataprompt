"""Cash tracking: identity over time, who holds each stack, splits, and where each stack ends up.

ByteTrack-style IoU matching fails on cash: stacks are small and move fast between frames 1/3 s apart, so
their boxes barely overlap. Here detections are matched by center distance (Hungarian assignment, gated by
the stack size), a stack may stay unseen for MAX_GAP frames (hidden in a hand), and a new stack born right
next to an existing one is recorded as split from it.

Holder per frame (annotated value wins when it is set): safe zone -> safe; on the counting machine -> machine;
inside a person's box and moving (or not on the desk) -> that person's hand; on the desk -> desk.
"""
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

MAX_GAP = 6          # frames (2 s) a stack may be hidden before its track ends
GATE = 2.5           # max center jump, in stack sizes ...
BASE_PX = 40         # ... plus this many pixels (fast hand movements)
SPLIT_RADIUS = 2.0   # a new stack this close (in stack sizes) to a live one is split from it
STILL_PX = 4.0       # center speed (px/frame) below which a stack is lying, not carried
HANDS = {"cashier": "cashier_hand", "client": "client_hand", "collector": "client_hand", "colleague": "cashier_hand"}


@dataclass
class CashTrack:
    id: int
    obs: list = field(default_factory=list)     # (frame index, t, box, holder)
    parent: int | None = None                   # track it split from
    end: str | None = None                      # where it ended: safe, machine, client, cashier, desk, out_of_view

    @property
    def t0(self):
        return self.obs[0][1]

    @property
    def t1(self):
        return self.obs[-1][1]

    def holders(self):
        return [o[3] for o in self.obs]


def _center(b):
    return np.array([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2])


def _size(b):
    return max(8.0, ((b[2] - b[0]) * (b[3] - b[1])) ** 0.5)


def _inside(pt, box, pad=0.0):
    return box is not None and box[0] - pad <= pt[0] <= box[2] + pad and box[1] - pad <= pt[1] <= box[3] + pad


def _assign(frames_cash):
    """frames_cash: per frame list of (box, annotated_track_or_None). Returns per frame list of track ids."""
    next_id, live, ids = 0, {}, []   # live: id -> (last frame, last box)
    for i, dets in enumerate(frames_cash):
        frame_ids = [None] * len(dets)
        # annotated identities (CVAT tracks) are kept as they are
        for k, (box, tr) in enumerate(dets):
            if tr is not None:
                frame_ids[k] = ("a", tr)
        todo = [k for k in range(len(dets)) if frame_ids[k] is None]
        cand = [tid for tid, (lf, _) in live.items() if i - lf <= MAX_GAP and not (isinstance(tid, tuple) and tid[0] == "a")]
        if todo and cand:
            cost = np.full((len(todo), len(cand)), 1e6)
            for r, k in enumerate(todo):
                c = _center(dets[k][0])
                for col, tid in enumerate(cand):
                    lb = live[tid][1]
                    d = np.linalg.norm(c - _center(lb))
                    gate = GATE * max(_size(lb), _size(dets[k][0])) + BASE_PX * (i - live[tid][0])
                    if d <= gate:
                        cost[r, col] = d
            rows, cols = linear_sum_assignment(cost)
            for r, col in zip(rows, cols):
                if cost[r, col] < 1e6:
                    frame_ids[todo[r]] = cand[col]
        for k in range(len(dets)):
            if frame_ids[k] is None:
                frame_ids[k] = next_id
                next_id += 1
            live[frame_ids[k]] = (i, dets[k][0])
        ids.append(frame_ids)
    return ids


def track_cash(frames, zones, roles):
    """frames: list[Frame]; roles: person track -> role. Returns list[CashTrack] (ids renumbered 0..n)."""
    per_frame = [[(o.box, o.track) for o in f.of("cash")] for f in frames]
    ids = _assign(per_frame)
    machines = [o.box for f in frames for o in f.of("counting_machine")]
    machine = list(np.median(np.asarray(machines, float), 0)) if machines else None

    tracks, key2id = {}, {}
    for i, (f, fids) in enumerate(zip(frames, ids)):
        people = [(roles.get(o.track, "client"), o.box) for o in f.of("person") if roles.get(o.track) not in (None, "other")]
        for o, key in zip(f.of("cash"), fids):
            if key not in key2id:
                key2id[key] = len(key2id)
                tracks[key2id[key]] = CashTrack(key2id[key])
            tr = tracks[key2id[key]]
            prev = tr.obs[-1][2] if tr.obs else None
            speed = np.linalg.norm(_center(o.box) - _center(prev)) / max(1, i - tr.obs[-1][0]) if prev else 0.0
            tr.obs.append((i, f.t, o.box, _holder(o, speed, zones, machine, people)))

    out = sorted(tracks.values(), key=lambda tr: tr.t0)
    for tr in out:
        tr.parent = _split_parent(tr, out)
        tr.end = _end(tr, frames, zones, machine, roles)
    return out


def _holder(o, speed, zones, machine, people):
    annotated = o.attrs.get("holder")
    c = _center(o.box)
    if annotated not in (None, "auto", "hand"):
        return annotated
    if _inside(c, zones.safe, pad=10):
        return "safe"
    if machine is not None and _inside(c, machine, pad=5):
        return "machine"
    holding = [(role, box) for role, box in people if _inside(c, box, pad=10)]
    on_desk = _inside(c, zones.desk)
    if holding and (speed > STILL_PX or not on_desk or annotated == "hand"):
        role, box = min(holding, key=lambda rb: np.linalg.norm(c - _center(rb[1])))
        return HANDS.get(role, "client_hand")
    if on_desk:
        return "desk"
    return HANDS.get(holding[0][0], "client_hand") if holding else "unknown"


def _split_parent(tr, tracks):
    """A stack that first appears next to a stack that is visible at the same moment was split from it."""
    i0, b0 = tr.obs[0][0], tr.obs[0][2]
    best, best_d = None, None
    for other in tracks:
        if other.id == tr.id or other.obs[0][0] >= i0:
            continue
        near = [o for o in other.obs if abs(o[0] - i0) <= 1]
        if not near:
            continue
        d = np.linalg.norm(_center(b0) - _center(near[0][2])) / max(_size(b0), _size(near[0][2]))
        if d <= SPLIT_RADIUS and (best_d is None or d < best_d):
            best, best_d = other.id, d
    return best


def _end(tr, frames, zones, machine, roles):
    last_i, _, box, holder = tr.obs[-1]
    if holder == "hidden":
        return "cashier"
    if last_i >= len(frames) - 1 - MAX_GAP:   # still visible at the end of the video
        return {"desk": "desk", "safe": "safe", "machine": "machine"}.get(holder, "out_of_view")
    if holder == "safe" or _inside(_center(box), zones.safe, pad=30):
        return "safe"
    if holder == "machine":
        return "machine"
    if holder == "client_hand":
        return "client"
    if holder == "cashier_hand":
        return "cashier"
    return "desk" if holder == "desk" else "out_of_view"
