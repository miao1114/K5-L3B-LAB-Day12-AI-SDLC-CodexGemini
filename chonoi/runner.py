"""Vòng tick (Contract B, mô hình tick). KHUNG — thường không cần sửa.

Thứ tự ghi: snapshot tick 0 -> với mỗi bước: sự kiện (theo thứ tự xử lý) rồi snapshot (nếu tới lượt
hoặc buổi kết thúc) -> dòng 'end'. Mỗi tick tối đa một snapshot.

`Session` là API bước tick gọn dùng chung cho headless (`run`) và cửa sổ chơi trực tiếp (`chonoi.live`):
cả hai chạy CÙNG một lớp sim, không nhân đôi logic.
"""

import math
import os
import tempfile
from pathlib import Path

from .ids import IdAllocator
from .inputs import BUTTONS_V11, InputPlayer
from .inventory import write_inventory
from .jsonl import JsonlWriter
from .rng import Streams
from .sim.day import DaySim
from .sim.gather import GatherSim
from .sim.quan import QuanSim


def build_sim(mode, tuning, scenario, seed, inventory, days=1):
    if mode == "day":
        return DaySim(tuning, scenario, seed, days)
    streams, ids = Streams(seed), IdAllocator()
    if mode == "gather":
        return GatherSim(tuning, scenario, streams, ids)
    return QuanSim(tuning, scenario, streams, ids, inventory=inventory)


def _common(sim, tick, sim_tick, phase_tick, tuning, state):
    mult = tuning["score"]["reputation_multiplier"]
    return {
        "type": "snapshot", "tick": tick, "sim_tick": sim_tick, "mode": sim.mode, "phase": sim.phase,
        "phase_tick": phase_tick, "state": state, "time_left_ticks": sim.time_left_ticks,
        "money": sim.money, "earned": sim.earned, "reputation": sim.reputation,
        "score": sim.earned + mult * math.floor(sim.reputation),
    }


class Session:
    """Một lượt chơi: dựng sim, bước từng tick, lấy snapshot / dòng end."""

    def __init__(self, mode, tuning, scenario, seed, inventory=None, days=1):
        self.mode = mode
        self.tuning = tuning
        self.sim = build_sim(mode, tuning, scenario, seed, inventory, days)
        self.tick = 0
        self.sim_tick = 0
        self.phase_tick = 0
        self.paused = False
        self.phase_changed = False

    @property
    def done(self) -> bool:
        return self.sim.done

    def snapshot(self) -> dict:
        state = "finished" if self.done else "paused" if self.paused else "playing"
        s = _common(self.sim, self.tick, self.sim_tick, self.phase_tick, self.tuning, state)
        s.update(self.sim.snapshot())
        return s

    def _event_rows(self, events):
        rows = [{"type": "event", "tick": self.tick, "phase": self.sim.phase, "name": name, "data": data}
                for name, data in events]
        if self.mode == "day":
            for row in rows:
                row["day"] = self.sim.day
        return rows

    def start_events(self):
        # day: day_start/day_plan/phase_start; quan có extension đặt trước: reservation_announced
        starter = getattr(self.sim, "start_events", None)
        return self._event_rows(starter()) if starter else []

    def step(self, inp) -> list:
        """Read pause before gameplay and stamp events before each phase change."""
        if self.done:
            return []
        self.tick += 1
        self.phase_changed = False
        rows = []
        if inp.pressed("pause"):
            self.paused = not self.paused
            rows = self._event_rows([("paused" if self.paused else "resumed", {})])
        if self.paused:
            return rows
        self.sim_tick += 1
        self.phase_tick += 1
        events = self.sim.step(inp)
        rows.extend(self._event_rows(events))
        if self.mode == "day":
            next_events = self.sim.advance_phase(events)
            if next_events:
                self.phase_tick = 0
                self.phase_changed = True
                rows.extend(self._event_rows(next_events))
        return rows

    def end_row(self) -> dict:
        sim = self.sim
        score = _common(sim, self.tick, self.sim_tick, self.phase_tick, self.tuning, "")["score"]
        row = {"type": "end", "ticks": self.tick, "sim_tick": self.sim_tick, "mode": sim.mode,
                "state": "finished" if sim.done else "playing",
                "reason": sim.reason if sim.done else "tick_limit",
                "money": sim.money, "earned": sim.earned, "reputation": sim.reputation, "score": score}
        if self.mode == "day":
            row["days_completed"] = sim.days_completed
        return row

    def write_inventory_if_done(self, inventory_out):
        """File kho: ghi MỘT lần khi có gather_end; chưa kết thúc thì giữ nguyên file đích."""
        if self.mode == "gather" and self.sim.done and inventory_out:
            write_inventory(inventory_out, self.sim.inventory_items())


def run(mode, tuning, scenario, seed, frames, ticks, out_path, snapshot_every, inventory=None, inventory_out=None,
        days=1):
    sess = Session(mode, tuning, scenario, seed, inventory, days)
    target = Path(out_path)
    temp_path = None
    if mode == "day":
        # Fixture conflicts for Quan can only be discovered after Gather hands over its real stock.
        fd, name = tempfile.mkstemp(prefix=".day-", suffix=".tmp", dir=target.absolute().parent)
        os.close(fd)
        temp_path = Path(name)
    try:
        _write_run(sess, frames, ticks, temp_path or target, snapshot_every)
        if temp_path is not None:
            temp_path.replace(target)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    sess.write_inventory_if_done(inventory_out)
    return sess.sim


def _write_run(sess, frames, ticks, path, snapshot_every):
    player = InputPlayer(frames, BUTTONS_V11)
    w = JsonlWriter(path)
    try:
        for row in sess.start_events():
            w.write(row)
        w.write(sess.snapshot())  # tick 0: sau sự kiện khởi tạo, trước mọi input
        last_snapped = 0
        while sess.tick < ticks and not sess.done:
            inp = player.advance(sess.tick)  # bước k đọc input có tick == k
            for row in sess.step(inp):
                w.write(row)
            if sess.tick % snapshot_every == 0 or sess.phase_changed or sess.done:
                w.write(sess.snapshot())
                last_snapped = sess.tick
        if last_snapped != sess.tick:
            w.write(sess.snapshot())
        w.write(sess.end_row())
    finally:
        w.close()
