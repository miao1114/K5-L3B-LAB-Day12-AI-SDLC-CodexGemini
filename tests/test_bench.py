import contextlib
import io
import math
import unittest
from chonoi.bench import main, metrics


class BenchmarkMath(unittest.TestCase):
    def test_small_sample_uses_slowest_not_percentile(self):
        r = metrics([.01, .02, .1], .13, 200)
        self.assertEqual(r["p1_low_fps"], 10)
        self.assertAlmostEqual(r["avg_fps"], 3 / .13)
        self.assertEqual(set(r), {"avg_fps", "p1_low_fps", "frames", "measured_s", "load_ms"})

    def test_ceil_one_percent_and_irregular_frames(self):
        frames = [.01] * 99 + [.1, .2]
        r = metrics(frames, sum(frames), 0)
        self.assertAlmostEqual(r["p1_low_fps"], 1 / .15)
        self.assertEqual(r["frames"], 101)

    def test_one_frame(self):
        self.assertEqual(metrics([.05], .05, 0)["avg_fps"], 20)

    def test_reject_invalid_measurements(self):
        for frames, seconds, load in (([], 1, 0), ([0], 1, 0), ([math.nan], 1, 0),
                                       ([.1], 0, 0), ([.1], 1, -1), ([.1], 1, math.inf)):
            with self.assertRaises(ValueError):
                metrics(frames, seconds, load)

    def test_bad_cli(self):
        for value in ("0", "-1", "nan", "inf", "x"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as e:
                main(["--seed", "42", "--duration", value, "--out", "unused.json"])
            self.assertEqual(e.exception.code, 2)
