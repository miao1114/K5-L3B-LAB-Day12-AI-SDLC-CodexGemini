"""P4-B: real short fixtures for state persistence and isolated v1.3 CLI checks."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from chonoi import headless, soak
from chonoi.contract import DEFAULT_PATH, load_contract
from chonoi.errors import BadInput
from chonoi.inputs import InputState
from chonoi.runner import Session

NEUTRAL = InputState((0, 0), {}, set())
ROOT = Path(__file__).resolve().parents[1]


class SoakTest(unittest.TestCase):
    def setUp(self):
        self.tuning = deepcopy(load_contract()["tuning"])
        self.tuning["shop"]["max_ticks"] = 2
        self.scenario = {"gather": {"time_left_ticks": 1, "random_fish": False, "monsters": []},
                         "quan": {"time_left_ticks": 1, "random_customers": False}}
        self.work = self.enterContext(tempfile.TemporaryDirectory())

    def test_ten_real_days_all_phases_cyclic_plan_and_shop_boundary(self):
        session = soak.SoakSession(self.tuning, self.scenario, 7, 10)
        sim, ids, streams = session.sim, session.sim.ids, session.sim.streams
        seen, plans, rows = set(), {}, []
        def observe(s):
            self.assertIs(s.sim, sim)
            self.assertIs(s.sim.ids, ids)
            self.assertIs(s.sim.streams, streams)
            seen.add((s.sim.day, s.sim.phase))
            plans[s.sim.day] = deepcopy(s.sim.plan)
            if s.sim.phase == "shop":
                self.assertEqual(s.sim.days_completed, s.sim.day - 1)
            return NEUTRAL
        report, error = soak.run_soak(session, observe)
        self.assertIsNone(error)
        self.assertEqual(report["days_completed"], 10)
        self.assertEqual(len(report["results"]), 10)
        self.assertEqual(session.tick, 40)
        self.assertEqual(len(seen), 30)
        self.assertEqual(plans[6]["dishes"], plans[1]["dishes"])
        self.assertEqual(plans[10]["ingredients"], plans[5]["ingredients"])
        self.assertEqual(plans[6]["day"], 6)
        self.assertEqual([r["day"] for r in report["results"]], list(range(1, 11)))
        self.assertEqual(set(report), {"days", "days_completed", "crashes", "results", "duration_s"})
        self.assertEqual(set(report["results"][0]), {"day", "earned", "reputation", "score"})
        self.assertGreaterEqual(report["duration_s"], 0)

    def test_economy_upgrades_and_item_ids_survive_day_six(self):
        t = deepcopy(self.tuning)
        scenario = {"day": {"money": 1000, "earned": 1000, "reputation": 3.4,
                     "day_plan": [{"day": d, "dishes": {"ca_loc_nuong_trui": 1}} for d in range(1, 6)]},
                    "gather": {"time_left_ticks": 2, "random_fish": False, "monsters": [],
                               "player": {"pos": [8, 0]},
                               "nodes": [{"id": "N1", "kind": "bong_sung", "pos": [8, 0]}]},
                    "quan": {"time_left_ticks": 2, "random_customers": False,
                             "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                               "state": "eating", "order_status": "served", "reserved": [],
                               "eat_ticks_left": 1, "base_price": 50, "tip": 10}]}}
        session = soak.SoakSession(t, scenario, 7, 10)
        item_ids, oxygen, starts = [], {}, {}
        def control(s):
            sim = s.sim
            if sim.phase == "gather":
                if s.phase_tick == 0:
                    starts[sim.day] = (sim.money, sim.earned, sim.reputation)
                    oxygen[sim.day] = sim.current.oxygen_max
                    return InputState((0, 0), {}, {"interact"})
                item_ids.extend(i["id"] for i in sim.current.hold_items)
            if sim.phase == "shop" and sim.day == 1 and not sim.upgrades:
                return InputState((0, 0), {}, set(), buy="oxygen")
            return NEUTRAL
        report, error = soak.run_soak(session, control)
        self.assertIsNone(error)
        self.assertEqual(item_ids, [f"I{i}" for i in range(1, 11)])
        self.assertEqual(starts[6][:2], (1100, 1300))
        self.assertGreater(starts[6][2], starts[1][2])
        self.assertEqual(oxygen[1], 1800)
        self.assertEqual(oxygen[2], 2700)
        self.assertEqual(oxygen[10], 2700)
        self.assertEqual(session.sim.upgrades, {"oxygen": 1})
        self.assertEqual((session.sim.money, session.sim.earned), (1400, 1600))
        self.assertEqual(report["results"][-1]["earned"], 1600)

    def test_empty_stock_timeout_and_insufficient_shop_money_are_not_crashes(self):
        session = soak.SoakSession(self.tuning, self.scenario, 7, 2)
        def control(s):
            return InputState((0, 0), {}, set(), buy="oxygen" if s.sim.phase == "shop" else None)
        report, error = soak.run_soak(session, control)
        self.assertIsNone(error)
        self.assertEqual(report["crashes"], 0)
        self.assertEqual(report["days_completed"], 2)
        self.assertEqual(session.sim.upgrades, {})

    def test_exception_returns_honest_partial_results_and_cli_failure(self):
        session = soak.SoakSession(self.tuning, self.scenario, 7, 10)
        def crash(s):
            if s.sim.day == 3:
                raise RuntimeError("injected crash")
            return NEUTRAL
        report, error = soak.run_soak(session, crash)
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual((report["days_completed"], report["crashes"], len(report["results"])), (2, 1, 2))
        target = Path(self.work) / "partial.json"
        with patch.object(soak, "run_soak", return_value=(report, error)), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(soak.main(["--seed", "7", "--days", "10", "--out", str(target)]), 1)
        self.assertEqual(json.loads(target.read_text())["crashes"], 1)

    def test_invalid_cli_values_and_write_failure(self):
        target = Path(self.work) / "out.json"
        for days in ("0", "-1", "x", "1.5"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                soak.main(["--seed", "7", "--days", days, "--out", str(target)])
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(target.exists())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(soak.main(["--seed", "7", "--days", "1", "--out", DEFAULT_PATH]), 2)
        report, _ = soak.run_soak(soak.SoakSession(self.tuning, self.scenario, 7, 1))
        with patch.object(soak, "run_soak", return_value=(report, None)), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(soak.main(["--seed", "7", "--days", "1", "--out", self.work]), 1)

    def test_v13_validates_freshness_and_cli_matches_v12_all_modes(self):
        contract = json.loads(Path(DEFAULT_PATH).read_text(encoding="utf-8"))
        version_file = Path(self.work) / "v13.json"
        contract["contract_version"] = "1.3"
        version_file.write_text(json.dumps(contract), encoding="utf-8")
        v13 = load_contract(version_file)
        self.assertEqual(v13["tuning"], load_contract()["tuning"])
        for mode in ("gather", "quan", "day"):
            outputs = []
            for version in ("1.2", "1.3"):
                contract["contract_version"] = version
                version_file.write_text(json.dumps(contract), encoding="utf-8")
                loaded = load_contract(version_file)
                out = Path(self.work) / f"{mode}-{version}.jsonl"
                args = ["--mode", mode, "--seed", "7", "--ticks", "2", "--out", str(out)]
                with patch.object(headless, "load_contract", return_value=loaded):
                    self.assertEqual(headless.main(args), 0)
                outputs.append(out.read_bytes())
            self.assertEqual(*outputs)
        contract["contract_version"] = "1.3"
        contract["tuning"].pop("inventory")
        version_file.write_text(json.dumps(contract), encoding="utf-8")
        with self.assertRaises(BadInput):
            load_contract(version_file)

    def test_standard_day_cli_still_rejects_six_days(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(headless.main(["--mode", "day", "--seed", "7", "--days", "6",
                "--ticks", "0", "--out", str(Path(self.work) / "invalid.jsonl")]), 2)

    def test_short_runs_are_deterministic_ignoring_wall_clock(self):
        reports = [soak.run_soak(soak.SoakSession(self.tuning, self.scenario, 7, 10))[0] for _ in range(2)]
        for report in reports:
            report.pop("duration_s")
        self.assertEqual(*reports)


if __name__ == "__main__":
    unittest.main()
