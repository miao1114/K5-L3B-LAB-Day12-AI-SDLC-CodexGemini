"""Exercise the Day web adapter with the real Phase 1 engines."""
from pathlib import Path
from runpy import run_path
from chonoi.sim.day import DaySim
from chonoi.contract import load_contract
from chonoi.scenario import load_scenario
import unittest

ROOT = Path(__file__).resolve().parents[1]
Preview = run_path(str(ROOT / "docs/proof/phase-2/day_fixture.py"))["LiveScenesPreview"]


class LiveDayPreviewTest(unittest.TestCase):
    def setUp(self):
        self.now = 0
        scope = Preview.tick.__globals__
        real_clock = scope["monotonic"]
        self.addCleanup(scope.__setitem__, "monotonic", real_clock)
        scope["monotonic"] = lambda: self.now

    def step(self, ticks=1):
        self.now += (ticks + 0.1) / 60
        return self.preview.snapshot()

    def press(self, key):
        self.assertTrue(self.preview.keys({key: True}))
        self.assertTrue(self.preview.keys({key: False}))
        return self.step()

    def start(self, faint=False):
        self.preview = Preview(1, faint)
        for action in ("start", "continue"):
            self.assertTrue(self.preview.action(action, {}))
        return self.preview

    def at(self, pos):
        self.preview.game.session.sim.pos = list(pos)

    def test_real_catch_transfers_stock_and_real_service_is_paid(self):
        preview = self.start()
        state = preview.snapshot()
        fish = next(f for f in state["snapshot"]["fish"] if f["kind"] == "ca_loc")
        self.at(fish["pos"])
        state = self.press("catch")
        self.assertEqual(state["snapshot"]["hold"], [{"id": "I1", "kind": "ca_loc", "fresh": 100}])
        self.assertIn("fish_caught", [event["name"] for event in state["events"]])
        self.assertTrue(preview.action("pause", {}))
        tick = preview.snapshot()["snapshot"]["tick"]
        self.assertEqual(self.step(120)["snapshot"]["tick"], tick)
        self.assertTrue(preview.action("resume", {}))

        self.at(state["snapshot"]["meta"]["dock_pos"])
        state = self.press("interact")
        self.assertEqual(state["screen"], "evening_intro")
        inventory = state["inventory"]
        self.assertEqual([(item["id"], item["kind"]) for item in inventory], [("I1", "ca_loc")])
        self.assertGreater(inventory[0]["fresh"], 30)
        self.assertLess(inventory[0]["fresh"], 100)
        self.assertEqual(state["cookable"], ["ca_loc_nuong_trui"])
        self.assertTrue(preview.action("continue", {}))
        self.assertEqual(preview.snapshot()["snapshot"]["stock"], inventory)
        state = self.step(preview.game.tuning["quan"]["first_customer_tick"] + 1)
        self.assertEqual([item["kind"] for item in state["snapshot"]["stock"]], ["ca_loc"])

        self.at(state["snapshot"]["stoves"][0]["pos"])
        state = self.press("interact")
        stove = state["snapshot"]["stoves"][0]
        self.assertEqual(stove["state"], "cooking")
        self.step(stove["cook_ticks_left"] + 1)
        self.assertEqual(self.press("interact")["snapshot"]["hand"]["dish_id"], "ca_loc_nuong_trui")
        self.at(state["snapshot"]["tables"][0]["pos"])
        state = self.press("interact")
        diner = state["snapshot"]["customers"][0]
        self.assertEqual(diner["state"], "eating")
        state = self.step(diner["eat_ticks_left"] + 1)
        self.assertIn("paid", [event["name"] for event in state["events"]])
        self.assertEqual(state["snapshot"]["money"], 70)

        state = self.step(state["snapshot"]["time_left_ticks"] + 1)
        self.assertEqual(state["screen"], "day_result")
        self.assertEqual((state["result"]["served"], state["result"]["tips"]), (1, 11))
        self.assertTrue(preview.action("continue", {}))
        self.assertTrue(preview.snapshot()["shop_unavailable"])
        self.assertFalse(preview.action("buy", {"upgrade_id": "oxygen_1"}))
        self.assertTrue(preview.action("shop_done", {}))
        self.assertEqual(preview.snapshot()["result"]["money"], 70)
        self.assertEqual(preview.snapshot()["screen"], "summary")

    def test_real_faint_does_not_create_sample_inventory(self):
        preview = self.start(faint=True)
        state = self.step(2)
        self.assertEqual((state["screen"], state["gather_reason"]), ("evening_intro", "fainted"))
        self.assertEqual(state["inventory"], [])
        self.assertTrue(preview.action("continue", {}))
        self.assertEqual(preview.snapshot()["snapshot"]["stock"], [])

    def test_evening_preview_excludes_spoiled_from_cookable_without_discarding_it(self):
        preview = self.start()
        preview.set_screen("evening_intro")
        inventory = [{"id": "I7", "kind": "ca_loc", "fresh": 29.99}]
        preview.inventory = inventory
        state = preview.snapshot()
        self.assertEqual(state["inventory"], inventory)
        self.assertEqual(state["cookable"], [])
        inventory[0]["fresh"] = 30
        self.assertEqual(preview.snapshot()["cookable"], ["ca_loc_nuong_trui"])

    def test_all_day_targets_match_real_day_sim_and_reset_basket(self):
        preview = Preview(5, False)
        tuning = load_contract()["tuning"]
        day_sim = DaySim(tuning, {}, 1, 5)
        for day in range(1, 6):
            with self.subTest(day=day):
                day_sim.day = day
                day_sim._start_day()
                preview.day = day
                preview.set_screen("day_intro")
                intro = preview.snapshot()
                self.assertEqual(intro["day_plan"], day_sim.snapshot()["day_plan"])
                self.assertEqual(intro["needed"], tuning["day_plan"][day - 1]["ingredients"])
                self.assertEqual({row["dish_id"]: row["servings"] for row in intro["menu"]},
                                 intro["day_plan"]["dishes"])
                preview.action("continue", {})
                gather = preview.snapshot()
                self.assertEqual(gather["day_plan"], intro["day_plan"])
                self.assertEqual(gather["snapshot"]["hold"], [])
                preview.inventory = [{"id": "I99", "kind": "ca_linh", "fresh": 90}]
                preview.set_screen("quan")
                self.assertEqual(set(preview.game.tuning["menu"]), set(intro["day_plan"]["dishes"]))

    def test_custom_plan_and_prefilled_items_survive_start_and_phase_change(self):
        items = [{"id": "I7", "kind": "ca_keo", "fresh": 30},
                 {"id": "I8", "kind": "ca_keo", "fresh": 29.99}]
        scenario = {"day": {"day_plan": [{"day": 1, "dishes": {"ca_keo_nuong": 1}}]},
                    "gather": {"hold": items}}
        preview = Preview(5, False, scenario)
        preview.action("start", {})
        self.assertEqual(preview.snapshot()["needed"], {"ca_keo": 2})
        preview.action("continue", {})
        self.assertEqual(preview.snapshot()["snapshot"]["hold"], items)
        self.assertEqual(preview.snapshot()["day_plan"]["ingredients"], {"ca_keo": 2})
        preview.day = 2
        preview.set_screen("gather")
        self.assertEqual(preview.snapshot()["snapshot"]["hold"], [])

    def test_web_progression_preserves_recipes_and_standard_contract(self):
        tuning = load_contract()["tuning"]
        scenario = load_scenario(ROOT / "chonoi/web/day-plan.json", "day", tuning)
        preview = Preview(5, False, scenario)
        preview.action("start", {})
        self.assertEqual(preview.snapshot()["needed"], {"ca_loc": 1, "bong_sung": 2})
        for day in range(1, 6):
            preview.day = day
            preview.set_screen("day_intro")
            state = preview.snapshot()
            self.assertEqual(sum(state["day_plan"]["dishes"].values()), day + 1)
            self.assertEqual(state["needed"]["bong_sung"], 2)
        self.assertEqual(tuning["day_plan"][0]["ingredients"], {"ca_loc": 3, "bong_sung": 6})
