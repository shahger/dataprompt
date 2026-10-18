"""Scene timeline: smoothed per-frame signals + events, built from list[Frame].

Zones are derived from each video's own detections (never hard-coded pixels), so they follow the camera angle:
- glass/door region: union of door boxes; a person whose foot point is inside it and above its bottom edge
  is in the corridor behind the glass and is ignored;
- desk zone: hull of desk-top objects (laptop, counting machine, cash, stamp, ...), slightly expanded.
"""
from dataclasses import dataclass, field

import numpy as np

from .cash import track_cash

DESK_OBJECTS = {"laptop", "counting_machine", "uv_scanner", "cash", "stamp", "document_id", "cup_food", "package"}
ACTIONS = ["entering_room", "leaving_room", "starting_workday", "ending_workday", "putting_personal_items",
           "showing_id", "checking_id", "handover_give", "handover_take", "opening_package",
           "counting_by_hand", "counting_by_machine", "using_scanner", "putting_into_safe", "taking_from_safe",
           "waiting_while_other_served", "leaving_during_count",
           "safe_op", "id"]   # classifier-level classes: safe operation (direction from the ledger), ID shown/checked
MIN_ON = 3    # frames (1 s at 3 fps) a state must hold before it switches on ...
MIN_OFF = 3   # ... or off (hysteresis)


def debounce(x, min_on=MIN_ON, min_off=MIN_OFF, flush_end=0):
    """Boolean hysteresis: the output flips only after the input agrees for min_on / min_off frames.
    flush_end > 0: a change still pending at the end of the video is applied if it lasted >= flush_end frames."""
    x = np.asarray(x, bool)
    out, state, run_start = np.zeros_like(x), False, None
    for i, v in enumerate(x):
        if v == state:
            run_start = None
        else:
            run_start = i if run_start is None else run_start
            if i - run_start + 1 >= (min_on if v else min_off):
                state = v
                out[run_start:i + 1] = v   # backdate the switch to when the change began
                run_start = None
                continue
        out[i] = state
    if flush_end and run_start is not None and len(x) - run_start >= flush_end:
        out[run_start:] = x[run_start:]
    return out


def _inside(pt, box, pad=0.0):
    return box is not None and box[0] - pad <= pt[0] <= box[2] + pad and box[1] - pad <= pt[1] <= box[3] + pad


def _near(box, target, min_cover=0.3):
    """Person is at the target: the person box covers >= min_cover of the target's area."""
    if target is None:
        return False
    ix = max(0.0, min(box[2], target[2]) - max(box[0], target[0]))
    iy = max(0.0, min(box[3], target[3]) - max(box[1], target[1]))
    area = max(1e-6, (target[2] - target[0]) * (target[3] - target[1]))
    return ix * iy / area >= min_cover


def _union(boxes):
    b = np.asarray(boxes, float)
    return [b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max()] if len(b) else None


def _main_track(frames, label):
    """The longest-lived track of a label (e.g. the real safe among spurious safe boxes)."""
    count = {}
    for f in frames:
        for o in f.of(label):
            count[o.track] = count.get(o.track, 0) + 1
    return max(count, key=count.get) if count else None


@dataclass
class Zones:
    glass: list | None      # corridor region behind the glass/door
    desk: list | None       # desk top
    safe: list | None


def derive_zones(frames):
    doors = [o.box for f in frames for o in f.of("door")]
    glass = None
    if doors:
        d = np.asarray(doors, float)
        glass = [d[:, 0].min(), d[:, 1].min(), d[:, 2].max(), float(np.median(d[:, 3]))]
    desk_boxes = [o.box for f in frames for o in f.objs if o.label in DESK_OBJECTS]
    desk = _union(desk_boxes)
    if desk:
        w, h = desk[2] - desk[0], desk[3] - desk[1]
        desk = [desk[0] - 0.1 * w, desk[1] - 0.1 * h, desk[2] + 0.1 * w, desk[3] + 0.1 * h]
    safe_track = _main_track(frames, "safe")
    safes = [o.box for f in frames for o in f.of("safe") if o.track == safe_track]
    safe = list(np.median(np.asarray(safes, float), 0)) if safes else None
    return Zones(glass, desk, safe)


def infer_roles(frames, zones):
    """Role per person track. Uses the annotated `role` when present; otherwise the longest-present person
    inside the room is the cashier and every other person inside is a client."""
    annotated, presence = {}, {}
    for f in frames:
        for o in f.of("person"):
            if o.attrs.get("role") not in (None, "unknown"):   # "unknown" = not set by an annotator
                annotated.setdefault(o.track, {}).setdefault(o.attrs["role"], 0)
                annotated[o.track][o.attrs["role"]] += 1
            if not in_corridor(o, zones):
                presence[o.track] = presence.get(o.track, 0) + 1
    roles = {tr: max(r, key=r.get) for tr, r in annotated.items()}
    if roles:
        # roles were annotated: a person track without one is a duplicate/fragment, not a new client
        for tr in presence:
            roles.setdefault(tr, "other")
        return roles
    if presence:
        roles[max(presence, key=presence.get)] = "cashier"
    for tr in presence:
        roles.setdefault(tr, "client")
    return roles


def in_corridor(o, zones):
    """Person outside the cash room (seen through the glass wall).

    Box geometry alone can't separate the room from the corridor from this camera angle (the seated cashier
    overlaps the glass region), so the decision comes from, in order: the annotated role `other`, the learned
    corridor classifier (`p_corridor`), and only as a fallback a strict geometric test (feet in the upper half
    of the glass region)."""
    if o.attrs.get("role") == "other":
        return True
    if "p_corridor" in o.attrs:
        return o.attrs["p_corridor"] >= 0.5
    g = zones.glass
    return g is not None and g[0] <= o.foot[0] <= g[2] and o.foot[1] < g[1] + 0.5 * (g[3] - g[1])


@dataclass
class Timeline:
    t: np.ndarray
    sig: dict = field(default_factory=dict)        # name -> bool/float array over frames (smoothed)
    events: list = field(default_factory=list)     # (t, name, info)
    sessions: list = field(default_factory=list)   # client sessions: dict(start, end, i0, i1)
    zones: Zones | None = None
    roles: dict = field(default_factory=dict)
    cash: list = field(default_factory=list)       # list[CashTrack] (ml/cash.py)

    def at(self, name, t):
        return self.sig[name][int(np.argmin(np.abs(self.t - t)))]

    def window(self, name, t0, t1):
        m = (self.t >= t0) & (self.t <= t1)
        return self.sig[name][m]

    def first(self, name, t0=-np.inf, t1=np.inf):
        idx = np.where(self.sig[name] & (self.t >= t0) & (self.t <= t1))[0]
        return float(self.t[idx[0]]) if len(idx) else None

    def ev(self, name):
        return [e for e in self.events if e[1] == name]


ACTION_P = 0.5        # min classifier probability for a predicted action frame (grid-searched, LOPO)
STATE_P = {"state": 0.5, "screen": 0.5}


def _prob(o, attr, on_value):
    v = o.attrs.get(attr)
    if v is not None:
        return 1.0 if v == on_value else 0.0
    return float(o.attrs.get(f"p_{attr}", 0.0))


def _state(o, attr, on_value):
    v = o.attrs.get(attr)
    if v is None:
        return o.attrs.get(f"p_{attr}", 0.0) >= STATE_P.get(attr, 0.5)   # model mode: state-classifier probability
    return v == on_value


MONEY_IN = ["cashier_handover_take", "client_handover_give", "collector_handover_give", "cashier_taking_from_safe",
            "cashier_opening_package"]
MONEY_IN_SUSTAINED = ["cashier_counting_by_hand", "cashier_counting_by_machine"]   # count as money-in only if >= 2 s
MONEY_OUT = ["cashier_putting_into_safe", "cashier_handover_give"]


def money_ledger(tl):
    """Money appears only through operations: it is 'in play' from the first money-in operation (client hands it
    over, taken from the safe, package opened, counting) until a money-out operation ends (into the safe, handed to
    the client). Adds `money_in_play` and the events money_in / money_out."""
    n = len(tl.t)
    m_in = np.zeros(n, bool)
    m_out = np.zeros(n, bool)
    for k in MONEY_IN:
        m_in |= tl.sig.get(k, np.zeros(n, bool))
    for k in MONEY_IN_SUSTAINED:
        m_in |= debounce(tl.sig.get(k, np.zeros(n, bool)), min_on=6, min_off=2)
    for k in MONEY_OUT:
        m_out |= tl.sig.get(k, np.zeros(n, bool))
    # a safe operation of unknown direction (action classifier): money out of play if some is in play, else money in
    safe_op = tl.sig.get("cashier_safe_op", np.zeros(n, bool))
    play, state = np.zeros(n, bool), False
    for i in range(n):
        if safe_op[i]:
            (m_out if state else m_in)[i] = True
        if m_in[i] and not m_out[i]:
            if not state:
                tl.events.append((float(tl.t[i]), "money_in", {}))
            state = True
        if state and i > 0 and m_out[i - 1] and not m_out[i]:   # a money-out operation just finished
            tl.events.append((float(tl.t[i]), "money_out", {}))
            state = False
        play[i] = state
    tl.sig["money_in_play"] = play
    # new money arriving while earlier money is still in play (e.g. the next client's money onto the previous one)
    rises = np.where(np.diff(m_in.astype(int), prepend=0) == 1)[0]
    for i in rises:
        if i > 0 and play[i - 1]:
            tl.events.append((float(tl.t[i]), "money_in_on_top", {}))


def build_timeline(frames):
    zones = derive_zones(frames)
    roles = infer_roles(frames, zones)
    n = len(frames)
    t = np.array([f.t for f in frames])
    raw = {k: np.zeros(n, bool) for k in [
        "cashier_in_room", "cashier_at_desk", "cashier_near_safe", "safe_open", "key_in_lock", "door_open", "laptop_on",
        "cash_on_desk", "cash_cashier_hand", "cash_client_hand", "stamp_on_desk", "doc_present", "cup_on_desk", "clothing_on_desk",
        "package_present", "package_opened"]}
    counts = {k: np.zeros(n, int) for k in ["n_clients", "n_collectors", "n_colleagues", "n_unknown_inside", "n_cash_on_desk"]}
    acts = {f"{who}_{a}": np.zeros(n, bool) for who in ("cashier", "client", "collector", "any") for a in ACTIONS}
    model_acts = {k: np.zeros(n, bool) for k in acts}      # from classifier probabilities: need persistence
    prob = {k: np.zeros(n) for k in ("p_safe_open", "p_door_open", "p_laptop_on")}   # confidence (1.0 for annotations)
    safe_tr, door_tr, laptop_tr = (_main_track(frames, l) for l in ("safe", "door", "laptop"))

    for i, f in enumerate(frames):
        for o in f.of("person"):
            if in_corridor(o, zones):
                continue
            role = roles.get(o.track, "client")
            if role == "cashier":
                raw["cashier_in_room"][i] = True
                raw["cashier_at_desk"][i] |= _inside(o.center, zones.desk, pad=40)
                raw["cashier_near_safe"][i] |= _near(o.box, zones.safe)
            elif role == "client":
                counts["n_clients"][i] += 1
            elif role == "collector":
                counts["n_collectors"][i] += 1
            elif role == "colleague":
                counts["n_colleagues"][i] += 1
            else:
                counts["n_unknown_inside"][i] += 1
            a = o.attrs.get("action")
            if a in ACTIONS:
                acts[f"any_{a}"][i] = True
                if role in ("cashier", "client", "collector"):
                    acts[f"{role}_{a}"][i] = True
            for a in ACTIONS:   # model mode: action classifier probabilities
                if o.attrs.get(f"p_{a}", 0.0) >= ACTION_P:
                    model_acts[f"any_{a}"][i] = True
                    if role in ("cashier", "client", "collector"):
                        model_acts[f"{role}_{a}"][i] = True
        for o in f.of("safe"):
            if o.track == safe_tr or safe_tr is None:
                raw["safe_open"][i] |= _state(o, "state", "open")
                prob["p_safe_open"][i] = max(prob["p_safe_open"][i], _prob(o, "state", "open"))
                raw["key_in_lock"][i] |= _state(o, "key_in_lock", "yes")
        for o in f.of("door"):
            if o.track == door_tr or door_tr is None:
                raw["door_open"][i] |= _state(o, "state", "open")
                prob["p_door_open"][i] = max(prob["p_door_open"][i], _prob(o, "state", "open"))
        for o in f.of("laptop"):
            if o.track == laptop_tr or laptop_tr is None:
                raw["laptop_on"][i] |= _state(o, "screen", "on")
                prob["p_laptop_on"][i] = max(prob["p_laptop_on"][i], _prob(o, "screen", "on"))
        raw["stamp_on_desk"][i] = any(_inside(o.center, zones.desk) for o in f.of("stamp"))
        raw["doc_present"][i] = bool(f.of("document_id"))
        raw["cup_on_desk"][i] = any(_inside(o.center, zones.desk) for o in f.of("cup_food"))
        raw["clothing_on_desk"][i] = any(_inside(o.center, zones.desk) for o in f.of("clothing_bag"))
        raw["package_present"][i] = bool(f.of("package"))
        raw["package_opened"][i] = any(o.attrs.get("state") == "opened" for o in f.of("package"))

    cash = track_cash(frames, zones, roles)
    for tr in cash:
        for i, _, _, holder in tr.obs:
            if holder == "desk":
                raw["cash_on_desk"][i] = True
                counts["n_cash_on_desk"][i] += 1
            elif holder == "cashier_hand":
                raw["cash_cashier_hand"][i] = True
            elif holder == "client_hand":
                raw["cash_client_hand"][i] = True

    tl = Timeline(t=t, zones=zones, roles=roles, cash=cash)
    for k, v in raw.items():
        # leaving = gone for >= 2 s (or until the end of the video)
        tl.sig[k] = debounce(v, min_off=6, flush_end=2) if k == "cashier_in_room" else debounce(v)
    for k, v in acts.items():
        # actions are short: a single frame counts (persistence for predicted ones did not help, see grid search)
        tl.sig[k] = debounce(v, min_on=1, min_off=2) | debounce(model_acts[k], min_on=1, min_off=2)
    tl.sig.update(prob)
    for k, v in counts.items():
        tl.sig[k] = v
        tl.sig[k.replace("n_", "has_", 1)] = debounce(v > 0)
    tl.sig["two_clients"] = debounce(counts["n_clients"] >= 2)
    money_ledger(tl)

    # events from smoothed transitions
    for name, s in [("cashier", tl.sig["cashier_in_room"]), ("client", tl.sig["has_clients"]),
                    ("collector", tl.sig["has_collectors"]), ("safe_open", tl.sig["safe_open"]),
                    ("door_open", tl.sig["door_open"])]:
        d = np.diff(s.astype(int), prepend=int(s[0]))
        for i in np.where(d == 1)[0]:
            tl.events.append((float(t[i]), f"{name}_start", {}))
        for i in np.where(d == -1)[0]:
            tl.events.append((float(t[i]), f"{name}_end", {}))
    for tr in cash:
        if tr.parent is not None:
            tl.events.append((tr.t0, "cash_split", {"track": tr.id, "parent": tr.parent}))
        tl.events.append((tr.t1, "cash_end", {"track": tr.id, "where": tr.end}))
    tl.events.sort(key=lambda e: e[0])

    # client sessions: one per client track (presence inside the room), so a client leaving while the next one
    # comes in still gives two sessions
    seen = {}
    for i, f in enumerate(frames):
        for o in f.of("person"):
            if roles.get(o.track) in ("client", "collector") and not in_corridor(o, zones):
                seen.setdefault(o.track, []).append(i)
    for tr, idx in sorted(seen.items(), key=lambda kv: kv[1][0]):
        if len(idx) >= 6:   # >= 2 s in the room
            tl.sessions.append(dict(start=float(t[idx[0]]), end=float(t[idx[-1]]), i0=idx[0], i1=idx[-1], track=tr))
    return tl
