"""Explicit web-only gameplay extensions. Standard runner never imports this module."""
from collections import Counter
from copy import deepcopy

from .day_config import gather_tuning
from .errors import BadInput
from .extensions import enabled, validate_extensions
from .interactive_menu import resource_tuning, target_slots, unlocked_menu, web_scenario
from .inventory import clone_items, items_to_counts
from .runner import Session
from .sim.day import DaySim
from .sim.gather import GatherSim
from .sim.monsters import step_monsters
from .sim.quan import QuanSim
from .sim.reservations import FINAL, make_reservations


def web_tuning(tuning, config):
    """Bật extension web (`current`, `reservations`) theo `config.extensions`; preset gốc không đổi."""
    contract = {"extensions": list(config.get("extensions", [])), "tuning": deepcopy(tuning)}
    validate_extensions(contract)
    return contract["tuning"]


class InteractiveGather(GatherSim):
    """Slots reference IDs; inventory items remain exactly {id,kind,fresh}."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Preloaded items have no catch provenance: each starts in its own slot.
        self.slots = [[item["id"]] for item in self.hold_items]

    def _sync_slots(self):
        alive = {item["id"] for item in self.hold_items}
        self.slots = [kept for slot in self.slots if (kept := [i for i in slot if i in alive])]

    def _collection_slots(self, kind, amount, action):
        self._sync_slots()
        required = 1 if action == "catch" and kind == "ca_linh" else amount
        return self.t["hold_capacity"] - len(self.slots), required

    def _collected_items(self, items, action):
        if action == "catch" and items[0]["kind"] == "ca_linh":
            self.slots.append([item["id"] for item in items])
        else:
            self.slots.extend([item["id"]] for item in items)

    def _apply_monsters(self):
        self._sync_slots()
        before = list(self.slots)
        # The shared monster algorithm drops floor(slot_count * loss_ratio)
        # slots in LIFO order. Map each lost slot back to all physical items.
        proxy = list(range(len(before)))
        self.hp, self.invuln_ticks, events, fainted = step_monsters(
            self.monsters, self.t, self.pos, self.hp, self.invuln_ticks,
            proxy, tick_hz=self.tick_hz)
        by_id = {item["id"]: item for item in self.hold_items}
        for name, data in events:
            if name in ("monster_hit", "faint"):
                data["lost"] = clone_items([by_id[i] for index in data["lost"]
                                             for i in reversed(before[index])])
        self.slots = [before[index] for index in proxy]
        kept = {i for slot in self.slots for i in slot}
        self.hold_items[:] = [item for item in self.hold_items if item["id"] in kept]
        self.hold[:] = [item["kind"] for item in self.hold_items]
        return events, fainted

    def snapshot(self):
        self._sync_slots()
        by_id = {item["id"]: item for item in self.hold_items}
        return {**super().snapshot(), "hold_slots_used": len(self.slots),
                "hold_slots": [{"kind": by_id[slot[0]]["kind"], "quantity": len(slot),
                                "item_ids": list(slot)} for slot in self.slots]}


class InteractiveQuan(QuanSim):
    def _can_continue(self):
        if any(c["state"] == "eating" for c in self.customers):
            return True
        if self.hand or any(s["dish"] and s["state"] in ("cooking", "ready") for s in self.stoves):
            return True
        for c in self.customers:
            if c["order_status"] == "reserved" and self.item_stock._claim_items(
                    self.menu[c["dish_id"]]["recipe"], c["reserved"], self._claimed_items(exclude=c)):
                return True
        blocked = self._claimed_items()
        if self.reservations is not None and any(
                r["state"] not in FINAL and self.item_stock.reserve(self.menu[r["dish_id"]]["recipe"], blocked)
                is not None for r in self.reservations):
            return True  # còn khách đặt trước sắp đến và kho đủ món của họ
        return any(self.item_stock.reserve(self.menu[d]["recipe"], blocked) is not None
                   for d in self.allowed_dishes)

    def _settle_customers(self, events):
        super()._settle_customers(events)
        if not self.done and not self._can_continue():
            self._fail_pending_at_closing(events)  # đơn đặt trước còn treo: lỡ đơn (closing)
            for c in list(self.customers):
                self._leave(c, "closing", events)
            self.done, self.reason = True, "inventory_exhausted"
            events.append(("quan_end", {"reason": self.reason, "money": self.money,
                                        "earned": self.earned, "shift_earned": self.shift_earned,
                                        "reputation": self.reputation}))


def new_stats(day):
    return {"day": day, "caught": Counter(), "schools": Counter(), "harvested": Counter(),
            "brought": {}, "used": Counter(), "remaining": {}, "spoiled": {},
            "served": 0, "left": 0, "sold": 0, "earned": 0, "tips": 0}


class InteractiveDaySim(DaySim):
    def __init__(self, tuning, scenario, seed, days, config):
        self.web_config = config
        self.results = []
        self.gather_inventory = []
        tuning = web_tuning(tuning, config)
        super().__init__(tuning, web_scenario(tuning, scenario), seed, days)
        for day, plan in self.plans.items():
            opened, _ = unlocked_menu(tuning, config, day)
            if set(plan["dishes"]) - set(opened):
                raise BadInput(f"ngày {day}: kế hoạch chứa món chưa mở khóa")
            if target_slots(tuning, plan["ingredients"]) > tuning["gather"]["hold_capacity"]:
                raise BadInput(f"ngày {day}: mục tiêu vượt sức chứa kể cả bắt nguyên đàn")

    def _start_day(self):
        self.stats = new_stats(self.day)
        self.active_upgrades = self.upgrades.copy()
        self.plan = self.plans[self.day]
        self.unlocked_dishes, self.newly_unlocked = unlocked_menu(self.tuning, self.web_config, self.day)
        self.phase = "gather"
        effective = gather_tuning(self.tuning, self.active_upgrades)
        effective, self.allowed_ingredients = resource_tuning(effective, self.unlocked_dishes)
        scenario = self.gather_scenario if self.day == 1 else {
            k: v for k, v in self.gather_scenario.items() if k != "hold"}
        for key in ("fish", "nodes"):
            if any(entity["kind"] not in self.allowed_ingredients for entity in scenario.get(key, [])):
                raise BadInput(f"web gather.{key} chứa nguyên liệu chưa mở khóa ngày {self.day}")
        self.current = InteractiveGather(effective, scenario, self.streams, self.ids,
                                         day=self.day, active_upgrades=self.active_upgrades)
        self.current.reputation = self.reputation
        # Khách đặt trước chỉ gọi món đã mở khóa tới Ngày này; công bố ngay sau phase_start(gather).
        self.reservations = (make_reservations(self.tuning, self.streams.get("reservations"),
                                               self.unlocked_dishes, self.quan_scenario)
                             if enabled(self.tuning, "reservations") else None)

    def _start_quan(self, stock):
        tuning = {**self.tuning,
                  "menu": {d: self.tuning["menu"][d] for d in self.unlocked_dishes},
                  "quan": {**self.tuning["quan"],
                           "customer_interval_s": self.web_config["customer_interval_s"]}}
        self.current = InteractiveQuan(tuning, self.quan_scenario, self.streams, self.ids,
                                       inventory=clone_items(stock), economy={"money": self.money,
                                       "earned": self.earned, "reputation": self.reputation},
                                       reservations=self.reservations)
        self.phase = "quan"

    def step(self, inp):
        events = super().step(inp)
        s = self.stats
        for name, data in events:
            if name == "fish_caught":
                s["caught"][data["kind"]] += data["yield"]
                s["schools"][data["kind"]] += 1
            elif name == "gather":
                s["harvested"][data["kind"]] += data["amount"]
            elif name == "cook_started":
                s["used"].update(item["kind"] for item in data["items"])
            elif name == "served":
                s["served"] += 1
            elif name == "customer_left":
                s["left"] += 1
            elif name == "paid":
                s["sold"] += 1
                s["earned"] += data["amount"]
                s["tips"] += data["tip"]
        return events

    def advance_phase(self, events):
        if self.phase == "gather" and self.current.done:
            self.gather_inventory = self.current.inventory_items()
            self.gather_reason = self.current.reason
            self.stats["brought"] = items_to_counts(self.gather_inventory)
        elif self.phase == "quan" and self.current.done:
            remaining = self.current.inventory_items()
            self.stats.update(remaining=items_to_counts(remaining),
                              spoiled=items_to_counts([i for i in remaining
                                  if i["fresh"] < self.tuning["inventory"]["spoil_threshold"]]),
                              money=self.money, reputation=self.reputation, reason=self.current.reason)
            self.results.append(deepcopy(self.stats))
        return super().advance_phase(events)

    def summary(self):
        result = new_stats(self.day)
        for row in self.results:
            for key in ("caught", "schools", "harvested", "brought", "used", "remaining", "spoiled"):
                counts = Counter(result[key])
                counts.update(row[key])
                result[key] = dict(counts)
            for key in ("served", "left", "sold", "earned", "tips"):
                result[key] += row[key]
        return {**result, "money": self.money, "reputation": self.reputation}


class InteractiveSession(Session):
    """Reuse Session stepping/transition/serialization without building a second sim."""
    def __init__(self, tuning, scenario, seed, days, config):
        self.mode, self.tuning = "day", tuning
        self.sim = InteractiveDaySim(tuning, scenario, seed, days, config)
        self.tick = self.sim_tick = self.phase_tick = 0
        self.paused = self.phase_changed = False
