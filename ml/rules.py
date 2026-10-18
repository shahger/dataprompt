"""Violation rules over the scene timeline: one function per type, registered with its metadata.

Each rule yields Findings (time, score in [0, 1], evidence times, short factual description).
Thresholds per type are set by calibration (ml/calibrate.py), not here; scores only rank evidence strength.
Descriptions state what is visible and that it needs checking; citations are attached later from rules_db.json.
"""
from dataclasses import dataclass, field

import numpy as np

RULES = {}


@dataclass
class Finding:
    type_id: str
    t: float
    score: float
    evidence_ts: list
    description: str
    facts: dict = field(default_factory=dict)


def rule(type_id, group, name=None, rule_ids=None, trained=True):
    """trained=False marks catalogue rules without training examples: calibrated to zero false positives only."""
    def deco(fn):
        RULES[type_id] = dict(fn=fn, group=group, name=name, rule_ids=rule_ids, trained=trained)
        return fn
    return deco


def run_rules(tl, only=None):
    out = []
    for type_id, r in RULES.items():
        if only and type_id not in only:
            continue
        out += list(r["fn"](tl))
    return out


def _ts(t):
    return f"{t:.1f} с"


def _leaves(tl, min_away=3.0):
    """Moments the cashier really leaves the room: gone for >= min_away s, or until the end of the video."""
    out = []
    for t, _, _ in tl.ev("cashier_end"):
        back = [e[0] for e in tl.ev("cashier_start") if e[0] > t]
        if not back or back[0] - t >= min_away:
            out.append(t)
    return out


def _any(tl, sig, t0, t1):
    return bool(tl.window(sig, t0, t1).any())


def _conf(tl, prob, t0, t1):
    """Mean model confidence of a state over a window (1.0 with annotations)."""
    w = tl.window(prob, t0, t1)
    return float(w.mean()) if len(w) else 0.0


def _frac(tl, sig, t0, t1):
    w = tl.window(sig, t0, t1)
    return float(w.mean()) if len(w) else 0.0


# ---------- A. the cashier leaves the room ----------

@rule("V-DESK", "A")
def cash_left_on_desk(tl):
    for t in _leaves(tl):
        seen = _any(tl, "cash_on_desk", t - 1.5, t) or _any(tl, "package_present", t - 1.5, t)
        in_play = _any(tl, "money_in_play", t - 1, t)    # money came in and never went to the safe / client
        if seen or in_play:
            yield Finding("V-DESK", t, 0.8 if seen and in_play else (0.6 + 0.2 * seen), [t - 1, t],
                          f"Кассир покидает помещение ({_ts(t)}), а наличные, поступившие в ходе операции, не убраны в сейф"
                          f"{' и видны на столе' if seen else ''}. Возможное нарушение хранения наличных — требуется проверка.")


@rule("V-OPEN", "A")
def safe_left_open(tl):
    for t in _leaves(tl):
        if _any(tl, "safe_open", t - 1, t + 1):
            yield Finding("V-OPEN", t, 0.8 * _conf(tl, "p_safe_open", t - 1, t + 1), [t], f"Кассир покидает помещение ({_ts(t)}), сейф остаётся открытым. Требуется проверка.")
    # cashier works at the desk while the safe stays open and nobody uses it
    busy = tl.sig["cashier_taking_from_safe"] | tl.sig["cashier_putting_into_safe"] | tl.sig["cashier_safe_op"]
    # open safe left behind: nobody at the safe (the cashier works elsewhere) for >= 3 s
    away = tl.sig["cashier_in_room"] & ~tl.sig["cashier_near_safe"]
    cond = tl.sig["safe_open"] & away & ~busy
    runs = [(i, j) for i, j in _runs(cond) if j - i + 1 >= 9]
    idx = np.arange(runs[0][0], runs[0][1] + 1) if runs else np.array([], int)
    if len(idx):
        t = float(tl.t[idx[0]])
        conf = float(tl.sig["p_safe_open"][idx].mean())
        yield Finding("V-OPEN", t, (0.5 + 0.5 * min(1.0, len(idx) / 30)) * conf, [t, float(tl.t[idx[min(len(idx) - 1, 6)]])],
                      f"С {_ts(t)} кассир работает за столом, при этом сейф открыт и не используется. Требуется проверка.")


@rule("V-KEY", "A")
def key_left_in_safe(tl):
    for t in _leaves(tl):
        if _any(tl, "key_in_lock", t - 1, t + 1):
            yield Finding("V-KEY", t, 0.8, [t - 1, t], f"Кассир покидает помещение ({_ts(t)}), ключ остаётся в замке сейфа. Требуется проверка.")


@rule("V-STAMP", "A")
def stamp_left_on_desk(tl):
    for t in _leaves(tl):
        if _any(tl, "stamp_on_desk", t - 1.5, t):
            yield Finding("V-STAMP", t, 0.7, [t - 1, t], f"Кассир покидает помещение ({_ts(t)}), печать/штамп остаются на столе. Требуется проверка.")


@rule("V-PC", "A")
def laptop_left_on(tl):
    for t in _leaves(tl):
        if _any(tl, "laptop_on", t - 1, t + 1):
            yield Finding("V-PC", t, 0.6 * _conf(tl, "p_laptop_on", t - 1, t + 1), [t - 1, t], f"Кассир покидает помещение ({_ts(t)}), ноутбук остаётся включённым с открытым экраном. "
                          "Прямого запрета в открытых нормативах НБРК нет; рекомендуется проверка по требованиям ИБ.")


DOOR_OPEN_MIN = 18   # frames (6 s): someone walking through keeps the door open ~3-5 s, that is normal


def _runs(mask):
    i, out = 0, []
    while i < len(mask):
        if mask[i]:
            j = i
            while j + 1 < len(mask) and mask[j + 1]:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


@rule("V-DOOR", "A/B")
def door_open(tl):
    # left open behind the cashier until the end of the video
    for t in _leaves(tl):
        if tl.window("door_open", t, tl.t[-1]).all() and tl.t[-1] - t >= 3:
            yield Finding("V-DOOR", t, 0.7, [t, t + 2], f"Кассир покидает помещение ({_ts(t)}), дверь кассы остаётся открытой. Требуется проверка.")
    # door stays open while the cashier is inside (not just someone walking through)
    for i, j in _runs(tl.sig["door_open"] & tl.sig["cashier_in_room"]):
        if j - i + 1 >= DOOR_OPEN_MIN:
            t = float(tl.t[i])
            conf = float(tl.sig["p_door_open"][i:j + 1].mean())
            yield Finding("V-DOOR", t, (0.6 + 0.3 * min(1.0, (j - i + 1) / 45)) * conf, [t, float(tl.t[min(j, i + 6)])],
                          f"С {_ts(t)} дверь кассы остаётся открытой, пока кассир находится в помещении. Требуется проверка.")
    # someone comes in through a door that was already open before they arrived
    for e in tl.ev("client_start") + tl.ev("collector_start"):
        t = e[0]
        before = tl.window("door_open", t - 4, t - 1)
        if len(before) and before.all() and tl.at("cashier_in_room", t):
            yield Finding("V-DOOR", t, 0.9, [t], f"В {_ts(t)} в помещение кассы входит посторонний через уже открытую дверь. Требуется проверка.")


# ---------- C. personal items at the workplace ----------

@rule("V-PERS", "C")
def personal_items(tl):
    for i, j in _runs(tl.sig["cashier_putting_personal_items"]):
        t = float(tl.t[j])
        yield Finding("V-PERS", t, 0.7, [float(tl.t[i]), t], f"В {_ts(float(tl.t[i]))}–{_ts(t)} кассир кладёт на рабочий стол личные вещи "
                      "(одежда/сумка/напиток). Требуется проверка.")
    cond = (tl.sig["cup_on_desk"] | tl.sig["clothing_on_desk"]) & tl.sig["cashier_in_room"]
    idx = np.where(cond)[0]
    if len(idx) >= 6:
        seated = np.where(cond & tl.sig["cashier_at_desk"])[0]
        t = float(tl.t[seated[0]] if len(seated) else tl.t[idx[0]])
        what = "напиток/еда" if tl.window("cup_on_desk", t - 1, t + 3).any() else "личные вещи (одежда/сумка)"
        yield Finding("V-PERS", t, 0.6 + 0.4 * min(1.0, len(idx) / 30), [t], f"С {_ts(t)} на рабочем столе кассира находятся {what}. Требуется проверка.")


# ---------- D. client sessions ----------

def _session_mask(tl, s):
    m = np.zeros(len(tl.t), bool)
    m[s["i0"]:s["i1"] + 1] = True
    return m


@rule("V-ID", "D")
def no_id_before_cash(tl):
    for s in tl.sessions:
        m = _session_mask(tl, s)
        takes = np.where(m & (tl.sig["cashier_handover_take"] | tl.sig["client_handover_give"]))[0]
        if not len(takes):
            continue
        i = takes[0]
        id_seen = (tl.sig["any_showing_id"] | tl.sig["any_checking_id"] | tl.sig["any_id"] | tl.sig["doc_present"])[s["i0"]:i + 1].any()
        if not id_seen:
            t = float(tl.t[i])
            pkg = tl.sig["package_present"][i]
            yield Finding("V-ID", t, 0.75, [t], f"В {_ts(t)} кассир принимает {'пакет' if pkg else 'наличные'} от клиента; "
                          "предъявление документа до этого момента не видно. Требуется проверка вида операции и процедуры.")


@rule("V-NOCL", "D")
def client_left_during_count(tl):
    counting = tl.sig["cashier_counting_by_hand"] | tl.sig["cashier_counting_by_machine"]
    for s in tl.sessions:
        t = s["end"]
        if counting[max(0, s["i1"] - 2):s["i1"] + 4].any() or tl.sig["client_leaving_during_count"][s["i0"]:s["i1"] + 1].any():
            yield Finding("V-NOCL", t, 0.7, [t], f"В {_ts(t)} клиент отходит от кассы, пока кассир пересчитывает его деньги. Требуется проверка.")


@rule("V-2CL", "D")
def two_clients(tl):
    counting = tl.sig["cashier_counting_by_hand"] | tl.sig["cashier_counting_by_machine"]
    idx = np.where(tl.sig["two_clients"])[0]
    if len(idx):
        busy = np.where(tl.sig["two_clients"] & counting)[0]
        i = busy[0] if len(busy) else idx[0]
        t = float(tl.t[i])
        yield Finding("V-2CL", t, 0.8 if len(busy) else 0.45, [t],
                      f"В {_ts(t)} в помещении находятся два клиента{', пока кассир пересчитывает деньги' if len(busy) else ''}. Требуется проверка.")


@rule("V-SAFE", "D")
def previous_cash_on_desk(tl):
    for k, s in enumerate(tl.sessions[1:], 1):
        t = s["start"]
        seen = _any(tl, "cash_on_desk", t - 1, t + 1)
        in_play = _any(tl, "money_in_play", t - 1, t)    # previous client's money never went to the safe
        if seen or in_play:
            yield Finding("V-SAFE", t, 0.85 if seen and in_play else 0.7, [t], f"В {_ts(t)} подходит следующий клиент, а наличные предыдущего клиента "
                          "не убраны в сейф и остаются на рабочем месте. Требуется проверка.")


@rule("V-MIX", "D")
def cash_merged(tl):
    for t, _, _ in tl.ev("money_in_on_top"):
        if any(s["start"] <= t <= s["end"] for s in tl.sessions[1:]):
            yield Finding("V-MIX", t, 0.7, [t], f"В {_ts(t)} кассир принимает наличные следующего клиента, пока деньги предыдущего клиента "
                          "не убраны в сейф. Возможное смешивание наличных разных клиентов — требуется проверка.")
    n = tl.sig["n_cash_on_desk"]
    for s in tl.sessions[1:]:
        seg = n[s["i0"]:s["i1"] + 1]
        drops = np.where((seg[:-1] >= 2) & (seg[1:] == 1))[0]
        if _any(tl, "cash_on_desk", s["start"] - 1, s["start"] + 1) and len(drops):
            t = float(tl.t[s["i0"] + drops[0] + 1])
            yield Finding("V-MIX", t, 0.6, [t], f"В {_ts(t)} наличные текущего клиента складываются с наличными предыдущего клиента. Требуется проверка.")


@rule("V-FAKE", "D")
def rejected_notes_not_checked(tl):
    """Machine count, then the cashier sorts notes by hand (rejected ones) without checking them on the scanner."""
    for i, j in _runs(tl.sig["cashier_counting_by_machine"]):
        nxt = slice(j + 1, min(len(tl.t), j + 1 + 15))
        if not tl.sig["cashier_counting_by_hand"][nxt].any():
            continue
        if tl.sig["cashier_using_scanner"][j:min(len(tl.t), j + 45)].any() or tl.sig["has_clients"][i:j + 15].any():
            continue
        aside = tl.sig["n_cash_on_desk"][j:min(len(tl.t), j + 30)].max(initial=0) >= 2
        t = float(tl.t[j])
        yield Finding("V-FAKE", t, 0.55 + 0.3 * aside, [t], f"После пересчёта на машинке ({_ts(t)}) кассир перебирает банкноты вручную, "
                      f"проверка сомнительных банкнот на детекторе не видна{', часть банкнот отложена отдельно' if aside else ''}. Требуется проверка.")


@rule("V-COUNT", "D")
def opened_package_not_counted(tl):
    opened = tl.sig["cashier_opening_package"] | tl.sig["package_opened"]
    o = np.where(opened)[0]
    if not len(o):
        return
    to_safe = np.where((tl.sig["cashier_putting_into_safe"] | tl.sig["cashier_safe_op"]) & (np.arange(len(tl.t)) > o[0]))[0]
    if not len(to_safe):
        return
    counted = (tl.sig["cashier_counting_by_hand"] | tl.sig["cashier_counting_by_machine"])[o[0]:to_safe[0]].any()
    if not counted:
        t = float(tl.t[to_safe[0]])
        yield Finding("V-COUNT", t, 0.75, [float(tl.t[o[0]]), t], f"Упаковка вскрыта в {_ts(float(tl.t[o[0]]))}, в {_ts(t)} деньги убираются в сейф без видимого пересчёта. Требуется проверка.")


@rule("V-THEFT", "D")
def cash_kept_by_cashier(tl):
    """Part of a payout stays with the cashier: a stack goes to the client while another stack
    (split from it or held at the same time) stays in the cashier's hand and disappears without
    going to the desk, the safe or the machine."""
    by_id = {tr.id: tr for tr in tl.cash}
    to_client = [tr for tr in tl.cash if tr.end == "client" or "client_hand" in tr.holders()]
    seen = set()
    for a in to_client:
        t_hand = next(o[1] for o in a.obs if o[3] == "client_hand") if "client_hand" in a.holders() else a.t1
        for b in tl.cash:
            if b.id == a.id or b.id in seen or b.end != "cashier":
                continue
            related = b.parent == a.id or a.parent == b.id or (a.parent is not None and a.parent == b.parent)
            overlaps = b.t0 <= t_hand + 3 and b.t1 >= t_hand - 3 and "cashier_hand" in b.holders()
            if not (related or overlaps):
                continue
            seen.add(b.id)
            t = b.t1
            split_t = b.t0 if related else t_hand
            yield Finding("V-THEFT", t, 0.85 if related else 0.6, [split_t, t_hand, t],
                          f"В {_ts(t_hand)} кассир передаёт клиенту часть наличных; другая часть "
                          f"{'отделена от той же пачки и ' if related else ''}остаётся у кассира и в {_ts(t)} пропадает из вида, "
                          "не попав на стол, в сейф или в счётную машину. Возможная неполная выдача — требуется проверка.")
    # weaker fallback when cash itself is not tracked: the cashier gives but the client is never seen taking
    if not tl.cash:
        give, took = tl.sig["cashier_handover_give"], tl.sig["client_handover_take"]
        for s in tl.sessions:
            m = _session_mask(tl, s)
            g = np.where(m & give)[0]
            if len(g) and not (m & took).any():
                t = float(tl.t[g[0]])
                yield Finding("V-THEFT", t, 0.35, [t], f"В {_ts(t)} при выдаче наличных получение всей суммы клиентом не видно. Требуется проверка.")


# ---------- E. catalogue rules without training examples ----------

@rule("N-42", "E", name="Пересчёт/упаковка без контролирующего работника", rule_ids=["231-42"], trained=False)
def counting_alone(tl):
    counting = tl.sig["cashier_counting_by_hand"] | tl.sig["cashier_counting_by_machine"]
    alone = counting & ~tl.sig["has_clients"] & ~tl.sig["has_collectors"] & ~tl.sig["has_colleagues"]
    idx = np.where(alone)[0]
    if len(idx) >= 9:
        t = float(tl.t[idx[0]])
        yield Finding("N-42", t, 0.5, [t], f"С {_ts(t)} кассир пересчитывает/упаковывает наличные в отсутствие клиента и второго работника. Требуется проверка.")


@rule("N-98", "E", name="Бригада инкассаторов менее 3 человек", rule_ids=["231-98"], trained=False)
def small_collector_team(tl):
    n = tl.sig["n_collectors"]
    if n.max(initial=0) in (1, 2) and tl.sig["has_collectors"].sum() >= 6:
        t = float(tl.t[np.where(n > 0)[0][0]])
        yield Finding("N-98", t, 0.5, [t], f"В {_ts(t)} в помещении видны {int(n.max())} инкассатор(а); бригада должна быть не менее 3 человек. Требуется проверка.")


@rule("N-24", "E", name="Приём сумки от инкассатора без проверки", rule_ids=["231-24", "231-107"], trained=False)
def bag_without_check(tl):
    give = tl.sig["collector_handover_give"] & tl.sig["package_present"]
    g = np.where(give)[0]
    if len(g):
        i = g[0]
        checked = (tl.sig["any_checking_id"] | tl.sig["doc_present"])[max(0, i - 30):i + 30].any()
        if not checked:
            t = float(tl.t[i])
            yield Finding("N-24", t, 0.5, [t], f"В {_ts(t)} кассир принимает сумку от инкассатора; проверка сопроводительного документа и пломбы не видна. Требуется проверка.")


# ---------- F. generic suspicious situation ----------

@rule("S-UNK", "F", name="Необычная ситуация — требуется проверка", rule_ids=["231-20", "231-75"], trained=False)
def unknown_person(tl):
    cond = tl.sig["has_unknown_inside"] & (tl.sig["cash_on_desk"] | tl.sig["safe_open"])
    idx = np.where(cond)[0]
    if len(idx) >= 6:
        t = float(tl.t[idx[0]])
        yield Finding("S-UNK", t, 0.35, [t], f"В {_ts(t)} в помещении кассы находится посторонний при открытом сейфе или наличных на столе. Требуется проверка.")
