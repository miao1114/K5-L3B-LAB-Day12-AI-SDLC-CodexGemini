"""Real Chrome Canvas benchmark: python3 -m chonoi.bench --seed 42 --duration 30 --out bench.json."""
import argparse
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time

from .contract import load_contract
from .live import LiveGame, LiveServer


def metrics(times, measured_s, load_ms):
    if (not times or any(not math.isfinite(t) or t <= 0 for t in times)
            or not math.isfinite(measured_s) or measured_s <= 0
            or not math.isfinite(load_ms) or load_ms < 0):
        raise ValueError("benchmark không có frame/thời gian hợp lệ")
    count = len(times)
    slow = sorted(times, reverse=True)[:max(1, math.ceil(.01 * count))]
    return {"avg_fps": count / measured_s, "p1_low_fps": 1 / statistics.mean(slow),
            "frames": count, "measured_s": measured_s, "load_ms": load_ms}


def duration(value):
    try:
        result = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("duration phải là số dương hữu hạn")
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("duration phải là số dương hữu hạn")
    return result


def benchmark(seed, seconds, output):
    started = time.perf_counter()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Cần pip install playwright và Google Chrome (hoặc playwright install chromium)") from exc
    tuning = load_contract()["tuning"]
    game = LiveGame("gather", tuning, {}, seed)
    server = LiveServer(game, port=0)
    server.start()
    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(channel="chrome", headless=True)
            except Exception:
                browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.add_init_script("""(() => {
                    const seen=new Set(), original=CanvasRenderingContext2D.prototype.drawImage;
                    CanvasRenderingContext2D.prototype.drawImage=function(img,...args){
                        const result=original.call(this,img,...args);
                        if(this.canvas.id==='world' && img.src)seen.add(img.src.split('/').pop());
                        return result;
                    };
                    window.benchData={ready:null,start:null,end:null,times:[],seen:[]};
                    window.onBenchmarkFrame=now=>{
                        const b=window.benchData;
                        if(!seen.has('ca-sau.webp') || !seen.has('ba-ut.webp') ||
                            !(seen.has('ca-loc.webp') || seen.has('ca-linh.webp')))return;
                        b.seen=Array.from(seen);
                        if(b.ready===null)b.ready=now;
                        if(b.end!==null || now-b.ready<3000)return;
                        if(b.start===null){b.start=now;b.previous=now;return;}
                        b.times.push((now-b.previous)/1000);b.previous=now;
                        if(now-b.start>=window.benchDuration*1000)b.end=now;
                    };
                })();""")
                page.add_init_script(f"window.benchDuration={seconds!r}")
                page.goto(server.url + "?benchmark=render", wait_until="load")
                page.wait_for_function("window.benchData?.ready!==null", timeout=30000)
                load_ms = (time.perf_counter() - started) * 1000
                page.wait_for_function("window.benchData.start!==null", timeout=10000)
                output = Path(output)
                evidence = output.parent / (output.stem + "-evidence")
                evidence.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(evidence / "benchmark-scene.png"))
                page.wait_for_function("window.benchData.end!==null", timeout=max(30000, seconds * 1000 + 10000))
                data = page.evaluate("window.benchData")
                size = page.evaluate("""()=>({viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,
                    canvas:[document.getElementById('world').width,document.getElementById('world').height],
                    css:[document.getElementById('world').clientWidth,document.getElementById('world').clientHeight]})""")
                with game._lock:
                    snapshot = game.session.snapshot()
                if errors or size["viewport"] != [1280, 720] or snapshot["player"]["pos"] != tuning["gather"]["dock_pos"]:
                    raise RuntimeError(f"cảnh benchmark lỗi: {errors}, {size}")
                result = metrics(data["times"], (data["end"] - data["start"]) / 1000, load_ms)
                environment = {"browser": browser.version, "os": platform.platform(), "headless_browser": True,
                    "seed": seed, "warmup_s": (data["start"] - data["ready"]) / 1000, **size,
                    "scene": "core Gather, full simulation/animation; continuous draw only with benchmark query",
                    "snapshot": snapshot, "assets_drawn": data["seen"], "page_errors": errors}
                (evidence / "environment.json").write_text(json.dumps(environment, ensure_ascii=False, indent=2), encoding="utf-8")
                (evidence / "frame-times.json").write_text(json.dumps(data["times"]), encoding="utf-8")
                (evidence / "benchmark-environment.md").write_text(
                    f"# Benchmark environment\n\n{platform.platform()}\n\nChrome/Chromium {browser.version}, headless with real Canvas.\n"
                    f"Viewport 1280x720, DPR 1; CSS canvas {size['css']}, backing canvas {size['canvas']}.\n"
                    "Core Gather simulation; assets/player/fish/crocodile confirmed through actual drawImage calls.\n"
                    "load_ms: Python monotonic before startup until browser acknowledges first completed ready scene frame.\n"
                    "Includes readiness polling overhead; no clock-domain subtraction. Warm-up >=3 seconds.\n"
                    "Frame times: consecutive completed draw calls, anchor and all samples inside measurement.\n"
                    "One screenshot during measurement may introduce an honest outlier. No effects disabled.\n",
                    encoding="utf-8")
                output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
                return result
            finally:
                browser.close()
    finally:
        server.stop()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="chonoi.bench")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--duration", type=duration, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(benchmark(args.seed, args.duration, args.out)))
    except Exception as exc:
        print(f"benchmark thất bại: {exc}. Cần Playwright và browser cài sẵn.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
