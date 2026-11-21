"""Dòng lũ và khách đặt trước trong bản web 5 ngày (InteractiveDaySim/InteractiveDayWeb)."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from chonoi.contract import load_contract
from chonoi.errors import BadInput
from chonoi.inputs import InputState
from chonoi.interactive import InteractiveSession
from chonoi.interactive_menu import unlocked_menu
from chonoi.interactive_web import InteractiveDayWeb
from chonoi.scenario import load_scenario

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "chonoi/web/gameplay.json").read_text(encoding="utf-8"))
NEUTRAL = InputState((0, 0), {}, set())


def items(kinds):
    return [{"id": f"I{i + 1}", "kind": kind, "fresh": 100.0} for i, kind in enumerate(kinds)]


class InteractiveExtensions(unittest.TestCase):
    def setUp(self):
        self.tuning = deepcopy(load_contract()["tuning"])
        self.scenario = load_scenario(ROOT / "chonoi/web/day-plan.json", "day", self.tuning)

    def session(self, config=CONFIG, scenario=None, seed=1):
        return InteractiveSession(self.tuning, deepcopy(scenario or self.scenario), seed, 5, config)

    def test_web_config_enables_both_extensions_without_touching_preset(self):
        sim = self.session().sim
        self.assertEqual(sim.tuning["extensions"], ["current", "reservations"])
        self.assertEqual(load_contract()["extensions"], [])  # headless/manifest vẫn tắt
        self.assertEqual(self.tuning["extensions"], [])  # preset truyền vào không bị sửa

    def test_reservations_only_use_dishes_unlocked_for_that_day(self):
        for seed in range(1, 31):
            sim = self.session(seed=seed).sim
            for day in range(1, 6):
                sim.day = day
                sim._start_day()
                opened, _ = unlocked_menu(self.tuning, CONFIG, day)
                self.assertEqual(len(sim.reservations), self.tuning["reservations"]["count"])
                for r in sim.reservations:
                    self.assertIn(r["dish_id"], opened, f"seed {seed} ngày {day}")

    def test_explicit_reservation_for_locked_dish_is_rejected(self):
        scenario = deepcopy(self.scenario)
        scenario["quan"] = {"reservations": [
            {"id": "R1", "table_id": "T1", "dish_id": "lau_mam", "arrival_tick": 600}]}
        with self.assertRaises(BadInput):
            self.session(scenario=scenario)  # lau_mam mở ở Ngày 5, không được đặt ở Ngày 1

    def test_day_announces_and_quan_receives_same_reservations(self):
        session = self.session()
        events = [row["name"] for row in session.start_events()]
        self.assertEqual(events.count("reservation_announced"), 2)
        sim = session.sim
        announced = deepcopy(sim.reservations)
        sim._start_quan(items(["ca_loc", "bong_sung", "bong_sung", "ca_loc", "bong_sung", "bong_sung"]))
        snap = sim.current.snapshot()
        self.assertEqual([r["id"] for r in snap["reservations"]], [r["id"] for r in announced])
        self.assertEqual({r["dish_id"] for r in snap["reservations"]} - set(sim.unlocked_dishes), set())

    def test_early_close_fails_pending_reservations_once(self):
        sim = self.session().sim
        reputation = sim.reputation
        sim._start_quan([])  # kho rỗng: Quán đóng sớm ngay bước đầu
        events = sim.current.step(NEUTRAL)
        failed = [data for name, data in events if name == "reservation_failed"]
        self.assertEqual([d["reason"] for d in failed], ["closing", "closing"])
        self.assertEqual(sim.current.reason, "inventory_exhausted")
        delta = self.tuning["reservations"]["failed_reputation_delta"]
        self.assertEqual(sim.current.reputation, max(0, reputation + 2 * delta))

    def test_quan_stays_open_while_a_reservation_can_still_be_served(self):
        sim = self.session().sim
        recipe = self.tuning["menu"][sim.reservations[0]["dish_id"]]["recipe"]
        stock = items([kind for kind, n in sorted(recipe.items()) for _ in range(n)])
        sim._start_quan(stock)
        sim.current.step(NEUTRAL)
        self.assertFalse(sim.current.done)

    def test_web_snapshot_exposes_current_and_reservations(self):
        web = InteractiveDayWeb(5, False, tuning=self.tuning, scenario=self.scenario, config=CONFIG)
        web.action("start", {})
        self.assertEqual(len(web.snapshot()["reservations"]), 2)  # màn đầu ngày liệt kê khách đặt trước
        web.action("continue", {})
        snap = web.snapshot()["snapshot"]
        self.assertIn("current", snap)
        expected = {**self.tuning["gather"]["current"], "speed": CONFIG["gather_world"]["current_speed"]}
        self.assertEqual(snap["meta"]["current"], expected)  # bản web ghi đè tốc độ dòng lũ
        self.assertEqual(len(snap["reservations"]), 2)

    def test_config_without_extensions_keeps_previous_web_rules(self):
        config = {k: v for k, v in CONFIG.items() if k != "extensions"}
        sim = self.session(config=config).sim
        self.assertIsNone(sim.reservations)
        self.assertNotIn("current", sim.current.snapshot())


if __name__ == "__main__":
    unittest.main()
