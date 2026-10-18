"""Per-type thresholds and timecode offsets.

Objective (agreed): 100 % recall on the labelled violations first, then the fewest false positives.
- trained types: threshold = the lowest score that still keeps every labelled event of that type
  (a finding of the type within MATCH_TOL seconds), times SLACK for unseen videos;
- catalogue rules without training examples (trained=False): threshold just above their highest score on the
  training videos, i.e. they must stay silent on all training videos;
- timecode offset per type = median (label time - finding time) over matched events.
"""
import json

import numpy as np

from .rules import RULES

MATCH_TOL = 6.0   # s between a finding and the labelled second to count as the same event
SLACK = 0.8       # keep thresholds below the training minimum (few examples per type)
DEFAULT_THRESHOLD = 0.5   # for a trained type that has no labelled example in the calibration videos


def _match(findings, t, type_id):
    cand = [f for f in findings if f.type_id == type_id and abs(f.t - t) <= MATCH_TOL]
    return max(cand, key=lambda f: f.score) if cand else None


def calibrate(findings_by_video, events_by_video):
    """findings_by_video: vid -> list[Finding]; events_by_video: vid -> [(t, type_id), ...] (labels)."""
    params, report = {"threshold": {}, "offset": {}}, {}
    for type_id, meta in RULES.items():
        if not meta["trained"]:
            scores = [f.score for fs in findings_by_video.values() for f in fs if f.type_id == type_id]
            params["threshold"][type_id] = (max(scores) + 1e-3) if scores else 0.0
            params["offset"][type_id] = 0.0
            continue
        matched, missed, dts = [], [], []
        for vid, evs in events_by_video.items():
            for t, ty in evs:
                if ty != type_id:
                    continue
                f = _match(findings_by_video.get(vid, []), t, type_id)
                if f is None:
                    missed.append(vid)
                else:
                    matched.append(f.score)
                    dts.append(t - f.t)
        if matched:
            params["threshold"][type_id] = SLACK * min(matched)
        elif not missed:
            params["threshold"][type_id] = DEFAULT_THRESHOLD   # no labelled example in these videos: neutral prior
        else:
            # no labelled example was found by this rule: like an untrained rule, it must stay silent on training videos
            scores = [f.score for vid, fs in findings_by_video.items() for f in fs
                      if f.type_id == type_id and not any(ty == type_id for _, ty in events_by_video.get(vid, []))]
            params["threshold"][type_id] = (max(scores) + 1e-3) if scores else 0.0
        params["offset"][type_id] = float(np.median(dts)) if dts else 0.0
        report[type_id] = dict(labelled=len(matched) + len(missed), matched=len(matched), missed=missed)
    # video-level verdict: the strongest finding of any type, threshold at full recall on these videos
    pos_max = [max((f.score for f in findings_by_video.get(v, [])), default=0.0) for v, evs in events_by_video.items() if evs]
    params["verdict_threshold"] = SLACK * min(pos_max) if pos_max and min(pos_max) > 0 else 0.0
    return params, report


def decide(findings, params):
    """-> (verdict, findings to report). The verdict uses the video-level threshold; reported findings are those
    passing their type thresholds, or the strongest one when the verdict is positive but none passes."""
    kept = apply(findings, params)
    top = max(findings, key=lambda f: f.score, default=None)
    violation = top is not None and top.score >= params.get("verdict_threshold", 0.0)
    if violation and not kept:
        kept = apply([top], {**params, "threshold": {top.type_id: 0.0}})
    if not violation:
        kept = []
    return violation, kept


def apply(findings, params):
    """Keep findings at/above their type threshold, shift timecodes, collapse duplicates (same type within 3 s)."""
    kept = []
    for f in sorted(findings, key=lambda f: -f.score):
        if f.score < params["threshold"].get(f.type_id, 0.0):
            continue
        t = max(0.0, f.t + params["offset"].get(f.type_id, 0.0))
        if any(k.type_id == f.type_id and abs(k.t - t) < 10 for k in kept):
            continue
        if sum(k.type_id == f.type_id for k in kept) >= 2:   # at most 2 findings of one type per video
            continue
        # keep the description's time in step with the shifted timecode
        desc = f.description.replace(f"{f.t:.1f} с", f"{t:.1f} с", 1) if t != f.t else f.description
        f2 = type(f)(**{**f.__dict__, "t": t, "description": desc})
        kept.append(f2)
    return sorted(kept, key=lambda f: f.t)


def to_result(findings, type_names):
    """Findings -> the API result shape (evidence images are added later by the report step)."""
    return {
        "verdict": "violation" if findings else "no_violation",
        "violations": [dict(type=type_names.get(f.type_id, f.type_id), type_id=f.type_id, timecode_sec=round(f.t, 1),
                            description=f.description, score=round(f.score, 2),
                            evidence_frames=[dict(timestamp_sec=round(max(0.0, x), 1), image_base64="") for x in [f.t] + f.evidence_ts[:2]])
                       for f in findings],
    }


def leave_one_pair_out(findings_by_video, events_by_video, fold_of, type_names):
    """For each fold: calibrate on the other folds, apply to the held-out videos. Returns vid -> result."""
    results = {}
    for fold in sorted(set(fold_of.values())):
        train = [v for v in findings_by_video if fold_of[v] != fold]
        params, _ = calibrate({v: findings_by_video[v] for v in train}, {v: events_by_video.get(v, []) for v in train})
        for v in findings_by_video:
            if fold_of[v] == fold:
                violation, kept = decide(findings_by_video[v], params)
                results[v] = to_result(kept, type_names)
    return results


def save_params(params, path):
    path.write_text(json.dumps(params, indent=2))
