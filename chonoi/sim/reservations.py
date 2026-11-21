"""Extension "Khách đặt trước" (TICKET-03 `reservations`).

Trạng thái mỗi đơn: scheduled -> holding -> waiting -> served | failed.
- Day: DaySim gọi `make_reservations` khi bắt đầu Ngày (công bố sau phase_start(gather)) và truyền
  danh sách vào QuanSim. Quán độc lập tự sinh lúc dựng pha.
- QuanSim gọi các hàm trong `ReservationMixin`; khi extension tắt, `self.reservations is None` và
  không đổi gì ở lõi.
"""

from fractions import Fraction

from ..errors import BadInput
from ..ids import sort_by_id

FINAL = ("served", "failed")


def make_reservations(tuning, rng, dishes, scenario):
    """Danh sách đặt trước của một pha Quán: tường minh từ scenario hoặc sinh theo seed."""
    cfg = tuning["reservations"]
    if "reservations" in scenario:
        src = [dict(r) for r in scenario["reservations"]]
        for r in src:
            if r["dish_id"] not in dishes:
                raise BadInput(f"reservations.{r['id']}: món không thuộc thực đơn của pha")
    elif scenario.get("random_reservations", True) is False:
        src = []
    else:
        hold = int(round(cfg["table_hold_s"] * tuning["tick_hz"]))
        last = int(round(tuning["quan"]["duration_s"] * tuning["tick_hz"])) - 1
        tables = rng.sample([t["id"] for t in sort_by_id(tuning["quan"]["tables"])], cfg["count"])
        src = [{"id": f"R{i + 1}", "table_id": table, "dish_id": rng.choice(sorted(dishes)),
                "arrival_tick": rng.randint(hold, last)} for i, table in enumerate(tables)]
    return [dict(r, state="scheduled", order_id=None) for r in sort_by_id(src)]


def announce_events(reservations):
    return [("reservation_announced", {"reservation_id": r["id"], "table_id": r["table_id"],
                                       "dish_id": r["dish_id"], "arrival_tick": r["arrival_tick"]})
            for r in sort_by_id(reservations)]


def public(reservations):
    return [dict(r) for r in sort_by_id(reservations)]


class ReservationMixin:
    """Dùng chung với QuanSim/KitchenServingMixin."""

    def _init_reservations(self, tuning, scenario, reservations):
        from ..extensions import enabled
        if not enabled(tuning, "reservations"):
            self.reservations = None
            return
        self.res_cfg = tuning["reservations"]
        self.res_hold_ticks = self._ticks(self.res_cfg["table_hold_s"])
        self.res_announced = reservations is not None
        if reservations is None:
            reservations = make_reservations(tuning, self.rng.get("reservations"), self.allowed_dishes, scenario)
        else:
            reservations = [dict(r) for r in reservations]
        self.reservations = reservations
        for c in self.customers:
            c.setdefault("reservation_id", None)
        self._update_holds()  # giữ từ tick 0 thì hiện ngay trong snapshot dựng quán

    def start_events(self):
        """Quán độc lập công bố lúc dựng pha; trong Day, DaySim đã công bố ở buổi sáng."""
        if self.reservations is None or self.res_announced:
            return []
        return announce_events(self.reservations)

    def _reservation(self, res_id):
        return next(r for r in self.reservations if r["id"] == res_id)

    def _held_tables(self):
        if self.reservations is None:
            return set()
        return {r["table_id"] for r in self.reservations if r["state"] == "holding"}

    def _update_holds(self):
        for r in sort_by_id(self.reservations):
            if r["state"] == "scheduled" and self.phase_tick >= max(0, r["arrival_tick"] - self.res_hold_ticks):
                r["state"] = "holding"

    def _step_reservations(self, events):
        """Sau settlement, khi còn giờ: cập nhật giữ bàn rồi xử lý khách đặt đến, theo ID."""
        if self.reservations is None:
            return
        self._update_holds()
        for r in sort_by_id(self.reservations):
            if r["state"] != "holding" or r["arrival_tick"] != self.phase_tick:
                continue
            if any(c["table_id"] == r["table_id"] for c in self.customers):
                self._fail_reservation(r, "occupied", events)
                continue
            recipe = self.menu[r["dish_id"]]["recipe"]
            if self.item_stock is not None:
                claim = self.item_stock.reserve(recipe, self._claimed_items())
            else:
                available = self._available_stock()
                claim = dict(recipe) if all(available.get(k, 0) >= n for k, n in recipe.items()) else None
            if claim is None:
                self._fail_reservation(r, "stock", events)
                continue
            order_id = self.ids.new("C")
            self.customers.append({
                "id": order_id, "table_id": r["table_id"], "dish_id": r["dish_id"], "state": "waiting",
                "order_tick": self.phase_tick, "order_status": "reserved", "reserved": claim,
                "patience_ticks_left": self.patience_ticks, "eat_ticks_left": 0, "base_price": 0, "tip": 0,
                "reservation_id": r["id"],
            })
            r.update(state="waiting", order_id=order_id)
            events.append(("reservation_arrived", {"reservation_id": r["id"], "order_id": order_id}))
            events.append(("customer_arrived", {"order_id": order_id, "table_id": r["table_id"],
                                                "dish_id": r["dish_id"]}))

    def _fail_reservation(self, r, reason, events, customer=None):
        """Lỡ đơn: nhả hàng/bàn, hủy món, uy tín giảm đúng một lần; không phạt như khách thường."""
        if r["state"] in FINAL:
            return
        r["state"] = "failed"
        self._change_reputation(self.res_cfg["failed_reputation_delta"])
        events.append(("reservation_failed", {"reservation_id": r["id"], "reason": reason,
                                              "reputation": self.reputation}))
        if customer is not None:
            self._remove_order(customer)

    def _fail_pending_at_closing(self, events):
        """Đóng ca: fail mọi đơn chưa served/failed theo ID đặt, trước phần thanh toán khách thường."""
        if self.reservations is None:
            return
        for r in sort_by_id(self.reservations):
            if r["state"] in FINAL:
                continue
            customer = next((c for c in self.customers if c.get("reservation_id") == r["id"]), None)
            if customer is not None and customer["state"] == "eating":
                continue  # đã served: thanh toán bình thường
            self._fail_reservation(r, "closing", events, customer)

    def _reservation_price(self, base_price):
        return int(base_price * Fraction(str(self.res_cfg["price_multiplier"])))

    def _reservation_tables(self):
        """Bàn -> id đơn đặt đang giữ hoặc đang ngồi (snapshot tables[].reservation_id)."""
        return {r["table_id"]: r["id"] for r in self.reservations if r["state"] in ("holding", "waiting")}
