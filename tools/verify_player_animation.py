"""Real Chrome + live simulation: walk/swim cadence, idle, pause, stale snapshots.
Run: .venv/Scripts/python.exe tools/verify_player_animation.py
"""
import json
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chonoi.contract import load_contract
from chonoi.live import LiveGame, LiveServer


def main():
    results, errors = [], []
    proof = ROOT / "docs/proof/player-animation"
    proof.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        for mode, filename, count in (("quan", "ba-ut-di-bo.webp", 4), ("gather", "ba-ut-nhip-boi.webp", 5)):
            game = LiveGame(mode, load_contract()["tuning"],
                            {"player": {"pos": [6, 5]}, **({"monsters": []} if mode == "gather" else {})}, 1,
                            inventory=[dict(id=f"I{i}", kind="ca_loc", fresh=100) for i in range(1, 9)] if mode == "quan" else None)
            server = LiveServer(game, port=0)
            context = browser.new_context(viewport={"width": 1280, "height": 720}, reduced_motion="no-preference")
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.add_init_script("""(filename=>{
                window.poses=[]; const draw=CanvasRenderingContext2D.prototype.drawImage;
                CanvasRenderingContext2D.prototype.drawImage=function(image,...args){
                    if(image.src?.endsWith('/'+filename)&&args.length===8){
                        const [x,y,w,h]=args; const pose=[x/w,y/h,Math.sign(this.getTransform().a)];
                        const key=pose.join(':');
                        if(window.poses.at(-1)?.key!==key)window.poses.push({key,pose,time:performance.now()});
                    }
                    return draw.call(this,image,...args);
                };
            })(""" + json.dumps(filename) + ")")
            server.start()
            try:
                page.goto(server.url)
                page.wait_for_function("canPlay()")
                page.wait_for_function("window.poses.length>0")
                page.keyboard.down("d")
                page.wait_for_function("playerMotion.moving && playerMotion.speed>3")
                page.evaluate("window.poses=[]")
                page.wait_for_timeout(1050)
                poses = page.evaluate("window.poses")
                if mode == "quan":
                    distinct = {p["pose"][0] for p in poses}
                    assert all(p["pose"][1:] == [2, 1] for p in poses), poses
                else:
                    distinct = {p["pose"][1] * 3 + p["pose"][0] for p in poses}
                    assert all(p["pose"][2] == -1 for p in poses), poses
                assert len(distinct - {0}) == count and len(poses) >= 8, poses
                results.append(f"{mode}: all {count} moving poses, >=8 frame changes/second, correct facing")
                page.screenshot(path=str(proof / f"{mode}-moving.png"))
                page.keyboard.up("d")
                page.wait_for_function("!playerMotion.moving && motionFrame(snap.mode)===0")
                page.wait_for_timeout(100)
                phase = page.evaluate("playerMotion.phase")
                page.wait_for_timeout(150)
                assert page.evaluate("playerMotion.phase") == phase == 0
                results.append(f"{mode}: release returns to stable idle")
                page.keyboard.down("a")
                page.wait_for_function("playerMotion.moving")
                page.keyboard.up("a")
                page.wait_for_function("!playerMotion.moving")
                results.append(f"{mode}: direction reversal animates")
                if mode == "quan":
                    page.wait_for_function("[...npcWalk.actors.values()].some(a=>a.phase==='entering')", timeout=5000)
                    page.keyboard.down("d")
                    page.wait_for_function("playerMotion.moving")
                    before_both = page.evaluate("({phase:playerMotion.phase,pos:[...npcWalk.actors.values()][0].pos.slice()})")
                    page.wait_for_timeout(180)
                    after_both = page.evaluate("({phase:playerMotion.phase,pos:[...npcWalk.actors.values()][0].pos.slice()})")
                    assert before_both["phase"] != after_both["phase"] and before_both["pos"] != after_both["pos"]
                    page.keyboard.up("d")
                    page.wait_for_function("!playerMotion.moving")
                    results.append("quan: player walking and NPC entering animate simultaneously and independently")
                # Freeze polling, then inject known movement in the current real snapshot shape.
                page.evaluate("poll=()=>{}")
                page.wait_for_timeout(100)
                page.evaluate("""()=>{
                    const a=structuredClone(snap);a.tick+=2;a.player.pos[0]-=.13;acceptState(a);
                }""")
                page.wait_for_function("playerMotion.moving")
                before = page.evaluate("playerMotion.phase")
                page.wait_for_timeout(80)
                assert page.evaluate("playerMotion.phase") != before
                results.append(f"{mode}: RAF advances sprite phase between snapshots")
                page.wait_for_timeout(350)
                assert page.evaluate("!playerMotion.moving && motionFrame(snap.mode)===0")
                results.append(f"{mode}: stalled snapshots stop animation")
                page.evaluate("""()=>{
                    const a=structuredClone(snap);a.tick+=2;a.player.pos[0]-=.13;acceptState(a);
                    acceptState({mode:'day',screen:a.mode,day:1,days:5,paused:true,snapshot:a,events:[]});
                }""")
                page.wait_for_timeout(150)
                assert page.evaluate("!playerMotion.moving && playerMotion.phase===0")
                results.append(f"{mode}: day pause freezes animation")
                page.emulate_media(reduced_motion="reduce")
                page.evaluate("""()=>{
                    const a=structuredClone(snap);a.tick+=2;a.player.pos[0]-=.13;acceptState(a);
                }""")
                page.wait_for_timeout(100)
                assert page.evaluate("motionFrame(snap.mode)===0")
                results.append(f"{mode}: reduced motion retains static pose")
            finally:
                context.close()
                server.stop()
        browser.close()
    assert not errors, errors
    report = dict(status="PASS", checks=len(results), results=results, browser_errors=errors)
    (proof / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
