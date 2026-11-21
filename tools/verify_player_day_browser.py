"""Actual enhanced Day adapter, real inputs/polling, reduced-motion override."""
import json
from pathlib import Path
from runpy import run_path
import sys
from threading import Thread

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chonoi.interactive_web import InteractiveDayWeb
from verify_p3_05_browser import observe_motion


def main():
    scope = run_path(str(ROOT / "docs/proof/phase-2/day_fixture.py"))
    tuning = scope["TUNING"]
    config = json.loads((ROOT / "chonoi/web/gameplay.json").read_text(encoding="utf-8"))
    proof = ROOT / "docs/proof/player-animation"
    proof.mkdir(parents=True, exist_ok=True)
    checks, errors = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge")
        for mode in ("gather", "quan"):
            scenario = {"gather": {"player": {"pos": [20, 5] if mode == "gather" else tuning["gather"]["dock_pos"]},
                                   "hold": [{"id": f"I{i}", "kind": "ca_loc", "fresh": 100} for i in range(1, 9)],
                                   "monsters": []}}
            web = InteractiveDayWeb(5, False, tuning=tuning, scenario=scenario, config=config)
            server = scope["create_server"](web)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            context = browser.new_context(viewport={"width": 1280, "height": 720}, reduced_motion="reduce")
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            observe_motion(page, "ba-ut-di-bo.webp" if mode == "quan" else "ba-ut-nhip-boi.webp")
            try:
                page.goto(f"http://127.0.0.1:{server.server_port}/?motion=on")
                page.get_by_role("button", name="Chơi", exact=True).click()
                page.get_by_role("button", name="Ra bến", exact=True).click()
                page.wait_for_function("snap?.mode==='gather' && canPlay()")
                if mode == "quan":
                    page.keyboard.press("e")
                    page.wait_for_function("day?.screen==='evening_intro'")
                    page.locator('button[data-action="continue"]').click()
                    page.wait_for_function("snap?.mode==='quan' && canPlay()")
                page.wait_for_function("window.motionPose!==undefined")
                assert page.evaluate("reducedMotion.matches && playerMotionEnabled() && npcMotionEnabled()")
                page.locator("#playfield").focus()
                page.keyboard.down("d")
                page.wait_for_function("playerMotion.moving && window.motionFrames.size>=4", timeout=4000)
                observed = page.evaluate("({frames:[...window.motionFrames],phase:playerMotion.phase,tick:snap.tick,position:snap.player.pos,preference:localStorage.getItem('chonoi.playerMotion')})")
                assert observed["preference"] == "true", observed
                page.screenshot(path=str(proof / f"edge-day-{mode}-motion-on.png"), full_page=True)
                page.keyboard.up("d")
                page.wait_for_function("!playerMotion.moving")
                checks.append({"mode": mode, "result": "PASS", "observed": observed})
                page.locator("#player-motion").uncheck()
                page.locator("#playfield").focus()
                page.keyboard.down("a")
                page.wait_for_timeout(250)
                assert page.evaluate("!playerMotion.moving && motionFrame(snap.mode)===0")
                page.keyboard.up("a")
                checks.append({"mode": mode, "result": "PASS", "check": "explicit off keeps idle; NPC setting remains on"})
                assert page.evaluate("npcMotionEnabled()")
            finally:
                context.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
        browser.close()
    assert not errors, errors
    report = dict(status="PASS", checks=checks, browser_errors=errors,
                  scope="Real Microsoft Edge, enhanced Day adapter, real WASD/HTTP; system reduced motion emulated ON.")
    (proof / "edge-day-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
