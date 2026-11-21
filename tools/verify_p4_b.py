"""Two real v1.3 ten-day CLI runs without modifying the team's manifest."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "docs/proof/phase-4/p4-b"


def main():
    PROOF.mkdir(parents=True, exist_ok=True)
    contract = json.loads((ROOT / "game.contract.json").read_text(encoding="utf-8"))
    contract["contract_version"] = "1.3"
    manifest = PROOF / "contract-v1.3.json"
    manifest.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    runs = []
    for name in ("soak-a.json", "soak-b.json"):
        output = PROOF / name
        args = [sys.executable, "-m", "chonoi.soak", "--seed", "7", "--days", "10",
                "--out", str(output), "--contract", str(manifest)]
        result = subprocess.run(args, cwd=ROOT, capture_output=True, encoding="utf-8")
        (PROOF / (name + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
        assert result.returncode == 0, result.stderr
        report = json.loads(output.read_text(encoding="utf-8"))
        assert set(report) == {"days", "days_completed", "crashes", "results", "duration_s"}
        assert (report["days"], report["days_completed"], report["crashes"]) == (10, 10, 0)
        assert [row["day"] for row in report["results"]] == list(range(1, 11))
        runs.append(report)
        print(f"{name}: completed={report['days_completed']}, crashes={report['crashes']}, duration_s={report['duration_s']:.3f}", flush=True)
    gameplay = [{k: v for k, v in run.items() if k != "duration_s"} for run in runs]
    assert gameplay[0] == gameplay[1]
    # Publish the requested artifact once; never replace another member's proof.
    primary = PROOF.parent / "soak.json"
    if not primary.exists():
        with primary.open("x", encoding="utf-8") as stream:
            json.dump(runs[0], stream, ensure_ascii=False, indent=2)
    summary = {"seed": 7, "version": "1.3", "determinism": "PASS",
               "comparison": "all fields except duration_s", "duration_s": [r["duration_s"] for r in runs],
               "days_completed": [r["days_completed"] for r in runs], "crashes": [r["crashes"] for r in runs],
               "input_policy": "neutral inputs; actual Gather, Quan and Shop timers, no bot shortcuts"}
    (PROOF / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("PASS: two actual ten-day v1.3 soaks, deterministic gameplay", flush=True)


if __name__ == "__main__":
    main()
