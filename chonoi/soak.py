"""Standard simulation soak: python3 -m chonoi.soak --seed 7 --days 10 --out soak.json.

Neutral inputs intentionally exercise full phase timers, including empty-stock Quan.
No web extensions, bot shortcuts, subprocess games or per-day reconstruction.
"""
import argparse
import json
import math
import os
import sys
import tempfile
import time
import traceback

from .contract import DEFAULT_PATH, load_contract
from .errors import BadInput
from .inputs import InputState
from .runner import Session


class SoakSession(Session):
    def __init__(self, tuning, scenario, seed, days):
        if type(days) is not int or days <= 0:
            raise BadInput("--days phải là số nguyên dương")
        super().__init__("day", tuning, scenario, seed, days=days)
        # Day 1 is identical; enable cyclic lookup before advancing any gameplay.
        self.sim.repeat_plans = True


def run_soak(session, input_provider=None):
    """Return exact schema plus an exception for the CLI to report, if any.

    input_provider is a Python test hook, not a CLI option that shortens real runs.
    It receives the same live Session on every tick.
    """
    started = time.perf_counter()
    results, error = [], None
    sim = session.sim
    neutral = InputState((0, 0), {}, set())

    def record(day):
        results.append({"day": day, "earned": sim.earned, "reputation": sim.reputation,
                        "score": sim.earned + session.tuning["score"]["reputation_multiplier"]
                        * math.floor(sim.reputation)})

    day = sim.day
    try:
        while not session.done:
            day = sim.day
            session.step(input_provider(session) if input_provider else neutral)
            if sim.days_completed > len(results):
                record(day)
    except Exception as exc:
        error = exc
        # Shop may close successfully before construction of the next day fails.
        if sim.days_completed > len(results):
            record(day)
    report = {"days": sim.days, "days_completed": sim.days_completed,
              "crashes": int(error is not None), "results": results,
              "duration_s": time.perf_counter() - started}
    return report, error


def write_report(path, report):
    directory = os.path.dirname(os.path.abspath(path))
    fd, temporary = tempfile.mkstemp(prefix=".soak-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def positive_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("days phải là số nguyên dương")
    if number <= 0:
        raise argparse.ArgumentTypeError("days phải là số nguyên dương")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(prog="chonoi.soak")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--days", required=True, type=positive_int)
    parser.add_argument("--out", required=True)
    parser.add_argument("--contract", default=DEFAULT_PATH,
                        help="optional manifest path for isolated version-compatibility verification")
    args = parser.parse_args(argv)
    try:
        if os.path.normcase(os.path.abspath(args.out)) == os.path.normcase(os.path.abspath(args.contract)):
            raise BadInput("đường dẫn out phải khác contract")
        contract = load_contract(args.contract)
        if contract.get("contract_version") not in ("1.2", "1.3"):
            raise BadInput("soak yêu cầu contract v1.2 hoặc v1.3")
        session = SoakSession(contract["tuning"], {}, args.seed, args.days)
    except BadInput as exc:
        print(f"đầu vào sai: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"không khởi tạo được soak: {exc}", file=sys.stderr)
        return 1
    report, error = run_soak(session)
    try:
        write_report(args.out, report)
    except OSError as exc:
        print(f"lỗi ghi: {exc}", file=sys.stderr)
        return 1
    if error:
        traceback.print_exception(type(error), error, error.__traceback__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
