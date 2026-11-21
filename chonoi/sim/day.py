"""Compose gather, quan and the Shop without resetting the outer clock."""

from .gather import GatherSim
from .quan import QuanSim
from .reservations import announce_events, make_reservations, public
from ..day_config import day_plans, gather_tuning
from ..extensions import enabled
from ..ids import IdRegistry
from ..inventory import clone_items
from ..rng import Streams


class DaySim:
    mode = "day"
    # Extension đặt trước. Lớp con tự viết _start_day (vd. InteractiveDaySim) không tạo đơn -> coi như tắt.
    reservations = None

    def __init__(self, tuning, scenario, seed, days):
        self.tuning = tuning
        self.gather_scenario = scenario.get("gather", {})
        self.quan_scenario = scenario.get("quan", {})
        self.streams = Streams(seed)
        self.ids = IdRegistry()
        initial = scenario.get("day", {})
        self.plans = day_plans(tuning, initial.get("day_plan", ()))
        self.money = initial.get("money", 0)
        self.earned = initial.get("earned", 0)
        self.reputation = initial.get("reputation", tuning["quan"]["reputation_initial"])
        self.upgrades = initial.get("upgrades", {}).copy()
        self.days = days
        self.day = 1
        self.days_completed = 0
        self.done = False
        self.reason = None
        self._start_day()

    def _start_day(self):
        self.active_upgrades = self.upgrades.copy()
        self.plan = self.plans[self.day]
        self.phase = "gather"
        effective = gather_tuning(self.tuning, self.active_upgrades)
        gather_scenario = self.gather_scenario if self.day == 1 else {
            key: value for key, value in self.gather_scenario.items() if key != "hold"}
        self.current = GatherSim(effective, gather_scenario, self.streams, self.ids,
                                 day=self.day, active_upgrades=self.active_upgrades)
        self.current.reputation = self.reputation
        # extension đặt trước: công bố R1, R2 của Ngày ngay sau phase_start(gather)
        self.reservations = (make_reservations(self.tuning, self.streams.get("reservations"),
                                               self.plan["dishes"], self.quan_scenario)
                             if enabled(self.tuning, "reservations") else None)

    def _start_quan(self, stock):
        menu = {dish: self.tuning["menu"][dish] for dish in self.plan["dishes"]}
        tuning = {**self.tuning, "menu": menu}
        scenario = {**self.quan_scenario, "reputation": self.reputation}
        self.current = QuanSim(tuning, scenario, self.streams, self.ids, inventory=clone_items(stock),
                               reservations=self.reservations)
        self.current.money = self.money
        self.current.earned = self.earned
        self.phase = "quan"

    def _start_shop(self):
        self.shop_stock = self.current.inventory_items()
        self.current = None
        self.shop_ticks = self.tuning["shop"]["max_ticks"]
        self.phase = "shop"

    @property
    def time_left_ticks(self):
        return self.shop_ticks if self.phase == "shop" else self.current.time_left_ticks

    def snapshot(self):
        state = {"stock": clone_items(self.shop_stock)} if self.phase == "shop" else self.current.snapshot()
        if self.phase == "gather":
            state["hold"] = self.current.inventory_items()
            if self.reservations is not None:
                state["reservations"] = public(self.reservations)
        elif self.phase == "quan":
            state["stock"] = self.current.inventory_items()
        return {**state, "day": self.day, "day_plan": self.plan,
                "upgrades": self.upgrades.copy(), "active_upgrades": self.active_upgrades.copy()}

    def start_events(self):
        events = [("day_start", {}), ("day_plan", {k: self.plan[k] for k in ("dishes", "ingredients")}),
                  ("phase_start", {})]
        return events + announce_events(self.reservations) if self.reservations is not None else events

    def step(self, inp):
        """Return events from the phase that owns this gameplay step."""
        if self.phase == "shop":
            return self._step_shop(inp)
        events = self.current.step(inp)
        self.reputation = self.current.reputation
        if self.phase == "quan":
            self.money = self.current.money
            self.earned = self.current.earned
        return events

    def advance_phase(self, events):
        """Transition after the old phase's events have been stamped."""
        if self.phase == "gather" and self.current.done:
            _, end = events[-1]
            self._start_quan(end["inventory"]["items"])
            return [("phase_start", {})]
        if self.phase == "quan" and self.current.done:
            self._start_shop()
            return [("phase_start", {})]
        if self.phase == "shop" and events and events[-1][0] == "shop_end":
            self.days_completed += 1
            self.shop_stock = []
            if self.days_completed == self.days:
                self.done, self.reason = True, "days_complete"
            else:
                self.day += 1
                self._start_day()
                return self.start_events()
        return []

    def _step_shop(self, inp):
        events = []
        if inp.buy is not None:
            events.append(self._buy(inp.buy))
        self.shop_ticks -= 1
        if inp.pressed("shop_done"):
            events.append(("shop_end", {"reason": "done"}))
        elif self.shop_ticks == 0:
            events.append(("shop_end", {"reason": "time"}))
        return events

    def _buy(self, action):
        levels = self.tuning["shop"]["upgrades"].get(action)
        current_level = self.upgrades.get(action, 0)
        if levels is None:
            reason = "unknown"
        elif current_level >= len(levels):
            reason = "max_level"
        else:
            target = levels[current_level]
            price = target["price"]
            if self.money >= price:
                self.money -= price
                self.upgrades[action] = target["level"]
                return ("bought", {"upgrade": action, "level": target["level"], "price": price,
                                   "money": self.money})
            reason = "funds"
        return ("buy_failed", {"action": action, "reason": reason})
