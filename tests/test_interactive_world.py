"""Bản đồ Gather 200 m và cá lượn tự nhiên của bản web; headless chuẩn không đổi."""
from copy import deepcopy
import json
import math
from pathlib import Path
import unittest

from chonoi.contract import load_contract
from chonoi.errors import BadInput
from chonoi.ids import IdAllocator
from chonoi.inputs import InputState
from chonoi.interactive import InteractiveGather, InteractiveSession
from chonoi.interactive_world import world_tuning
from chonoi.rng import Streams
from chonoi.runner import Session
from chonoi.scenario import load_scenario

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "chonoi/web/gameplay.json").read_text(encoding="utf-8"))
NEUTRAL = InputState((0, 0), {}, set())
CATCH = InputState((0, 0), {}, {"catch"})


class InteractiveWorld(unittest.TestCase):
    def setUp(self):
        self.tuning = deepcopy(load_contract()["tuning"])
        self.scenario = load_scenario(ROOT / "chonoi/web/day-plan.json", "day", self.tuning)

    def gather_sim(self, seed=1):
        return InteractiveSession(self.tuning, deepcopy(self.scenario), seed, 5, CONFIG).sim

    def test_standard_contract_and_headless_keep_100m(self):
        self.assertEqual(load_contract()["tuning"]["gather"]["bounds"]["x"], [0, 100])
        sim = Session("gather", self.tuning, {}, 1).sim
        self.assertEqual(sim.t["bounds"]["x"], [0, 100])
        self.assertNotIn("view", sim.t)
        self.assertNotIn("natural_fish", sim.t)

    def test_world_is_200m_with_same_counts_dock_and_kinds(self):
        g = self.gather_sim().current
        base = self.tuning["gather"]
        self.assertEqual(g.t["bounds"]["x"], [0, 200])
        self.assertEqual(g.t["bounds"]["d"], base["bounds"]["d"])  # độ sâu và oxy giữ nguyên
        self.assertEqual(g.t["dock_pos"], base["dock_pos"])
        self.assertEqual((g.t["fish_initial"], g.t["fish_max"], g.t["fish_spawn_ticks"]),
                         (base["fish_initial"], base["fish_max"], base["fish_spawn_ticks"]))
        self.assertEqual(len(g.fish), base["fish_initial"])
        self.assertEqual(len(g.nodes), len(base["nodes"]))
        self.assertEqual(len(g.t["monsters"]["spawns"]), len(base["monsters"]["spawns"]))
        self.assertEqual(g.t["fish_yield"], base["fish_yield"])
        self.assertGreater(max(n["pos"][0] for n in g.nodes), 100)
        self.assertGreater(max(g.t["fish_spawn_x"]), 100)
        self.assertEqual(g.t["view"], {"art_span_m": 100})

    def test_fish_spread_past_old_edge_and_stay_inside_river(self):
        beyond = 0
        for seed in range(1, 11):
            g = self.gather_sim(seed).current
            beyond += sum(f["pos"][0] > 100 for f in g.fish)
            for _ in range(900):
                g.step(NEUTRAL)
                for f in g.fish:
                    self.assertTrue(g.t["fish_x"][0] <= f["pos"][0] <= g.t["fish_x"][1])
                    lo, hi = g.t["fish_depths"][f["kind"]]
                    self.assertTrue(lo <= f["pos"][1] <= hi)
        self.assertGreater(beyond, 0)

    def test_natural_fish_travel_turn_smoothly_and_are_deterministic(self):
        runs = []
        for _ in range(2):
            g = self.gather_sim(3).current
            start = {f["id"]: list(f["pos"]) for f in g.fish}
            heading = {f["id"]: f["heading_deg"] for f in g.fish}
            max_turn = 0.0
            for _ in range(600):
                g.step(NEUTRAL)
                for f in g.fish:
                    if f["id"] in heading:
                        diff = abs((f["heading_deg"] - heading[f["id"]] + 180) % 360 - 180)
                        # chỉ khi dội mép sông/độ sâu mới được đổi hướng gấp; còn lại quay tối đa 1,5°/tick
                        lo, hi = g.t["fish_depths"][f["kind"]]
                        edge = g.t["fish_speed"] / 60 + 1e-6
                        at_edge = (min(abs(f["pos"][1] - lo), abs(f["pos"][1] - hi)) <= edge or
                                   min(abs(f["pos"][0] - g.t["fish_x"][0]), abs(f["pos"][0] - g.t["fish_x"][1])) <= edge)
                        if not at_edge:
                            max_turn = max(max_turn, diff)
                    heading[f["id"]] = f["heading_deg"]
            moved = [math.dist(start[f["id"]], f["pos"]) for f in g.fish if f["id"] in start]
            # cá thật sự đi qua không gian (10 s ở 1,5 m/s; quay đầu làm vài con dịch ít hơn)
            self.assertGreater(sum(moved) / len(moved), 6, moved)
            self.assertTrue(all(d > 1 for d in moved), moved)
            self.assertLessEqual(max_turn, InteractiveGather.WANDER_TURN_DEG_PER_TICK + 1e-9)
            runs.append(json.dumps(g.snapshot()["fish"], sort_keys=True))
        self.assertEqual(*runs)

    def test_catch_beyond_old_edge_uses_simulation_position(self):
        tuning = world_tuning(self.tuning, CONFIG)
        scenario = {"random_fish": False, "player": {"pos": [170, 12]},
                    "fish": [{"id": "F1", "kind": "ca_loc", "pos": [171.5, 12]}]}
        g = InteractiveGather(tuning, scenario, Streams(1), IdAllocator())
        g.step(CATCH)
        self.assertEqual([i["kind"] for i in g.hold_items], ["ca_loc"])

    def test_sprint_moves_faster_only_while_held(self):
        multiplier = CONFIG["sprint_multiplier"]
        for screen, speed_key in (("gather", "swim_speed"), ("quan", "walk_speed")):
            distances = []
            for sprint in (False, True):
                sim = self.gather_sim()
                if screen == "quan":
                    sim._start_quan([])
                g = sim.current
                start = list(g.pos)
                held = {"sprint": True} if sprint else {}
                for _ in range(30):  # 0,5 s, quá ramp 6 tick
                    g.step(InputState((1, 0), held, set()))
                distances.append(g.pos[0] - start[0])
            normal, fast = distances
            expected = g.t[speed_key] * 30 / 60
            self.assertAlmostEqual(fast / normal, multiplier, delta=0.08)
            self.assertLess(normal, expected + 1e-6)
        # Headless chuẩn không biết nút sprint: GatherSim gốc bỏ qua.
        std = Session("gather", self.tuning, {}, 1).sim
        self.assertFalse(hasattr(std, "sprint_multiplier"))

    def test_web_accepts_sprint_key_and_bad_multiplier_rejected(self):
        from chonoi.interactive_web import InteractiveDayWeb
        web = InteractiveDayWeb(5, False, tuning=self.tuning, scenario=self.scenario, config=CONFIG)
        web.action("start", {})
        web.action("continue", {})
        self.assertTrue(web.snapshot()["sprint"])
        self.assertTrue(web.keys({"move": [1, 0], "sprint": True}))
        self.assertFalse(web.keys({"move": [1, 0], "sprint": "yes"}))
        for bad in (0.5, 5, True):
            with self.assertRaises(BadInput):
                InteractiveSession(self.tuning, deepcopy(self.scenario), 1, 5, {**CONFIG, "sprint_multiplier": bad})

    def test_web_speeds_swim_6_sprint_9_against_current_4_croc_7(self):
        g = self.gather_sim().current
        self.assertAlmostEqual(g.t["swim_speed"], 6)
        self.assertAlmostEqual(g.t["swim_speed"] * CONFIG["sprint_multiplier"], 9)
        self.assertAlmostEqual(g.t["swim_speed"] - g.t["current"]["speed"], 4)  # bơi ngược dòng lũ
        self.assertEqual({s["chase_speed"] for s in g.t["monsters"]["species"].values()}, {7})
        std = Session("gather", self.tuning, {}, 1).sim.t  # headless giữ nguyên số chuẩn
        self.assertEqual((std["swim_speed"], std["current"]["speed"]), (4.0, 1.5))
        self.assertEqual({s["chase_speed"] for s in std["monsters"]["species"].values()}, {3})

    def test_swimming_against_current_moves_4_mps(self):
        tuning = world_tuning(self.tuning, CONFIG)
        tuning = {**tuning, "extensions": ["current"]}
        scenario = {"random_fish": False, "player": {"pos": [100, 15]}, "monsters": [], "current_direction": 1}
        g = InteractiveGather(tuning, scenario, Streams(1), IdAllocator())
        g.current = {"direction": 1, "end_tick": 10 ** 6}  # đang có lũ chảy sang phải
        g.random_current = False
        for _ in range(10):  # quá ramp
            g.step(InputState((-1, 0), {}, set()))
        x0 = g.pos[0]
        for _ in range(60):
            g.step(InputState((-1, 0), {}, set()))
        self.assertAlmostEqual(x0 - g.pos[0], 4.0, places=6)

    def test_bad_world_config_is_rejected(self):
        for world in ({"length_m": 50}, {"length_m": 1000}, {"length_m": True}, {"width": 2},
                      {"swim_speed_multiplier": 0.5}, {"swim_speed_multiplier": 9},
                      {"current_speed": 0}, {"monster_chase_speed": -1}, {"monster_chase_speed": True}):
            with self.assertRaises(BadInput):
                world_tuning(self.tuning, {"gather_world": world})


if __name__ == "__main__":
    unittest.main()
