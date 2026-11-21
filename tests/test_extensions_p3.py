"""Extension Phase 3 (TICKET-03 mục 2): dòng nước lũ `current`, khách đặt trước `reservations`,
và vòng ngày thật trên web (`chonoi.live --mode day`).

Extension bật bằng `tuning["extensions"]` (load_contract chép từ manifest). Manifest mặc định để
`extensions: []`, nên các test lõi khác không bị ảnh hưởng; test "tắt" bên dưới kiểm điều đó.
"""

import json
import unittest
from copy import deepcopy

from chonoi.contract import load_contract
from chonoi.errors import BadInput
from chonoi.extensions import validate_extensions
from chonoi.inputs import InputState
from chonoi.live_day import LiveDayGame
from chonoi.runner import Session
from chonoi.scenario import _validate_block
from helpers import Workdir, events, read_jsonl, run_headless, write_json

IDLE = InputState((0.0, 0.0), {}, set())
PRESS = InputState((0.0, 0.0), {"interact": True}, {"interact"})


def tuning_with(*exts):
    t = deepcopy(load_contract()["tuning"])
    t["extensions"] = list(exts)
    return t


def names(rows):
    return [r["name"] for r in rows]


def run_until(session, tick, inp=IDLE):
    rows = []
    while session.tick < tick and not session.done:
        rows.extend(session.step(inp))
    return rows


def items(*kinds, fresh=100.0):
    return [{"id": f"I{i}", "kind": k, "fresh": fresh} for i, k in enumerate(kinds, 1)]


# --- Dòng nước lũ -------------------------------------------------------------------------------
CALM = {"random_fish": False, "monsters": [], "nodes": [{"id": "N1", "kind": "bong_sung", "pos": [90, 0]}]}


def gather_session(pos, **extra):
    scenario = {**CALM, "player": {"pos": pos}, **extra}
    return Session("gather", tuning_with("current"), scenario, 7)


class CurrentTest(unittest.TestCase):
    def setUp(self):
        self.cfg = load_contract()["tuning"]["gather"]["current"]

    def _deep_session(self, **extra):
        s = gather_session([50, 12], current_direction=1, **extra)
        s.sim.oxygen_max = s.sim.oxygen_ticks = 10 ** 6  # giữ ở dưới sâu mà không ngạt
        return s

    def test_schedule_warning_start_end_and_snapshot(self):
        s = self._deep_session()
        t0 = self.cfg["interval_ticks"]
        rows = run_until(s, t0 - self.cfg["warning_ticks"])
        self.assertEqual(rows[-1]["name"], "current_warning")
        self.assertEqual(rows[-1]["data"], {"starts_at_phase_tick": t0})
        self.assertIsNone(s.snapshot()["current"])
        x_before = s.sim.pos[0]
        rows = run_until(s, t0)
        self.assertEqual(rows[-1], {"type": "event", "tick": t0, "phase": "gather", "name": "current_start",
                                    "data": {"direction": 1, "duration_ticks": self.cfg["duration_ticks"]}})
        self.assertAlmostEqual(s.sim.pos[0] - x_before, self.cfg["speed"] / 60)
        self.assertEqual(s.snapshot()["current"], {"direction": 1, "ticks_left": self.cfg["duration_ticks"]})
        self.assertEqual(s.sim.vel, [0.0, 0.0])  # không tích lũy vào vel
        end = t0 + self.cfg["duration_ticks"]
        run_until(s, end - 1)
        self.assertEqual(s.snapshot()["current"]["ticks_left"], 1)
        x_last = s.sim.pos[0]
        rows = run_until(s, end)
        self.assertEqual(rows[0]["name"], "current_end")
        self.assertEqual(rows[0]["data"], {"direction": 1, "reason": "elapsed"})
        self.assertEqual(s.sim.pos[0], x_last)  # kết thúc trước di chuyển: tick này không bị cuốn
        self.assertIsNone(s.snapshot()["current"])

    def test_shallow_player_is_not_pushed_and_fish_ignore_current(self):
        s = gather_session([50, 5], current_direction=-1, random_fish=False,
                           fish=[{"id": "F1", "kind": "ca_loc", "pos": [30, 12]}])
        s.sim.oxygen_max = s.sim.oxygen_ticks = 10 ** 6
        run_until(s, self.cfg["interval_ticks"] + 10)
        self.assertEqual(s.sim.pos, [50.0, 5.0])
        self.assertEqual(s.sim.fish[0]["pos"], [30.0, 12.0])

    def test_clamped_at_bound(self):
        s = gather_session([100, 12], current_direction=1)
        s.sim.oxygen_max = s.sim.oxygen_ticks = 10 ** 6
        run_until(s, self.cfg["interval_ticks"] + 5)
        self.assertEqual(s.sim.pos[0], 100)

    def test_phase_end_mid_current_emits_end_before_gather_end(self):
        t0 = self.cfg["interval_ticks"]
        s = self._deep_session(time_left_ticks=t0 + 10)
        rows = run_until(s, t0 + 20)
        self.assertTrue(s.done)
        self.assertEqual(names(rows)[-2:], ["current_end", "gather_end"])
        self.assertEqual(rows[-2]["data"], {"direction": 1, "reason": "phase_end"})

    def test_start_on_last_tick_still_pushes(self):
        t0 = self.cfg["interval_ticks"]
        s = self._deep_session(time_left_ticks=t0)
        run_until(s, t0 - 1)
        x = s.sim.pos[0]
        rows = run_until(s, t0)
        self.assertEqual(names(rows)[-3:], ["current_start", "current_end", "gather_end"])
        self.assertAlmostEqual(s.sim.pos[0] - x, self.cfg["speed"] / 60)

    def test_random_current_false_disables_schedule(self):
        s = gather_session([50, 12], random_current=False)
        s.sim.oxygen_max = s.sim.oxygen_ticks = 10 ** 6
        rows = run_until(s, self.cfg["interval_ticks"] + 10)
        self.assertFalse([n for n in names(rows) if n.startswith("current")])
        self.assertIsNone(s.snapshot()["current"])

    def test_random_direction_is_deterministic_by_seed(self):
        dirs = []
        for _ in range(2):
            s = gather_session([50, 12])
            s.sim.oxygen_max = s.sim.oxygen_ticks = 10 ** 6
            rows = run_until(s, self.cfg["interval_ticks"] * 3)
            dirs.append([r["data"]["direction"] for r in rows if r["name"] == "current_start"])
        self.assertEqual(len(dirs[0]), 3)
        self.assertEqual(dirs[0], dirs[1])
        self.assertTrue(set(dirs[0]) <= {-1, 1})

    def test_disabled_keeps_core_snapshot_and_rejects_fields(self):
        t = tuning_with()
        s = Session("gather", t, {**CALM, "player": {"pos": [50, 12]}}, 7)
        self.assertNotIn("current", s.snapshot())
        with self.assertRaises(BadInput):
            _validate_block({"random_current": False}, "gather", t)
        with self.assertRaises(BadInput):
            _validate_block({"current_direction": 2}, "gather", tuning_with("current"))


# --- Khách đặt trước ------------------------------------------------------------------------------
STOVE_B1, TABLE = [2, 8], {"T1": [9, 2], "T2": [13, 2], "T3": [9, 6], "T4": [13, 6]}


def quan_session(reservations, stock=None, **extra):
    scenario = {"random_customers": False, "reservations": reservations, **extra}
    return Session("quan", tuning_with("reservations"), scenario, 5,
                   inventory=stock if stock is not None else items("ca_loc", "ca_loc", "bong_sung", "bong_sung"))


def interact_at(session, pos):
    session.sim.pos = list(pos)
    return session.step(PRESS)


class ReservationTest(unittest.TestCase):
    def test_announce_hold_arrive_price_and_served(self):
        s = quan_session([{"id": "R1", "table_id": "T2", "dish_id": "ca_loc_nuong_trui", "arrival_tick": 1900}])
        start = s.start_events()
        self.assertEqual([(r["name"], r["data"]) for r in start], [("reservation_announced", {
            "reservation_id": "R1", "table_id": "T2", "dish_id": "ca_loc_nuong_trui", "arrival_tick": 1900})])
        self.assertEqual(s.snapshot()["reservations"][0]["state"], "scheduled")
        run_until(s, 99)
        self.assertEqual(s.snapshot()["reservations"][0]["state"], "scheduled")
        run_until(s, 100)
        self.assertEqual(s.snapshot()["reservations"][0]["state"], "holding")  # giữ từ 1900 - 1800
        self.assertEqual({t["id"]: t["reservation_id"] for t in s.snapshot()["tables"]}["T2"], "R1")
        rows = run_until(s, 1900)
        self.assertEqual(names(rows)[-2:], ["reservation_arrived", "customer_arrived"])
        order_id = rows[-1]["data"]["order_id"]
        self.assertEqual(rows[-2]["data"], {"reservation_id": "R1", "order_id": order_id})
        customer = s.snapshot()["customers"][0]
        self.assertEqual(customer["reservation_id"], "R1")
        self.assertEqual(customer["reserved"], ["I1"])
        rows = interact_at(s, STOVE_B1)
        cook = next(r for r in rows if r["name"] == "cook_started")
        # tick 1901: cá lóc 100 hao 1901 × 0.25/60 -> fresh ~92.08; floor(60 × fresh/100)=55; × 1.5 -> 82
        self.assertEqual(cook["data"]["base_price"], 82)
        run_until(s, s.tick + 6 * 60)
        interact_at(s, STOVE_B1)  # lấy món
        rows = interact_at(s, TABLE["T2"])
        self.assertEqual(names(rows)[-2:], ["served", "reservation_served"])
        self.assertEqual(rows[-1]["data"], {"reservation_id": "R1", "order_id": order_id, "base_price": 82})
        self.assertEqual(rows[-2]["data"]["tip"], 16)  # boa tính trên giá đã nhân
        self.assertEqual(s.snapshot()["reservations"][0]["state"], "served")

    def test_held_table_is_skipped_by_regular_customers(self):
        s = quan_session([{"id": "R1", "table_id": "T1", "dish_id": "goi_bong_sung", "arrival_tick": 100}],
                         random_customers=True)
        self.assertEqual(s.snapshot()["reservations"][0]["state"], "holding")  # giữ từ tick 0
        rows = run_until(s, 120)
        regular = [r for r in rows if r["name"] == "customer_arrived" and r["tick"] == 120]
        self.assertEqual(regular[0]["data"]["table_id"], "T2")

    def test_fail_occupied_and_reputation_once(self):
        s = quan_session([{"id": "R1", "table_id": "T1", "dish_id": "goi_bong_sung", "arrival_tick": 50}],
                         customers=[{"id": "C9", "table_id": "T1", "dish_id": "ca_loc_nuong_trui"}])
        rows = run_until(s, 50)
        failed = [r for r in rows if r["name"] == "reservation_failed"]
        self.assertEqual(failed[0]["data"], {"reservation_id": "R1", "reason": "occupied", "reputation": 2.0})
        self.assertEqual(s.snapshot()["reservations"][0]["state"], "failed")
        rows = run_until(s, 10800)
        self.assertFalse([r for r in rows if r["name"] == "reservation_failed"])  # không fail lần hai

    def test_fail_stock(self):
        s = quan_session([{"id": "R1", "table_id": "T3", "dish_id": "lau_mam", "arrival_tick": 30}])
        rows = run_until(s, 30)
        self.assertEqual(rows[-1]["name"], "reservation_failed")
        self.assertEqual(rows[-1]["data"]["reason"], "stock")
        self.assertFalse(s.snapshot()["customers"])

    def test_fail_patience_replaces_customer_left(self):
        s = quan_session([{"id": "R1", "table_id": "T1", "dish_id": "goi_bong_sung", "arrival_tick": 10}])
        rows = run_until(s, 10 + 3600)
        self.assertNotIn("customer_left", names(rows))
        failed = [r for r in rows if r["name"] == "reservation_failed"]
        self.assertEqual(failed[0]["data"], {"reservation_id": "R1", "reason": "patience", "reputation": 2.0})
        self.assertEqual(s.snapshot()["customers"], [])
        self.assertEqual(s.sim.inventory_items()[2]["id"], "I3")  # phần giữ được nhả, không tiêu

    def test_closing_fails_pending_in_id_order(self):
        s = quan_session([{"id": "R2", "table_id": "T2", "dish_id": "goi_bong_sung", "arrival_tick": 10700},
                          {"id": "R1", "table_id": "T1", "dish_id": "goi_bong_sung", "arrival_tick": 10},
                          ], time_left_ticks=600)
        rows = run_until(s, 700)
        closing = [r["data"] for r in rows if r["name"] == "reservation_failed"]
        self.assertEqual([(d["reservation_id"], d["reason"]) for d in closing], [("R1", "closing"), ("R2", "closing")])
        self.assertEqual(closing[-1]["reputation"], 1.0)
        self.assertEqual(rows[-1]["name"], "quan_end")
        self.assertEqual(rows[-1]["data"]["reputation"], 1.0)

    def test_random_reservations_are_two_distinct_tables_in_window(self):
        tuning = tuning_with("reservations")
        s = Session("quan", tuning, {"random_customers": False}, 11, inventory=items("ca_loc"))
        res = s.snapshot()["reservations"]
        self.assertEqual([r["id"] for r in res], ["R1", "R2"])
        self.assertEqual(len({r["table_id"] for r in res}), 2)
        self.assertTrue(all(1800 <= r["arrival_tick"] <= 10799 for r in res))
        again = Session("quan", tuning, {"random_customers": False}, 11, inventory=items("ca_loc"))
        self.assertEqual(again.snapshot()["reservations"], res)
        off = Session("quan", tuning, {"random_reservations": False}, 11, inventory=items("ca_loc"))
        self.assertEqual(off.snapshot()["reservations"], [])

    def test_scenario_validation(self):
        t = tuning_with("reservations")
        bad = [
            [{"id": "R1", "table_id": "T1", "dish_id": "goi_bong_sung", "arrival_tick": 0}],
            [{"id": "R1", "table_id": "T9", "dish_id": "goi_bong_sung", "arrival_tick": 5}],
            [{"id": "R1", "table_id": "T1", "dish_id": "goi_bong_sung", "arrival_tick": 5},
             {"id": "R2", "table_id": "T1", "dish_id": "goi_bong_sung", "arrival_tick": 6}],
            [{"id": f"R{i}", "table_id": f"T{i}", "dish_id": "goi_bong_sung", "arrival_tick": 5} for i in (1, 2, 3)],
            [{"id": "R1", "table_id": "T1", "dish_id": "pho", "arrival_tick": 5}],
        ]
        for arr in bad:
            with self.subTest(arr=arr), self.assertRaises(BadInput):
                _validate_block({"reservations": arr}, "quan", t)
        with self.assertRaises(BadInput):  # extension tắt: trường lạ
            _validate_block({"reservations": []}, "quan", tuning_with())

    def test_disabled_quan_snapshot_unchanged(self):
        s = Session("quan", tuning_with(), {}, 5, inventory=items("ca_loc"))
        snap = s.snapshot()
        self.assertNotIn("reservations", snap)
        self.assertNotIn("reservation_id", snap["tables"][0])
        self.assertEqual(s.start_events(), [])

    def test_day_announces_after_phase_start_and_shows_in_gather(self):
        s = Session("day", tuning_with("reservations"), {}, 3, days=1)
        start = s.start_events()
        self.assertEqual(names(start), ["day_start", "day_plan", "phase_start",
                                        "reservation_announced", "reservation_announced"])
        plan = s.sim.plan["dishes"]
        self.assertTrue(all(r["data"]["dish_id"] in plan for r in start[3:]))
        self.assertEqual(len(s.snapshot()["reservations"]), 2)


class ManifestTest(unittest.TestCase):
    def test_manifest_extensions_validated(self):
        contract = {"extensions": ["weapon"], "tuning": deepcopy(load_contract()["tuning"])}
        with self.assertRaises(BadInput):
            validate_extensions(contract)
        contract["extensions"] = ["current", "reservations"]
        validate_extensions(contract)
        self.assertEqual(contract["tuning"]["extensions"], ["current", "reservations"])

    def test_headless_with_manifest_defaults_has_no_extension_events(self):
        with Workdir() as w:
            out = w.path("q.jsonl")
            code, err = run_headless("--mode", "quan", "--seed", "3", "--ticks", "200", "--out", out)
            self.assertEqual(code, 0, err)
            self.assertFalse([e for e in events(read_jsonl(out)) if e["name"].startswith(("reservation", "current"))])
            scen = write_json(w.path("s.json"), {"gather": {"random_current": False}})
            code, _ = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5", "--out", out, "--scenario", scen)
            self.assertEqual(code, 2)


# --- Vòng ngày trên web ---------------------------------------------------------------------------
class LiveDayTest(unittest.TestCase):
    def test_full_day_flow_with_real_shop(self):
        g = LiveDayGame(tuning_with("current", "reservations"), {}, 1, 2)
        self.assertEqual(g._state()["screen"], "menu")
        self.assertFalse(g.action({"action": "continue"}))
        self.assertTrue(g.action({"action": "start"}))
        st = g._state()
        self.assertEqual((st["screen"], st["day"]), ("day_intro", 1))
        self.assertEqual(len(st["reservations"]), 2)
        g._tick_once()
        self.assertEqual(g.session.tick, 0)  # màn giới thiệu không bước tick
        g.action({"action": "continue"})
        g.set_input({"move": [0, 0], "interact": False})
        st = g._state()
        self.assertEqual(st["snapshot"]["mode"], "day")
        self.assertIn("current", st["snapshot"])
        while g.screen == "gather":
            g._tick_once()
        st = g._state()
        self.assertEqual((st["screen"], st["gather_reason"]), ("evening_intro", "time"))
        g.action({"action": "continue"})
        while g.screen == "quan":
            g._tick_once()
        st = g._state()
        self.assertEqual(st["screen"], "day_result")
        self.assertEqual(set(st["result"]), {"served", "left", "tips", "earned", "money", "reputation"})
        g.action({"action": "continue"})
        g.session.sim.money = 200  # đủ tiền cho bình oxy cấp 1
        self.assertTrue(g.action({"action": "buy", "upgrade_id": "oxygen"}))
        g._tick_once()
        shop = g._state()["shop"]
        self.assertEqual(shop["upgrades"]["oxygen"], 1)
        self.assertEqual(shop["money"], 0)
        self.assertIn("bình oxy".lower(), shop["message"].lower())
        g.action({"action": "pause"})
        g._tick_once()
        self.assertEqual(g._state()["shop"]["time_left_ticks"], shop["time_left_ticks"])
        g.action({"action": "resume"})
        g.action({"action": "shop_done"})
        g._tick_once()
        st = g._state()
        self.assertEqual((st["screen"], st["day"]), ("day_intro", 2))
        json.dumps(st)

    def test_shop_timeout_after_last_day_goes_to_summary(self):
        g = LiveDayGame(tuning_with(), {}, 1, 1)
        g.action({"action": "start"})
        for _ in range(3):
            g.action({"action": "continue"})
            while g.screen in ("gather", "quan"):
                g._tick_once()
        self.assertEqual(g.screen, "shop")
        while g.screen == "shop":
            g._tick_once()
        st = g._state()
        self.assertEqual(st["screen"], "summary")
        self.assertIn("earned", st["result"])


if __name__ == "__main__":
    unittest.main()
