"""Web-only rules and their separation from the official headless runner."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import unittest

from chonoi.contract import load_contract
from chonoi.ids import IdAllocator
from chonoi.inputs import InputState
from chonoi.interactive import InteractiveGather, InteractiveQuan, InteractiveSession
from chonoi.interactive_web import InteractiveDayWeb
from chonoi.rng import Streams
from chonoi.runner import Session
from chonoi.scenario import load_scenario
from chonoi.sim.gather import GatherSim

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "chonoi/web/gameplay.json").read_text())
NEUTRAL = InputState((0, 0), {}, set())
INTERACT = InputState((0, 0), {}, {"interact"})
CATCH = InputState((0, 0), {}, {"catch"})


def items(kinds, fresh=100):
    return [{"id": f"I{i+1}", "kind": kind, "fresh": fresh} for i, kind in enumerate(kinds)]


class InteractiveGameplay(unittest.TestCase):
    def setUp(self):
        self.tuning = deepcopy(load_contract()["tuning"])

    def gather(self, hold=(), *, standard=False, monsters=None, hp=3):
        scenario = {"hold": items(hold), "random_fish": False,
                    "player": {"pos": [20, 10], "hp": hp},
                    "fish": [{"id": "F1", "kind": "ca_linh", "pos": [20, 10]},
                             {"id": "F2", "kind": "ca_linh", "pos": [20, 10]}],
                    "monsters": monsters or []}
        return (GatherSim if standard else InteractiveGather)(self.tuning, scenario, Streams(1), IdAllocator())

    def quan(self, kinds=(), *, fresh=100, customers=(), stoves=(), hand=None, menu=None):
        tuning = deepcopy(self.tuning)
        tuning["menu"] = {d: tuning["menu"][d] for d in (menu or ["ca_loc_nuong_trui", "goi_bong_sung"])}
        tuning["quan"]["first_customer_tick"] = 1
        tuning["quan"]["customer_interval_s"] = CONFIG["customer_interval_s"]
        scenario = {"stock": items(kinds, fresh), "customers": deepcopy(list(customers)),
                    "stoves": deepcopy(list(stoves)), "hand": deepcopy(hand)}
        return InteractiveQuan(tuning, scenario, Streams(1), IdAllocator())

    def test_school_keeps_three_ids_one_slot_and_second_school_new_slot(self):
        g = self.gather()
        g.step(CATCH)
        self.assertEqual((len(g.hold_items), g.snapshot()["hold_slots_used"]), (3, 1))
        first_ids = [i["id"] for i in g.hold_items]
        for _ in range(round(self.tuning["gather"]["catch_cooldown_s"] * self.tuning["tick_hz"])):
            g.step(NEUTRAL)
        g.step(CATCH)
        self.assertEqual((len(g.hold_items), g.snapshot()["hold_slots_used"]), (6, 2))
        self.assertEqual(len({i["id"] for i in g.hold_items}), 6)
        self.assertEqual(g.snapshot()["hold_slots"][0]["item_ids"], first_ids)
        self.assertTrue(all(set(i) == {"id", "kind", "fresh"} for i in g.inventory_items()))

    def test_last_slot_accepts_school_but_full_basket_rejects_it(self):
        g = self.gather(["ca_loc"] * 11)
        g.step(CATCH)
        self.assertEqual((len(g.hold_items), g.snapshot()["hold_slots_used"]), (14, 12))
        for _ in range(31):
            g.step(NEUTRAL)
        events = g.step(CATCH)
        self.assertEqual(next(d for n, d in events if n == "hold_full")["free"], 0)
        self.assertEqual(len(g.hold_items), 14)
        standard = self.gather(["ca_loc"] * 11, standard=True)
        self.assertIn("hold_full", [n for n, _ in standard.step(CATCH)])
        self.assertEqual(len(standard.hold_items), 11)

    def test_other_kinds_still_use_individual_slots(self):
        g = self.gather(["ca_loc"] * 11)
        g.fish[0]["kind"] = "ca_keo"
        self.assertIn("hold_full", [n for n, _ in g.step(CATCH)])
        self.assertEqual(len(g.hold_items), 11)

    def test_monster_loses_whole_last_stack_lifo_and_faint_clears_all(self):
        for hp in (3, 1):
            g = self.gather(["bong_sung"], hp=hp)
            g.step(CATCH)  # [flower] [linh x3]
            from chonoi.sim.monsters import init_monsters
            g.monsters = init_monsters(g.t, {"monsters": [{"id": "M1", "kind": "ca_sau",
                "pos": [20, 10], "waypoints": [[20, 10], [21, 10]]}]}, day=1)
            rows = g.step(NEUTRAL)
            lost = next(d["lost"] for n, d in rows if n == "monster_hit")
            self.assertEqual([i["id"] for i in lost], ["I4", "I3", "I2"])
            self.assertEqual(len(g.hold_items), 1 if hp == 3 else 0)
            if hp == 1:
                self.assertEqual(next(d["lost"] for n, d in rows if n == "faint")[0]["id"], "I1")
                self.assertEqual(g.snapshot()["hold_slots_used"], 0)

    def test_stack_handoff_preserves_items_then_recipe_consumes_three(self):
        g = self.gather(["bong_dien_dien"])
        g.step(CATCH)
        inventory = g.inventory_items()
        tuning = deepcopy(self.tuning)
        tuning["menu"] = {"lau_ca_linh_dien_dien": tuning["menu"]["lau_ca_linh_dien_dien"]}
        tuning["quan"]["first_customer_tick"] = 1
        q = InteractiveQuan(tuning, {}, Streams(1), IdAllocator(), inventory=inventory)
        self.assertEqual(q.inventory_items(), inventory)
        q.step(NEUTRAL)
        q.pos = q.stoves[0]["pos"][:]
        rows = q.step(INTERACT)
        consumed = next(d["items"] for n, d in rows if n == "cook_started")
        self.assertEqual(Counter(i["kind"] for i in consumed), {"ca_linh": 3, "bong_dien_dien": 1})
        self.assertEqual(q.inventory_items(), [])
        self.assertFalse(q.done)

    def test_recipe_using_two_linh_does_not_discard_third(self):
        q = self.quan(["ca_linh"] * 3 + ["ca_keo", "keo_neo", "bong_dien_dien"], menu=["lau_mam"])
        q.step(NEUTRAL)
        q.pos = q.stoves[0]["pos"][:]
        q.step(INTERACT)
        self.assertEqual([i["kind"] for i in q.inventory_items()], ["ca_linh"])

    def test_one_spoiled_individual_keeps_stack_but_cannot_satisfy_three_fish_recipe(self):
        g = self.gather(["bong_dien_dien"])
        g.step(CATCH)
        g.hold_items[1]["fresh"] = 30
        rows = g.step(NEUTRAL)
        self.assertIn("spoiled", [n for n, _ in rows])
        self.assertEqual(g.snapshot()["hold_slots"][-1]["quantity"], 3)
        inventory = g.inventory_items()
        tuning = {**self.tuning, "menu": {"lau_ca_linh_dien_dien": self.tuning["menu"]["lau_ca_linh_dien_dien"]}}
        q = InteractiveQuan(tuning, {}, Streams(1), IdAllocator(), inventory=inventory)
        self.assertEqual(len(q.inventory_items()), 4)
        self.assertEqual([n for n, _ in q.step(NEUTRAL)], ["quan_end"])
        self.assertEqual({i["id"] for i in q.inventory_items()}, {i["id"] for i in inventory})

    def test_auto_end_nonempty_unusable_recipe_once_without_erasing_stock(self):
        q = self.quan(["bong_sung"])
        rows = q.step(NEUTRAL)
        self.assertEqual(q.reason, "inventory_exhausted")
        self.assertEqual([i["kind"] for i in q.inventory_items()], ["bong_sung"])
        self.assertEqual([n for n, _ in rows], ["quan_end"])
        self.assertEqual(q.step(NEUTRAL), [])
        self.assertEqual((q.money, q.earned, q.reputation), (0, 0, 3))

    def test_can_cook_and_reserved_stock_prevent_close(self):
        q = self.quan(["ca_loc"])
        self.assertTrue(q._can_continue())
        rows = q.step(NEUTRAL)
        self.assertIn("customer_arrived", [n for n, _ in rows])
        self.assertFalse(q.done)
        self.assertEqual(q.item_stock.reserve({"ca_loc": 1}, q._claimed_items()), None)
        self.assertEqual(q.customers[0]["reserved"], ["I1"])
        for _ in range(60):
            q.step(NEUTRAL)
        self.assertFalse(q.done)

    def test_two_stoves_ready_and_hand_all_prevent_close(self):
        q = self.quan(["ca_loc"] * 2)
        for _ in range(302):
            q.step(NEUTRAL)
        self.assertEqual(len(q.customers), 2)
        for stove in q.stoves:
            q.pos = stove["pos"][:]
            q.step(INTERACT)
        self.assertTrue(all(s["state"] == "cooking" for s in q.stoves))
        self.assertEqual(q.inventory_items(), [])
        self.assertFalse(q.done)
        for _ in range(361):
            q.step(NEUTRAL)
        self.assertTrue(all(s["state"] == "ready" for s in q.stoves))
        self.assertFalse(q.done)
        q.pos = q.stoves[0]["pos"][:]
        q.step(INTERACT)
        self.assertIsNotNone(q.hand)
        self.assertFalse(q.done)

    def test_eating_waits_for_real_payment_then_closes(self):
        customer = {"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                    "state": "eating", "order_status": "served", "reserved": [],
                    "eat_ticks_left": 2, "base_price": 59, "tip": 11}
        q = self.quan(customers=[customer])
        self.assertNotIn("quan_end", [n for n, _ in q.step(NEUTRAL)])
        rows = q.step(NEUTRAL)
        self.assertEqual([n for n, _ in rows], ["paid", "quan_end"])
        self.assertEqual((q.money, q.earned, q.reputation), (70, 70, 3.2))
        self.assertEqual(q.step(NEUTRAL), [])

    def test_hand_alone_keeps_valid_order_alive_without_stock_or_stove(self):
        dish = {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 59}
        customer = {"id": "C1", "table_id": "T1", "dish_id": dish["dish_id"],
                    "state": "waiting", "order_status": "assigned", "reserved": [], "base_price": 59}
        q = self.quan(customers=[customer], hand=dish)
        q.step(NEUTRAL)
        self.assertFalse(q.done)
        self.assertTrue(all(s["state"] == "idle" for s in q.stoves))

    def test_spoiled_and_outside_menu_items_close_and_clean_impossible_order(self):
        customer = {"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                    "state": "waiting", "order_status": "unfulfillable", "reserved": []}
        for kinds, fresh in ((["ca_loc"], 29.9), (["ca_keo"] * 2, 100)):
            q = self.quan(kinds, fresh=fresh, customers=[customer])
            rows = q.step(NEUTRAL)
            self.assertEqual([n for n, _ in rows], ["customer_left", "quan_end"])
            self.assertEqual(q.customers, [])
            self.assertEqual(q.reputation, 3)
            self.assertEqual(len(q.inventory_items()), len(kinds))

    def test_spoiled_reserved_no_longer_blocks_close(self):
        customer = {"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "reserved": ["I1"]}
        q = self.quan(["ca_loc"], fresh=30, customers=[customer])
        self.assertEqual([n for n, _ in q.step(NEUTRAL)], ["spoiled", "customer_left", "quan_end"])

    def test_schedule_continues_without_overlapping_claims_or_tables(self):
        q = self.quan(["ca_loc"] * 8)
        arrived = []
        for _ in range(1200):
            arrived += [d for n, d in q.step(NEUTRAL) if n == "customer_arrived"]
        self.assertEqual(len(arrived), 4)
        self.assertEqual(len({c["table_id"] for c in q.customers}), 4)
        claims = [i for c in q.customers for i in c["reserved"]]
        self.assertEqual(len(set(claims)), len(claims))
        c = q.customers[0]
        q._leave(c, "patience", [])  # Free a table before the next configured arrival.
        for _ in range(2):
            arrived += [d for n, d in q.step(NEUTRAL) if n == "customer_arrived"]
        self.assertEqual(len(arrived), 5)
        self.assertFalse(q.done)

    def test_standard_mode_retains_capacity_schedule_and_no_early_close(self):
        session = Session("quan", self.tuning, {"stock": items(["bong_sung"])}, 1)
        rows = session.step(NEUTRAL)
        self.assertFalse(session.done)
        self.assertEqual(rows, [])
        self.assertEqual(session.sim.customer_interval_ticks, 900)
        self.assertNotIn("hold_slots", self.gather(standard=True).snapshot())

    def test_five_day_progression_capacity_recipe_and_deterministic_results(self):
        scenario = load_scenario(ROOT / "chonoi/web/day-plan.json", "day", self.tuning)
        plans = InteractiveSession(self.tuning, scenario, 1, 5, CONFIG).sim.plans
        for day, plan in plans.items():
            self.assertEqual(sum(plan["dishes"].values()), day + 1)
            required = Counter()
            for dish, count in plan["dishes"].items():
                required.update({k: v * count for k, v in self.tuning["menu"][dish]["recipe"].items()})
            self.assertEqual(required, plan["ingredients"])
            linh = required.get("ca_linh", 0)
            slots = sum(required.values()) - linh + (linh + 2) // 3
            self.assertLessEqual(slots, self.tuning["gather"]["hold_capacity"])
        traces = []
        for _ in range(2):
            scenario["gather"] = {"time_left_ticks": 1, "random_fish": False, "monsters": []}
            session = InteractiveSession(self.tuning, scenario, 1, 5, CONFIG)
            trace = []
            while not session.done:
                inp = InputState((0, 0), {}, {"shop_done"} if session.sim.phase == "shop" else set())
                trace.extend(session.step(inp))
                trace.append(session.snapshot())
            self.assertEqual(session.sim.days_completed, 5)
            self.assertEqual(len(session.sim.results), 5)
            self.assertEqual(session.sim.summary()["earned"], 0)
            traces.append(json.dumps(trace, sort_keys=True))
        self.assertEqual(*traces)

    def test_web_result_real_shop_purchase_pause_and_next_day(self):
        scenario = load_scenario(ROOT / "chonoi/web/day-plan.json", "day", self.tuning)
        scenario["day"].update(money=400, earned=400)
        scenario["gather"] = {"hold": items(["bong_sung"])}
        web = InteractiveDayWeb(5, False, tuning=self.tuning, scenario=scenario, config=CONFIG)
        web.action("start", {})
        web.action("continue", {})
        web._step(INTERACT)  # Dock; transfer one unusable flower.
        self.assertEqual(web.screen, "evening_intro")
        web.action("continue", {})
        web._step(NEUTRAL)
        self.assertEqual(web.screen, "day_result")
        result = deepcopy(web.snapshot()["result"])
        self.assertEqual(result["brought"], {"bong_sung": 1})
        self.assertEqual(result["remaining"], {"bong_sung": 1})
        self.assertEqual(result["reason"], "inventory_exhausted")
        self.assertEqual(web.snapshot()["result"], result)
        self.assertEqual(web.session.sim.days_completed, 0)
        web.action("continue", {})
        self.assertEqual(web.screen, "shop")
        web.action("buy", {"upgrade_id": "oxygen"})
        self.assertEqual(web.session.sim.money, 200)
        self.assertEqual(web.session.sim.upgrades["oxygen"], 1)
        web.action("pause", {})
        ticks = web.session.sim.shop_ticks
        web.snapshot()
        self.assertEqual(web.session.sim.shop_ticks, ticks)
        self.assertFalse(web.action("shop_done", {}))
        web.action("resume", {})
        web.action("shop_done", {})
        self.assertEqual((web.screen, web.session.sim.day), ("day_intro", 2))
        self.assertEqual(web.session.sim.stats["brought"], {})
        self.assertEqual(web.session.sim.current.oxygen_max, 2700)
        self.assertEqual(web.session.sim.current.inventory_items(), [])
