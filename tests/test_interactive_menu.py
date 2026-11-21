"""Focused unlock/spawn tests; the standard runner must retain its own presets."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from chonoi.contract import load_contract
from chonoi.errors import BadInput
from chonoi.inputs import InputState
from chonoi.interactive import InteractiveSession
from chonoi.interactive_menu import target_slots, unlocked_menu
from chonoi.interactive_web import InteractiveDayWeb
from chonoi.runner import Session
from chonoi.scenario import load_scenario

ROOT = Path(__file__).resolve().parents[1]
NEUTRAL = InputState((0, 0), {}, set())
EXPECTED = [
    {"ca_loc", "bong_sung"},
    {"ca_loc", "bong_sung", "ca_keo"},
    {"ca_loc", "bong_sung", "ca_keo", "bong_dien_dien"},
    {"ca_loc", "bong_sung", "ca_keo", "bong_dien_dien", "ca_linh"},
    {"ca_loc", "bong_sung", "ca_keo", "bong_dien_dien", "ca_linh", "keo_neo"},
]


class MenuUnlockTest(unittest.TestCase):
    def setUp(self):
        self.tuning = load_contract()["tuning"]
        self.config = json.loads((ROOT / "chonoi/web/gameplay.json").read_text())
        self.scenario = load_scenario(ROOT / "chonoi/web/day-plan.json", "day", self.tuning)

    def session(self):
        return InteractiveSession(self.tuning, self.scenario, 1, 5, self.config)

    def test_cumulative_unlock_order_and_all_recipe_pools(self):
        previous = set()
        expected_new = [None, "ca_keo_nuong", "canh_chua_ca_loc", "lau_ca_linh_dien_dien", "lau_mam"]
        for day in range(1, 6):
            opened, new = unlocked_menu(self.tuning, self.config, day)
            self.assertEqual(len(opened), day + 1)
            self.assertLessEqual(previous, set(opened))
            if day > 1:
                self.assertEqual(new, (expected_new[day - 1],))
            self.assertEqual({k for d in opened for k in self.tuning["menu"][d]["recipe"]}, EXPECTED[day - 1])
            previous = set(opened)

    def test_each_day_keeps_initial_count_nodes_positions_timers_and_monsters(self):
        sim = self.session().sim
        original = deepcopy(self.tuning)
        for day in range(1, 6):
            with self.subTest(day=day):
                sim.day = day
                sim._start_day()
                g = sim.current
                standard = Session("day", self.tuning, {}, 1, days=5).sim
                standard.day = day
                standard._start_day()
                self.assertEqual(len(g.fish), self.tuning["gather"]["fish_initial"])
                self.assertEqual(len({tuple(f["pos"]) for f in g.fish}), len(g.fish))
                self.assertEqual(len(g.nodes), len(self.tuning["gather"]["nodes"]))
                self.assertEqual([n["pos"] for n in g.nodes], [n["pos"] for n in self.tuning["gather"]["nodes"]])
                self.assertEqual({f["kind"] for f in g.fish} | {n["kind"] for n in g.nodes}, EXPECTED[day - 1])
                self.assertEqual(g.snapshot()["monsters"], standard.current.snapshot()["monsters"])
                for key in ("fish_initial", "fish_max", "fish_spawn_ticks", "regrow_s", "fish_yield", "fish_spawn_clearance"):
                    self.assertEqual(g.t[key], self.tuning["gather"][key])
                for fish in g.fish:
                    self.assertIn(fish["pos"][0], g.t["fish_spawn_x"])
                    self.assertIn(fish["pos"][1], g.t["fish_spawn_depths"][fish["kind"]])
        self.assertEqual(self.tuning, original)

    def test_spawn_at_360_not_before_and_cap_12_without_locked_species(self):
        for day in range(1, 6):
            sim = self.session().sim
            sim.day = day
            sim._start_day()
            g = sim.current
            spawned = []
            for tick in range(1, g.t["fish_spawn_ticks"] * 5 + 1):
                rows = g.step(NEUTRAL)
                spawned += [(tick, d) for n, d in rows if n == "fish_spawned"]
                self.assertLessEqual(len(g.fish), g.t["fish_max"])
                self.assertTrue(all(f["kind"] in EXPECTED[day - 1] for f in g.fish))
                if tick < g.t["fish_spawn_ticks"]:
                    self.assertEqual(len(g.fish), 8)
            self.assertEqual([tick for tick, _ in spawned], [360, 720, 1080, 1440])
            self.assertEqual(len(g.fish), 12)

    def test_plant_harvest_regrows_at_original_tick(self):
        g = self.session().sim.current
        node = g.nodes[0]
        g.pos = node["pos"][:]
        self.assertEqual(node["kind"], "bong_sung")
        rows = g.step(InputState((0, 0), {}, {"interact"}))
        self.assertIn("gather", [n for n, _ in rows])
        cooldown = round(g.t["regrow_s"] * self.tuning["tick_hz"])
        self.assertEqual(node["regrow_ticks"], cooldown)
        for _ in range(cooldown - 1):
            self.assertNotIn("node_regrown", [n for n, _ in g.step(NEUTRAL)])
        self.assertIn("node_regrown", [n for n, _ in g.step(NEUTRAL)])
        self.assertEqual(len(g.nodes), 6)

    def test_plan_targets_capacity_and_restaurant_use_same_unlocks(self):
        sim = self.session().sim
        for day in range(1, 6):
            sim.day = day
            sim._start_day()
            self.assertEqual(sum(sim.plan["dishes"].values()), day + 1)
            self.assertLessEqual(set(sim.plan["dishes"]), set(sim.unlocked_dishes))
            self.assertLessEqual(set(sim.plan["ingredients"]), sim.allowed_ingredients)
            self.assertLessEqual(target_slots(self.tuning, sim.plan["ingredients"]), 12)
            pool = set(sim.allowed_ingredients)
            inventory = [{"id": f"I{i+1}", "kind": k, "fresh": 100}
                         for i, k in enumerate(k for k in sorted(pool) for _ in range(6))]
            sim._start_quan(inventory)
            self.assertEqual(set(sim.current.menu), set(sim.unlocked_dishes))
            self.assertEqual(sim.current.menu, {d: self.tuning["menu"][d] for d in sim.unlocked_dishes})
            for _ in range(1100):
                sim.current.step(NEUTRAL)
            self.assertTrue(sim.current.customers)
            self.assertTrue(all(c["dish_id"] in sim.unlocked_dishes for c in sim.current.customers))

    def test_unplanned_but_unlocked_dish_still_cookable_and_keeps_quan_open(self):
        sim = self.session().sim
        sim.day = 5
        sim._start_day()
        self.assertNotIn("ca_keo_nuong", sim.plan["dishes"])
        sim._start_quan([{"id": f"I{i+1}", "kind": "ca_keo", "fresh": 100} for i in range(2)])
        q = sim.current
        rows = []
        for _ in range(q.t["first_customer_tick"]):
            rows.extend(q.step(NEUTRAL))
        self.assertFalse(q.done)
        self.assertEqual(q.customers[0]["dish_id"], "ca_keo_nuong")
        self.assertEqual([n for n, _ in rows], ["customer_arrived"])

    def test_locked_plan_or_explicit_spawn_rejected_without_touching_standard_scenarios(self):
        bad = deepcopy(self.scenario)
        bad["day"]["day_plan"][0] = {"day": 1, "dishes": {"lau_mam": 1}}
        with self.assertRaises(BadInput):
            InteractiveSession(self.tuning, bad, 1, 5, self.config)
        bad = deepcopy(self.scenario)
        bad["gather"] = {"random_fish": False, "fish": [{"id": "F1", "kind": "ca_linh", "pos": [20, 10]}]}
        with self.assertRaises(BadInput):
            InteractiveSession(self.tuning, bad, 1, 5, self.config)
        # The official scenario still works unchanged in the standard runner.
        standard = Session("day", self.tuning, bad, 1, days=5)
        self.assertEqual(standard.sim.current.fish[0]["kind"], "ca_linh")

    def test_web_state_publishes_one_shared_unlock_list(self):
        web = InteractiveDayWeb(5, False, tuning=self.tuning, scenario=self.scenario, config=self.config)
        web.action("start", {})
        self.assertEqual(len(web.snapshot()["unlocked_menu"]), 2)
        web.session.sim.day = 2
        web.session.sim._start_day()
        state = web.snapshot()
        self.assertEqual(len(state["unlocked_menu"]), 3)
        self.assertEqual(state["newly_unlocked"], ["ca_keo_nuong"])

    def test_partial_scenario_inherits_other_web_days_without_changing_input(self):
        scenario = {"day": {"day_plan": [{"day": 1, "dishes": {"goi_bong_sung": 1}}]},
                    "gather": {"hold": [{"id": "I7", "kind": "bong_sung", "fresh": 70}]}}
        before = deepcopy(scenario)
        sim = InteractiveSession(self.tuning, scenario, 1, 5, self.config).sim
        self.assertEqual(sim.plan["ingredients"], {"bong_sung": 2})
        self.assertIn("ca_keo_nuong", sim.plans[2]["dishes"])
        self.assertEqual(sim.current.inventory_items(), scenario["gather"]["hold"])
        self.assertEqual(scenario, before)

    def test_standard_preset_spawn_and_rng_unchanged(self):
        first = Session("day", self.tuning, {}, 1, days=5)
        second = Session("day", self.tuning, {}, 1, days=5)
        self.assertEqual(first.snapshot(), second.snapshot())
        self.assertEqual({n["kind"] for n in first.sim.current.nodes}, {"bong_sung", "bong_dien_dien", "keo_neo"})
        self.assertEqual(first.sim.plan["ingredients"], {"ca_loc": 3, "bong_sung": 6})
        self.assertNotIn("unlocked_menu", first.snapshot())


if __name__ == "__main__":
    unittest.main()
