"""Chơi vòng ngày trên trình duyệt bằng DaySim THẬT: Gather -> Quán -> Shop, 1–5 Ngày.

    python3 -m chonoi.live --mode day [--days 3] [--seed 1]

Dùng cùng `runner.Session("day")` như headless. Các màn giới thiệu (day_intro, evening_intro, day_result)
chỉ là màn của giao diện: lúc đó không bước tick nào, nên không đổi kết quả mô phỏng.
Giao thức HTTP giống bản preview Phase 2 mà `chonoi/web/index.html` đã hỗ trợ:
    GET /state, POST /input {move, interact, catch}, POST /action {action, upgrade_id}.
"""

import json
import sys
import threading
import time
import traceback

from .inputs import BUTTONS_V11, InputState, LiveInputs
from .inventory import items_to_counts
from .runner import Session

TICK_S = 1.0 / 60.0
RECENT_EVENTS = 40
PLAY_SCREENS = ("gather", "quan", "shop")
LABELS = {"oxygen": "Bình oxy", "hp": "Máu"}


class LiveDayGame:
    mode = "day"

    def __init__(self, tuning, scenario, seed, days):
        self.tuning = tuning
        self._args = (tuning, scenario, seed, days)
        self.days = days
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._reset()

    # --- trạng thái -----------------------------------------------------------------
    def _reset(self):
        self.screen = "menu"
        self.session = None
        self.paused = False
        self.error = None
        self.events = []
        self.results = []
        self.message = ""
        self.inputs = LiveInputs(BUTTONS_V11)
        self._pending_buy = None
        self._pending_done = False

    def _new_run(self):
        tuning, scenario, seed, days = self._args
        self._reset()
        self.session = Session("day", tuning, scenario, seed, days=days)
        self.events = self.session.start_events()
        self._new_day()

    def _new_day(self):
        self.screen = "day_intro"
        self.stats = {"served": 0, "left": 0, "tips": 0}
        self.gather_reason = None
        self.evening_stock = []
        self.message = ""

    # --- luồng nền ------------------------------------------------------------------
    def start(self):
        self._thread = threading.Thread(target=self._loop, name="chonoi-day", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self):
        nxt = time.perf_counter()
        while not self._stop.is_set():
            nxt += TICK_S
            with self._lock:
                try:
                    self._tick_once()
                except Exception:
                    self.error = traceback.format_exc()
                    sys.stderr.write(self.error)
                    self.screen = "summary"
            delay = nxt - time.perf_counter()
            if delay > 0:
                self._stop.wait(delay)
            elif delay < -0.25:
                nxt = time.perf_counter()

    def _tick_once(self):
        s = self.session
        if s is None or s.done or self.paused or self.screen not in PLAY_SCREENS or self.error:
            return
        base = self.inputs.advance()
        edges = set(base._edges)
        if self._pending_done:
            edges.add("shop_done")
            self._pending_done = False
        inp = InputState(base.move, base.held, edges, buy=self._pending_buy)
        self._pending_buy = None
        phase_before = s.sim.phase
        rows = s.step(inp)
        self.events.extend(rows)
        del self.events[:-RECENT_EVENTS]
        for row in rows:
            self._observe(row)
        if s.done:
            self.screen = "summary"
        elif s.phase_changed:
            self.inputs = LiveInputs(BUTTONS_V11)
            if phase_before == "gather":
                self.evening_stock = s.sim.current.inventory_items()
                self.screen = "evening_intro"
            elif phase_before == "quan":
                self.screen = "day_result"
            else:
                self._new_day()

    def _observe(self, row):
        name, data = row["name"], row["data"]
        if name == "gather_end":
            self.gather_reason = data["reason"]
        elif name == "served":
            self.stats["served"] += 1
        elif name in ("customer_left", "reservation_failed"):
            self.stats["left"] += 1
        elif name == "paid":
            self.stats["tips"] += data["tip"]
        elif name == "quan_end":
            self.results.append({**self.stats, "earned": data["shift_earned"], "money": data["money"],
                                 "reputation": data["reputation"]})
        elif name == "bought":
            self.message = f"Đã mua {LABELS.get(data['upgrade'], data['upgrade'])} cấp {data['level']}. Có hiệu lực từ Ngày sau."
        elif name == "buy_failed":
            why = {"funds": "chưa đủ tiền", "max_level": "đã đạt cấp tối đa"}.get(data["reason"], data["reason"])
            self.message = f"Không mua được: {why}."

    # --- API cho handler ------------------------------------------------------------
    def action(self, body) -> bool:
        act = body.get("action")
        with self._lock:
            if act == "start" and self.screen == "menu":
                self._new_run()
            elif act == "menu":
                self._reset()
            elif act == "pause" and self.screen in PLAY_SCREENS and not self.paused:
                self.paused = True
                self.inputs = LiveInputs(BUTTONS_V11)
            elif act == "resume" and self.paused:
                self.paused = False
            elif act == "continue" and self.screen in ("day_intro", "evening_intro", "day_result"):
                self.screen = {"day_intro": "gather", "evening_intro": "quan", "day_result": "shop"}[self.screen]
            elif act == "buy" and self.screen == "shop" and not self.paused and isinstance(body.get("upgrade_id"), str):
                self._pending_buy = body["upgrade_id"]
            elif act == "shop_done" and self.screen == "shop" and not self.paused:
                self._pending_done = True
            else:
                return False
            return True

    def set_input(self, body: dict):
        move = body.get("move")
        if move is not None and not (isinstance(move, list) and len(move) == 2 and all(
                isinstance(c, (int, float)) and not isinstance(c, bool) and abs(c) <= 1 for c in move)):
            raise ValueError("move phải là [a, b] trong [-1, 1]")
        buttons = {}
        for b in ("interact", "catch"):
            if b in body:
                if not isinstance(body[b], bool):
                    raise ValueError(f"{b} phải là boolean")
                buttons[b] = body[b]
        with self._lock:
            if self.screen in ("gather", "quan") and not self.paused:
                self.inputs.set(move, **buttons)

    def restart(self):
        with self._lock:
            self._reset()

    def state_json(self) -> bytes:
        with self._lock:
            return json.dumps(self._state(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def _state(self):
        state = {"mode": "day", "screen": self.screen, "days": self.days, "live_day": True,
                 "paused": self.paused, "can_pause": self.screen in PLAY_SCREENS,
                 "tick_hz": self.tuning["tick_hz"], "events": list(self.events), "error": self.error}
        s = self.session
        if s is None:
            state["day"] = 1
            return state
        sim = s.sim
        state["day"] = sim.day
        threshold = self.tuning["inventory"]["spoil_threshold"]
        if self.screen in ("gather", "quan"):
            snap = s.snapshot()
            snap["meta"] = {**self.tuning[self.screen], "spoil_threshold": threshold}
            snap["finished"] = False
            state["snapshot"] = snap
        elif self.screen == "day_intro":
            state["menu"] = [{"dish_id": d, "servings": n} for d, n in sim.plan["dishes"].items()]
            state["needed"] = dict(sim.plan["ingredients"])
            if getattr(sim, "reservations", None) is not None:
                state["reservations"] = [dict(r) for r in sim.reservations]
        elif self.screen == "evening_intro":
            available = items_to_counts([i for i in self.evening_stock if i["fresh"] >= threshold])
            state.update(inventory=self.evening_stock, spoil_threshold=threshold, gather_reason=self.gather_reason,
                         cookable=[d for d in sim.plan["dishes"] if all(
                             available.get(k, 0) >= v for k, v in self.tuning["menu"][d]["recipe"].items())])
        elif self.screen == "day_result" and self.results:
            state["result"] = self.results[-1]
        elif self.screen == "summary" and self.results:
            total = dict(self.results[-1])
            for key in ("served", "left", "earned", "tips"):
                total[key] = sum(r[key] for r in self.results)
            state["result"] = total
        elif self.screen == "shop":
            state["shop"] = {"money": sim.money, "time_left_ticks": sim.shop_ticks,
                             "upgrades": {k: sim.upgrades.get(k, 0) for k in self.tuning["shop"]["upgrades"]},
                             "options": self._shop_options(sim), "message": self.message}
        return state

    def _shop_options(self, sim):
        options = []
        for kind, levels in self.tuning["shop"]["upgrades"].items():
            have = sim.upgrades.get(kind, 0)
            if have < len(levels):
                nxt = levels[have]
                options.append({"id": kind, "label": LABELS.get(kind, kind), "level": nxt["level"],
                                "price": nxt["price"], "enabled": sim.money >= nxt["price"]})
            else:
                options.append({"id": kind, "label": LABELS.get(kind, kind) + " (tối đa)", "level": have,
                                "price": levels[-1]["price"], "enabled": False})
        return options
