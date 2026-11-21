"""P1-04 cooking, serving and settlement helpers for QuanSim.

Integration with P1-03: customer.id is the order_id carried by each dish/event,
stock is physical inventory, and customer.reserved is its claim on
that inventory. Only cook_started consumes stock. Customer arrivals/menu
selection belong to P1-03, outside this helper. See docs/notes/P1-04.md.
"""

from collections import Counter
from decimal import Decimal, ROUND_FLOOR
from math import dist, isfinite, ulp

from ..errors import BadInput
from ..ids import sort_by_id


class KitchenServingMixin:
    def _ticks(self, seconds):
        return int(round(seconds * self.tick_hz))

    def _validate_kitchen_state(self):
        """Reject inconsistent order/dish ownership before headless writes tick 0.

        Validation stays here to avoid changing the shared scenario loader.
        P1-03 owns constructing new customers and their reservations.
        """
        self.patience_max_ticks = self._ticks(self.t["patience_s"])
        for entity in self.stoves + self.tables:
            pos = entity.get("pos")
            if (not isinstance(pos, list) or len(pos) != 2
                    or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v)
                           for v in pos)
                    or any(not self.t["bounds"][axis][0] <= value <= self.t["bounds"][axis][1]
                           for axis, value in zip(("x", "z"), pos))):
                raise BadInput(f"{entity['id']}.pos ngoài miền quán")
        for table in self.tables:
            if set(table) - {"id", "pos"}:
                raise BadInput(f"tables.{table['id']}: trường ngoài contract")
        if not (isinstance(self.reputation, (int, float)) and not isinstance(self.reputation, bool)
                and isfinite(self.reputation)
                and self.t["reputation_min"] <= self.reputation <= self.t["reputation_max"]):
            raise BadInput("reputation ngoài miền")
        orders = {}
        table_ids = {table["id"] for table in self.tables}
        occupied = set()
        for c in self.customers:
            if not isinstance(c.get("table_id"), str) or c["table_id"] not in table_ids or c["table_id"] in occupied:
                raise BadInput("mỗi khách cần một bàn có thật, không trùng bàn")
            occupied.add(c["table_id"])
            c.setdefault("order_tick", 0)
            self._require_counter(c, "order_tick")
        by_table = sort_by_id(self.customers, key=lambda c: c["table_id"])
        fixture_orders = sorted(by_table, key=lambda c: c["order_tick"])
        for c in fixture_orders:
            if set(c) - {"id", "table_id", "dish_id", "order_tick", "state", "patience_ticks_left",
                         "eat_ticks_left", "order_status", "reserved", "base_price", "tip"}:
                raise BadInput(f"customers.{c['id']}: trường ngoài contract")
            if (c["id"] in orders or not isinstance(c.get("dish_id"), str)
                    or c["dish_id"] not in self.allowed_dishes):
                raise BadInput(f"customers.{c['id']}: id trùng hoặc dish_id không hợp lệ")
            orders[c["id"]] = c
            c.setdefault("state", "waiting")
            c.setdefault("order_status", "reserved")
            c.setdefault("patience_ticks_left", self.patience_max_ticks if c["state"] == "waiting" else 0)
            c.setdefault("eat_ticks_left", 0)
            if (c.get("state"), c.get("order_status")) not in (
                ("waiting", "reserved"), ("waiting", "assigned"),
                ("waiting", "unfulfillable"), ("eating", "served"),
            ):
                raise BadInput(f"customers.{c['id']}: state/order_status mâu thuẫn")
            if self.item_stock is None:
                self._validate_count_claim(c)
            self._require_counter(c, "patience_ticks_left")
            self._require_counter(c, "eat_ticks_left", minimum=int(c["state"] == "eating"))
            if c["patience_ticks_left"] > self.patience_max_ticks:
                raise BadInput(f"customers.{c['id']}: patience vượt tối đa")
            if c["state"] == "waiting" and c["eat_ticks_left"] != 0:
                raise BadInput(f"customers.{c['id']}: waiting có timer ăn")
            if c["state"] == "eating":
                self._require_counter(c, "tip")
                if "base_price" not in c:
                    raise BadInput(f"customers.{c['id']}: eating thiếu base_price")
            c.setdefault("base_price", self.menu[c["dish_id"]]["price"])
            c.setdefault("tip", 0)
            self._require_counter(c, "base_price", minimum=int(c["order_status"] in ("assigned", "served")))
            self._require_counter(c, "tip")
        if self.item_stock is not None:
            self.item_stock.load_claims(fixture_orders, self.menu)
        elif not self._reservations_fit_stock():
            raise BadInput("tổng reserved vượt stock")

        locations = Counter()
        for stove in self.stoves:
            if set(stove) - {"id", "pos", "state", "dish", "cook_ticks_left", "ready_ticks"}:
                raise BadInput(f"stoves.{stove['id']}: trường ngoài contract")
            if stove["state"] not in ("idle", "cooking", "ready"):
                raise BadInput(f"stoves.{stove['id']}: state không hợp lệ")
            self._require_counter(stove, "cook_ticks_left", minimum=int(stove["state"] == "cooking"))
            self._require_counter(stove, "ready_ticks")
            if (stove["state"] == "idle") != (stove["dish"] is None):
                raise BadInput(f"stoves.{stove['id']}: state/dish mâu thuẫn")
            if stove["state"] != "cooking" and stove["cook_ticks_left"] != 0:
                raise BadInput(f"stoves.{stove['id']}: timer nấu ngoài trạng thái cooking")
            if stove["state"] != "ready" and stove["ready_ticks"] != 0:
                raise BadInput(f"stoves.{stove['id']}: ready_ticks ngoài trạng thái ready")
            if stove["dish"] is not None:
                self._validate_dish(stove["dish"], orders, locations)
        if self.hand is not None:
            if self.t["carry_limit"] < 1:
                raise BadInput("hand vượt carry_limit")
            self._validate_dish(self.hand, orders, locations)
        for order_id, c in orders.items():
            expected = int(c["order_status"] == "assigned")
            if locations[order_id] != expected:
                raise BadInput(f"order {order_id}: assigned phải có đúng một món")

    @staticmethod
    def _require_counter(entity, key, minimum=0):
        value = entity.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise BadInput(f"{entity['id']}.{key}: cần số nguyên >= {minimum}")

    def _validate_count_claim(self, customer):
        expected = self.menu[customer["dish_id"]]["recipe"] if customer["order_status"] == "reserved" else {}
        claim = customer.setdefault("reserved", expected.copy())
        if (not isinstance(claim, dict)
                or any(type(count) is not int or count < 0 for count in claim.values())
                or claim != expected):
            raise BadInput(f"customers.{customer['id']}: reserved phải khớp công thức và trạng thái đơn")

    @staticmethod
    def _validate_dish(dish, orders, locations):
        if not isinstance(dish, dict) or set(dish) != {"order_id", "dish_id", "base_price"}:
            raise BadInput("dish phải chứa order_id, dish_id, base_price")
        if not isinstance(dish["order_id"], str):
            raise BadInput("dish.order_id cần id khách")
        if isinstance(dish["base_price"], bool) or not isinstance(dish["base_price"], int):
            raise BadInput("dish.base_price cần số nguyên")
        c = orders.get(dish["order_id"])
        if (c is None or c["order_status"] != "assigned"
                or dish.get("dish_id") != c["dish_id"]
                or dish.get("base_price") != c["base_price"]):
            raise BadInput("dish không khớp đơn assigned")
        locations[c["id"]] += 1

    def _reservations_fit_stock(self):
        total = Counter()
        for c in self.customers:
            total.update(c["reserved"])
        return all(qty <= self.stock.get(kind, 0) for kind, qty in total.items())

    def _advance_kitchen_timers(self):
        for c in sort_by_id(self.customers):
            timer = "eat_ticks_left" if c["state"] == "eating" else "patience_ticks_left"
            c[timer] = max(0, c[timer] - 1)
        for stove in sort_by_id(self.stoves):
            if stove["state"] == "ready":
                stove["ready_ticks"] += 1
            elif stove["state"] == "cooking":
                stove["cook_ticks_left"] = max(0, stove["cook_ticks_left"] - 1)

    def _finish_cooking(self, events):
        for stove in sort_by_id(self.stoves):
            if stove["state"] == "cooking" and stove["cook_ticks_left"] == 0:
                stove.update(state="ready", ready_ticks=0)
                dish = stove["dish"]
                events.append(("dish_ready", {"stove_id": stove["id"],
                                              "order_id": dish["order_id"], "dish_id": dish["dish_id"]}))

    def _interact(self, events):
        # Stable natural ID order supplies the final tie-break, even for B2/B10.
        objects = sort_by_id([(0, s) for s in self.stoves] + [(1, t) for t in self.tables],
                             key=lambda pair: pair[1]["id"])
        nearby = []
        radius = self.t["interact_radius"]
        for priority, obj in objects:
            distance = dist(self.pos, obj["pos"])
            # Decimal coordinates such as (9.9, 3.2) can land a few ULPs
            # outside an exact 1.5-radius edge after binary subtraction.
            tolerance = sum(ulp(v) for v in (*self.pos, *obj["pos"], radius))
            if distance <= radius + tolerance:
                nearby.append((distance, priority, obj))
        if not nearby:
            return
        _, priority, obj = min(nearby, key=lambda item: (item[0], item[1]))
        if priority == 0:
            self._interact_stove(obj, events)
        else:
            self._serve(obj, events)

    def _interact_stove(self, stove, events):
        if stove["state"] == "ready":
            if self.hand is not None or self.t["carry_limit"] < 1:
                return
            self.hand = stove["dish"]
            self._reset_stove(stove)
            events.append(("dish_picked", {"stove_id": stove["id"],
                                          "order_id": self.hand["order_id"], "dish_id": self.hand["dish_id"]}))
        elif stove["state"] == "idle":
            # Sort by table ID first; stable order_tick sort then yields FIFO.
            orders = sort_by_id([c for c in self.customers
                                 if c["state"] == "waiting" and c["order_status"] == "reserved"
                                 and c["dish_id"] in self.allowed_dishes],
                                key=lambda c: c["table_id"])
            if not orders:
                return
            c = min(orders, key=lambda c: c["order_tick"])
            dish = self.menu[c["dish_id"]]
            consumed = self._consume_order_items(c, dish)
            if consumed is None:
                return
            c["base_price"], items = consumed
            if c.get("reservation_id"):  # extension đặt trước: giá theo fresh × hệ số, làm tròn xuống
                c["base_price"] = self._reservation_price(c["base_price"])
            c["reserved"].clear()
            c["order_status"] = "assigned"
            stove.update(state="cooking", dish=self._dish_for(c), ready_ticks=0,
                         cook_ticks_left=self._ticks(dish["cook_s"]))
            events.append(("cook_started", {"stove_id": stove["id"], **stove["dish"], "items": items}))

    def _consume_order_items(self, customer, dish):
        recipe = dish["recipe"]
        if self.item_stock is not None:
            return self.item_stock.consume(recipe, customer["reserved"], self._claimed_items(exclude=customer),
                                           dish["price"])
        if customer["reserved"] != recipe or not self._reservations_fit_stock():
            return None
        for kind, qty in recipe.items():
            self.stock[kind] -= qty
        return dish["price"], [kind for kind in sorted(recipe) for _ in range(recipe[kind])]

    @staticmethod
    def _dish_for(customer):
        return {"order_id": customer["id"], "dish_id": customer["dish_id"], "base_price": customer["base_price"]}

    @staticmethod
    def _reset_stove(stove):
        stove.update(state="idle", dish=None, cook_ticks_left=0, ready_ticks=0)

    def _serve(self, table, events):
        if self.hand is None:
            return
        c = next((c for c in self.customers if c["table_id"] == table["id"]), None)
        if (c is None or c["state"] != "waiting" or c["order_status"] != "assigned"
                or self.hand["order_id"] != c["id"] or self.hand["dish_id"] != c["dish_id"]):
            return
        ratio = Decimal(c["patience_ticks_left"]) / Decimal(self.patience_max_ticks)
        tip = 0
        if ratio >= Decimal(str(self.t["tip_min_patience_ratio"])):
            tip = int((Decimal(c["base_price"]) * Decimal(str(self.t["tip_rate"]))).to_integral_value(
                rounding=ROUND_FLOOR))
        self.hand = None
        c.update(state="eating", order_status="served", tip=tip,
                 eat_ticks_left=self._ticks(self.t["eat_s"]))
        events.append(("served", {**self._dish_for(c), "table_id": c["table_id"],
                                  "patience_ticks_left": c["patience_ticks_left"], "tip": tip}))
        if c.get("reservation_id"):
            self._reservation(c["reservation_id"])["state"] = "served"
            events.append(("reservation_served", {"reservation_id": c["reservation_id"], "order_id": c["id"],
                                                  "base_price": c["base_price"]}))

    def _settle_customers(self, events):
        if self.time_left_ticks == 0 and getattr(self, "reservations", None) is not None:
            self._fail_pending_at_closing(events)
        # One table-ordered pass, including mixed payments/departures. An eating
        # timer that expires on closing still gets reason=finished_eating.
        for c in sort_by_id(self.customers, key=lambda c: c["table_id"]):
            if c["state"] == "eating" and c["eat_ticks_left"] == 0:
                self._pay(c, "finished_eating", events)
            elif self.time_left_ticks == 0:
                if c["state"] == "eating":
                    self._pay(c, "closing", events)
                else:
                    self._leave(c, "closing", events)
            elif c["state"] == "waiting" and c["patience_ticks_left"] == 0:
                self._leave(c, "patience", events)
        if self.time_left_ticks == 0:
            self.done, self.reason = True, "time"
            events.append(("quan_end", {"reason": "time", "money": self.money, "earned": self.earned,
                                        "shift_earned": self.shift_earned, "reputation": self.reputation}))

    def _change_reputation(self, delta):
        # Decimal avoids repeated +0.2 drifting below an integer score boundary.
        value = Decimal(str(self.reputation)) + Decimal(str(delta))
        self.reputation = float(max(Decimal(str(self.t["reputation_min"])),
                                    min(Decimal(str(self.t["reputation_max"])), value)))

    def _pay(self, c, reason, events):
        amount = c["base_price"] + c["tip"]
        self.money += amount
        self.earned += amount
        self.shift_earned += amount
        if c["tip"] > 0:
            self._change_reputation(self.t["tip_reputation"])
        events.append(("paid", {"order_id": c["id"], "table_id": c["table_id"],
                                "base_price": c["base_price"], "tip": c["tip"],
                                "amount": amount, "reason": reason}))
        self._remove_order(c)

    def _leave(self, c, reason, events):
        # Shared cleanup for fixture and scheduled customers; emit only once.
        if c.get("reservation_id"):  # khách đặt trước: reservation_failed thay cho customer_left
            self._fail_reservation(self._reservation(c["reservation_id"]), reason, events, c)
            return
        if reason != "closing":
            self._change_reputation(self.t["left_reputation_delta"])
        events.append(("customer_left", {"order_id": c["id"], "table_id": c["table_id"],
                                         "reason": reason, "reputation": self.reputation}))
        self._remove_order(c)

    def _remove_order(self, c):
        """Shared cancellation hook: release claims; never refund consumed stock."""
        c["reserved"].clear()
        for stove in self.stoves:
            if stove["dish"] is not None and stove["dish"]["order_id"] == c["id"]:
                self._reset_stove(stove)
        if self.hand is not None and self.hand["order_id"] == c["id"]:
            self.hand = None
        self.customers.remove(c)
