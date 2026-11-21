"""Buổi tối — Mở Quán: khách/giữ chỗ P1-03 và bếp/phục vụ P1-04.

KitchenServingMixin quản lý validation, timers và cleanup dùng chung.
Khách mới sinh sau settlement, chỉ tham gia tương tác từ bước sau.
"""

from copy import deepcopy

from ..errors import BadInput
from ..ids import sort_by_id
from ..inventory import clone_items, items_to_counts, materialize_items
from .kitchen import KitchenServingMixin
from .ramp import ramp_velocity
from .reservations import ReservationMixin, public
from .restaurant_stock import RestaurantStock


class QuanSim(ReservationMixin, KitchenServingMixin):
    mode = "quan"
    phase = "quan"

    def __init__(self, tuning, scenario, streams, ids, inventory=None, *, day_plan=None, economy=None,
                 reservations=None):
        """Standalone by default; P2-03 can pass a per-day plan and economy.

        day_plan uses its existing {dishes: {dish_id: servings}} object. Counts
        are gathering goals, never sales caps. economy is a copied map with
        money/earned/reputation; hand it back via economy_state() after closing.
        These are Python integration hooks, not additional scenario fields.
        """
        # LiveGame restart must not reuse mutated customers, reservations or dishes.
        scenario = deepcopy(scenario)
        t = tuning["quan"]
        self.t = t
        self.tick_hz = tuning["tick_hz"]
        self.tick = 0
        self.menu = deepcopy(tuning["menu"])
        self.allowed_dishes = tuple(sorted(self.menu))
        if day_plan is not None:
            dishes = day_plan.get("dishes") if isinstance(day_plan, dict) else None
            if (not isinstance(dishes, dict) or not dishes
                    or any(d not in self.menu or type(count) is not int or count <= 0
                           for d, count in dishes.items())):
                raise BadInput("day_plan.dishes cần các món hợp lệ với số suất nguyên dương")
            self.allowed_dishes = tuple(sorted(dishes))
        if (day_plan is not None or economy is not None) and {"stock", "reputation"} & scenario.keys():
            raise BadInput("day không nhận quan.stock/reputation; dùng inventory và economy")
        if economy is not None:
            if (not isinstance(economy, dict) or set(economy) != {"money", "earned", "reputation"}
                    or any(type(economy[k]) is not int for k in ("money", "earned"))
                    or not 0 <= economy["money"] <= economy["earned"]):
                raise BadInput("economy cần money/earned nguyên, 0 <= money <= earned và reputation")
        self.rng = streams
        self.ids = ids
        p = scenario.get("player", {})
        self.pos = list(p.get("pos", t["start_pos"]))
        self.vel = [float(c) for c in p.get("vel", [0.0, 0.0])]
        self._tgt = None
        self._ramp_left = 0
        # kho: --inventory HOẶC scenario.stock (cả hai -> cli đã báo mã 2)
        if inventory is not None and "stock" in scenario:
            raise BadInput("vừa có quan.stock vừa có inventory")
        legacy_orders = any(isinstance(c.get("reserved"), dict) for c in scenario.get("customers", []))
        default_stock = {} if legacy_orders else []
        stock_source = inventory if inventory is not None else scenario.get("stock", default_stock)
        self.stock_items = materialize_items(stock_source, ids, allow_legacy=inventory is None)
        inventory_tuning = tuning.get("inventory")
        # Keep explicitly counted Phase 1/2 fixtures usable through the internal adapter.
        self.item_stock = (RestaurantStock(self.stock_items, inventory_tuning, self.tick_hz)
                           if isinstance(stock_source, list) and inventory_tuning is not None else None)
        self.stock = self.item_stock.items if self.item_stock is not None else items_to_counts(self.stock_items)
        self.hand = scenario.get("hand")
        self.time_left_ticks = scenario.get("time_left_ticks", self._ticks(t["duration_s"]))
        self.phase_tick = 0
        self.customer_interval_ticks = self._ticks(t["customer_interval_s"])
        self.patience_ticks = self._ticks(t["patience_s"])
        self.random_customers = scenario.get("random_customers", True)
        if not isinstance(self.random_customers, bool):
            raise BadInput("random_customers phải là boolean")
        self.reputation = (economy["reputation"] if economy is not None
                           else scenario.get("reputation", t["reputation_initial"]))
        self.stoves = [dict(s, state=s.get("state", "idle"), dish=s.get("dish"),
                            cook_ticks_left=s.get("cook_ticks_left", 0), ready_ticks=s.get("ready_ticks", 0))
                       for s in self._merge(t["stoves"], scenario.get("stoves", []))]
        self.tables = self._merge(t["tables"], scenario.get("tables", []))
        self.customers = [dict(c) for c in scenario.get("customers", [])]
        for e in self.customers:
            ids.reserve(e["id"])
        self.money = economy["money"] if economy is not None else 0
        self.earned = economy["earned"] if economy is not None else 0
        self.shift_earned = 0
        self.done = False
        self.reason = None
        self._validate_kitchen_state()
        # extension khách đặt trước; `reservations` do DaySim truyền (đã công bố buổi sáng)
        self._init_reservations(tuning, scenario, reservations)

    def economy_state(self):
        """Copy totals to P2-03/Shop without sharing mutable restaurant state."""
        return {"money": self.money, "earned": self.earned, "reputation": self.reputation}

    @staticmethod
    def _merge(defaults, updates):
        by_id = {d["id"]: dict(d) for d in defaults}
        for u in updates:
            if u["id"] not in by_id:
                raise BadInput(f"id bếp/bàn không tồn tại: {u['id']}")
            by_id[u["id"]].update(u)
        return sort_by_id(list(by_id.values()))

    def snapshot(self) -> dict:
        occupied = {c["table_id"]: c["id"] for c in self.customers}
        items = self.inventory_items()
        stock = items
        if self.item_stock is None:
            stock = {k: self.stock[k] for k in sorted(self.stock) if self.stock[k] > 0}
        snap = {
            "player": {"pos": self.pos, "vel": self.vel},
            "stock": stock,
            "stock_items": items,
            "hand": self.hand,
            "stoves": [{k: s.get(k) for k in ("id", "pos", "state", "dish", "cook_ticks_left", "ready_ticks")}
                       for s in self.stoves],
            "tables": [{"id": tb["id"], "pos": tb["pos"], "customer_id": occupied.get(tb["id"])} for tb in self.tables],
            "customers": sort_by_id(self.customers),
        }
        if self.reservations is not None:
            by_table = self._reservation_tables()
            for table in snap["tables"]:
                table["reservation_id"] = by_table.get(table["id"])
            snap["customers"] = [{**c, "reservation_id": c.get("reservation_id")} for c in snap["customers"]]
            snap["reservations"] = public(self.reservations)
        return snap

    def inventory_items(self):
        """Danh sách cá thể còn trong kho vật lý sau các lần nấu."""
        if self.item_stock is not None:
            return self.item_stock.snapshot()
        remaining = self.stock.copy()
        kept = []
        for item in self.stock_items:
            kind = item["kind"]
            if remaining.get(kind, 0) > 0:
                kept.append(item)
                remaining[kind] -= 1
        return clone_items(kept)

    def step(self, inp):
        if self.done:
            return []
        events = []
        self.tick += 1
        self.phase_tick += 1
        self.time_left_ticks = max(0, self.time_left_ticks - 1)
        self._advance_kitchen_timers()
        if self.item_stock is not None:
            self._age_stock(events)
        self._finish_cooking(events)
        self._move(inp)
        if inp.pressed("interact"):
            self._interact(events)
        self._settle_customers(events)
        if not self.done:
            self._step_reservations(events)  # đặt trước xử lý trước khách thường
            self._maybe_add_customer(events)
        return events

    def _available_stock(self):
        available = self.stock.copy()
        for customer in self.customers:
            for kind, count in customer["reserved"].items():
                available[kind] = available.get(kind, 0) - count
        return available

    def _claimed_items(self, *, exclude=None):
        return {item_id for customer in self.customers if customer is not exclude for item_id in customer["reserved"]}

    def _age_stock(self, events):
        spoiled = self.item_stock.age()
        if not spoiled:
            return
        for item in spoiled:
            events.append(("spoiled", {"item_id": item["id"], "kind": item["kind"], "location": "stock"}))
        expired = {item["id"] for item in spoiled}
        by_table = sort_by_id(self.customers, key=lambda c: c["table_id"])
        for customer in sorted(by_table, key=lambda c: c["order_tick"]):
            if not expired.intersection(customer["reserved"]):
                continue
            customer["reserved"].clear()
            recipe = self.menu[customer["dish_id"]]["recipe"]
            claim = self.item_stock.reserve(recipe, self._claimed_items())
            if claim is None and customer.get("reservation_id"):
                self._fail_reservation(self._reservation(customer["reservation_id"]), "stock", events, customer)
            elif claim is None:
                customer["order_status"] = "unfulfillable"
            else:
                customer["reserved"] = claim

    def _maybe_add_customer(self, events):
        since_first = self.phase_tick - self.t["first_customer_tick"]
        if not self.random_customers or since_first < 0 or since_first % self.customer_interval_ticks:
            return
        occupied = {customer["table_id"] for customer in self.customers} | self._held_tables()
        table = next((table for table in self.tables if table["id"] not in occupied), None)
        if table is None:
            return
        table_id = table["id"]
        if self.item_stock is not None:
            blocked = self._claimed_items()
            claims = {dish_id: self.item_stock.reserve(self.menu[dish_id]["recipe"], blocked)
                      for dish_id in self.allowed_dishes}
        else:
            available = self._available_stock()
            claims = {dish_id: dict(self.menu[dish_id]["recipe"]) for dish_id in self.allowed_dishes
                      if all(available.get(kind, 0) >= count for kind, count in self.menu[dish_id]["recipe"].items())}
        dishes = [dish_id for dish_id, claim in claims.items() if claim is not None]
        if not dishes:
            events.append(("no_dish", {}))
            return
        dish_id = self.rng.get("customer_order").choice(dishes)
        reserved = claims[dish_id]
        order_id = self.ids.new("C")
        self.customers.append({
            "id": order_id, "table_id": table_id, "dish_id": dish_id, "state": "waiting",
            "order_tick": self.phase_tick, "order_status": "reserved", "reserved": reserved,
            "patience_ticks_left": self.patience_ticks, "eat_ticks_left": 0, "base_price": 0, "tip": 0,
        })
        events.append(("customer_arrived", {"order_id": order_id, "table_id": table_id, "dish_id": dish_id}))

    def _move(self, inp):
        speed = self.t["walk_speed"]
        mx, mz = inp.move
        self.vel = ramp_velocity(self, (mx * speed, mz * speed), int(self.t.get("ramp_max_ticks", 6)))
        b = self.t["bounds"]
        for i, axis in enumerate(("x", "z")):
            self.pos[i] += self.vel[i] / self.tick_hz
            lo, hi = b[axis]
            if self.pos[i] <= lo:
                self.pos[i], self.vel[i] = lo, max(0.0, self.vel[i])
            elif self.pos[i] >= hi:
                self.pos[i], self.vel[i] = hi, min(0.0, self.vel[i])
