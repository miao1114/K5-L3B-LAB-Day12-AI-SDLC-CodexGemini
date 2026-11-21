"""Web screen adapter over the existing DaySim/Session, including the real Shop."""
from copy import deepcopy
from time import monotonic

from .inputs import BUTTONS_V11, InputState, LiveInputs
from .interactive import InteractiveSession
from .inventory import items_to_counts
from .sim.reservations import public


BUTTONS_WEB = (*BUTTONS_V11, "sprint")  # sprint: giữ Shift để chạy nhanh (chỉ bản web)


class InteractiveDayWeb:
    live_scenes = True

    def __init__(self, days, faint, *, tuning, scenario=None, config, seed=1):
        self.days, self.faint = days, faint
        self.tuning, self.scenario, self.config, self.seed = tuning, deepcopy(scenario or {}), config, seed
        self.screen, self.paused, self.session = "menu", False, None
        self.events, self.message = [], ""
        self._reset_clock()

    def _reset_clock(self):
        self.started, self.elapsed, self.scene_ticks = monotonic(), 0, 0
        self.inputs = LiveInputs(BUTTONS_WEB)

    def _screen(self, screen):
        self.screen, self.paused = screen, False
        self._reset_clock()

    def _step(self, inp):
        old_phase = self.session.sim.phase
        rows = self.session.step(inp)
        self.events.extend(rows)
        self.events = self.events[-200:]
        self.scene_ticks += 1
        if self.session.done:
            self._screen("summary")
        elif self.session.phase_changed:
            self._screen({"gather": "evening_intro", "quan": "day_result", "shop": "day_intro"}[old_phase])
        return rows

    def update_scene(self):
        if self.paused or self.screen not in ("gather", "quan", "shop"):
            return
        target = int((self.elapsed + monotonic() - self.started) * self.tuning["tick_hz"])
        while self.scene_ticks < target:
            screen = self.screen
            self._step(self.inputs.advance())
            if self.screen != screen:
                break

    def expire_shop(self):
        self.update_scene()

    def keys(self, data):
        self.update_scene()
        move = data.get("move")
        if move is not None and not (isinstance(move, list) and len(move) == 2
                and all(type(v) in (int, float) and -1 <= v <= 1 for v in move)):
            return False
        buttons = {k: data[k] for k in ("interact", "catch", "sprint") if k in data}
        if any(type(v) is not bool for v in buttons.values()):
            return False
        if not self.paused and self.screen in ("gather", "quan"):
            self.inputs.set(move, **buttons)
        return True

    def action(self, action, data):
        self.update_scene()
        if action == "menu":
            self._screen("menu")
        elif action == "start" and self.screen == "menu":
            scenario = deepcopy(self.scenario)
            if self.faint:
                scenario.setdefault("gather", {})["player"] = {
                    "pos": [50, 10], "hp": 1, "oxygen_ticks": 0, "zero_oxy_ticks": 59}
            self.session = InteractiveSession(self.tuning, scenario, self.seed, self.days, self.config)
            self.events = self.session.start_events()
            self._screen("day_intro")
        elif action == "continue" and self.screen in ("day_intro", "evening_intro", "day_result"):
            self._screen({"day_intro": "gather", "evening_intro": "quan", "day_result": "shop"}[self.screen])
        elif action == "pause" and not self.paused and self.screen in ("gather", "quan", "shop"):
            self.elapsed += monotonic() - self.started
            self.inputs = LiveInputs(BUTTONS_WEB)
            self.paused = True
        elif action == "resume" and self.paused:
            self.started, self.paused = monotonic(), False
        elif action in ("buy", "shop_done") and self.screen == "shop" and not self.paused:
            upgrade = data.get("upgrade_id")
            if action == "buy" and (not isinstance(upgrade, str) or not upgrade):
                return False
            rows = self._step(InputState((0, 0), {}, {"shop_done"} if action == "shop_done" else set(),
                                         buy=upgrade if action == "buy" else None))
            self.message = next(("Đã mua nâng cấp, áp dụng ngày kế tiếp." if r["name"] == "bought"
                                 else "Chưa thể mua nâng cấp này."
                                 for r in rows if r["name"] in ("bought", "buy_failed")), "")
        else:
            return False
        return True

    def snapshot(self):
        self.update_scene()
        sim = self.session.sim if self.session else None
        day = sim.day if sim else 1
        state = dict(mode="day", screen=self.screen, day=day, days=self.days, live_scenes=True,
                     enhanced=True, sprint=self.config.get("sprint_multiplier", 1) > 1, paused=self.paused, tick_hz=self.tuning["tick_hz"],
                     can_pause=self.screen in ("gather", "quan", "shop"), events=list(self.events))
        if sim is None:
            return state
        plan = sim.plan
        threshold = self.tuning["inventory"]["spoil_threshold"]
        state.update(day_plan=deepcopy(plan), needed=plan["ingredients"],
                     unlocked_menu=[{"dish_id": d} for d in sim.unlocked_dishes],
                     newly_unlocked=list(sim.newly_unlocked) if day > 1 else [],
                     menu=[{"dish_id": d, "servings": n} for d, n in plan["dishes"].items()])
        if sim.reservations is not None:
            state["reservations"] = public(sim.reservations)
        if self.screen in ("gather", "quan"):
            snap = self.session.snapshot()
            meta = sim.current.t
            if self.screen == "quan" and sim.reservations is not None:
                meta = {**meta, "reservations": sim.tuning["reservations"]}
            state["snapshot"] = {**snap, "mode": self.screen,
                                 "meta": {**meta, "spoil_threshold": threshold}}
        elif self.screen == "evening_intro":
            available = items_to_counts([i for i in sim.gather_inventory if i["fresh"] >= threshold])
            state.update(inventory=sim.gather_inventory, spoil_threshold=threshold,
                         gather_reason=sim.gather_reason, cookable=[d for d in sim.unlocked_dishes
                         if all(available.get(k, 0) >= n for k, n in self.tuning["menu"][d]["recipe"].items())])
        elif self.screen in ("day_result", "summary"):
            state["result"] = deepcopy(sim.results[-1]) if self.screen == "day_result" else sim.summary()
        elif self.screen == "shop":
            options = []
            for kind, levels in self.tuning["shop"]["upgrades"].items():
                level = sim.upgrades.get(kind, 0)
                if level < len(levels):
                    target = levels[level]
                    options.append({"id": kind, "label": {"oxygen": "Bình oxy", "hp": "Máu"}.get(kind, kind),
                                    "level": target["level"], "price": target["price"],
                                    "enabled": sim.money >= target["price"]})
            state["shop"] = dict(money=sim.money, upgrades=sim.upgrades,
                                 time_left_ticks=sim.shop_ticks, options=options, message=self.message)
        return state
