"""P2-04 regressions against TICKET-02 1.3 and inherited PRD-0 D--G."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import unittest

from chonoi.contract import load_contract
from chonoi.errors import BadInput
from chonoi.ids import IdAllocator
from chonoi.inputs import InputPlayer, InputState
from chonoi.inventory import KINDS_P2, items_to_counts, read_inventory, validate_items
from chonoi.rng import Streams
from chonoi.runner import Session
from chonoi.sim.quan import QuanSim
from helpers import Workdir, events, read_jsonl, run_headless, snapshots, write_json


FIXTURES = Path(__file__).parent / "fixtures"
# Independent acceptance values copied from TICKET-02 1.3, not generated from gameplay.
EXPECTED_MENU = {
    "ca_loc_nuong_trui": ({"ca_loc": 1}, 6, 60),
    "goi_bong_sung": ({"bong_sung": 2}, 4, 40),
    "lau_ca_linh_dien_dien": ({"ca_linh": 3, "bong_dien_dien": 1}, 10, 120),
    "canh_chua_ca_loc": ({"ca_loc": 1, "bong_dien_dien": 1}, 8, 90),
    "ca_keo_nuong": ({"ca_keo": 2}, 6, 70),
    "lau_mam": ({"ca_linh": 2, "ca_keo": 1, "keo_neo": 1, "bong_dien_dien": 1}, 12, 200),
}


def individual_items(counts):
    """P3 v1.2: fixture bàn giao dùng cá thể; kho đếm chỉ còn trong luật bếp cũ."""
    kinds = [kind for kind in sorted(counts) for _ in range(counts[kind])]
    return [{"id": f"I{n}", "kind": kind, "fresh": 100.0}
            for n, kind in enumerate(kinds, 1)]


class RestaurantExpansion(unittest.TestCase):
    def setUp(self):
        self.tuning = deepcopy(load_contract()["tuning"])
        self.q = self.tuning["quan"]
        self.menu = self.tuning["menu"]
        self.hz = self.tuning["tick_hz"]

    def customer(self, table, dish="ca_loc_nuong_trui", **changes):
        c = {"id": "C" + table[1:], "table_id": table, "dish_id": dish}
        c.update(changes)
        return c

    def session(self, customers=(), **scenario):
        stock = Counter()
        for c in customers:
            if c.get("order_status", "reserved") == "reserved":
                stock.update(self.menu[c["dish_id"]]["recipe"])
        block = {"customers": list(customers), "random_customers": False, "stock": dict(stock)}
        block.update(scenario)
        return Session("quan", self.tuning, block, 42)

    @staticmethod
    def step(session, interact=False):
        return session.step(InputState((0, 0), {}, {"interact"} if interact else set()))

    def advance(self, session, ticks):
        return [row for _ in range(ticks) for row in self.step(session)]

    def at(self, session, object_id):
        obj = next(o for o in session.sim.stoves + session.sim.tables if o["id"] == object_id)
        session.sim.pos = list(obj["pos"])

    def test_manifest_matches_ticket_restaurant_and_six_recipes(self):
        # v1.3 inherits the same restaurant recipes/tuning from v1.2.
        self.assertIn(load_contract()["contract_version"], ("1.2", "1.3"))
        self.assertEqual(self.hz, 60)
        self.assertEqual(self.q["stoves"], [{"id": "B1", "pos": [2, 8]}, {"id": "B2", "pos": [5, 8]}])
        self.assertEqual(self.q["tables"], [{"id": "T1", "pos": [9, 2]}, {"id": "T2", "pos": [13, 2]},
                                           {"id": "T3", "pos": [9, 6]}, {"id": "T4", "pos": [13, 6]}])
        self.assertEqual(set(self.menu), set(EXPECTED_MENU))
        for dish, (recipe, seconds, price) in EXPECTED_MENU.items():
            self.assertEqual(self.menu[dish], {"recipe": recipe, "cook_s": seconds, "price": price})
        expected = {"duration_s": 180, "walk_speed": 4, "ramp_max_ticks": 6, "interact_radius": 1.5,
                    "first_customer_tick": 120, "customer_interval_s": 15, "patience_s": 60,
                    "eat_s": 10, "burn_s": None, "carry_limit": 1, "tip_rate": 0.2,
                    "tip_min_patience_ratio": 0.5, "tip_reputation": 0.2, "left_reputation_delta": -0.5,
                    "reputation_initial": 3, "reputation_min": 0, "reputation_max": 5}
        for key, value in expected.items():
            self.assertEqual(self.q[key], value, key)

    def test_two_stoves_fifo_parallel_timers_and_unique_orders(self):
        # T1 wins the tie even though C10 sorts after C2; T3 is the later order.
        cs = [self.customer("T2", "ca_keo_nuong", id="C2"),
              self.customer("T1", "canh_chua_ca_loc", id="C10"),
              self.customer("T3", "lau_mam", order_tick=1), self.customer("T4", "goi_bong_sung", order_tick=2)]
        s = self.session(cs)
        self.at(s, "B1")
        first, = self.step(s, True)
        self.assertEqual((first["data"]["stove_id"], first["data"]["order_id"]), ("B1", "C10"))
        self.at(s, "B2")
        second, = self.step(s, True)
        self.assertEqual((second["data"]["stove_id"], second["data"]["order_id"]), ("B2", "C2"))
        self.assertEqual([b["cook_ticks_left"] for b in s.sim.stoves], [479, 360])
        self.assertEqual(self.step(s, True), [])  # busy B2 cannot cook C3 or duplicate C2
        rows = self.advance(s, 478)
        ready = events(rows, "dish_ready")
        self.assertEqual([(r["tick"], r["data"]["stove_id"]) for r in ready], [(362, "B2"), (481, "B1")])
        self.assertEqual([b["state"] for b in s.sim.stoves], ["ready", "ready"])
        self.assertEqual(s.sim.stoves[0]["ready_ticks"], 0)
        self.assertEqual(s.sim.stoves[1]["ready_ticks"], 119)
        self.assertEqual(s.sim.snapshot()["stock"], {"bong_sung": 2, "ca_linh": 2, "ca_keo": 1,
                                                   "keo_neo": 1, "bong_dien_dien": 1})
        self.assertFalse(events(self.advance(s, 10), "dish_ready"))
        self.at(s, "B2")
        picked, = self.step(s, True)
        self.assertEqual(picked["data"]["order_id"], "C2")
        self.assertEqual([b["state"] for b in s.sim.stoves], ["ready", "idle"])
        self.at(s, "B1")
        self.assertEqual(self.step(s, True), [])  # hand is full; B1 stays ready
        self.assertEqual(s.sim.hand["order_id"], "C2")

    def test_two_ready_same_tick_are_sorted_once_and_do_not_burn(self):
        cs = [self.customer("T1", order_status="assigned", reserved={}, base_price=60),
              self.customer("T2", "ca_keo_nuong", order_status="assigned", reserved={}, base_price=70)]
        stoves = [{"id": b, "state": "cooking", "cook_ticks_left": 1,
                   "dish": {"order_id": c["id"], "dish_id": c["dish_id"], "base_price": c["base_price"]}}
                  for b, c in zip(("B2", "B1"), cs)]
        s = self.session(cs, stoves=stoves)
        rows = self.step(s)
        self.assertEqual([r["data"]["stove_id"] for r in rows], ["B1", "B2"])
        self.assertFalse(events(self.advance(s, 1201), "dish_ready"))
        self.assertEqual([b["ready_ticks"] for b in s.sim.stoves], [1201, 1201])
        self.assertEqual([b["state"] for b in s.sim.stoves], ["ready", "ready"])

    def test_all_tables_refuse_wrong_orders_and_preserve_other_claims(self):
        for target in ("T1", "T2", "T3", "T4"):
            with self.subTest(table=target):
                cs = [self.customer(t) for t in ("T1", "T2", "T3", "T4")]
                c = next(c for c in cs if c["table_id"] == target)
                c.update(order_status="assigned", reserved={}, base_price=60)
                hand = {"order_id": c["id"], "dish_id": c["dish_id"], "base_price": 60}
                s = self.session(cs, hand=hand)
                for other in (t for t in ("T1", "T2", "T3", "T4") if t != target):
                    self.at(s, other)
                    self.assertEqual(self.step(s, True), [])
                    self.assertEqual(s.sim.hand, hand)
                self.at(s, target)
                served, = self.step(s, True)
                self.assertEqual(served["data"]["table_id"], target)
                self.assertEqual(served["data"]["order_id"], c["id"])
                self.assertIsNone(s.sim.hand)
                self.assertEqual(s.sim.money, 0)
                self.assertEqual([x["state"] for x in s.sim.customers].count("eating"), 1)
                self.assertEqual(sum(bool(x["reserved"]) for x in s.sim.customers), 3)

    def test_six_prices_tip_boundary_after_timer_and_exactly_one_payment(self):
        for dish, (_, _, price) in EXPECTED_MENU.items():
            for patience, tip in ((1801, price // 5), (1800, 0)):
                with self.subTest(dish=dish, patience=patience):
                    c = self.customer("T4", dish, order_status="assigned", reserved={}, base_price=price,
                                      patience_ticks_left=patience)
                    hand = {"order_id": c["id"], "dish_id": dish, "base_price": price}
                    s = self.session([c], hand=hand)
                    self.at(s, "T4")
                    served, = self.step(s, True)
                    self.assertEqual(served["data"]["tip"], tip)
                    self.assertEqual(served["data"]["patience_ticks_left"], patience - 1)
                    self.assertEqual(s.sim.money, 0)
                    self.assertFalse(events(self.advance(s, 599), "paid"))
                    paid, = self.step(s)
                    self.assertEqual(paid["tick"], 601)
                    self.assertEqual(paid["data"]["amount"], price + tip)
                    self.assertEqual((s.sim.money, s.sim.earned, s.sim.shift_earned), (price + tip,) * 3)
                    self.assertEqual(s.sim.reputation, 3.2 if tip else 3.0)
                    self.assertEqual(self.step(s), [])

    def test_four_simultaneous_payments_follow_tables_and_accumulate_once(self):
        dishes = ["canh_chua_ca_loc", "ca_keo_nuong", "lau_mam", "goi_bong_sung"]
        cs = [self.customer("T" + str(i), dish, id="C" + str(10 - i), state="eating",
                            order_status="served", reserved={}, base_price=self.menu[dish]["price"],
                            tip=self.menu[dish]["price"] // 5, eat_ticks_left=1)
              for i, dish in enumerate(dishes, 1)]
        s = self.session(cs)
        rows = self.step(s)
        self.assertEqual([r["name"] for r in rows], ["paid"] * 4)
        self.assertEqual([r["data"]["table_id"] for r in rows], ["T1", "T2", "T3", "T4"])
        self.assertEqual((s.sim.money, s.sim.earned, s.sim.shift_earned, s.sim.reputation), (480, 480, 480, 3.8))
        self.assertEqual(s.sim.customers, [])
        self.assertEqual(self.step(s), [])

    def test_mixed_departures_and_payments_follow_table_order(self):
        for closing in (False, True):
            with self.subTest(closing=closing):
                cs = [self.customer("T1", patience_ticks_left=1),
                      self.customer("T2", state="eating", order_status="served", reserved={},
                                    base_price=60, tip=12, eat_ticks_left=1),
                      self.customer("T3", patience_ticks_left=1),
                      self.customer("T4", state="eating", order_status="served", reserved={},
                                    base_price=60, tip=12, eat_ticks_left=5)]
                s = self.session(cs, time_left_ticks=1 if closing else 100)
                rows = self.step(s)
                expected = ["customer_left", "paid", "customer_left"]
                if closing:
                    expected += ["paid", "quan_end"]
                self.assertEqual([r["name"] for r in rows], expected)
                self.assertEqual([r["data"]["table_id"] for r in rows if "table_id" in r["data"]],
                                 ["T1", "T2", "T3", "T4"] if closing else ["T1", "T2", "T3"])
                self.assertEqual(rows[1]["data"]["reason"], "finished_eating")
                if closing:
                    self.assertEqual(rows[3]["data"]["reason"], "closing")
                    self.assertEqual(s.sim.reputation, 3.4)
                    self.assertEqual(s.sim.customers, [])
                else:
                    self.assertEqual(s.sim.reputation, 2.2)

    def test_timeout_cleans_only_its_order_at_each_location(self):
        for target in ("T1", "T2", "T3", "T4"):
            with self.subTest(target=target):
                cs = [self.customer(t, order_status="assigned", reserved={}, base_price=60)
                      for t in ("T1", "T2", "T3")]
                cs += [self.customer("T4")]
                next(c for c in cs if c["table_id"] == target)["patience_ticks_left"] = 1
                dish = lambda i: {"order_id": "C" + str(i), "dish_id": "ca_loc_nuong_trui", "base_price": 60}
                s = self.session(cs, hand=dish(3), stoves=[
                    {"id": "B1", "state": "cooking", "cook_ticks_left": 5, "dish": dish(1)},
                    {"id": "B2", "state": "ready", "dish": dish(2)}])
                left, = self.step(s)
                self.assertEqual(left["data"]["table_id"], target)
                self.assertEqual(s.sim.reputation, 2.5)
                self.assertEqual(len(s.sim.customers), 3)
                self.assertEqual(s.sim.snapshot()["stock"], {"ca_loc": 1})
                self.assertEqual(s.sim.stoves[0]["state"], "idle" if target == "T1" else "cooking")
                self.assertEqual(s.sim.stoves[1]["state"], "idle" if target == "T2" else "ready")
                self.assertEqual(s.sim.hand, None if target == "T3" else dish(3))
                self.assertEqual(sum(bool(c["reserved"]) for c in s.sim.customers), int(target != "T4"))
                self.assertEqual(self.step(s), [])

    def test_scheduler_fills_four_tables_and_reuses_freed_table_after_cleanup(self):
        s = self.session(stock={"ca_loc": 5}, random_customers=True)
        first = self.q["first_customer_tick"]
        interval = round(self.q["customer_interval_s"] * self.hz)
        rows = self.advance(s, first + 3 * interval)
        self.assertEqual([r["data"]["table_id"] for r in events(rows, "customer_arrived")],
                         ["T1", "T2", "T3", "T4"])
        self.assertEqual(len(s.sim.customers), 4)
        rows = self.advance(s, interval)
        self.assertEqual([r["name"] for r in rows], ["customer_left", "customer_arrived"])
        self.assertEqual(rows[1]["data"]["table_id"], "T1")
        self.assertEqual(rows[1]["data"]["order_id"], "C5")
        self.assertEqual(s.sim.customers[-1]["patience_ticks_left"], 3600)
        self.assertEqual(s.sim.stock, {"ca_loc": 5})
        self.assertEqual(s.sim._available_stock(), {"ca_loc": 1})

    def test_single_input_edge_at_stove_tie_chooses_b1_and_never_autopicks(self):
        s = self.session([self.customer("T1"), self.customer("T2")], player={"pos": [3.5, 8]})
        player = InputPlayer([{"tick": 0, "interact": True}])
        rows = [r for tick in range(365) for r in s.step(player.advance(tick))]
        self.assertEqual([r["name"] for r in rows], ["cook_started", "dish_ready"])
        self.assertEqual(rows[0]["data"]["stove_id"], "B1")
        self.assertEqual(s.sim.stoves[1]["state"], "idle")
        self.assertIsNone(s.sim.hand)

    def test_unknown_dish_duplicate_table_and_overreservation_are_rejected(self):
        cases = [([self.customer("T1", "unknown")], {}),
                 ([self.customer("T1"), self.customer("T1", id="C9")], {"ca_loc": 2}),
                 ([self.customer("T1", "lau_mam")], {"ca_keo": 1})]
        for cs, stock in cases:
            with self.subTest(customers=cs), self.assertRaises(BadInput):
                QuanSim(self.tuning, {"customers": cs, "stock": stock}, Streams(1), IdAllocator())

    def test_inventory_six_kinds_and_invalid_counts(self):
        items = individual_items({kind: 1 for kind in KINDS_P2})
        with Workdir() as work:
            path = write_json(work.path("inventory.json"), {"items": items})
            self.assertEqual(read_inventory(path), items)
        for bad in ({"unknown": 1}, {"ca_keo": -1}, {"keo_neo": True}, {"ca_keo": 0.5}):
            with self.subTest(items=bad), self.assertRaises(BadInput):
                validate_items(bad)


class RestaurantDayHooks(unittest.TestCase):
    """Python handoff tests only; these do not claim --mode day is implemented."""

    def setUp(self):
        self.tuning = deepcopy(load_contract()["tuning"])

    def quan(self, scenario=None, **kwargs):
        return QuanSim(self.tuning, scenario or {}, Streams(42), IdAllocator(), **kwargs)

    def test_day_plan_filters_before_stock_without_limiting_servings(self):
        self.tuning["quan"]["first_customer_tick"] = 1
        self.tuning["quan"]["customer_interval_s"] = 1 / 60
        plan = {"day": 3, "dishes": {"ca_keo_nuong": 1}}
        inventory = {"ca_keo": 8, "ca_loc": 5, "bong_sung": 10}
        q = self.quan(day_plan=plan, inventory=individual_items(inventory))
        for _ in range(4):
            q.step(InputState((0, 0), {}, set()))
        self.assertEqual([c["dish_id"] for c in q.customers], ["ca_keo_nuong"] * 4)
        self.assertEqual([c["table_id"] for c in q.customers], ["T1", "T2", "T3", "T4"])
        self.assertEqual(items_to_counts(q.inventory_items()), inventory)
        self.assertEqual(inventory["ca_keo"], 8)
        self.assertEqual(plan["dishes"], {"ca_keo_nuong": 1})

    def test_no_dish_when_only_unplanned_menu_items_have_stock(self):
        self.tuning["quan"]["first_customer_tick"] = 1
        q = self.quan(day_plan={"dishes": {"lau_mam": 1}}, inventory=individual_items({"ca_loc": 5}))
        self.assertEqual(q.step(InputState((0, 0), {}, set())), [("no_dish", {})])

    def test_day_fixture_outside_plan_is_rejected(self):
        c = {"id": "C1", "table_id": "T1", "dish_id": "ca_keo_nuong"}
        with self.assertRaises(BadInput):
            self.quan({"customers": [c]}, day_plan={"dishes": {"goi_bong_sung": 1}},
                      inventory=individual_items({"ca_keo": 2}))

    def test_economy_copies_preserve_totals_across_two_restaurant_shifts(self):
        plan = {"dishes": {"ca_keo_nuong": 1}}
        economy = {"money": 200, "earned": 450, "reputation": 4.9}
        scenario = {"time_left_ticks": 1, "customers": [{"id": "C1", "table_id": "T2",
                    "dish_id": "ca_keo_nuong", "state": "eating", "order_status": "served",
                    "base_price": 70, "tip": 14, "eat_ticks_left": 5}]}
        q = self.quan(scenario, inventory=[], day_plan=plan, economy=economy)
        rows = q.step(InputState((0, 0), {}, set()))
        self.assertEqual([name for name, _ in rows], ["paid", "quan_end"])
        self.assertEqual(q.economy_state(), {"money": 284, "earned": 534, "reputation": 5.0})
        self.assertEqual(q.shift_earned, 84)
        self.assertEqual(economy, {"money": 200, "earned": 450, "reputation": 4.9})
        exported = q.economy_state()
        # Mimic P2-03 passing totals to the next restaurant; no DayLoop/Shop implementation here.
        q2 = self.quan(inventory=[], day_plan=plan, economy=exported)
        self.assertEqual(q2.economy_state(), exported)
        self.assertEqual(q2.shift_earned, 0)
        exported["money"] = 0
        self.assertEqual(q.money, 284)
        self.assertEqual(q2.money, 284)
        self.assertEqual(scenario["customers"][0]["eat_ticks_left"], 5)

    def test_invalid_plan_economy_or_day_stock_is_rejected(self):
        for plan in ({}, {"dishes": {}}, {"dishes": {"ca_keo_nuong": 0}},
                     {"dishes": {"ca_keo_nuong": True}}, {"dishes": {"unknown": 1}}):
            with self.subTest(plan=plan), self.assertRaises(BadInput):
                self.quan(day_plan=plan)
        for economy in ({"money": 1, "earned": 0, "reputation": 3},
                        {"money": True, "earned": 1, "reputation": 3},
                        {"money": 0, "earned": 0, "reputation": 6}, {"money": 0}):
            with self.subTest(economy=economy), self.assertRaises(BadInput):
                self.quan(economy=economy)
        for scenario in ({"stock": {}}, {"reputation": 3}):
            with self.subTest(scenario=scenario), self.assertRaises(BadInput):
                self.quan(scenario, day_plan={"dishes": {"goi_bong_sung": 1}})

    def test_menu_and_scenario_are_isolated_from_later_mutation(self):
        q = self.quan()
        self.tuning["menu"]["lau_mam"]["price"] = 1
        self.assertEqual(q.menu["lau_mam"]["price"], 200)


class RestaurantHeadless(unittest.TestCase):
    def test_six_ingredients_transfer_between_real_gather_and_quan_processes(self):
        with Workdir() as work:
            sc = write_json(work.path("gather.json"), {"gather": {"hold": list(KINDS_P2), "random_fish": False}})
            inp = write_json(work.path("inputs.json"), {"frames": [{"tick": 0, "interact": True}]})
            inventories = []
            for index in range(2):
                inv = work.path(f"inventory{index}.json")
                code, err = run_headless("--mode", "gather", "--seed", "42", "--ticks", "1",
                                         "--scenario", sc, "--inputs", inp, "--inventory-out", inv,
                                         "--out", work.path(f"gather{index}.jsonl"))
                self.assertEqual(code, 0, err)
                inventories.append(Path(inv).read_bytes())
            self.assertEqual(*inventories)
            out = work.path("quan.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "42", "--ticks", "0", "--inventory", inv,
                                     "--out", out)
            self.assertEqual(code, 0, err)
            self.assertEqual(snapshots(read_jsonl(out))[0]["stock"], read_inventory(inv))

    def test_tick_zero_has_two_stoves_four_tables_and_no_money(self):
        with Workdir() as work:
            out = work.path("quan.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "42", "--ticks", "0", "--out", out)
            self.assertEqual(code, 0, err)
            s = snapshots(read_jsonl(out))[0]
        self.assertEqual([b["id"] for b in s["stoves"]], ["B1", "B2"])
        self.assertEqual([t["id"] for t in s["tables"]], ["T1", "T2", "T3", "T4"])
        self.assertEqual((s["money"], s["earned"], s["reputation"]), (0, 0, 3.0))

    def test_each_of_six_dishes_cooks_and_pays_via_cli(self):
        for dish, (recipe, seconds, price) in EXPECTED_MENU.items():
            with self.subTest(dish=dish), Workdir() as work:
                cook = seconds * 60
                sc = write_json(work.path("scenario.json"), {"quan": {
                    "random_customers": False, "stock": recipe, "player": {"pos": [2, 8]},
                    "tables": [{"id": "T1", "pos": [4, 8]}],
                    "customers": [{"id": "C1", "table_id": "T1", "dish_id": dish}]}})
                inp = write_json(work.path("inputs.json"), {"frames": [
                    {"tick": 0, "interact": True}, {"tick": 1, "interact": False},
                    {"tick": cook, "interact": True}, {"tick": cook + 1, "interact": False, "move": [1, 0]},
                    {"tick": cook + 31, "move": [0, 0]}, {"tick": cook + 37, "interact": True}]})
                out = work.path("quan.jsonl")
                code, err = run_headless("--mode", "quan", "--seed", "42", "--ticks", str(cook + 638),
                                         "--scenario", sc, "--inputs", inp, "--snapshot-every", "1", "--out", out)
                self.assertEqual(code, 0, err)
                rows = read_jsonl(out)
                self.assertEqual([(r["tick"], r["name"]) for r in events(rows)], [
                    (1, "cook_started"), (cook + 1, "dish_ready"), (cook + 1, "dish_picked"),
                    (cook + 38, "served"), (cook + 638, "paid")])
                self.assertEqual(events(rows, "cook_started")[0]["data"]["items"],
                                 sorted(kind for kind, count in recipe.items() for _ in range(count)))
                self.assertEqual(rows[-1]["money"], price + price // 5)
                self.assertEqual(snapshots(rows)[-1]["stock"], {})

    def test_four_customer_two_stove_playthrough_is_byte_deterministic(self):
        with Workdir() as work:
            outs = [work.path("a.jsonl"), work.path("b.jsonl")]
            for out in outs:
                code, err = run_headless("--mode", "quan", "--seed", "42", "--ticks", "10800",
                                         "--scenario", str(FIXTURES / "p2_04_quan.json"),
                                         "--inputs", str(FIXTURES / "p2_04_inputs.json"),
                                         "--snapshot-every", "1", "--out", out)
                self.assertEqual(code, 0, err)
            self.assertEqual(Path(outs[0]).read_bytes(), Path(outs[1]).read_bytes())
            rows = read_jsonl(outs[0])
        self.assertEqual(len(events(rows, "cook_started")), 4)
        self.assertEqual(len(events(rows, "dish_ready")), 4)
        self.assertEqual(len(events(rows, "dish_picked")), 4)
        self.assertEqual(len(events(rows, "served")), 4)
        self.assertEqual(len(events(rows, "paid")), 4)
        self.assertEqual(len(events(rows, "quan_end")), 1)
        self.assertEqual(events(rows, "customer_left"), [])
        self.assertEqual([r["data"]["table_id"] for r in events(rows, "served")], ["T1", "T2", "T3", "T4"])
        self.assertEqual((rows[-1]["money"], rows[-1]["earned"], rows[-1]["reputation"], rows[-1]["score"]),
                         (480, 480, 3.8, 780))
        ss = snapshots(rows)
        self.assertEqual(max(sum(b["state"] == "cooking" for b in s["stoves"]) for s in ss), 2)
        self.assertEqual(ss[-1]["customers"], [])
        self.assertEqual(ss[-1]["stock"], {})
        for s in ss:
            assigned = [c["id"] for c in s["customers"] if c["order_status"] == "assigned"]
            dishes = [b["dish"] for b in s["stoves"] if b["dish"] is not None]
            if s["hand"] is not None:
                dishes.append(s["hand"])
            self.assertCountEqual([d["order_id"] for d in dishes], assigned)
            self.assertTrue(all(count >= 0 for count in s["stock"].values()))
