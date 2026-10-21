"""Mô phỏng giao thông và điều khiển đèn cho video demo (Python thuần, tất định theo seed). Đơn vị mm, giây.

Xe đi thẳng trên 6 làn của hành lang J1–J2 (đường Đông–Tây xuyên qua cả hai ngã tư, hai đường Bắc–Nam).
Video minh họa luồng hệ thống theo 2 giai đoạn:
  1. Trước t = T_ON: đèn chạy chu kỳ cố định (chưa có AI), xe xếp hàng tự nhiên ở vạch dừng.
  2. Từ t = T_ON: "EdgeFlow AI kích hoạt". Mỗi nút chọn pha theo số xe trong ROI (quy tắc kiểu max-pressure đơn
     giản, tôn trọng xanh tối thiểu/tối đa, vàng và all-red do thiết bị quyết).
Đây là MÔ PHỎNG MINH HỌA luồng hệ thống: số xe lấy thẳng từ mô phỏng (không phải kết quả YOLO), quy tắc chọn pha là
bản rút gọn, không phải log của graph-control thật. Video là "vòng hở" với đèn LED thật trên sa bàn.

Đầu ra: JSON gồm quỹ đạo từng xe, số xe thật trong từng ROI theo khung, trạng thái đèn và số giây theo khung
(cho lớp chú thích), sự kiện hệ thống, và kết quả kiểm xe không đè nhau.

  python3 video_mo_phong.py --seconds 150 --fps 10 --seed 1 --out ../video_demo/kich_ban_train.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bo_tri as L  # noqa: E402

CAR_L, CAR_W = L.CAR_L, L.CAR_W
V0 = 170.0                     # tốc độ mong muốn, mm/s (~ 40 km/h ở tỉ lệ 1:64)
A_MAX, B_COMF = 110.0, 160.0   # gia tốc, giảm tốc êm, mm/s²
HEADWAY, MIN_GAP = 0.7, 14.0   # s, mm
STOP_P = 202.0                 # từ mép bạt tới vạch dừng (= 300 − 98)

# Thời gian an toàn do thiết bị quyết (CLAUDE.md): vàng 3 s, all-red 2 s, xanh tối thiểu 5 s, tối đa 60 s
YELLOW, ALL_RED, MIN_GREEN, MAX_GREEN = 3.0, 2.0, 5.0, 60.0
FIXED_GREEN = 20.0             # xanh của chế độ chu kỳ cố định
T_ON = 40.0                    # giây: hệ thống kích hoạt
WARMUP = 70.0                  # chạy trước để t = 0 đã có hàng đợi
SWITCH_MARGIN = 1              # đổi pha khi hàng đợi hướng kia nhiều hơn hướng đang xanh ít nhất chừng này xe


@dataclass(frozen=True)
class Lane:
    name: str
    node_axes: tuple          # ((p của vạch dừng, nút, trục) ...), trục "NS" hoặc "EW"
    length: float
    base_rate: float          # xe/phút
    phase: float              # pha của sóng nhu cầu, rad
    heading: float


def _lanes() -> list[Lane]:
    return [
        Lane("EB", ((STOP_P, "J1", "EW"), (600.0 + STOP_P, "J2", "EW")), 1200.0, 14.0, 0.0, 0.0),
        Lane("WB", ((STOP_P, "J2", "EW"), (600.0 + STOP_P, "J1", "EW")), 1200.0, 10.0, 1.6, 180.0),
        Lane("J1_SB", ((STOP_P, "J1", "NS"),), 600.0, 6.0, 3.0, -90.0),
        Lane("J1_NB", ((STOP_P, "J1", "NS"),), 600.0, 4.0, 4.4, 90.0),
        Lane("J2_SB", ((STOP_P, "J2", "NS"),), 600.0, 5.0, 0.7, -90.0),
        Lane("J2_NB", ((STOP_P, "J2", "NS"),), 600.0, 7.0, 5.2, 90.0),
    ]


def lane_xy(lane: Lane, p: float) -> tuple[float, float]:
    """Tâm xe khi đầu xe ở p (mm dọc làn tính từ mép bạt)."""
    c = p - CAR_L / 2
    j1, j2 = L.JUNCTIONS["J1"][0], L.JUNCTIONS["J2"][0]
    if lane.name == "EB":
        return -600.0 + c, -L.LANE_W / 2
    if lane.name == "WB":
        return 600.0 - c, L.LANE_W / 2
    jx = j1 if lane.name.startswith("J1") else j2
    if lane.name.endswith("SB"):
        return jx - L.LANE_W / 2, 300.0 - c
    return jx + L.LANE_W / 2, -300.0 + c


def visible(p: float, length: float) -> bool:
    """Xe hiện trong video khi tâm xe nằm trên bạt (ra khỏi mép bạt thì biến mất, không lơ lửng trên bàn)."""
    return 0.0 <= p - CAR_L / 2 <= length


# ------------------------------------------------------------------ bộ điều khiển đèn của một nút
PHASES = ("NS_G", "NS_Y", "AR_EW", "EW_G", "EW_Y", "AR_NS")
AXIS_STATE = {
    "NS_G": ("G", "R"), "NS_Y": ("Y", "R"), "AR_EW": ("R", "R"),
    "EW_G": ("R", "G"), "EW_Y": ("R", "Y"), "AR_NS": ("R", "R"),
}
NEXT = {"NS_G": "NS_Y", "NS_Y": "AR_EW", "AR_EW": "EW_G", "EW_G": "EW_Y", "EW_Y": "AR_NS", "AR_NS": "NS_G"}
APPR_AXIS = {"N": "NS", "S": "NS", "E": "EW", "W": "EW"}
AXIS_VN = {"NS": "Bắc–Nam", "EW": "Đông–Tây"}


@dataclass
class Signal:
    node: str
    phase: str
    t_in: float = 0.0
    adaptive: bool = False
    pending: str = ""          # lý do chuyển pha gần nhất, để hiện trên video

    def axis_states(self) -> tuple[str, str]:
        return AXIS_STATE[self.phase]

    def state(self, axis: str) -> str:
        ns, ew = AXIS_STATE[self.phase]
        return ns if axis == "NS" else ew

    def step(self, dt: float, queues: dict[str, int], events: list, t: float) -> None:
        self.t_in += dt
        ph = self.phase
        if ph.endswith("_G"):
            own = ph[:2]
            other = "EW" if own == "NS" else "NS"
            q_own = sum(v for k, v in queues.items() if APPR_AXIS[k] == own)
            q_other = sum(v for k, v in queues.items() if APPR_AXIS[k] == other)
            if self.adaptive:
                want = (self.t_in >= MIN_GREEN and q_other >= q_own + SWITCH_MARGIN) or self.t_in >= MAX_GREEN
                if want:
                    why = (f"hàng đợi {AXIS_VN[other]} {q_other} > {AXIS_VN[own]} {q_own}"
                           if self.t_in < MAX_GREEN else "đạt xanh tối đa 60 s")
                    self.pending = why
                    events.append((t, f"{self.node}: chuyển sang {AXIS_VN[other]} ({why})"))
                    self._advance()
            elif self.t_in >= FIXED_GREEN:
                self._advance()
        elif ph.endswith("_Y") and self.t_in >= YELLOW:
            self._advance()
        elif ph.startswith("AR_") and self.t_in >= ALL_RED:
            self._advance()

    def _advance(self) -> None:
        self.phase = NEXT[self.phase]
        self.t_in = 0.0

    def countdown(self) -> tuple[float, str]:
        """(số giây hiện trên đèn, 'down' đếm ngược hoặc 'up' đếm lên). Xanh thích ứng không biết trước ngày kết thúc."""
        ph = self.phase
        if ph.endswith("_Y"):
            return max(YELLOW - self.t_in, 0.0), "down"
        if ph.startswith("AR_"):
            return max(ALL_RED - self.t_in, 0.0), "down"
        if self.adaptive:
            return self.t_in, "up"
        return max(FIXED_GREEN - self.t_in, 0.0), "down"


@dataclass
class Car:
    cid: int
    lane: Lane
    color: int
    p: float = 0.0
    v: float = V0
    rows: list = field(default_factory=list)   # (t, p)


def _accel(car: Car, leader: Car | None, sigs: dict[str, Signal]) -> float:
    gap_v = None
    if leader is not None:
        gap_v = (leader.p - CAR_L - car.p, leader.v)
    for p_stop, node, axis in car.lane.node_axes:
        d = p_stop - car.p
        if d < -2.0:
            continue
        state = sigs[node].state(axis)
        brake_dist = car.v * car.v / (2 * B_COMF)
        if state == "R" or (state == "Y" and d > brake_dist + 8.0):
            stop_gap = (max(d - 4.0, 0.1), 0.0)
            if gap_v is None or stop_gap[0] < gap_v[0]:
                gap_v = stop_gap
    free = 1.0 - (car.v / V0) ** 4
    if gap_v is None:
        return A_MAX * free
    gap, vl = gap_v
    s_star = MIN_GAP + max(0.0, car.v * HEADWAY + car.v * (car.v - vl) / (2 * math.sqrt(A_MAX * B_COMF)))
    return A_MAX * (free - (s_star / max(gap, 0.1)) ** 2)


def _rect_counts(cars: dict[str, list[Car]], rois: dict) -> dict[str, int]:
    out = dict.fromkeys(rois, 0)
    for lane_cars in cars.values():
        for c in lane_cars:
            if not visible(c.p, c.lane.length):
                continue
            x, y = lane_xy(c.lane, c.p)
            for name, rect in rois.items():
                xs, ys = [r[0] for r in rect], [r[1] for r in rect]
                if min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys):
                    out[name] += 1
    return out


def simulate(seconds: float, fps: int, seed: int) -> dict:
    rng = random.Random(seed)
    lanes = _lanes()
    dt = 1.0 / fps
    rois = {f"{n}_{a}_IN": L.roi_rect(n, a) for n in L.JUNCTIONS for a in "NSEW"}
    cars: dict[str, list[Car]] = {ln.name: [] for ln in lanes}
    done: list[Car] = []
    sigs = {"J1": Signal("J1", "NS_G"), "J2": Signal("J2", "EW_G")}
    events: list[tuple[float, str]] = []
    hud: list[dict] = []
    nid, t, on = 0, -WARMUP, False
    while t < seconds:
        if not on and t >= T_ON:
            on = True
            for s in sigs.values():
                s.adaptive = True
            events.append((t, "EdgeFlow AI kích hoạt: đèn chọn pha theo số xe trong ROI"))
        counts = _rect_counts(cars, rois)
        for node, sg in sigs.items():
            sg.step(dt, {a: counts[f"{node}_{a}_IN"] for a in "NSEW"}, events if t >= 0 else [], t)
        for ln in lanes:
            active = cars[ln.name]
            rate = ln.base_rate * (1.0 + 0.6 * math.sin(2 * math.pi * t / 90.0 + ln.phase)) / 60.0
            rear_clear = (not active) or (active[0].p - CAR_L > 40.0)
            if rear_clear and rng.random() < rate * dt:
                active.insert(0, Car(nid, ln, rng.randrange(10), p=0.0, v=V0 * 0.8))
                nid += 1
        for ln in lanes:
            active = cars[ln.name]
            for i, car in enumerate(active):          # active[0] là xe sau cùng; xe đứng trước có chỉ số i + 1
                leader = active[i + 1] if i + 1 < len(active) else None
                car.v = max(0.0, car.v + _accel(car, leader, sigs) * dt)
                car.p += car.v * dt
                if t >= 0:
                    car.rows.append((t, car.p))
            for car in [c for c in active if c.p - CAR_L > ln.length]:
                active.remove(car)
                done.append(car)
        if t >= 0:
            frame = {"on": on, "nodes": {}, "queues": counts}
            for node, sg in sigs.items():
                secs, direction = sg.countdown()
                ns, ew = sg.axis_states()
                frame["nodes"][node] = {"phase": sg.phase, "NS": ns, "EW": ew, "secs": round(secs, 1),
                                        "dir": direction}
            hud.append(frame)
        t += dt
    for ln in lanes:
        done.extend(cars[ln.name])
    return {"cars": done, "lanes": lanes, "hud": hud, "events": events, "rois": rois}


def _overlaps(tracks: list[dict], n: int) -> list[tuple[int, int, int]]:
    """Các cặp xe đè nhau (khung, id, id), so hình chữ nhật xe (đã xoay theo hướng làn) trên xe đang hiện."""
    by_frame: list[list[tuple[int, float, float, bool]]] = [[] for _ in range(n)]
    for tr in tracks:
        horizontal = tr["heading"] in (0.0, 180.0)
        for k, (x, y) in enumerate(zip(tr["x"], tr["y"])):
            f = tr["f0"] + k
            if 0 <= f < n and tr["vis"][k]:
                by_frame[f].append((tr["id"], x, y, horizontal))
    bad = []
    for f, items in enumerate(by_frame):
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                ax, ay = (CAR_L, CAR_W) if a[3] else (CAR_W, CAR_L)
                bx, by = (CAR_L, CAR_W) if b[3] else (CAR_W, CAR_L)
                if abs(a[1] - b[1]) < (ax + bx) / 2 and abs(a[2] - b[2]) < (ay + by) / 2:
                    bad.append((f, a[0], b[0]))
    return bad


def build_output(sim: dict, seconds: float, fps: int) -> dict:
    n = int(round(seconds * fps))
    tracks = []
    for car in sorted(sim["cars"], key=lambda c: c.cid):
        if not car.rows:
            continue
        f0 = int(round(car.rows[0][0] * fps))
        xs, ys = [], []
        for _, p in car.rows:
            x, y = lane_xy(car.lane, p)
            xs.append(round(x, 2))
            ys.append(round(y, 2))
        tracks.append({"id": car.cid, "lane": car.lane.name, "color": car.color, "heading": car.lane.heading,
                       "len": car.lane.length, "f0": f0, "x": xs, "y": ys,
                       "p": [round(p, 2) for _, p in car.rows],
                       "vis": [visible(p, car.lane.length) for _, p in car.rows]})
    rois = sim["rois"]
    counts = [dict.fromkeys(rois, 0) for _ in range(n)]
    for tr in tracks:
        for k, (x, y) in enumerate(zip(tr["x"], tr["y"])):
            f = tr["f0"] + k
            if not 0 <= f < n or not tr["vis"][k]:
                continue
            for name, rect in rois.items():
                xs, ys = [r[0] for r in rect], [r[1] for r in rect]
                if min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys):
                    counts[f][name] += 1
    bad = _overlaps(tracks, n)
    return {"fps": fps, "frames": n, "seconds": seconds, "t_on": T_ON,
            "signal": {"yellow": YELLOW, "all_red": ALL_RED, "min_green": MIN_GREEN, "max_green": MAX_GREEN,
                       "fixed_green": FIXED_GREEN,
                       "note": "đèn trong video là mô phỏng minh họa, không phải đèn LED thật hay log graph-control"},
            "tracks": tracks, "roi_truth": counts, "hud": sim["hud"][:n],
            "events": [{"f": int(round(t * fps)), "t": round(t, 1), "text": text}
                       for t, text in sim["events"] if 0 <= t < seconds],
            "overlap_pairs": len(bad), "overlap_frames": len({b[0] for b in bad}), "overlap_sample": bad[:5]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=150.0)
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = build_output(simulate(args.seconds, args.fps, args.seed), args.seconds, args.fps)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    peak = {k: max(c[k] for c in out["roi_truth"]) for k in out["roi_truth"][0]}
    print(f"{len(out['tracks'])} xe, {out['frames']} khung, đỉnh số xe trong ROI: {peak}")
    print(f"xe đè nhau: {out['overlap_pairs']} cặp trong {out['overlap_frames']} khung {out['overlap_sample']}")
    print(f"{len(out['events'])} sự kiện:")
    for e in out["events"][:14]:
        print(f"  t={e['t']:>6}s  {e['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
