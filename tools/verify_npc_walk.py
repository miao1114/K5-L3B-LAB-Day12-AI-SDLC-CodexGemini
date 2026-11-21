"""Focused controller + one Chrome session; fixtures never alter gameplay rules.

Run: .venv/Scripts/python.exe tools/verify_npc_walk.py
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chonoi.contract import load_contract
from chonoi.live import LiveGame, LiveServer

PROOF = ROOT / "docs/proof/npc-walk"


def main():
    PROOF.mkdir(parents=True, exist_ok=True)
    game = LiveGame("quan", load_contract()["tuning"], {"random_customers": False}, 1)
    base = json.loads(game.state_json())
    state = deepcopy(base)
    customers = [dict(id=f"C{i}", table_id=f"T{i}", state="waiting",
                      dish_id="ca_loc_nuong_trui", order_status="reserved", reserved=[],
                      patience_ticks_left=2400, eat_ticks_left=0) for i in range(1, 5)]
    errors, results = [], []
    server = LiveServer(game, port=0)
    server.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome")
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.add_init_script(r"""window.npcDraws=[];
                window.guestFallbacks=0;
                const original=CanvasRenderingContext2D.prototype.drawImage;
                CanvasRenderingContext2D.prototype.drawImage=function(image,...args){
                    if(/\/khach-(nam|nu)\.webp$/.test(image.src))window.guestFallbacks++;
                    if(image.src?.includes('/khach-') && args.length===8){
                        window.npcDraws.push({src:image.src.split('/').pop(),crop:args.slice(0,4),
                            facing:Math.sign(this.getTransform().a),time:performance.now()});
                        if(window.npcDraws.length>2000)window.npcDraws.splice(0,1000);
                    }
                    return original.call(this,image,...args);
                };""")
            page.route("**/state", lambda route: route.fulfill(json=state))
            page.goto(server.url)
            page.wait_for_function("typeof npcWalk !== 'undefined' && snap?.mode === 'quan'")
            page.wait_for_function("npcSheets.every(s => s.walk.naturalWidth && s.sit.naturalWidth)")
            page.evaluate("poll=()=>{}")
            page.wait_for_timeout(100)  # Drain the already scheduled poll, then drive snapshots explicitly.
            results += page.evaluate("""({base, customers}) => {
                const results=[], check=(ok,name)=>{if(!ok)throw Error(name);results.push(name);};
                const fixture=cs=>({...base,customers:structuredClone(cs)});
                const c=new NpcWalkController(), full=fixture(customers), original=JSON.stringify(full);
                c.sync(full,'day1');
                check([...c.actors.values()].every(a=>a.phase==='waiting'),'hydrate seated on refresh');
                const fresh=new NpcWalkController();
                fresh.sync({...full,tick:18000,phase_tick:125,customers:[{...customers[0],order_tick:120}]},'day');
                check(fresh.actors.get('C1').phase==='entering','first poll with recent arrival walks in using phase tick');
                const old=new NpcWalkController();
                old.sync({...full,phase_tick:500,customers:[{...customers[0],order_tick:120}]},'day');
                check(old.actors.get('C1').phase==='waiting','older orders on refresh remain seated');
                const n=new NpcWalkController(); n.sync(fixture([]),'day1');n.sync(full,'day1');
                check(n.actors.size===4 && [...n.actors.values()].every(a=>a.phase==='entering' &&
                    JSON.stringify(a.pos)===JSON.stringify(n.entry)),'all four start at doorway');
                check(new Set([...n.actors.values()].map(a=>a.gender)).size===2,'both genders');
                const a=n.actors.get('C1'); n.update(.2);const before=JSON.stringify(a.pos);
                n.sync(full,'day1');check(n.actors.get('C1')===a && JSON.stringify(a.pos)===before,'poll preserves identity/progress');
                const frozen=JSON.stringify(a.pos);n.update(0);
                check(JSON.stringify(a.pos)===frozen,'zero visual delta freezes movement');
                for(let i=0;i<60;i++)n.update(.05);
                check([...n.actors.values()].every(a=>a.phase==='waiting' &&
                    JSON.stringify(a.pos)===JSON.stringify(a.seat)),'all four arrive and sit');
                const eaten=structuredClone(full);eaten.customers[0].state='eating';n.sync(eaten,'day1');
                check(a.phase==='eating','waiting to eating');
                const paid=fixture(customers.slice(1));n.sync(paid,'day1');n.update(.3);
                const exitElapsed=a.elapsed;n.sync(paid,'day1');
                check(a.phase==='leaving' && a.elapsed===exitElapsed,'paid/disappearance exits only once');
                const reused=fixture([...customers.slice(1),{...customers[0],id:'C5'}]);n.sync(reused,'day1');
                check(n.actors.has('C1')&&n.actors.has('C5'),'table reuse keeps separate identities');
                for(let i=0;i<60;i++)n.update(.05);
                check(!n.actors.has('C1'),'exit deletes visual');
                const early=new NpcWalkController();early.sync(fixture([]),'d');early.sync(full,'d');early.update(.3);
                const pos=JSON.stringify(early.actors.get('C1').pos);early.sync(fixture([]),'d');
                check(JSON.stringify(early.actors.get('C1').pos)===pos,'patience exit from current position');
                early.sync(null,'shop');check(early.actors.size===0,'shop/result clears ghosts');
                n.sync(fixture([customers[0]]),'day2');
                check(n.actors.size===1&&n.actors.get('C1')!==a,'same ID new day has fresh identity');
                n.sync(full,'day2',true);check([...n.actors.values()].every(a=>a.phase==='waiting'),'reduced motion seats instantly');
                n.sync(fixture([]),'day2',true);check(n.actors.size===0,'reduced motion removes departures');
                early.sync(fixture([]),'new');early.sync(full,'new');early.sync(eaten,'new');
                check(early.actors.get('C1').phase==='eating','service while entering snaps safely');
                check(JSON.stringify(full)===original,'controller never mutates snapshot');
                return results;
            }""", {"base": base, "customers": customers})

            def publish(value):
                state.clear()
                state.update(deepcopy(value))
                page.evaluate("s=>acceptState(s)", state)

            filled = deepcopy(base)
            filled["customers"] = customers
            publish(filled)
            page.wait_for_timeout(350)
            x1 = page.evaluate("npcWalk.actors.get('C1').pos.slice()")
            # Identical tick/snapshot: RAF must advance without invalidations from polling.
            page.wait_for_timeout(150)
            x2 = page.evaluate("npcWalk.actors.get('C1').pos.slice()")
            assert x1 != x2, "RAF did not advance between snapshots"
            results.append("standalone quan RAF advances between snapshots")
            publish(filled)
            page.wait_for_timeout(2600)
            assert page.evaluate("[...npcWalk.actors.values()].every(a=>a.phase==='waiting')")
            page.screenshot(path=str(PROOF / "seated-four-tables.png"), full_page=True)
            results.append("real Canvas four seats + screenshot 1280x720")

            eaten = deepcopy(filled)
            eaten["customers"][0].update(state="eating", eat_ticks_left=300)
            eaten["customers"][1]["patience_ticks_left"] = 100
            publish(eaten)
            page.wait_for_timeout(2300)
            poses = page.evaluate("npcDraws.filter(d=>d.src.includes('ngoi')).map(d=>d.crop[0]/d.crop[2])")
            assert 2 in poses and 3 in poses
            page.screenshot(path=str(PROOF / "eating-and-status.png"), full_page=True)
            results.append("eating/drinking atlas frames + existing status bars")

            finished = deepcopy(base)
            finished["finished"] = True
            publish(finished)
            page.wait_for_timeout(2800)
            assert page.evaluate("npcWalk.actors.size===0")
            results.append("standalone finished shift still completes departures")
            publish(base)

            def day_state(snapshot, paused=False, day=1, screen="quan"):
                return dict(mode="day", screen=screen, day=day, days=5, paused=paused,
                            can_pause=True, live_scenes=True, snapshot=snapshot, events=[])

            publish(day_state(base))
            publish(day_state(filled))
            page.wait_for_timeout(250)
            page.evaluate("epoch++")  # Real pause actions also increment the request epoch.
            publish(day_state(filled, paused=True))
            frozen = page.evaluate("JSON.stringify([...npcWalk.actors.values()].map(a=>a.pos))")
            page.wait_for_timeout(350)
            assert page.evaluate("JSON.stringify([...npcWalk.actors.values()].map(a=>a.pos))") == frozen
            publish(day_state(filled))
            page.wait_for_timeout(250)
            assert page.evaluate("JSON.stringify([...npcWalk.actors.values()].map(a=>a.pos))") != frozen
            results.append("day mode pause freezes and resume continues without cache reset")
            publish(day_state(base))
            assert page.evaluate("[...npcWalk.actors.values()].every(a=>a.phase==='leaving')")
            page.screenshot(path=str(PROOF / "walking-out.png"), full_page=True)
            page.wait_for_timeout(2800)
            assert page.evaluate("npcWalk.actors.size===0")
            results.append("day walk-out completes after backend removes customers")
            publish(day_state(None, screen="shop"))
            assert page.evaluate("npcWalk.actors.size===0")
            page.emulate_media(reduced_motion="reduce")
            publish(day_state(filled, day=2))
            assert page.evaluate("[...npcWalk.actors.values()].every(a=>a.phase==='waiting')")
            results.append("Day Shop/new day + reduced-motion integration")
            page.locator("#npc-motion").check()
            with_new = deepcopy(filled)
            with_new["customers"].append({**customers[0], "id": "C9"})
            publish(day_state(with_new, day=2))
            motion_state = page.evaluate("({phase:npcWalk.actors.get('C9').phase,reduced:reducedMotion.matches,enabled:npcMotionEnabled(),preference:npcMotionPreference})")
            assert motion_state["phase"] == "entering" and motion_state["reduced"], motion_state
            previous = page.evaluate("npcWalk.actors.get('C9').pos.slice()")
            page.wait_for_timeout(200)
            assert previous != page.evaluate("npcWalk.actors.get('C9').pos.slice()")
            assert page.evaluate("localStorage.getItem('chonoi.npcMotion')==='true'")
            results.append("explicit walk checkbox overrides system reduced motion and saves preference")
            page.set_viewport_size({"width": 960, "height": 720})
            page.wait_for_timeout(100)
            assert page.evaluate("document.querySelector('#world').width>0")
            results.append("resize redraw")
            page.evaluate("npcSheets[0].sit.src='/art/no-npc.webp'")
            page.wait_for_timeout(150)
            page.evaluate("draw()")
            assert page.evaluate("guestFallbacks>0")
            results.append("missing sprite uses original guest fallback without crash")
            page.evaluate("async()=>{await restart();}")
            assert page.evaluate("npcWalk.actors.size===0")
            results.append("real restart endpoint clears visual cache")
            assert not errors, errors
            results.append("no browser JavaScript errors; four WebP sheets served successfully")
            context.close()

            # Real /state polling + real customer_arrived from the engine, without routing fixtures.
            live_game = LiveGame("quan", load_contract()["tuning"], {}, 1,
                                 inventory=[dict(id=f"I{i}", kind="ca_loc", fresh=100) for i in range(1, 9)])
            live_server = LiveServer(live_game, port=0)
            live_context = browser.new_context(viewport={"width": 1280, "height": 720}, reduced_motion="no-preference")
            live_page = live_context.new_page()
            live_page.on("pageerror", lambda e: errors.append(str(e)))
            live_server.start()
            try:
                live_page.goto(live_server.url)
                live_page.wait_for_function("npcWalk.actors.size>0 && [...npcWalk.actors.values()][0].phase==='entering'", timeout=10000)
                entry = live_page.evaluate("[...npcWalk.actors.values()][0].pos.slice()")
                live_page.screenshot(path=str(PROOF / "real-arrival-door.png"))
                live_page.wait_for_timeout(500)
                halfway = live_page.evaluate("[...npcWalk.actors.values()][0].pos.slice()")
                assert entry != halfway
                live_page.screenshot(path=str(PROOF / "real-arrival-walking.png"))
                live_page.wait_for_function("[...npcWalk.actors.values()][0].phase==='waiting'", timeout=4000)
                results.append("real simulation customer_arrived and continuous HTTP polling: doorway -> walking -> seated")
                assert not errors, errors
            finally:
                live_context.close()
                live_server.stop()
            browser.close()
    finally:
        server.stop()
    report = {"status": "PASS", "checks": len(results), "results": results, "browser_errors": errors,
              "scope": "Real Chrome/Canvas: controller fixtures plus actual simulation arrivals and HTTP polling; no benchmark/soak."}
    (PROOF / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
